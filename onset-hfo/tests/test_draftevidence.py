"""The drafted report paragraphs: what each sentence rests on, the
limitations paragraph, the Methods paragraph, and the reader's verdicts as
evidence. Qt-free.

What these pin down:

* a sentence's windows and numbers are worked out from the answer the agent
  returned, with no model -- and a number is credited to a query only when it
  is one the check had to look up;
* a sentence the reader rewrote loses its evidence, and the report says it
  was not checked; one they left alone keeps it;
* a paragraph written for an earlier analysis of the same window is marked as
  such, because a read is filed under the window, not the analysis;
* the paragraphs survive a re-analysis and a save (they did not: `reconcile`
  dropped the findings paragraph);
* the Methods paragraph is the settings, verbatim, and the same settings give
  the same words;
* the reader's verdicts and the quality checks reach the assistant through
  tools whose numbers pass the number check.
"""

from __future__ import annotations

import pytest

from onset_agent import guard
from onset_agent.agent import AgentAnswer, OnsetAgent
from onset_review import adjudication, draftevidence, report
from onset_review.session import ReviewRequest, session_from_recording

ID_A = "sub-01|AR1-AR2|rms|12.31"
ID_B = "sub-01|AR1-AR2|rms|40.02"
ID_C = "sub-01|AR3-AR4|rms|5.5"


@pytest.fixture(scope="module")
def review(recording):
    return session_from_recording(
        recording, ReviewRequest(t_start=0.0, t_stop=float(recording.duration)))


def _answer(**kw) -> AgentAnswer:
    return AgentAnswer(question="q", text="", verified=True, **kw)


# -- sentences and what they rest on ------------------------------------------

def test_sentences_split_at_full_stops_but_never_inside_a_decimal_or_an_id():
    text = (f"AR1-AR2 led at 52.3 events/min [{ID_A}]. It is tied with 3 channels! "
            "Is that robust? (Not at 2x.)")
    assert draftevidence.split_sentences(text) == [
        f"AR1-AR2 led at 52.3 events/min [{ID_A}].", "It is tied with 3 channels!",
        "Is that robust?", "(Not at 2x.)"]
    assert draftevidence.split_sentences("  ") == []


def test_numbers_are_listed_with_their_units_and_ids_and_channel_digits_left_out():
    found = guard.numbers_in(f"AR1-AR2 led at 52.3 events/min (interval 39-68), "
                             f"3 channels tied; 12.5 dB at 192 Hz [{ID_A}].")
    assert found == [("52.3", "/min"), ("39", ""), ("68", ""), ("3", ""),
                     ("12.5", "dB"), ("192", "Hz")]
    assert guard.traced_to(52.3, {52.3: ["top_channels(k=5)"]}) == ["top_channels(k=5)"]
    assert guard.traced_to(52.31, {52.3: ["x()"]}) == ["x()"], "the check's own rounding"
    assert guard.traced_to(99.0, {52.3: ["x()"]}) == []


def test_each_sentence_gets_the_windows_of_the_channels_it_names_and_each_number_its_query():
    answer = _answer(evidence_ids=[ID_B], retrieved=[ID_A, ID_B, ID_C,
                                                     "sub-01|AR1-AR2|rms|50.0"],
                     number_sources={52.3: ["top_channels(k=5)"],
                                     39.0: ["top_channels(k=5)"],
                                     30.0: ["data_quality()"]})
    text = ("AR1-AR2 led at 52.3 events/min (interval 39-44). "
            "The window is 30 s long and 3 channels are tied.")
    first, second = draftevidence.annotate(text, answer)
    # Cited first, then retrieved, two per channel; AR3-AR4 is not named.
    assert first["evidence"] == [ID_B, ID_A]
    assert first["numbers"] == [
        {"value": "52.3/min", "source": "top_channels(k=5)"},
        {"value": "39", "source": "top_channels(k=5)"},
        {"value": "44", "source": ""}]          # nothing returned it: shown as such
    assert second["evidence"] == []
    assert second["numbers"] == [{"value": "30 s", "source": "data_quality()"},
                                 {"value": "3", "source": ""}], \
        "a small count is not credited to whichever query happened to return a 3"


