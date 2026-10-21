"""A map of any stretch of the window: band power, line length, energy ratio. Qt-free.

The Map page colours each contact by what the detectors found over the whole
analysed window. This module adds measures taken straight from the signal
over a stretch the reader chooses -- the trace on screen, or a window stepped
along the recording -- so a map can answer "where is the delta now?" or "where
does the fast activity build?" in a second or two:

* **band power**, in dB, in the classic bands and the ripple bands (a band is
  offered only when it fits below the window's Nyquist frequency);
* **line length** per second, the summed absolute sample-to-sample change, a
  measure of how busy the signal is;
* **the fast/slow energy ratio** the Epileptogenicity Index is built from
  (12.4-97 Hz over 3.5-12.4 Hz), as log10;
* **the HFO rate in the stretch**, from the ranking detector's accepted events.

Values are computed from the signal the detectors saw (`session.raw`:
filtered and re-referenced), so a map and the trace above it agree. They are
measurements of this stretch and nothing else; none is a finding by itself.

For scalp EEG, :func:`scalp_info` places the electrodes by their 10-05 names
(MNE's standard layout), so the page can draw a head topomap instead of a
diagram of channel names. Files that carry positions are not needed for this,
and names it cannot place are left out of the topomap and listed.
"""

from __future__ import annotations

import numpy as np

from onset_hfo.modality import trace_scale

__all__ = ["SIGNAL_MEASURES", "is_signal_measure", "available", "stretch_values",
           "scalp_info", "measure_unit"]

#: (key, label, colour-bar label, band in Hz or None).
SIGNAL_MEASURES = (
    ("power_delta", "Power, delta (1–4 Hz)", "dB re 1 µV²", (1.0, 4.0)),
    ("power_theta", "Power, theta (4–8 Hz)", "dB re 1 µV²", (4.0, 8.0)),
    ("power_alpha", "Power, alpha (8–13 Hz)", "dB re 1 µV²", (8.0, 13.0)),
    ("power_beta", "Power, beta (13–30 Hz)", "dB re 1 µV²", (13.0, 30.0)),
    ("power_gamma", "Power, gamma (30–80 Hz)", "dB re 1 µV²", (30.0, 80.0)),
    ("power_ripple", "Power, ripple (80–250 Hz)", "dB re 1 µV²", (80.0, 250.0)),
    ("power_fast_ripple", "Power, fast ripple (250–500 Hz)", "dB re 1 µV²", (250.0, 500.0)),
    ("signal_line_length", "Line length", "µV per second", None),
    ("energy_ratio", "Fast/slow energy (12.4–97 over 3.5–12.4 Hz)", "log10 ratio", None),
    ("rate_in_stretch", "HFO rate in the stretch", "events / min", None),
)

#: The Epileptogenicity Index's bands (`onset_hfo.ictal.IctalSettings`).
SLOW_BAND = (3.5, 12.4)
FAST_BAND = (12.4, 97.0)


def is_signal_measure(key: str) -> bool:
    return any(key == k for k, *_ in SIGNAL_MEASURES)


def measure_unit(key: str, unit: str = "µV") -> str:
    for k, _label, bar, _band in SIGNAL_MEASURES:
        if k == key:
            return bar.replace("µV", unit) if unit != "µV" else bar
    return ""


def available(sfreq: float) -> list[tuple[str, str]]:
    """The (key, label) of every measure this sampling rate supports: a band
    whose top is within 90% of the Nyquist frequency is left out."""
    out = []
    for key, label, _bar, band in SIGNAL_MEASURES:
        if band is not None and band[1] > 0.45 * sfreq:
            continue
        if key == "energy_ratio" and FAST_BAND[1] > 0.45 * sfreq:
            continue
        out.append((key, label))
    return out


def _band_power(spectrum: np.ndarray, freqs: np.ndarray, band: tuple) -> np.ndarray:
    inside = (freqs >= band[0]) & (freqs < band[1])
    if not inside.any():
        return np.full(spectrum.shape[0], np.nan)
    step = float(freqs[1] - freqs[0]) if freqs.size > 1 else 1.0
    return spectrum[:, inside].sum(axis=1) * step


