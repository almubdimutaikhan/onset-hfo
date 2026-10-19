"""Two report faults a reader found in the first week (October 2026).

* The data-quality line counted rejection reasons with their measured values,
  so "only 1.7 dB above the 1/f background" and "only 1.5 dB above ..." were
  separate groups: about thirty groups for one kind, over 2,000 characters.
* A synthetic recording's implanted events travel in the field an archive's
  expert markings use, and the report called them expert markings.
"""

from __future__ import annotations

import pytest

from onset_hfo.detectors.base import Event
from onset_hfo.report import build_report
from onset_hfo.validate import reason_kind, rejection_summary


@pytest.mark.parametrize("reason, kind", [
    ("only 2.4 cycles (< 4)", "too few cycles"),
    ("in-band spectral peak only 1.7 dB above the 1/f background (< 4 dB): probable "
     "filter ringing", "no clear spectral peak, probably filter ringing"),
    ("spectrum not measurable and a large low-frequency transient is present: probable "
     "filter ringing", "low-frequency transient, probably filter ringing"),
    ("seen on 19 other channels at once (more than 50% of them): probable muscle or "
     "movement artefact", "on too many channels at once, probably muscle or movement"),
    ("on a channel set aside by the quality checks",
     "on a channel set aside by the quality checks"),
    ("inside a rejected segment (12-14 s)", "inside a rejected segment"),
    (None, "accepted"),
])
def test_each_reason_is_counted_by_its_kind(reason, kind):
    assert reason_kind(reason) == kind


def test_an_unknown_reason_keeps_its_words_without_its_numbers():
    assert reason_kind("amplitude 950.2 uV above 900 uV") == "amplitude # uV above # uV"


def _event(reason):
    return Event(channel="A1-A2", start=0.0, stop=0.01, detector="rms", band=(80.0, 250.0),
                 accepted=reason is None, reject_reason=reason)


def test_values_measured_differently_fall_in_one_group():
    events = [_event(f"in-band spectral peak only {db:.1f} dB above the 1/f background "
                     "(< 4 dB): probable filter ringing") for db in (1.2, 1.5, 1.7, 2.1, 3.9)]
    events += [_event("only 3.1 cycles (< 4)"), _event(None)]
    assert rejection_summary(events) == {
        "no clear spectral peak, probably filter ringing": 5,
        "too few cycles": 1, "accepted": 1}


def test_the_reports_rejection_lines_stay_short(result):
    lines = [line for line in result.report.data_quality if "candidate events" in line]
    assert lines
    assert all(len(line) < 400 for line in lines), [len(line) for line in lines]


def test_a_synthetic_report_does_not_claim_expert_markings(result):
    text = " ".join(result.report.limitations)
    assert result.recording.provenance()["source"] == "synthetic"
    assert "expert HFO markings" not in text
    assert "synthetic recording with known, implanted events" in text
    assert "single patient" not in text


def test_an_archive_with_markings_still_says_so(result):
    provenance = {**result.recording.provenance(), "source": "openneuro:ds003498"}
    report = build_report(
        provenance=provenance, rates=result.rates, comparison=result.comparison,
        events=result.events, spike_rates=result.spike_rates, duration_s=result.duration_s,
        preprocessing_steps=result.prepared.steps, config=result.config.as_dict(),
        rejections={})
    text = " ".join(report.limitations)
    assert "carries expert HFO markings" in text
    assert "single patient" in text


def test_the_rejection_line_has_no_parentheses_inside_its_parentheses(result):
    lines = [line for line in result.report.data_quality if "rejected by artifact validation" in line]
    assert lines
    for line in lines:
        inside = line[line.index("validation (") + len("validation ("):-1]
        assert "(" not in inside and ")" not in inside, line
