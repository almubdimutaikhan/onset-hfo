"""Around one event: its neighbours, the seconds either side, its two contacts. Qt-free.

Review mode shows one event on one channel, half a second either side. That is
enough to tell an island from a column, and not enough for what a reader asks
when unsure:

* **Is it on one channel or many?** An HFO is usually focal: one contact pair
  or two neighbouring ones. Muscle, movement and electrode artefacts reach many
  channels at once. :func:`context` draws the event's electrode a few contacts
  either side, and counts the other channels with a detection at the same
  moment.
* **What happens around it?** A second or more either side shows whether it
  rides a discharge, sits in an artefact burst or repeats.
* **The view a reader was trained on.** Visual HFO marking sets the signal
  beside the same signal high-passed at the band's lower edge, several
  channels at once. :func:`context` returns both.
* **Bipolar against the two contacts it is made from.** :func:`contacts` reads
  the two single contacts of a bipolar channel from the fetched slice, so a
  reader can see whether the oscillation is in one contact or is shared by
  both (a reference artefact cancels in the difference only partly).

Everything here is computed from the session in memory -- the prepared signal
the detectors saw, and the slice it was prepared from -- and nothing is fetched.
`onset_review.reviewmode` only draws it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from onset_hfo.modality import trace_scale

__all__ = ["Context", "neighbours", "context", "contacts", "elsewhere"]

#: One contact's name: the electrode's letters, then the contact number.
#: An apostrophe marks the left hemisphere in some centres' naming ("A'3").
_CONTACT = re.compile(r"^(?P<lead>[A-Za-z]+'?)(?P<number>\d+)$")

#: Two events "at the same moment" when they overlap after widening each by
#: this much: the 20 ms the benchmark matches detections with, halved.
SAME_MOMENT_S = 0.010


@dataclass
class Context:
    """Several channels around one event, as drawn.

    `times` are seconds from the event's start; `wideband` and `highpassed`
    hold one row per name in `channels`, in the window's unit. `boxes` are the
    detections on those channels inside the window, with times relative to the
    event's start too.
    """

    channels: list[str]
    times: np.ndarray
    wideband: np.ndarray
    highpassed: np.ndarray
    highpass_hz: float
    event_channel: str
    event_span: tuple[float, float]
    boxes: list[dict] = field(default_factory=list)
    elsewhere: list[str] = field(default_factory=list)
    unit: str = "µV"
    title: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return bool(self.channels) and self.times.size > 0


def _lead_number(channel: str) -> tuple[str, int] | None:
    """The electrode and contact number of a channel's first contact."""
    first = str(channel).split("-")[0].strip()
    match = _CONTACT.match(first)
    if not match:
        return None
    return match.group("lead"), int(match.group("number"))


def neighbours(names: list[str], channel: str, n: int = 2) -> list[str]:
    """`channel` and up to `n` channels either side on the same electrode,
    in contact order. A channel whose name gives no electrode stands alone."""
    own = _lead_number(channel)
    if own is None or channel not in names:
        return [channel] if channel in names else []
    lead = own[0]
    same = sorted((number, name) for name in names
                   if (parsed := _lead_number(name)) is not None and parsed[0] == lead
                   for number in (parsed[1],))
    order = [name for _, name in same]
    at = order.index(channel)
    return order[max(0, at - n): at + n + 1]


def _highpass(data: np.ndarray, sfreq: float, low: float) -> np.ndarray:
    """Zero-phase high-pass at `low` Hz, row by row."""
    from scipy.signal import butter, sosfiltfilt

    if not (0 < low < 0.45 * sfreq) or data.shape[-1] < 30:
        return np.zeros_like(data)
    sos = butter(4, low, btype="highpass", fs=sfreq, output="sos")
    return sosfiltfilt(sos, data, axis=-1)


def _notch(data: np.ndarray, sfreq: float, line_freq: float, width: float = 2.0) -> np.ndarray:
    """Notch the mains and its harmonics, as the analysis does (2 Hz wide).

    IIR notches with zero phase rather than the analysis's FIR ones: a FIR
    notch two hertz wide needs seconds of filter, longer than a snippet.
    """
    from scipy.signal import filtfilt, iirnotch

    if not line_freq or line_freq <= 0:
        return data
    out = data
    for f in np.arange(line_freq, 0.45 * sfreq, line_freq):
        b, a = iirnotch(f, f / width, fs=sfreq)
        if out.shape[-1] > 3 * max(len(a), len(b)):
            out = filtfilt(b, a, out, axis=-1)
    return out


def _span(raw, offset: float, start: float, stop: float) -> tuple[int, int, list[str]]:
    """Samples [first, last) of the loaded window for file seconds
    [start, stop), clipped to it, and a note when the clip bites."""
    sfreq = float(raw.info["sfreq"])
    first = int(round((start - offset) * sfreq))
    last = int(round((stop - offset) * sfreq))
    notes = []
    if first < 0 or last > int(raw.n_times):
        notes.append("Near the edge of the loaded window: there is less signal on "
                     "one side of the event than the other.")
    return max(0, first), min(int(raw.n_times), last), notes


