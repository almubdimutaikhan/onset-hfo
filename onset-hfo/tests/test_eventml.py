"""The learned second stage for HFO candidates: scoring, splits and protocols.

Offline and synthetic: the cohort numbers come from ``python -m
onset_hfo.eventml`` on the cached ds003498 slices and are committed under
``data/eventml/``. What is pinned here is what those numbers rest on:

* precision is counted over selected candidates and recall over expert
  events, exactly as the benchmark counts them, so a candidate pair matching
  one expert event finds it once;
* the subject-specific protocol never trains on the window it scores, and the
  learning curve never tests on anything before its last judged candidate;
* leave-one-patient-out never trains on the patient it scores;
* a learnable signal is learned, and an unlearnable one is not claimed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from onset_hfo import eventml  # noqa: E402


@pytest.fixture(autouse=True)
def _small_model(monkeypatch):
    """The protocols fit hundreds of models; a few trees each is enough to
    test them, and keeps this file to seconds rather than minutes."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    monkeypatch.setattr(eventml, "_model", lambda seed=0: HistGradientBoostingClassifier(
        max_depth=2, max_iter=15, class_weight="balanced", random_state=seed))


def _cohort(n_subjects: int = 3, per_window: int = 40, signal: float = 2.5,
            seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Candidates whose label shows in `spectral_prominence_db` by `signal`
    standard deviations; the rule accepts at random, so it carries nothing."""
    rng = np.random.default_rng(seed)
    cands, refs = [], []
    for s in range(n_subjects):
        subject = f"sub-{s:02d}"
        for w0, w1 in eventml.WINDOWS:
            starts = np.sort(rng.uniform(w0, w1 - 0.2, per_window))
            label = rng.random(per_window) < 0.4
            for i, (t, y) in enumerate(zip(starts, label, strict=True)):
                eid = f"{subject}:{w0:g}:{i}" if y else ""
                cands.append({
                    "subject": subject, "band": "ripple", "window_start": w0,
                    "channel": "A1-A2", "start": t, "stop": t + 0.03,
                    "score": 1.0 + rng.random() * 2, "duration_ms": 30.0,
                    "peak_amplitude_uv": 20 + rng.normal(), "peak_frequency_hz": 120.0,
                    "spectral_prominence_db": rng.normal(signal * y, 1.0),
                    "n_peaks": 6, "n_cycles": 4.0, "low_band_sd": 2.0,
                    "rel_amplitude": 1.0, "channel_candidates_per_min": per_window,
                    "rule_accepted": bool(rng.random() < 0.6), "label": int(y),
                    "expert_ids": eid})
                if y:
                    refs.append({"subject": subject, "band": "ripple", "window_start": w0,
                                 "kind": "expert", "start": t, "channel": "A1-A2",
                                 "expert_ids": eid})
            # Expert events no candidate found: they count against recall.
            for j in range(5):
                refs.append({"subject": subject, "band": "ripple", "window_start": w0,
                             "kind": "expert", "start": w0 + 10 * j + 1, "channel": "A1-A2",
                             "expert_ids": f"{subject}:{w0:g}:missed{j}"})
    cand = pd.DataFrame(cands)
    rules = cand[cand["rule_accepted"]].assign(kind="rule")[
        ["subject", "band", "window_start", "kind", "start", "channel", "expert_ids"]]
    return cand, pd.concat([pd.DataFrame(refs), rules], ignore_index=True)


def test_precision_counts_detections_and_recall_counts_expert_events():
    experts = pd.DataFrame({"expert_ids": ["e1", "e2", "e3", "e4"]})
    selected = pd.DataFrame({"expert_ids": ["e1", "e1", "e2", "", None]})
    score = eventml.score_selection(selected, experts)
    # Two candidates on e1 are two true detections but one found event.
    assert (score.n_selected, score.n_true, score.n_found) == (5, 3, 2)
    assert score.precision == pytest.approx(0.6) and score.recall == pytest.approx(0.5)
    assert score.f1 == pytest.approx(2 * 0.6 * 0.5 / 1.1)
    assert eventml.score_selection(selected.iloc[0:0], experts).f1 == 0.0


def test_subject_specific_never_trains_on_the_window_it_scores(monkeypatch):
    cands, ref = _cohort(n_subjects=1)
    experts = ref[ref["kind"] == "expert"]
    seen = []
    real_fit = eventml._fit

    def spy(train, seed=0):
        seen.append(set(train["window_start"]))
        return real_fit(train, seed)

    monkeypatch.setattr(eventml, "_fit", spy)
    eventml._lowo_predictions(cands, experts)
    # Each outer fit leaves out one window; each inner fit leaves out two.
    outer = [w for w in seen if len(w) == 4]
    assert len(outer) == 5
    assert {next(iter(set(cands["window_start"]) - w)) for w in outer} == \
        set(cands["window_start"])
    assert all(len(w) in (3, 4) for w in seen)


def test_leave_one_patient_out_never_trains_on_the_patient_it_scores(monkeypatch):
    cands, ref = _cohort(n_subjects=4)
    experts = ref[ref["kind"] == "expert"]
    seen = []
    real_fit = eventml._fit

    def spy(train, seed=0):
        seen.append(set(train["subject"]))
        return real_fit(train, seed)

    monkeypatch.setattr(eventml, "_fit", spy)
    subjects = sorted(cands["subject"].unique())
    eventml._lopo_predictions(cands, experts, subjects, folds=3)
    outer = [s for s in seen if len(s) == 3]
    assert {next(iter(set(subjects) - s)) for s in outer} == set(subjects)


def test_the_learning_curve_tests_only_after_the_last_judged_candidate(monkeypatch):
    cands, ref = _cohort(n_subjects=1)
    experts, rules = ref[ref["kind"] == "expert"], ref[ref["kind"] == "rule"]
    calls = []
    real = eventml.score_selection

    def spy(selected, experts_):
        calls.append((selected, experts_))
        return real(selected, experts_)

    monkeypatch.setattr(eventml, "score_selection", spy)
    rows = eventml._learning_curve(cands, experts, rules, "sub-00", "ripple")
    assert [r["budget"] for r in rows] == [b for b in eventml.BUDGETS if b < len(cands)]
    ordered = cands.sort_values("start")
    for row in rows:
        boundary = float(ordered.iloc[:row["budget"]]["stop"].max())
        assert row["test_seconds"] == round(300.0 - boundary, 1)
    # Every scored selection and expert span lies after some boundary (the
    # tuned cut is chosen on the judged span, before it, and is not scored).
    for selected, experts_ in calls:
        if len(experts_) and len(selected) and experts_["start"].min() > 0:
            assert selected["start"].min() > 0


def test_a_learnable_signal_is_learned_and_beats_a_rule_that_carries_none():
    cands, ref = _cohort(n_subjects=3, signal=3.0)
    result = eventml.evaluate(cands, ref, out=__import__("pathlib").Path(
        __import__("tempfile").mkdtemp()), verbose=False)
    summary = result["summary"].set_index("method")
    assert set(summary.index) == {
        "rule (best threshold)", "rule on the candidates", "all candidates",
        "threshold tuned per subject (leave one window out)",
        "subject-specific (leave one window out)", "leave one patient out"}
    learned = summary.loc["subject-specific (leave one window out)"]
    assert learned["f1"] > summary.loc["rule (best threshold)", "f1"] + 0.1
    assert learned["f1_minus_tuned"] > 0
    assert summary.loc["leave one patient out", "f1"] > summary.loc["all candidates", "f1"]
    curve = result["curve"]
    assert list(curve["budget"]) == sorted(curve["budget"])


def test_nothing_to_learn_is_not_reported_as_a_gain():
    cands, ref = _cohort(n_subjects=3, signal=0.0, seed=3)
    summary = eventml.evaluate(cands, ref, out=__import__("pathlib").Path(
        __import__("tempfile").mkdtemp()), verbose=False)["summary"].set_index("method")
    row = summary.loc["subject-specific (leave one window out)"]
    # With no signal the interval of the gain over keeping every candidate
    # must not exclude zero in the model's favour by much.
    assert row["f1"] <= summary.loc["all candidates", "f1"] + 0.05
