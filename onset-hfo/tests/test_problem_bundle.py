"""The problem report: what is shown is what is saved, and nothing else.

No display needed. The window's dialog is tested beside the other dialogs in
`test_support.py`; this file holds the rules underneath it and the command line.

What has to hold:

* the zip contains exactly the text that was built and shown, file for file;
* a file left out is not in the zip, and the rest is unchanged;
* the person's own words are in `report.txt`, and the home folder is `~`
  everywhere;
* `report.txt` quotes no log, so unticking the logs leaves out every name
  they hold -- the recordings that were opened included;
* a command line report carries no window log, even when one exists, and saves
  nothing unless the person says yes -- or cannot be asked.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from onset_hfo import cli
from onset_review import applog, problemreport

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def logs(tmp_path, monkeypatch):
    """A log folder with a log, a rotated log, a crash log and a model check,
    each naming the home folder so that redaction has something to do."""
    folder = tmp_path / "logs"
    (folder / "model-checks").mkdir(parents=True)
    home = str(Path.home())
    (folder / applog.LOG_NAME).write_text(f"INFO opened {home}/data/sub-07.edf\nINFO second\n")
    (folder / f"{applog.LOG_NAME}.1").write_text("INFO an older line\n")
    (folder / applog.CRASH_NAME).write_text("Fatal Python error in a C extension\n")
    (folder / "model-checks" / "model-check-1.json").write_text(json.dumps({"home": home}))
    (folder / "model-checks" / "model-check-1.md").write_text("# Model check\n")
    monkeypatch.setenv("ONSET_REVIEW_LOG_DIR", str(folder))
    return folder


def _zip_texts(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as zipped:
        return {name: zipped.read(name).decode("utf-8") for name in zipped.namelist()}


# -- what is shown is what is saved ---------------------------------------------------
def test_the_zip_holds_exactly_the_text_that_was_built(logs, tmp_path):
    bundle = applog.build_bundle("it hung on open")
    written = applog.write_bundle(bundle, tmp_path / "out")
    assert written == tmp_path / "out.zip"
    assert _zip_texts(written) == bundle.files          # names, order-insensitive, and text


def test_every_file_the_report_would_hold_is_listed_with_its_size(logs):
    bundle = applog.build_bundle()
    rows = {row["name"]: row for row in bundle.manifest()}
    assert {"report.txt", applog.LOG_NAME, f"{applog.LOG_NAME}.1", applog.CRASH_NAME,
            "model-check-1.json", "model-check-1.md"} <= set(rows)
    assert rows[applog.LOG_NAME]["lines"] == 2
    assert rows[applog.LOG_NAME]["bytes"] == len(bundle.files[applog.LOG_NAME].encode())


def test_a_file_left_out_is_not_saved_and_the_rest_is_unchanged(logs, tmp_path):
    bundle = applog.build_bundle()
    kept = [name for name in bundle.files if name != applog.LOG_NAME]
    saved = _zip_texts(applog.write_bundle(bundle.only(kept), tmp_path / "out.zip"))
    assert applog.LOG_NAME not in saved
    assert saved == {name: bundle.files[name] for name in kept}


def test_the_persons_own_words_are_in_the_report(logs):
    bundle = applog.build_bundle("I pressed Apply and the window froze")
    assert "I pressed Apply and the window froze" in bundle.files["report.txt"]
    revised = bundle.with_description("Now it only freezes on fast ripple")
    assert "only freezes on fast ripple" in revised.files["report.txt"]
    assert "I pressed Apply" not in revised.files["report.txt"]
    # the logs are carried over untouched, not re-read
    assert {k: v for k, v in revised.files.items() if k != "report.txt"} == \
        {k: v for k, v in bundle.files.items() if k != "report.txt"}


def test_the_home_folder_is_written_as_a_tilde_in_every_file(logs):
    home = str(Path.home())
    bundle = applog.build_bundle(f"the file was {home}/data/sub-07.edf")
    for name, text in bundle.files.items():
        assert home not in text, name
    assert "~/data/sub-07.edf" in bundle.files[applog.LOG_NAME]


def test_the_report_lists_the_logs_and_quotes_none_of_them(logs, tmp_path):
    text = applog.build_bundle("it froze").files["report.txt"]
    for name in (applog.LOG_NAME, f"{applog.LOG_NAME}.1", applog.CRASH_NAME,
                 "model-check-1.json"):
        assert f"- {name}" in text, name
    for line in ("sub-07.edf", "second", "an older line", "Fatal Python error"):
        assert line not in text, line
    # Unticking the logs leaves no trace of what they name.
    kept = applog.build_bundle().only(["report.txt"])
    saved = _zip_texts(applog.write_bundle(kept, tmp_path / "plain.zip"))
    assert list(saved) == ["report.txt"]
    assert "sub-07" not in saved["report.txt"]


def test_the_old_entry_points_still_work(logs, tmp_path):
    assert applog.CRASH_NAME in applog.report_text()
    written = applog.write_report(tmp_path / "report")
    assert {"report.txt", applog.LOG_NAME, applog.CRASH_NAME} <= set(_zip_texts(written))


# -- the command line -----------------------------------------------------------------
def test_a_command_line_report_has_no_window_log_even_when_one_exists(logs):
    bundle = applog.build_bundle("a note", with_logs=False)
    assert list(bundle.files) == ["report.txt"]
    text = bundle.files["report.txt"]
    assert "a note" in text and "Versions and machine" in text
    assert "second" not in text and "lines of the log" not in text
    assert "Fatal Python error" not in text


def test_nothing_is_saved_unless_the_person_says_yes(logs, tmp_path, monkeypatch, capsys):
    out = tmp_path / "r.zip"
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert problemreport.main(["--note", "x", "--out", str(out)]) == 0
    assert not out.exists() and "Nothing was saved" in capsys.readouterr().out


def test_nothing_is_saved_when_there_is_nobody_to_ask(logs, tmp_path, monkeypatch, capsys):
    out = tmp_path / "r.zip"

    def no_terminal(*_):
        raise EOFError

    monkeypatch.setattr("builtins.input", no_terminal)
    assert problemreport.main(["--out", str(out)]) == 0
    assert not out.exists() and "Nothing was saved" in capsys.readouterr().out


def test_yes_saves_and_the_text_printed_first_is_the_text_saved(logs, tmp_path, capsys):
    out = tmp_path / "r.zip"
    assert problemreport.main(["--note", "stops at the figures", "--yes", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    saved = _zip_texts(out)
    assert list(saved) == ["report.txt"]
    assert saved["report.txt"] in printed               # shown in full before it was written
    assert "stops at the figures" in saved["report.txt"]
    assert "nothing has been sent" in printed


def test_a_yes_answer_at_the_prompt_saves(logs, tmp_path, monkeypatch):
    out = tmp_path / "r.zip"
    monkeypatch.setattr("builtins.input", lambda *_: "Y")
    assert problemreport.main(["--out", str(out)]) == 0
    assert out.exists()


def test_the_onset_hfo_subcommand_is_wired_to_it(logs, tmp_path):
    out = tmp_path / "via-cli.zip"
    assert cli.main(["report-problem", "--note", "wired", "--yes", "--out", str(out)]) == 0
    assert "wired" in _zip_texts(out)["report.txt"]


def test_end_to_end_as_a_user_would_run_it(tmp_path):
    """A real process, a real working directory: the default file name and the
    flags, with no test hooks in between."""
    env = dict(os.environ, ONSET_REVIEW_LOG_DIR=str(tmp_path / "logs"),
               PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    work = tmp_path / "work"
    work.mkdir()
    done = subprocess.run(
        [sys.executable, "-m", "onset_hfo.cli", "report-problem", "--note", "e2e", "--yes"],
        cwd=work, env=env, capture_output=True, text=True, timeout=120, input="")
    assert done.returncode == 0, done.stderr
    made = list(work.glob("onset-hfo-report-*.zip"))
    assert len(made) == 1
    assert "e2e" in _zip_texts(made[0])["report.txt"]
    assert "Saved to" in done.stdout


def test_declining_in_a_real_process_leaves_no_file(tmp_path):
    env = dict(os.environ, ONSET_REVIEW_LOG_DIR=str(tmp_path / "logs"),
               PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    work = tmp_path / "work"
    work.mkdir()
    done = subprocess.run(
        [sys.executable, "-m", "onset_hfo.cli", "report-problem", "--note", "e2e"],
        cwd=work, env=env, capture_output=True, text=True, timeout=120,
        input="n\n")
    assert done.returncode == 0, done.stderr
    assert list(work.iterdir()) == []
    assert "Nothing was saved" in done.stdout