def test_the_report_lists_what_each_sentence_rests_on_and_marks_the_readers_own():
    entries = draftevidence.annotate(
        "AR1-AR2 led at 52.3 events/min.",
        _answer(retrieved=[ID_A], number_sources={52.3: ["top_channels(k=5)"]}))
    lines = draftevidence.markdown_lines(
        "AR1-AR2 led at 52.3 events/min. I confirmed it on the trace.", entries)
    assert lines[0] == "**What each sentence rests on**"
    assert "windows: AR1-AR2 at 12.31 s (rms)" in lines[2]
    assert "numbers: 52.3/min ← top_channels(k=5)" in lines[2]
    assert "written or edited by the reader; not checked" in lines[3]
    assert draftevidence.markdown_lines("", entries) == []


# -- the read keeps the paragraphs, and knows what they were written for ------

def test_an_edited_sentence_loses_its_evidence_and_an_unchanged_one_keeps_it():
    read = adjudication.Adjudication(window="w")
    entries = [{"sentence": "AR1-AR2 led at 52.3 events/min.", "evidence": [ID_A],
                "numbers": []},
               {"sentence": "It is tied with 3 channels.", "evidence": [], "numbers": []}]
    read.set_draft("AR1-AR2 led at 52.3 events/min. It is tied with 3 channels.",
                   "assistant (scripted)", entries, "basis-1")
    assert read.draft_is_assistants and len(read.draft_evidence) == 2
    read.set_draft("AR1-AR2 led at 52.3 events/min. I count 4 tied.", "Dr A",
                   basis="basis-1")
    assert not read.draft_is_assistants
    assert [e["sentence"] for e in read.draft_evidence] == ["AR1-AR2 led at 52.3 events/min."]
    # Re-analysed with other settings: nothing found under the old ones is kept.
    read.set_draft("AR1-AR2 led at 52.3 events/min.", "Dr A", basis="basis-2")
    assert read.draft_evidence == [] and read.draft_basis == "basis-2"
    read.set_draft("", "Dr A")
    assert (read.draft, read.draft_by, read.draft_evidence, read.draft_basis) == ("", "", [], "")


def test_both_paragraphs_survive_a_save_and_a_reanalysis(review):
    read = adjudication.Adjudication(window="w")
    read.set_draft("AR1-AR2 led.", "assistant (scripted)",
                   [{"sentence": "AR1-AR2 led.", "evidence": [ID_A], "numbers": []}], "b")
    read.set_limits("The window is short.", "Dr A", [], "b")
    again = adjudication.Adjudication.from_json(read.to_json())
    for name in ("draft", "draft_by", "draft_at", "draft_evidence", "draft_basis",
                 "limits", "limits_by", "limits_at", "limits_evidence", "limits_basis"):
        assert getattr(again, name) == getattr(read, name), name
    assert again.limits_is_assistants is False
    # `reconcile` runs on every re-analysis; it used to drop the paragraph, and
    # the next save then erased what the reader had written.
    carried = adjudication.reconcile(again, review.events)
    assert (carried.draft, carried.draft_evidence, carried.limits) == \
        (read.draft, read.draft_evidence, read.limits)


def test_the_basis_names_every_setting_a_number_depends_on():
    base = draftevidence.analysis_basis(ReviewRequest())
    for changed in (ReviewRequest(threshold_sd=3.0), ReviewRequest(band="fast_ripple"),
                    ReviewRequest(detectors=("line_length",)),
                    ReviewRequest(check_quality=False), ReviewRequest(t_stop=120.0)):
        assert draftevidence.analysis_basis(changed) != base
    assert draftevidence.analysis_basis(ReviewRequest()) == base