def stretch_values(session, key: str, t0: float, t1: float) -> dict[str, float]:
    """Channel -> the measure over [t0, t1) seconds of the loaded window
    (0 is its first sample). Channels the measure cannot be computed on are
    NaN; a stretch shorter than a quarter of a second gives NaN everywhere."""
    raw = session.raw
    names = list(raw.ch_names)
    sfreq = float(raw.info["sfreq"])
    first = max(0, int(round(float(t0) * sfreq)))
    last = min(int(raw.n_times), int(round(float(t1) * sfreq)))
    if key == "rate_in_stretch":
        return _rate_in_stretch(session, names, first / sfreq, last / sfreq)
    if last - first < int(0.25 * sfreq):
        return {name: float("nan") for name in names}
    data = np.asarray(raw.get_data(start=first, stop=last), dtype=float) * trace_scale(raw)
    if key == "signal_line_length":
        seconds = (last - first) / sfreq
        values = np.abs(np.diff(data, axis=1)).sum(axis=1) / seconds
        return dict(zip(names, map(float, values), strict=True))
    from scipy.signal import welch

    per_segment = int(min(data.shape[1], max(sfreq, 256)))
    freqs, spectrum = welch(data, fs=sfreq, nperseg=per_segment, axis=1)
    if key == "energy_ratio":
        fast = _band_power(spectrum, freqs, FAST_BAND)
        slow = _band_power(spectrum, freqs, SLOW_BAND)
        values = np.log10(np.maximum(fast, 1e-30) / np.maximum(slow, 1e-30))
    else:
        band = next(b for k, _l, _u, b in SIGNAL_MEASURES if k == key)
        power = _band_power(spectrum, freqs, band)
        values = 10.0 * np.log10(np.maximum(power, 1e-30))
    return dict(zip(names, map(float, values), strict=True))


def _rate_in_stretch(session, names: list[str], start: float, stop: float) -> dict:
    offset = float(getattr(session, "t_offset", 0.0))
    minutes = max(stop - start, 1e-9) / 60.0
    request = getattr(session, "request", None)
    detector = getattr(request, "primary", None) if request is not None else None
    counts = dict.fromkeys(names, 0)
    for event in session.events:
        if not getattr(event, "accepted", True) or event.detector == "spike":
            continue
        if detector is not None and event.detector != detector:
            continue
        mid = (float(event.start) + float(event.stop)) / 2.0 - offset
        if start <= mid < stop and event.channel in counts:
            counts[event.channel] += 1
    return {name: counts[name] / minutes for name in names}


def scalp_info(session):
    """A scalp EEG window's channels placed by their 10-05 names, as an
    `mne.Info` for a head topomap, and the names it could not place.

    A bipolar pair ("Fp1-F7") sits midway between its two electrodes, where
    its signal comes from; a single electrode at its own place. None when
    fewer than four channels can be placed.
    """
    import mne

    raw = session.raw
    picks = mne.pick_types(raw.info, eeg=True, exclude=[])
    if len(picks) < 4:
        return None, []
    try:
        # MNE 1.11 renamed the template head; older versions know only the old name.
        montage = mne.channels.make_standard_montage("colin27_1005")
    except ValueError:
        montage = mne.channels.make_standard_montage("standard_1005")
    standard = montage.get_positions()
    where = {name.lower(): xyz for name, xyz in standard["ch_pos"].items()}
    names = [raw.ch_names[i] for i in picks]
    placed: dict[str, np.ndarray] = {}
    for name in names:
        parts = [part.strip().lower() for part in name.split("-")]
        if all(part in where for part in parts) and 1 <= len(parts) <= 2:
            placed[name] = np.mean([where[part] for part in parts], axis=0)
    missing = [n for n in names if n not in placed]
    if len(placed) < 4:
        return None, missing
    info = mne.create_info(list(placed), float(raw.info["sfreq"]), "eeg")
    dig = mne.channels.make_dig_montage(
        ch_pos=placed, nasion=standard["nasion"], lpa=standard["lpa"],
        rpa=standard["rpa"], coord_frame="head")
    info.set_montage(dig, verbose="ERROR")
    return info, missing
