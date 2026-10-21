"""A case's ictal onset: marked seizures in, the index per channel out.

A synthetic recording with two seizures: fast activity starts on one contact
of lead LA a second after each marked onset and, weaker and later, on one
contact of lead LB. What has to hold: the case's marks give the seizures (an
onset and a seizure span starting with it are one; a clinical onset alone is
listed and left out); each is analysed through the case's own preprocessing
(its bad contact absent); the LA pair leads both seizures; the results are
written and read back; and the window runs it.
"""

from __future__ import annotations

import os

import mne
import numpy as np
import pandas as pd
import pytest

from onset_hfo.case import annotations as marks
from onset_hfo.case import bridges
from onset_hfo.case.model import Case

SF = 512.0
NAMES = [f"LA{i}" for i in range(1, 5)] + [f"LB{i}" for i in range(1, 5)]
ONSETS = (50.0, 150.0)


@pytest.fixture(scope="module")
def seizures_edf(tmp_path_factory):
    rng = np.random.default_rng(4)
    t = np.arange(int(200 * SF)) / SF
    data = rng.normal(0, 1.0, (len(NAMES), len(t)))
    data += 4.0 * np.sin(2 * np.pi * 6.0 * t + rng.uniform(0, 6, (len(NAMES), 1)))
    for onset in ONSETS:
        early = (t >= onset + 1.0) & (t < onset + 31.0)
        late = (t >= onset + 7.0) & (t < onset + 31.0)
        data[1, early] += 6.0 * np.sin(2 * np.pi * 40.0 * t[early])
        data[6, late] += 3.0 * np.sin(2 * np.pi * 40.0 * t[late])
    raw = mne.io.RawArray(data * 1e-5, mne.create_info(NAMES, SF, "seeg"), verbose="ERROR")
    path = tmp_path_factory.mktemp("edf") / "seizures.edf"
    mne.export.export_raw(path, raw, fmt="edf", overwrite=True, verbose="ERROR")
    return path


@pytest.fixture
def case(seizures_edf, tmp_path, monkeypatch):
    monkeypatch.setenv("ONSET_REVIEW_READS", str(tmp_path / "reads"))
    case = Case.create(tmp_path / "case", "P40")
    bridges.convert(seizures_edf, case, channel_types={n: "seeg" for n in NAMES}, bad=["LB4"])
    case.save_marks("01", pd.DataFrame([
        marks.new_mark(10.0, "seizure-clinical-onset"),
        marks.new_mark(ONSETS[0], "seizure-onset"),
        marks.new_mark(ONSETS[1], "seizure-onset"),
        marks.new_mark(ONSETS[1] + 2.0, "seizure", 40.0),
        marks.new_mark(ONSETS[1] + 8.0, "seizure-clinical-onset")]))
    return case


def test_the_marks_give_the_seizures(case):
    from onset_review.caseictal import seizures_of

    frame = seizures_of(case)
    assert list(frame["onset"]) == [10.0, *ONSETS]
    assert list(frame["usable"]) == [False, True, True]
    assert frame.loc[0, "marker"] == "clinical onset only"
    assert "electrographic onset" in frame.loc[0, "note"]


def test_each_seizure_is_analysed_and_combined(case):
    from onset_review.caseictal import latest_ictal, run_ictal

    result = run_ictal(case)
    assert result.n_analysed == 2
    assert set(result.combined["channel"].head(2)) == {"LA1-LA2", "LA2-LA3"}
    lead = result.combined.set_index("channel")
    assert (lead.loc[["LA1-LA2", "LA2-LA3"], "seizures_high"] == 2).all()
    assert not any("LB4" in ch for ch in lead.index), "the bad contact is left out"
    assert lead.loc["LA1-LA2", "median_change_s"] == pytest.approx(1.0, abs=1.0)
    assert {"LA1-LA2", "LA2-LA3"} <= set(result.consistent())
    assert lead.loc["LA3-LA4", "median_ei"] == 0.0
    assert result.statement().startswith("Over 2 seizure(s): LA")
    status = result.seizures.set_index("onset")["status"]
    assert status[ONSETS[0]] == "ok" and status[10.0].startswith("not analysed")
    for name in ("combined.tsv", "per_seizure.tsv", "seizures.tsv", "settings.json",
                 "summary.md"):
        assert (result.folder / name).exists(), name
    back = latest_ictal(case)
    assert back.folder == result.folder
    assert list(back.combined["channel"]) == list(result.combined["channel"])
    assert back.statement() == result.statement()
    assert case.log[-1]["action"] == "ran the ictal onset analysis"


def test_a_low_pass_below_the_fast_band_is_refused(case):
    import dataclasses

    from onset_hfo.config import PreprocessConfig
    from onset_review import caseinterictal as ci
    from onset_review.caseictal import run_ictal

    ci.save_template(case, dataclasses.replace(
        ci.template_for(case), preprocess=PreprocessConfig(lowpass=60.0)))
    result = run_ictal(case)
    assert result.n_analysed == 0 and result.statement() == "No seizure could be analysed."
    assert result.seizures["status"].str.contains("low-pass at 60 Hz").sum() == 2


