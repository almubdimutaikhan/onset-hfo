"""Map a stretch: signal measures over a span, the stretch controls, the scalp topomap.

What has to hold:

* each measure is computed over the stretch asked for, from the signal the
  detectors saw; a band is offered only below the Nyquist frequency; a
  stretch too short to measure is NaN rather than a number;
* a channel carrying fast activity has the highest fast/slow energy ratio and
  gamma power, so the map points where the signal does;
* the HFO rate in a stretch counts the ranking detector's accepted events
  whose middle falls inside it, per minute of the stretch;
* on the Map page a signal measure shows the stretch controls, which move the
  span, follow the trace on screen and play along the window;
* scalp EEG is drawn as a head topomap, a bipolar pair placed midway between
  its two electrodes, with names it cannot place listed.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import mne
import numpy as np
import pytest

from onset_review import stretchmap

SF = 1000.0


def _session(names=("A1-A2", "A2-A3", "B1-B2", "B2-B3"), seconds=10.0, fast_on=1,
             kind="seeg", events=()):
    rng = np.random.default_rng(3)
    t = np.arange(int(seconds * SF)) / SF
    data = rng.normal(0, 5.0, (len(names), t.size)) + 20.0 * np.sin(2 * np.pi * 6.0 * t)
    if fast_on is not None:
        data[fast_on] += 15.0 * np.sin(2 * np.pi * 40.0 * t)
    raw = mne.io.RawArray(data * 1e-6, mne.create_info(list(names), SF, kind), verbose="ERROR")
    return SimpleNamespace(raw=raw, events=list(events), t_offset=100.0, unit="µV",
                           request=SimpleNamespace(primary="rms"))


def test_a_band_is_offered_only_below_the_nyquist_frequency():
    at_1000 = dict(stretchmap.available(1000.0))
    assert "power_ripple" in at_1000 and "power_fast_ripple" not in at_1000
    assert "power_fast_ripple" in dict(stretchmap.available(2000.0))
    assert "energy_ratio" not in dict(stretchmap.available(150.0))


def test_the_channel_with_fast_activity_leads_the_fast_measures():
    session = _session()
    ratio = stretchmap.stretch_values(session, "energy_ratio", 1.0, 5.0)
    gamma = stretchmap.stretch_values(session, "power_gamma", 1.0, 5.0)
    theta = stretchmap.stretch_values(session, "power_theta", 1.0, 5.0)
    assert max(ratio, key=ratio.get) == "A2-A3"
    assert max(gamma, key=gamma.get) == "A2-A3"
    assert max(theta.values()) - min(theta.values()) < 3.0, "the slow rhythm is everywhere"
    lengths = stretchmap.stretch_values(session, "signal_line_length", 1.0, 5.0)
    assert max(lengths, key=lengths.get) == "A2-A3"


def test_a_stretch_too_short_to_measure_is_nan_not_a_number():
    session = _session()
    values = stretchmap.stretch_values(session, "power_delta", 2.0, 2.1)
    assert all(np.isnan(v) for v in values.values())


def test_the_hfo_rate_counts_the_ranking_detectors_events_in_the_stretch():
    def event(channel, start, detector="rms", accepted=True):
        return SimpleNamespace(channel=channel, start=100.0 + start, stop=100.0 + start + 0.05,
                               detector=detector, accepted=accepted)

    events = [event("A1-A2", 1.0), event("A1-A2", 2.0), event("A1-A2", 7.0),
              event("A1-A2", 2.5, detector="line_length"),
              event("A1-A2", 3.0, accepted=False), event("B1-B2", 4.0)]
    session = _session(events=events)
    rates = stretchmap.stretch_values(session, "rate_in_stretch", 0.0, 6.0)
    assert rates["A1-A2"] == pytest.approx(2 / 0.1), "two in six seconds, per minute"
    assert rates["B1-B2"] == pytest.approx(1 / 0.1)
    assert rates["A2-A3"] == 0.0


def test_a_bipolar_scalp_pair_sits_between_its_electrodes():
    names = ("Fp1-F7", "F7-T7", "T7-P7", "P7-O1", "Fz-Cz", "Cz-Pz", "XX1-XX2")
    session = _session(names=names, kind="eeg", fast_on=None)
    info, missing = stretchmap.scalp_info(session)
    assert missing == ["XX1-XX2"]
    assert info.ch_names == list(names[:-1])
    try:
        montage = mne.channels.make_standard_montage("colin27_1005")
    except ValueError:
        montage = mne.channels.make_standard_montage("standard_1005")
    where = montage.get_positions()["ch_pos"]
    placed = info.get_montage().get_positions()["ch_pos"]
    assert np.allclose(placed["Fz-Cz"], (where["Fz"] + where["Cz"]) / 2)


def test_too_few_scalp_channels_is_no_topomap():
    session = _session(names=("Fp1-F7", "XX1-XX2", "YY1-YY2"), kind="eeg", fast_on=None)
    assert stretchmap.scalp_info(session)[0] is None


# -- the Map page ----------------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    widgets = pytest.importorskip("qtpy.QtWidgets", reason="the review extra is not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    yield widgets.QApplication.instance() or widgets.QApplication([])


@pytest.fixture(scope="module")
def review(recording):
    from onset_review.session import ReviewRequest, session_from_recording

    request = ReviewRequest(dataset="", subject="synthetic", t_start=0.0,
                            t_stop=float(recording.duration), detectors=("rms",))
    return session_from_recording(recording, request)


def test_a_signal_measure_shows_the_stretch_and_maps_over_it(qapp, review):
    from onset_review.mapview import ContactMapPanel

    panel = ContactMapPanel(review)
    try:
        assert panel.stretch_row.isHidden(), "the detectors' rate needs no stretch"
        panel.measure.setCurrentIndex(panel.measure.findData("power_gamma"))
        assert not panel.stretch_row.isHidden()
        assert not panel.labels.isEnabled(), "the detectors' ranks do not label a power map"
        panel.set_span(4.0, 7.0)
        assert panel.span() == pytest.approx((4.0, 7.0))
        assert panel.span_label.text() == "4.00–7.00 s"
        assert "4.00–7.00 s" in panel.headline.text() and "not a finding" in panel.headline.text()
        expected = stretchmap.stretch_values(review, "power_gamma", 4.0, 7.0)
        drawn = dict(zip(panel.frame["channel"], panel.frame["value"], strict=True))
        assert drawn == pytest.approx(expected)
        assert panel._points is not None and panel._colorbar is not None
    finally:
        panel.close()


def test_the_stretch_follows_the_trace_on_screen_and_plays_along(qapp, review):
    from onset_review.mapview import ContactMapPanel

    panel = ContactMapPanel(review)
    try:
        panel.measure.setCurrentIndex(panel.measure.findData("energy_ratio"))
        assert not panel.use_trace_span(), "no trace given: says so"
        panel.trace_span = lambda: (10.0, 20.0)
        assert panel.use_trace_span()
        assert panel.span() == pytest.approx((10.0, 20.0))
        panel.set_span(0.0, 2.0)
        panel.play.setChecked(True)
        panel._tick()
        assert panel.span()[0] == pytest.approx(1.0), "one second per tick"
        panel.set_span(panel._duration - 2.0, panel._duration)
        panel._tick()
        assert not panel.play.isChecked(), "stops at the end of the window"
    finally:
        panel.close()


def test_scalp_eeg_is_drawn_as_a_head(qapp, recording):
    from onset_hfo.synthetic import as_modality
    from onset_review.mapview import ContactMapPanel
    from onset_review.session import ReviewRequest, session_from_recording

    scalp = as_modality(recording, "eeg")
    session = session_from_recording(scalp, ReviewRequest(
        dataset="", subject="scalp", t_start=0.0, t_stop=float(recording.duration),
        detectors=("rms",), modality="eeg"))
    panel = ContactMapPanel(session)
    try:
        panel.measure.setCurrentIndex(panel.measure.findData("power_alpha"))
        assert panel.axes.get_title(loc="left") == "Head, seen from above"
        assert "10–05 names" in panel.caption.text()
        assert panel._colorbar is not None
    finally:
        panel.close()
