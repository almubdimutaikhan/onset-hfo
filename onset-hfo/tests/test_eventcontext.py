"""Around one event: neighbours, context and the two contacts (Qt-free).

What has to hold:

* the neighbours are the event's own electrode, in contact order, a few
  either side, and a channel whose name names no electrode stands alone;
* the context window is centred on the event, holds every neighbour, both as
  analysed and high-passed at the band's lower edge, and boxes the detections
  in it, the event itself among them;
* the other channels with a detection at the same moment are counted, and a
  detection elsewhere in time is not;
* the two contacts of a bipolar channel come from the fetched slice, and their
  difference is the bipolar signal the detector saw.
"""

from __future__ import annotations

import numpy as np
import pytest

from onset_review import eventcontext
from onset_review.session import ReviewRequest, session_from_recording


@pytest.fixture(scope="module")
def session(recording):
    request = ReviewRequest(dataset="", subject="synthetic", t_start=0.0,
                            t_stop=float(recording.duration), detectors=("rms",))
    return session_from_recording(recording, request)


@pytest.fixture(scope="module")
def event(session):
    return next(e for e in session.events if e.accepted and e.detector == "rms")


def test_neighbours_are_the_same_electrode_in_contact_order():
    names = ["AL1-AL2", "AL2-AL3", "AL3-AL4", "AL4-AL5", "AL5-AL6", "AL6-AL7",
             "PH1-PH2", "AL10-AL11", "AL7-AL8"]
    assert eventcontext.neighbours(names, "AL4-AL5", 2) == [
        "AL2-AL3", "AL3-AL4", "AL4-AL5", "AL5-AL6", "AL6-AL7"]
    assert eventcontext.neighbours(names, "AL1-AL2", 2) == ["AL1-AL2", "AL2-AL3", "AL3-AL4"]
    assert eventcontext.neighbours(names, "AL10-AL11", 1) == ["AL7-AL8", "AL10-AL11"], \
        "ordered by contact number, not by where the name sits in the list"
    assert eventcontext.neighbours(names, "PH1-PH2", 2) == ["PH1-PH2"]
    assert eventcontext.neighbours(["Fz", "Cz"], "Cz", 2) == ["Cz"]
    assert eventcontext.neighbours(names, "XX1-XX2", 2) == []


def test_the_context_is_centred_on_the_event_and_holds_every_neighbour(session, event):
    ctx = eventcontext.context(session, event, half_s=1.0, n=2)
    assert ctx.available and event.channel in ctx.channels
    assert ctx.channels == eventcontext.neighbours(session.raw.ch_names, event.channel, 2)
    assert ctx.wideband.shape == ctx.highpassed.shape == (len(ctx.channels), ctx.times.size)
    assert ctx.times[0] <= 0.0 and ctx.times[-1] >= ctx.event_span[1]
    assert ctx.highpass_hz == event.band[0]
    assert any(box["this"] for box in ctx.boxes), "the event itself is boxed"
    for box in ctx.boxes:
        assert box["channel"] in ctx.channels
        assert box["stop"] > ctx.times[0] and box["start"] < ctx.times[-1]


def test_the_high_passed_signal_has_no_slow_part(session, event):
    ctx = eventcontext.context(session, event, half_s=1.0)
    row = ctx.channels.index(event.channel)
    spectrum = np.abs(np.fft.rfft(ctx.highpassed[row]))
    freqs = np.fft.rfftfreq(ctx.times.size, 1.0 / session.raw.info["sfreq"])
    slow = spectrum[(freqs > 0) & (freqs < 20)].mean()
    fast = spectrum[(freqs > 100) & (freqs < 200)].mean()
    assert slow < fast


def test_detections_at_the_same_moment_elsewhere_are_counted(session, event):
    from dataclasses import replace

    near = eventcontext.neighbours(session.raw.ch_names, event.channel, 2)
    before = set(eventcontext.elsewhere(session, event, exclude=near))
    others = [c for c in session.raw.ch_names if c not in near and c not in before]
    twin = replace(event, channel=others[-1])
    later = replace(event, channel=others[-2], start=event.start + 5.0, stop=event.stop + 5.0)
    session.events.extend([twin, later])
    try:
        after = set(eventcontext.elsewhere(session, event, exclude=near))
        assert after == before | {others[-1]}, "the same moment counts; five seconds later does not"
    finally:
        session.events.remove(twin)
        session.events.remove(later)


def test_the_two_contacts_differ_into_the_bipolar_signal(session, event):
    pair = eventcontext.contacts(session, event, half_s=1.0)
    assert pair is not None
    first, second = event.channel.split("-")
    assert pair.channels == [first, second, f"{first} − {second}"]
    assert np.allclose(pair.wideband[2], pair.wideband[0] - pair.wideband[1])
    ctx = eventcontext.context(session, event, half_s=1.0)
    analysed = ctx.wideband[ctx.channels.index(event.channel)]
    n = min(analysed.size, pair.wideband.shape[1])
    assert np.corrcoef(analysed[:n], pair.wideband[2][:n])[0, 1] > 0.95
    assert any("notched at" in note for note in pair.notes)


def test_a_channel_that_is_not_a_pair_has_no_contacts(session, event):
    from dataclasses import replace

    assert eventcontext.contacts(session, replace(event, channel="SA1")) is None