@pytest.fixture(scope="module")
def qapp():
    widgets = pytest.importorskip("qtpy.QtWidgets", reason="the review extra is not installed")
    pytest.importorskip("mne_qt_browser", reason="the review extra is not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    yield widgets.QApplication.instance() or widgets.QApplication([])


def test_the_window_runs_the_ictal_step(qapp, case):
    from onset_review.casewindow import CaseWindow

    window = CaseWindow(case, reader="dr test")
    try:
        assert window.show_step("ictal")
        page = window.ictal_page
        assert page.what.text().startswith("3 seizure(s) marked, 2 with")
        assert page.seizures.rowCount() == 3
        assert page.seizures.item(0, 4).text().startswith("left out")
        page.run(wait=True)
        assert page.result is not None and page.result.n_analysed == 2
        assert page.statement.text().startswith("Over 2 seizure(s)")
        assert page.table.rowCount() == len(page.result.combined)
        assert page.seizures.item(1, 4).text() == "analysed"
        page.done_button.click()
        assert case.step_done("ictal")
    finally:
        window.close()


# -- how each seizure spread -----------------------------------------------------------------
def test_each_seizure_keeps_its_curves_and_the_order_follows_the_signal(case):
    from onset_review import ictalprogression
    from onset_review.caseictal import latest_ictal, run_ictal

    run_ictal(case)
    result = latest_ictal(case)
    seizures = result.analysed_seizures()
    assert len(seizures) == 2
    for seizure in seizures:
        prog = result.progression(seizure)
        assert prog is not None
        assert prog.ratio.shape == (len(prog.channels), len(prog.times))
        assert prog.times[0] < 0 < prog.times[-1], "from before the onset to after it"
        order = ictalprogression.order_table(prog)
        changed = list(order.loc[order["detected"], "channel"])
        # LA's activity starts a second after the onset, LB's seven.
        assert changed[0].startswith("LA")
        la = [c for c in changed if c.startswith("LA")]
        lb = [c for c in changed if c.startswith("LB")]
        assert la and all(changed.index(a) < changed.index(b) for a in la for b in lb)
        first = order.iloc[0]
        assert first["delay_s"] == 0.0 and first["change_s"] == pytest.approx(1.0, abs=1.0)
        early = ictalprogression.state_at(prog, -5.0).set_index("channel")
        late = ictalprogression.state_at(prog, 10.0).set_index("channel")
        assert not early["changed"].any()
        assert late.loc[changed[0], "changed"]
        assert late.loc[changed[0], "log_ratio"] > early.loc[changed[0], "log_ratio"]


def test_the_heatmap_and_map_are_drawn_without_a_display(case, tmp_path):
    from matplotlib.figure import Figure

    from onset_review import ictalprogression
    from onset_review.caseictal import run_ictal

    result = run_ictal(case)
    prog = result.progression(result.analysed_seizures()[0])
    figure = Figure()
    drawn = ictalprogression.draw(figure, prog, 2.0)
    assert drawn["channels"][0].startswith("LA") and drawn["map"] is False
    positions = __import__("pandas").DataFrame({
        "channel": list(prog.channels), "x": range(len(prog.channels)),
        "y": [0.0] * len(prog.channels), "placed": True})
    drawn = ictalprogression.draw(figure, prog, 2.0, positions, zone={prog.channels[0]})
    assert drawn["map"] is True
    figure.savefig(tmp_path / "progression.png")
    assert (tmp_path / "progression.png").stat().st_size > 0


def test_a_run_from_before_the_curves_were_kept_says_so(case):
    import shutil

    from onset_review.caseictal import run_ictal

    result = run_ictal(case)
    shutil.rmtree(result.folder / "progression")
    assert result.progression(result.analysed_seizures()[0]) is None


def test_the_window_shows_the_progression_with_a_slider_and_play(qapp, case):
    from onset_review.casewindow import CaseWindow

    window = CaseWindow(case, reader="dr test")
    try:
        window.show_step("ictal")
        page = window.ictal_page
        page.run(wait=True)
        view = page.progression
        assert [page.views.tabText(i) for i in range(page.views.count())] == [
            "Index", "Progression"]
        assert view.seizure.count() == 2
        assert view.order.rowCount() > 0 and view.order.item(0, 1).text().startswith("LA")
        assert view.moment() == pytest.approx(0.0, abs=0.3), "starts at the marked onset"
        view.slider.setValue(view.slider.maximum())
        assert view.at.text().startswith("+")
        view.slider.setValue(0)
        view.play.setChecked(True)
        view._tick()
        assert view.slider.value() > 0
        view.play.setChecked(False)
        view.seizure.setCurrentIndex(1)
        assert view.prog is not None and view.order.rowCount() > 0
    finally:
        window.close()
