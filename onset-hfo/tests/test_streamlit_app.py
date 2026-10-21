"""The no-install demo (app/): every page opens, headless, on a fresh clone.

The site is a Streamlit app that reads the committed results and the example
analysis. It has no logic of its own: what it shows comes from
`onset_review.studytables`, which `test_studytables.py` checks without
Streamlit. What this file adds is that each page *runs* -- a renamed function
or a moved table would otherwise surface only on the hosted demo.

Skipped without the `app` extra; CI installs it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="the app extra is not installed")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = [APP / "Home.py"] + sorted((APP / "pages").glob("[0-9]_*.py"))


def test_the_demo_has_its_home_and_nine_pages():
    assert [p.name for p in PAGES] == [
        "Home.py", "1_Recording.py", "2_Report.py", "3_Assistant.py", "4_Detectors.py",
        "5_Outcome.py", "6_Patients.py", "7_Data.py", "8_Architecture.py",
        "9_Research.py"]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_every_page_opens_without_an_exception(page):
    at = AppTest.from_file(str(page), default_timeout=180).run()
    assert not at.exception, [e.value for e in at.exception]


def test_every_page_carries_the_research_tool_disclaimer():
    from onset_review.studytables import DISCLAIMER_LEAD

    for page in PAGES:
        at = AppTest.from_file(str(page), default_timeout=180).run()
        shown = " ".join(str(m.value) for m in at.markdown) + " ".join(
            str(m.value) for m in at.sidebar.markdown)
        assert DISCLAIMER_LEAD in shown, page.name


def test_the_assistant_page_says_the_demo_runs_without_a_model():
    at = AppTest.from_file(str(APP / "pages" / "3_Assistant.py"), default_timeout=180).run()
    assert not at.exception
    assert any("runs without a language model" in str(i.value) for i in at.info)


def test_the_pages_read_the_shared_study_tables_not_a_copy():
    assert not (APP / "panels.py").exists()
    for page in [*PAGES, APP / "common.py", APP / "signal.py"]:
        assert "from app import panels" not in page.read_text(encoding="utf-8"), page.name
