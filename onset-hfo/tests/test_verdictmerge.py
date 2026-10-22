"""Merging several readers' verdict files, which needs no display and no data.

The files are written with the same `Adjudication` class the window uses, so a
change to the stored format breaks these tests before it breaks a study.
"""

from __future__ import annotations

import json
import math

import pytest

from onset_review import adjudication, trends, verdictmerge
from onset_review.adjudication import Adjudication, Judgement
from onset_review.session import ReviewRequest, session_from_recording

WINDOW = "ds003498-sub-01-run01-0-60s"
KEYS = [adjudication.event_key("AD1-AD2", 1.0 + i, "rms") for i in range(6)]


def _write(folder, name, reader, verdicts, window=WINDOW, at="2026-10-20T10:00:00Z"):
    """One reader's file: `verdicts` maps an event key to a verdict."""
    read = Adjudication(window=window, reader=reader)
    for key, verdict in verdicts.items():
        read.events[key] = Judgement(verdict=verdict, reader=reader, at=at)
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(read.to_json()), encoding="utf-8")
    return path


def test_one_row_per_verdict_with_the_reader_and_source(tmp_path):
    _write(tmp_path, "p01/read.json", "P01", {KEYS[0]: "agree", KEYS[1]: "disagree"})
    table, unreadable = verdictmerge.collect(tmp_path)
    assert unreadable == []
    assert list(table.columns) == verdictmerge.COLUMNS
    assert sorted(table["verdict"]) == ["agree", "disagree"]
    assert set(table["reader"]) == {"P01"}
    assert set(table["source"]) == {"p01/read.json"}


def test_two_machines_with_the_same_filename_both_survive(tmp_path):
    """The reason this module exists: same file name, different readers."""
    _write(tmp_path, "p01/read.json", "P01", {KEYS[0]: "agree"})
    _write(tmp_path, "p02/read.json", "P02", {KEYS[0]: "disagree"})
    table, _ = verdictmerge.collect(tmp_path)
    assert len(table) == 2
    assert set(table["reader"]) == {"P01", "P02"}


def test_a_reader_sent_twice_keeps_the_later_verdict(tmp_path):
    _write(tmp_path, "p01/first.json", "P01", {KEYS[0]: "agree"}, at="2026-10-20T10:00:00Z")
    _write(tmp_path, "p01/second.json", "P01", {KEYS[0]: "disagree"}, at="2026-10-20T11:00:00Z")
    table, _ = verdictmerge.collect(tmp_path)
    assert len(table) == 1
    assert table.iloc[0]["verdict"] == "disagree"
    assert verdictmerge.identity_notes(table) == []


def test_readers_who_left_their_name_blank_are_not_one_reader(tmp_path):
    _write(tmp_path, "a/read.json", "", {KEYS[0]: "agree", KEYS[1]: "agree"})
    _write(tmp_path, "b/read.json", "", {KEYS[0]: "disagree", KEYS[1]: "agree"})
    _write(tmp_path, "loose.json", "", {KEYS[0]: "unsure"})
    table, _ = verdictmerge.collect(tmp_path)
    assert len(table) == 5, "nobody's verdict is dropped as a duplicate of another's"
    assert set(table["reader"]) == {"unnamed · a", "unnamed · b", "unnamed · loose.json"}
    assert set(table["name"]) == {""}
    pairs = verdictmerge.agreement(table).set_index(["reader_a", "reader_b"])
    assert pairs.loc[("unnamed · a", "unnamed · b"), "n"] == 2
    assert pairs.loc[("unnamed · a", "unnamed · b"), "percent_agree"] == 50.0
    notes = verdictmerge.identity_notes(table)
    assert len(notes) == 1 and "left their name blank" in notes[0]
    assert "Who is who" in verdictmerge.summary(table, [])


def test_one_name_in_two_folders_is_two_readers_and_the_summary_says_so(tmp_path):
    """Two people whose machines both call them `user`."""
    _write(tmp_path, "ward/read.json", "user", {KEYS[0]: "agree"})
    _write(tmp_path, "lab/read.json", "user", {KEYS[0]: "disagree"})
    table, _ = verdictmerge.collect(tmp_path)
    assert set(table["reader"]) == {"user · ward", "user · lab"}
    pairs = verdictmerge.agreement(table)
    assert len(pairs) == 1 and pairs.iloc[0]["percent_agree"] == 0.0
    text = verdictmerge.summary(table, [])
    assert "The name 'user' is in 2 folders and is counted as 2 readers" in text


def test_an_unreadable_file_is_named_and_skipped_not_fatal(tmp_path):
    _write(tmp_path, "p01/read.json", "P01", {KEYS[0]: "agree"})
    (tmp_path / "p02").mkdir()
    (tmp_path / "p02" / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "p02" / "other.json").write_text(json.dumps({"something": "else"}),
                                                 encoding="utf-8")
    table, unreadable = verdictmerge.collect(tmp_path)
    assert len(table) == 1
    assert sorted(unreadable) == ["p02/broken.json", "p02/other.json"]