# -- the report ---------------------------------------------------------------

@pytest.fixture
def blank_paragraphs(review):
    read = review.read
    before = read.to_json()
    read.set_draft("", "")
    read.set_limits("", "")
    yield read
    restored = adjudication.Adjudication.from_json(before)
    for name in ("draft", "draft_by", "draft_at", "draft_evidence", "draft_basis",
                 "limits", "limits_by", "limits_at", "limits_evidence", "limits_basis"):
        setattr(read, name, getattr(restored, name))


def test_the_limitations_paragraph_has_its_own_section_attributed_like_the_findings(
        review, blank_paragraphs):
    read, basis = blank_paragraphs, draftevidence.analysis_basis(review.request)
    assert "## Limitations" not in report.review_markdown(review, appendix=False)
    read.set_draft("SA2-SA3 led.", "assistant (scripted)", [], basis)
    read.set_limits("The window is 30 s long.", "assistant (scripted)",
                    [{"sentence": "The window is 30 s long.", "evidence": [],
                      "numbers": [{"value": "30 s", "source": "data_quality()"}]}], basis)
    text = report.review_markdown(review, appendix=False)
    section = text[text.index("## Limitations"):text.index("## Per-channel findings")]
    assert text.index("## Findings") < text.index("## Limitations")
    assert "Drafted by the assistant (scripted)" in section
    assert "numbers: 30 s ← data_quality()" in section
    # The reader adds a sentence: the paragraph is theirs, the assistant's
    # sentence keeps its query, and theirs is marked as not checked.
    read.set_limits("The window is 30 s long. That is short.", "Dr A", basis=basis)
    section = report.review_markdown(review, appendix=False)
    section = section[section.index("## Limitations"):section.index("## Per-channel")]
    assert "_Written by Dr A on" in section
    assert "numbers: 30 s ← data_quality()" in section
    assert "“That is short.” — written or edited by the reader; not checked" in section
    # Every sentence rewritten: nothing left to list under it.
    read.set_limits("Thirty seconds is short.", "Dr A", basis=basis)
    section = report.review_markdown(review, appendix=False)
    assert "What each sentence rests on" not in \
        section[section.index("## Limitations"):section.index("## Per-channel")]


def test_a_paragraph_written_for_an_earlier_analysis_says_so_and_lists_no_evidence(
        review, blank_paragraphs):
    stale = draftevidence.analysis_basis(ReviewRequest(threshold_sd=3.0))
    blank_paragraphs.set_draft(
        "SA2-SA3 led at 54 events/min.", "assistant (scripted)",
        [{"sentence": "SA2-SA3 led at 54 events/min.", "evidence": [ID_A], "numbers": []}],
        stale)
    text = report.review_markdown(review, appendix=False)
    section = text[text.index("## Findings"):text.index("## Per-channel findings")]
    assert "for an earlier analysis of this window" in section
    assert "were not checked against it" in section
    assert "What each sentence rests on" not in section
    assert "Every number in it was checked" not in section


def test_the_methods_paragraph_is_the_settings_and_the_same_settings_give_the_same_words(
        review, recording):
    text = report.review_markdown(review, appendix=False)
    methods = text[text.index("## Methods"):text.index("## How the signal was prepared")]
    cfg = review.request.pipeline_config()
    for expected in (f"at {review.sfreq:g} Hz", "80–250 Hz",
                     f"root-mean-square energy at {cfg.rms.threshold_sd:.1f} robust SD",
                     f"at least {cfg.rms.min_peaks} peaks",
                     f"{cfg.validation.min_peak_prominence_db:g} dB above the fitted 1/f",
                     f"fewer than {cfg.validation.min_cycles:g} cycles",
                     "exact (Garwood) 95% Poisson interval",
                     f"Data-quality checks ran on {len(review.quality)} channels",
                     "no model was involved"):
        assert expected in methods, expected
    again = session_from_recording(
        recording, ReviewRequest(t_start=0.0, t_stop=float(recording.duration)))
    other = report.review_markdown(again, appendix=False)
    assert other[other.index("## Methods"):other.index("## How the signal")] == methods
    stricter = session_from_recording(
        recording, ReviewRequest(t_start=0.0, t_stop=float(recording.duration),
                                 threshold_sd=7.0, check_quality=False))
    changed = report.review_markdown(stricter, appendix=False)
    changed = changed[changed.index("## Methods"):changed.index("## How the signal")]
    assert "at 7.0 robust SD (the reviewer's threshold)" in changed
    assert "The data-quality checks were off" in changed