def elsewhere(session, event, exclude: list[str] | tuple = ()) -> list[str]:
    """The other channels with an accepted detection at the same moment as
    `event`, any detector, in channel order. The more there are, the more
    likely the event is an artefact that reached many contacts at once."""
    start = float(event.start) - SAME_MOMENT_S
    stop = float(event.stop) + SAME_MOMENT_S
    skip = set(exclude) | {event.channel}
    found = {e.channel for e in session.events
             if getattr(e, "accepted", True) and e.channel not in skip
             and float(e.start) < stop and float(e.stop) > start}
    names = list(getattr(session.raw, "ch_names", []))
    return sorted(found, key=lambda c: names.index(c) if c in names else len(names))


def _boxes(session, channels: list[str], event, start: float, stop: float) -> list[dict]:
    out = []
    for other in session.events:
        if other.channel not in channels:
            continue
        if float(other.stop) <= start or float(other.start) >= stop:
            continue
        out.append({"channel": other.channel, "detector": other.detector,
                    "start": float(other.start) - float(event.start),
                    "stop": float(other.stop) - float(event.start),
                    "accepted": bool(getattr(other, "accepted", True)),
                    "this": other is event})
    return out


def context(session, event, half_s: float = 1.0, n: int = 2) -> Context:
    """The event's electrode, `n` channels either side, `half_s` seconds
    either side of the event, as the detectors saw it and high-passed at the
    band's lower edge."""
    raw = session.raw
    unit = getattr(session, "unit", "µV")
    names = list(getattr(raw, "ch_names", []))
    channels = neighbours(names, event.channel, n)
    band = tuple(float(v) for v in (event.band or (0.0, 0.0)))
    if not channels:
        return Context([], np.empty(0), np.empty((0, 0)), np.empty((0, 0)), band[0],
                       event.channel, (0.0, 0.0), unit=unit,
                       notes=["This channel is not in the loaded window."])
    offset = float(getattr(session, "t_offset", 0.0))
    start, stop = float(event.start) - half_s, float(event.stop) + half_s
    first, last, notes = _span(raw, offset, start, stop)
    sfreq = float(raw.info["sfreq"])
    picks = [names.index(c) for c in channels]
    data = np.asarray(raw.get_data(picks=picks, start=first, stop=last),
                      dtype=float) * trace_scale(raw)
    times = np.arange(data.shape[1]) / sfreq + (first / sfreq + offset) - float(event.start)
    low = band[0] if band[0] > 0 else 80.0
    found = elsewhere(session, event, exclude=channels)
    title = (f"{event.channel} and its neighbours on the same electrode, "
             f"{half_s:g} s either side")
    return Context(
        channels=channels, times=times, wideband=data,
        highpassed=_highpass(data, sfreq, low), highpass_hz=low,
        event_channel=event.channel,
        event_span=(0.0, float(event.stop) - float(event.start)),
        boxes=_boxes(session, channels, event, start, stop),
        elsewhere=found, unit=unit, title=title, notes=notes)


def contacts(session, event, half_s: float = 1.0) -> Context | None:
    """The two single contacts a bipolar channel is made from, and their
    difference, from the fetched slice before re-referencing.

    None when the channel is not a bipolar pair, or when the slice is not in
    memory or lacks either contact. The contacts are high-passed at 1 Hz and
    notched at the mains and its harmonics, close to what the analysis did
    before it re-referenced; the difference row is computed from them.
    """
    parts = str(event.channel).split("-")
    recording = getattr(session, "recording", None)
    source = getattr(recording, "raw", None)
    if len(parts) != 2 or source is None:
        return None
    names = list(getattr(source, "ch_names", []))
    a, b = (p.strip() for p in parts)
    if a not in names or b not in names:
        return None
    offset = float(getattr(recording, "t_offset", getattr(session, "t_offset", 0.0)))
    start, stop = float(event.start) - half_s, float(event.stop) + half_s
    first, last, notes = _span(source, offset, start, stop)
    sfreq = float(source.info["sfreq"])
    data = np.asarray(source.get_data(picks=[names.index(a), names.index(b)],
                                      start=first, stop=last),
                      dtype=float) * trace_scale(source)
    line = float(getattr(recording, "line_freq", 0.0)
                 or getattr(getattr(session, "request", None), "line_freq", 0.0) or 0.0)
    data = _notch(_highpass(data, sfreq, 1.0), sfreq, line)
    rows = np.vstack([data, data[0] - data[1]])
    times = np.arange(rows.shape[1]) / sfreq + (first / sfreq + offset) - float(event.start)
    band = tuple(float(v) for v in (event.band or (0.0, 0.0)))
    low = band[0] if band[0] > 0 else 80.0
    labels = [a, b, f"{a} − {b}"]
    notes.append(f"The single contacts are high-passed at 1 Hz and notched at "
                 f"{line:g} Hz and its harmonics, as the analysis was; a signal "
                 f"in both contacts alike is cancelled in their difference."
                 if line else "The single contacts are high-passed at 1 Hz; the "
                 "mains frequency is unknown, so they are not notched.")
    return Context(
        channels=labels, times=times, wideband=rows,
        highpassed=_highpass(rows, sfreq, low), highpass_hz=low,
        event_channel=labels[2],
        event_span=(0.0, float(event.stop) - float(event.start)),
        boxes=[], elsewhere=elsewhere(session, event),
        unit=getattr(session, "unit", "µV"),
        title=f"{event.channel}: its two contacts and their difference, "
              f"{half_s:g} s either side",
        notes=notes)