def test_agreement_counts_only_events_both_readers_judged(tmp_path):
    _write(tmp_path, "a/read.json", "A",
           {KEYS[0]: "agree", KEYS[1]: "agree", KEYS[2]: "disagree", KEYS[3]: "disagree"})
    _write(tmp_path, "b/read.json", "B",
           {KEYS[0]: "agree", KEYS[1]: "disagree", KEYS[2]: "disagree", KEYS[4]: "agree"})
    table, _ = verdictmerge.collect(tmp_path)
    pair = verdictmerge.agreement(table).iloc[0]
    assert (pair["reader_a"], pair["reader_b"]) == ("A", "B")
    assert pair["n"] == 3                      # KEYS[3] and KEYS[4] were judged by one only
    assert pair["percent_agree"] == pytest.approx(66.7, abs=0.05)
    assert pair["kappa"] == pytest.approx(0.4, abs=0.001)   # Cohen's: (2/3 - 4/9) / (1 - 4/9)


def test_kappa_is_undefined_not_perfect_when_one_verdict_was_used(tmp_path):
    _write(tmp_path, "a/read.json", "A", {KEYS[0]: "agree", KEYS[1]: "agree"})
    _write(tmp_path, "b/read.json", "B", {KEYS[0]: "agree", KEYS[1]: "agree"})
    table, _ = verdictmerge.collect(tmp_path)
    pair = verdictmerge.agreement(table).iloc[0]
    assert pair["percent_agree"] == 100.0
    assert math.isnan(pair["kappa"])


def test_the_same_event_in_different_windows_is_not_one_event(tmp_path):
    _write(tmp_path, "a/read.json", "A", {KEYS[0]: "agree"}, window="window-one")
    _write(tmp_path, "b/read.json", "B", {KEYS[0]: "disagree"}, window="window-two")
    table, _ = verdictmerge.collect(tmp_path)
    assert verdictmerge.agreement(table).iloc[0]["n"] == 0


def test_channel_verdicts_are_kept_but_do_not_enter_event_agreement(tmp_path):
    read = Adjudication(window=WINDOW, reader="A")
    read.channels["AD1-AD2"] = Judgement(verdict="accept", reader="A", at="2026-10-20T10:00:00Z")
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "read.json").write_text(json.dumps(read.to_json()), encoding="utf-8")
    table, _ = verdictmerge.collect(tmp_path)
    assert list(table["scope"]) == ["channel"]
    assert verdictmerge.agreement(table).empty


def test_an_empty_folder_says_so_instead_of_crashing(tmp_path):
    table, unreadable = verdictmerge.collect(tmp_path)
    assert table.empty and unreadable == []
    assert verdictmerge.summary(table, unreadable) == "No verdicts found."


def test_main_writes_the_csv_and_prints_the_summary(tmp_path, capsys):
    _write(tmp_path / "study", "a/read.json", "A", {KEYS[0]: "agree", KEYS[1]: "disagree"})
    _write(tmp_path / "study", "b/read.json", "B", {KEYS[0]: "agree", KEYS[1]: "agree"})
    out = tmp_path / "verdicts.csv"
    assert verdictmerge.main([str(tmp_path / "study"), "-o", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "4 verdicts from 2 readers" in printed
    assert "Agreement on events both readers judged" in printed
    assert out.read_text(encoding="utf-8").splitlines()[0].startswith("window,scope,key,reader")


def test_main_refuses_a_path_that_is_not_a_folder(tmp_path, capsys):
    assert verdictmerge.main([str(tmp_path / "missing")]) == 1
    assert "not a folder" in capsys.readouterr().err


def test_two_readers_on_the_real_events_of_one_window_line_up(recording, tmp_path, monkeypatch):
    """End to end: analyse a window, two readers judge it on 'separate machines'
    through the reviewer's own save, and the merge matches their events.

    Each reader gets their own reads folder, as they would on their own
    computer, so both files carry the same name. The keys must agree because
    the analysis is deterministic, which is what lets a study share one command.
    """
    request = ReviewRequest(t_start=0.0, t_stop=float(recording.duration))
    session = session_from_recording(recording, request)
    keys = list(trends.event_table(session)["key"])[:8]
    assert len(keys) == 8

    def read_as(reader, verdicts):
        folder = tmp_path / reader
        monkeypatch.setenv("ONSET_REVIEW_READS", str(folder))
        read = adjudication.load(request)
        for key, verdict in zip(keys, verdicts, strict=True):
            read.judge_event(key, verdict, reader=reader)
        adjudication.save(request, read)
        return adjudication.path_for(request)

    first = read_as("P01", ["agree"] * 5 + ["disagree"] * 3)
    second = read_as("P02", ["agree"] * 4 + ["disagree"] * 3 + ["unsure"])
    assert first.name == second.name and first != second     # the collision, reproduced

    table, unreadable = verdictmerge.collect(tmp_path)
    assert unreadable == []
    assert len(table) == 16 and set(table["reader"]) == {"P01", "P02"}
    pair = verdictmerge.agreement(table).iloc[0]
    assert pair["n"] == 8
    assert pair["percent_agree"] == 75.0                      # all but events 5 and 8