def test_the_methods_paragraph_does_not_describe_a_detection_that_never_ran(review,
                                                                            monkeypatch):
    note = ("HFO detection skipped: the 80–250 Hz band needs a sampling rate of at "
            "least 750 Hz; this recording has 256 Hz.")
    monkeypatch.setattr(review, "notes", [note, *review.notes])
    text = report.review_markdown(review, appendix=False)
    methods = text[text.index("## Methods"):text.index("## How the signal was prepared")]
    assert note in methods
    assert "Candidate ripples were detected" not in methods
    assert "ranked by their rate of interictal discharges" in methods


def test_the_header_states_the_default_threshold_instead_of_calling_it_measured(review):
    text = report.review_markdown(review, appendix=False)
    assert "| Threshold | each detector's default (5.0 robust SD) |" in text
    assert "measured default" not in text
    assert ReviewRequest(detectors=("rms", "line_length")).default_thresholds() == \
        "Root-mean-square energy 5.0, Line length 3.0 robust SD"


# -- the reader's verdicts and the quality checks, as the assistant's evidence --

def test_the_readers_verdicts_and_the_quality_checks_are_tools_whose_numbers_pass_the_check(
        review, store, monkeypatch):
    from onset_review import assistant_tools

    accepted = [e for e in review.events if e.accepted and e.detector == "rms"]
    read = adjudication.Adjudication(window="w", reader="Dr A")
    for event, verdict in zip(accepted[:3], ("agree", "disagree", "agree"), strict=True):
        read.judge_event(adjudication.event_key(event.channel, event.start, event.detector),
                         verdict, "Dr A")
    monkeypatch.setattr(review, "read", read)
    tools = {**assistant_tools.reader_tools(review), **assistant_tools.quality_tools(review)}
    verdicts = tools["reader_verdicts"].handler(None)
    assert (verdicts["judged"], verdicts["agree"], verdicts["disagree"]) == (3, 2, 1)
    assert verdicts["accepted_events"] == len(accepted) and verdicts["reader"] == "Dr A"
    top = verdicts["busiest_channels"][0]
    assert top["channel"] == str(review.findings["channel"].iloc[0])
    quality = tools["data_quality"].handler(None)
    assert quality["analysed_s"] == pytest.approx(float(review.request.duration))
    assert quality["n_set_aside"] == int((~review.quality["good"]).sum())

    for question in (draftevidence.DRAFT_QUESTION, draftevidence.LIMITS_QUESTION):
        assert guard.check_question(question, "sim-01").ok, "never refused before the model"
    LIMITS_QUESTION = draftevidence.LIMITS_QUESTION
    agent = OnsetAgent(store, extra_tools=tools)
    answer = agent.ask(LIMITS_QUESTION,
                       extra_briefing=[("reader_verdicts", {}), ("data_quality", {})])
    assert answer.verified and not answer.refused, answer.text
    assert f"judged 3 of {len(accepted)} accepted events" in answer.text
    labels = {label for sources in answer.number_sources.values() for label in sources}
    assert {"reader_verdicts()", "data_quality()"} <= labels
    entries = draftevidence.annotate(answer.text, answer)
    traced = [n for e in entries for n in e["numbers"] if n["source"]]
    assert any("reader_verdicts()" in n["source"] for n in traced) or len(accepted) <= 20
