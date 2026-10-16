"""A learned second stage for HFO candidates, against the rules it would replace.

Step one of the deep-learning plan: before any network, does a model fitted
on the measurements the detectors already make -- score, duration, peak
frequency, amplitude, the in-band peak's prominence, cycles, the 1-30 Hz
deflection -- tell expert-marked events from the rest better than the
hand-written validation rules do? If a gradient-boosted model on these
features cannot, a convolutional network on the same windows has little to
work with; if it can, the margin is the bar a network has to clear.

    python -m onset_hfo.eventml candidates     # the candidate table (offline, cached slices)
    python -m onset_hfo.eventml evaluate       # every protocol below, with intervals

**The candidates.** RMS at a low threshold on the channels the annotators
reviewed, every cached 60-s window of ``ds003498`` run-01 (300 s per subject).
Each candidate is labelled 1 when it overlaps an expert-marked event of the
same band on the same channel within 20 ms -- the matching rule of
:func:`onset_hfo.evaluate.evaluate_detections` -- and keeps which expert
events it matched, so recall can be counted over expert events exactly as the
benchmark counts it, not over candidates.

**Two questions, two protocols.**

* *Subject-specific*: does it work once the reader has judged some of this
  patient's events? Trained on one patient only, and split **by time**, never
  at random: neighbouring candidates overlap and the same oscillation is often
  detected twice, so a random split puts near-copies on both sides. Two
  splits: leave-one-window-out over the five minutes, and a learning curve --
  train on the first N candidates in time order (what a reader has judged
  after N verdicts), test on everything after the last of them.
* *Leave-one-patient-out*: does it work on a patient with no labels at all?
  Trained on the other nineteen.

**The baselines.** The rules as shipped, at the operating point that agreed
best with the experts on this cohort (RMS 1.5 SD for ripples, 3.5 SD for fast
ripples; ``data/benchmark/agreement_sweep.csv``), scored on the same span. A
learned stage that beats chance but loses to them has established nothing.

**What the labels are.** The markings are the source study's Morphology
detector's events as a human validated them, not a census of every
oscillation. "Agreement with the experts" is what is measured, here as in
``docs/EVALUATION.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from onset_hfo.config import BANDS, RESULTS_DIR, DetectorConfig

__all__ = ["FEATURES", "CANDIDATE_SD", "RULE_SD", "build_candidates", "evaluate",
           "score_selection"]

DATASET = "ds003498"
RUN = "01"
WINDOWS = ((0.0, 60.0), (60.0, 120.0), (120.0, 180.0), (180.0, 240.0), (240.0, 300.0))
DETECTOR = "rms"
TOLERANCE_S = 0.02

#: Where the candidates are drawn: low enough that a second stage has recall
#: to recover, no lower than the rule's own best operating point.
CANDIDATE_SD = {"ripple": 1.5, "fast_ripple": 2.5}
#: The rule baseline: RMS + the validation rules at the threshold with the
#: highest event F1 against the experts on this cohort (agreement_sweep.csv).
RULE_SD = {"ripple": 1.5, "fast_ripple": 3.5}

#: The measurements the model sees. All exist for every candidate before the
#: validation rules run; none involves the label.
FEATURES = ("score", "duration_ms", "peak_amplitude_uv", "peak_frequency_hz",
            "spectral_prominence_db", "n_peaks", "n_cycles", "low_band_sd",
            "rel_amplitude", "channel_candidates_per_min")

#: Label budgets for the learning curve: verdicts a reader has given.
BUDGETS = (25, 50, 100, 200, 400)
OUT = RESULTS_DIR / "eventml"


# -- the candidate table -----------------------------------------------------

def _window_candidates(subject: str, t_start: float, t_stop: float, band_name: str,
                       verbose: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Candidates and the expert events of one window, one band."""
    from onset_hfo.datasets import fetch_slice
    from onset_hfo.detectors import HFO_DETECTORS
    from onset_hfo.detectors.base import bandpass, robust_scale
    from onset_hfo.evaluate import _overlapping
    from onset_hfo.preprocess import prepare
    from onset_hfo.validate import validate_events

    recording = fetch_slice(dataset=DATASET, subject=subject, run=RUN, t_start=t_start,
                            t_stop=t_stop, verbose=verbose)
    truth = recording.ground_truth
    prep = prepare(recording, verbose=False)
    reviewed = [c for c in recording.reviewed_channels if c in prep.ch_names]
    band = getattr(BANDS, band_name)
    if not reviewed or truth is None or not BANDS.usable(prep.sfreq, band):
        return pd.DataFrame(), pd.DataFrame()
    experts = truth[(truth["kind"] == band_name) & truth["channel"].isin(reviewed)] \
        .reset_index(drop=True)
    experts = experts.assign(expert_id=[f"{subject}:{t_start:g}:{i}" for i in range(len(experts))])

    cfg = DetectorConfig(band=band, threshold_sd=CANDIDATE_SD[band_name])
    events = HFO_DETECTORS[DETECTOR](prep, cfg, channels=reviewed)
    validate_events(events, prep)

    # The input of the 1-30 Hz rule, as a number rather than a yes/no.
    idx = [prep.ch_names.index(c) for c in reviewed]
    low = bandpass(prep.data[idx], prep.sfreq, BANDS.low)
    _, scale = robust_scale(low)
    low_rows = dict(zip(reviewed, low, strict=True))
    low_scale = dict(zip(reviewed, scale.ravel(), strict=True))

    rows = []
    for e in events:
        i0 = max(0, int(round((e.start - prep.t_offset) * prep.sfreq)))
        i1 = max(i0 + 1, int(round((e.stop - prep.t_offset) * prep.sfreq)))
        segment = low_rows[e.channel][i0:i1]
        hits = _overlapping(experts, e, {e.channel}, TOLERANCE_S)
        rows.append({
            "subject": subject, "band": band_name, "window_start": t_start,
            "channel": e.channel, "start": float(e.start), "stop": float(e.stop),
            "score": float(e.score), "duration_ms": float(e.duration_ms),
            "peak_amplitude_uv": float(e.peak_amplitude_uv),
            "peak_frequency_hz": float(e.peak_frequency_hz),
            "spectral_prominence_db": float(e.spectral_prominence_db),
            "n_peaks": int(e.n_peaks), "n_cycles": float(e.n_cycles),
            "low_band_sd": (float(np.max(np.abs(segment)) / low_scale[e.channel])
                            if segment.size and low_scale[e.channel] > 0 else float("nan")),
            "rule_accepted": bool(e.accepted),
            "label": int(bool(hits)),
            "expert_ids": ";".join(experts["expert_id"].iloc[hits]),
        })
    frame = pd.DataFrame(rows)
    if len(frame):
        # Context from the same window, unlabelled and so available at test
        # time: how this candidate compares with its channel's others.
        by_channel = frame.groupby("channel")["peak_amplitude_uv"].transform("median")
        frame["rel_amplitude"] = frame["peak_amplitude_uv"] / by_channel.replace(0, np.nan)
        frame["channel_candidates_per_min"] = (
            frame.groupby("channel")["start"].transform("size") / ((t_stop - t_start) / 60.0))

    # The rule baseline at its own best threshold, on the same window.
    rule_cfg = DetectorConfig(band=band, threshold_sd=RULE_SD[band_name])
    rule_events = HFO_DETECTORS[DETECTOR](prep, rule_cfg, channels=reviewed)
    validate_events(rule_events, prep)
    rule_rows = [{"subject": subject, "band": band_name, "window_start": t_start,
                  "kind": "rule", "start": float(e.start), "channel": e.channel,
                  "expert_ids": ";".join(experts["expert_id"].iloc[
                      _overlapping(experts, e, {e.channel}, TOLERANCE_S)])}
                 for e in rule_events if e.accepted]
    expert_rows = [{"subject": subject, "band": band_name, "window_start": t_start,
                    "kind": "expert", "start": float(r.start), "channel": r.channel,
                    "expert_ids": r.expert_id} for r in experts.itertuples()]
    return frame, pd.DataFrame(rule_rows + expert_rows)


def cached_subjects() -> list[str]:
    """The subjects with all five windows on this machine; the archive's own
    list when none are (which needs the network)."""
    from onset_hfo.config import DATA_CACHE
    from onset_hfo.datasets import list_subjects

    root = DATA_CACHE / DATASET
    found = sorted({d.name.split("_")[0] for d in root.glob("sub-*_run-01_*")}) \
        if root.exists() else []
    complete = [s for s in found
                if all((root / f"{s}_run-{RUN}_{a:g}-{b:g}s").exists() for a, b in WINDOWS)]
    return complete or list_subjects(DATASET)


def build_candidates(subjects: list[str] | None = None, bands=("ripple", "fast_ripple"),
                     out: Path = OUT, verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The candidate table and the reference table (expert events and the
    rule's accepted events), for every subject and window; written to `out`."""
    subjects = subjects or cached_subjects()
    candidates, reference = [], []
    for subject in subjects:
        for t_start, t_stop in WINDOWS:
            for band_name in bands:
                frame, ref = _window_candidates(subject, t_start, t_stop, band_name)
                candidates.append(frame)
                reference.append(ref)
        if verbose:
            done = pd.concat(candidates, ignore_index=True)
            mine = done[done["subject"] == subject] if len(done) else done
            print(f"[eventml] {subject}: {len(mine)} candidates, "
                  f"{int(mine['label'].sum()) if len(mine) else 0} expert-matched", flush=True)
    candidates = pd.concat([c for c in candidates if len(c)], ignore_index=True)
    reference = pd.concat([r for r in reference if len(r)], ignore_index=True)
    out.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(out / "candidates.csv", index=False)
    reference.to_csv(out / "reference.csv", index=False)
    return candidates, reference


# -- scoring a selection against the experts ----------------------------------

@dataclass
class Score:
    n_selected: int
    n_true: int          # selected candidates that match an expert event
    n_expert: int
    n_found: int         # expert events matched by at least one selected candidate

    @property
    def precision(self) -> float:
        return self.n_true / self.n_selected if self.n_selected else float("nan")

    @property
    def recall(self) -> float:
        return self.n_found / self.n_expert if self.n_expert else float("nan")

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if not (np.isfinite(p) and np.isfinite(r)) or p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)


def score_selection(selected: pd.DataFrame, experts: pd.DataFrame) -> Score:
    """Precision and recall of `selected` (rows with ``expert_ids``) against
    the expert events, counted as `evaluate_detections` counts them:
    precision over detections, recall over expert events."""
    ids = selected["expert_ids"].fillna("").astype(str)
    matched = ids[ids != ""]
    found = set(matched.str.split(";").explode()) - {""} if len(matched) else set()
    return Score(len(selected), int(len(matched)), len(experts),
                 len(found & set(experts["expert_ids"])))


# -- the model ----------------------------------------------------------------

def _model(seed: int = 0):
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.08, max_iter=200,
                                          l2_regularization=1.0, class_weight="balanced",
                                          random_state=seed)


def _fit(train: pd.DataFrame, seed: int = 0):
    from threadpoolctl import threadpool_limits

    if train["label"].nunique() < 2:
        return None
    model = _model(seed)
    # One thread: the protocols fit hundreds of small models, and OpenMP's
    # start-up and contention cost far more than the work (118 s against
    # 4.8 s for the same evaluation on four cores, measured).
    with threadpool_limits(1):
        model.fit(train[list(FEATURES)].to_numpy(float), train["label"].to_numpy(int))
    return model


def _predict(model, frame: pd.DataFrame) -> np.ndarray:
    from threadpoolctl import threadpool_limits

    if model is None or not len(frame):
        return np.zeros(len(frame))
    with threadpool_limits(1):
        return model.predict_proba(frame[list(FEATURES)].to_numpy(float))[:, 1]


def _best_threshold(prob: np.ndarray, frame: pd.DataFrame, experts: pd.DataFrame) -> float:
    """The probability cut with the highest F1 against `experts`, on data the
    held-out set never sees."""
    best, best_f1 = 0.5, -1.0
    for cut in np.linspace(0.05, 0.95, 19):
        f1 = score_selection(frame[prob >= cut], experts).f1
        if f1 > best_f1:
            best, best_f1 = float(cut), f1
    return best


# -- the protocols ------------------------------------------------------------

def _split(reference: pd.DataFrame):
    experts = reference[reference["kind"] == "expert"]
    rules = reference[reference["kind"] == "rule"]
    return experts, rules


def _lowo_predictions(cands: pd.DataFrame, experts: pd.DataFrame) -> pd.Series:
    """Subject-specific, leave-one-window-out: each window scored by a model
    fitted on the subject's other windows, cut at the threshold that worked
    best on those other windows (chosen by an inner leave-one-window-out)."""
    selected = pd.Series(False, index=cands.index)
    windows = sorted(cands["window_start"].unique())
    for held in windows:
        train = cands[cands["window_start"] != held]
        test = cands[cands["window_start"] == held]
        model = _fit(train)
        if model is None:
            continue
        inner_prob = np.zeros(len(train))
        for inner in sorted(train["window_start"].unique()):
            fit_on = train["window_start"] != inner
            inner_model = _fit(train[fit_on])
            mask = (train["window_start"] == inner).to_numpy()
            inner_prob[mask] = _predict(inner_model, train[~fit_on])
        cut = _best_threshold(inner_prob, train,
                              experts[experts["window_start"] != held])
        selected.loc[test.index] = _predict(model, test) >= cut
    return selected


#: Cuts on the candidate score (its peak over the candidate threshold, so 2.0
#: is roughly twice the candidate threshold) for the threshold-only baseline.
SCORE_CUTS = tuple(np.round(np.arange(1.0, 4.01, 0.1), 2))


def _best_score_cut(frame: pd.DataFrame, experts: pd.DataFrame) -> float:
    best, best_f1 = 1.0, -1.0
    kept = frame[frame["rule_accepted"]]
    for cut in SCORE_CUTS:
        f1 = score_selection(kept[kept["score"] >= cut], experts).f1
        if f1 > best_f1:
            best, best_f1 = float(cut), f1
    return best


def _lowo_threshold_only(cands: pd.DataFrame, experts: pd.DataFrame) -> pd.Series:
    """The rules as shipped, with only the detection threshold tuned for this
    patient on the other windows. What a per-patient model has to beat to
    show that its features, not just a per-patient threshold, did the work."""
    selected = pd.Series(False, index=cands.index)
    for held in sorted(cands["window_start"].unique()):
        train = cands[cands["window_start"] != held]
        test = cands[cands["window_start"] == held]
        cut = _best_score_cut(train, experts[experts["window_start"] != held])
        selected.loc[test.index] = test["rule_accepted"] & (test["score"] >= cut)
    return selected


def _lopo_predictions(cands: pd.DataFrame, experts: pd.DataFrame, subjects: list[str],
                      folds: int = 5) -> pd.Series:
    """Leave-one-patient-out: each patient scored by a model fitted on the
    others, cut at the threshold that worked best across them (chosen by a
    grouped inner cross-validation over the training patients)."""
    selected = pd.Series(False, index=cands.index)
    for held in subjects:
        train = cands[cands["subject"] != held]
        test = cands[cands["subject"] == held]
        if not len(test):
            continue
        others = sorted(train["subject"].unique())
        inner_prob = np.zeros(len(train))
        for k in range(folds):
            group = set(others[k::folds])
            fit_on = ~train["subject"].isin(group)
            inner_prob[(~fit_on).to_numpy()] = _predict(_fit(train[fit_on]), train[~fit_on])
        cut = _best_threshold(inner_prob, train, experts[experts["subject"] != held])
        selected.loc[test.index] = _predict(_fit(train), test) >= cut
    return selected


def _learning_curve(cands: pd.DataFrame, experts: pd.DataFrame, rules: pd.DataFrame,
                    subject: str, band: str) -> list[dict]:
    """Train on the first N candidates in time order (the reader's first N
    verdicts), test on everything that starts after the last of them; the
    rule is scored on the same remaining span. With so few labels there is
    no held-out data to tune a cut on, so the cut is 0.5 on a class-balanced
    model -- a choice made in advance, not on the test span."""
    ordered = cands.sort_values("start")
    rows = []
    for budget in BUDGETS:
        if budget >= len(ordered):
            break
        train = ordered.iloc[:budget]
        boundary = float(train["stop"].max())
        test = ordered[ordered["start"] > boundary]
        span_experts = experts[experts["start"] > boundary]
        span_rule = rules[rules["start"] > boundary]
        model = _fit(train)
        if model is None or not len(span_experts):
            continue
        learned = score_selection(test[_predict(model, test) >= 0.5], span_experts)
        rule = score_selection(span_rule, span_experts)
        # The same verdicts spent on the threshold alone: the cut that best
        # matches the experts on the judged span, applied after it.
        cut = _best_score_cut(train, experts[experts["start"] <= boundary])
        tuned = score_selection(test[test["rule_accepted"] & (test["score"] >= cut)],
                                span_experts)
        rows.append({"subject": subject, "band": band, "budget": budget,
                     "positives_in_budget": int(train["label"].sum()),
                     "test_seconds": round(300.0 - boundary, 1),
                     "learned_f1": learned.f1, "rule_f1": rule.f1,
                     "tuned_threshold_f1": tuned.f1,
                     "learned_precision": learned.precision, "learned_recall": learned.recall,
                     "rule_precision": rule.precision, "rule_recall": rule.recall})
    return rows


def _bootstrap_mean(values: np.ndarray, n: int = 5000, seed: int = 0) -> tuple[float, float]:
    """Percentile 95% interval of the mean, resampling subjects."""
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n, len(values)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def evaluate(candidates: pd.DataFrame, reference: pd.DataFrame,
             out: Path = OUT, verbose: bool = True) -> dict:
    """Every protocol, per subject and band, with intervals over subjects."""
    experts_all, rules_all = _split(reference)
    per_subject, curve = [], []
    for band in sorted(candidates["band"].unique()):
        cands = candidates[candidates["band"] == band]
        experts_b = experts_all[experts_all["band"] == band]
        rules_b = rules_all[rules_all["band"] == band]
        subjects = sorted(cands["subject"].unique())
        if verbose:
            print(f"[eventml] {band}: leave one patient out over {len(subjects)} patients",
                  flush=True)
        lopo = _lopo_predictions(cands, experts_b, subjects)
        for subject in subjects:
            if verbose:
                print(f"[eventml] {band}: {subject}, subject-specific", flush=True)
            mine = cands[cands["subject"] == subject]
            ex = experts_b[experts_b["subject"] == subject]
            if not len(ex):
                continue
            lowo = _lowo_predictions(mine, ex)
            tuned = _lowo_threshold_only(mine, ex)
            methods = {
                "rule (best threshold)": rules_b[rules_b["subject"] == subject],
                "rule on the candidates": mine[mine["rule_accepted"]],
                "all candidates": mine,
                "threshold tuned per subject (leave one window out)":
                    mine[tuned.loc[mine.index]],
                "subject-specific (leave one window out)": mine[lowo.loc[mine.index]],
                "leave one patient out": mine[lopo.loc[mine.index]],
            }
            for method, selected in methods.items():
                s = score_selection(selected, ex)
                per_subject.append({"subject": subject, "band": band, "method": method,
                                    "n_expert": s.n_expert, "n_selected": s.n_selected,
                                    "precision": s.precision, "recall": s.recall, "f1": s.f1,
                                    "positives": int(mine["label"].sum()),
                                    "candidates": len(mine)})
            curve += _learning_curve(mine, ex, rules_b[rules_b["subject"] == subject],
                                     subject, band)
    per_subject = pd.DataFrame(per_subject)
    curve = pd.DataFrame(curve)

    summary = []
    for (band, method), rows in per_subject.groupby(["band", "method"], sort=False):
        rule = per_subject[(per_subject["band"] == band)
                           & (per_subject["method"] == "rule (best threshold)")]
        tuned = per_subject[(per_subject["band"] == band) & (
            per_subject["method"] == "threshold tuned per subject (leave one window out)")]
        paired = rows.set_index("subject")["f1"] - rule.set_index("subject")["f1"]
        vs_tuned = rows.set_index("subject")["f1"] - tuned.set_index("subject")["f1"]
        low, high = _bootstrap_mean(rows["f1"].to_numpy())
        dlow, dhigh = _bootstrap_mean(paired.to_numpy())
        tlow, thigh = _bootstrap_mean(vs_tuned.to_numpy())
        summary.append({"band": band, "method": method, "subjects": len(rows),
                        "f1": rows["f1"].mean(), "f1_ci_low": low, "f1_ci_high": high,
                        "precision": rows["precision"].mean(), "recall": rows["recall"].mean(),
                        "f1_minus_rule": paired.mean(), "diff_ci_low": dlow,
                        "diff_ci_high": dhigh,
                        "subjects_better_than_rule": int((paired > 0).sum()),
                        "f1_minus_tuned": vs_tuned.mean(), "vs_tuned_ci_low": tlow,
                        "vs_tuned_ci_high": thigh})
    summary = pd.DataFrame(summary)
    curve_summary = pd.DataFrame()
    if len(curve):
        rows = []
        for (band, budget), g in curve.groupby(["band", "budget"]):
            diff = (g["learned_f1"] - g["rule_f1"]).to_numpy()
            low, high = _bootstrap_mean(diff)
            vs_tuned = (g["learned_f1"] - g["tuned_threshold_f1"]).to_numpy()
            tlow, thigh = _bootstrap_mean(vs_tuned)
            rows.append({"band": band, "budget": budget, "subjects": len(g),
                         "learned_f1": g["learned_f1"].mean(), "rule_f1": g["rule_f1"].mean(),
                         "tuned_threshold_f1": g["tuned_threshold_f1"].mean(),
                         "f1_minus_rule": diff.mean(), "diff_ci_low": low, "diff_ci_high": high,
                         "f1_minus_tuned": vs_tuned.mean(), "vs_tuned_ci_low": tlow,
                         "vs_tuned_ci_high": thigh,
                         "subjects_better_than_rule": int((diff > 0).sum()),
                         "median_positives_in_budget": float(g["positives_in_budget"].median())})
        curve_summary = pd.DataFrame(rows)

    out.mkdir(parents=True, exist_ok=True)
    per_subject.to_csv(out / "per_subject.csv", index=False)
    summary.to_csv(out / "summary.csv", index=False)
    curve.to_csv(out / "learning_curve_per_subject.csv", index=False)
    curve_summary.to_csv(out / "learning_curve.csv", index=False)
    if verbose:
        with pd.option_context("display.width", 200, "display.max_columns", 20):
            print(summary.round(3).to_string(index=False))
            if len(curve_summary):
                print()
                print(curve_summary.round(3).to_string(index=False))
    return {"summary": summary, "per_subject": per_subject, "curve": curve_summary}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m onset_hfo.eventml",
                                     description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=("candidates", "evaluate"))
    parser.add_argument("--subjects", nargs="*", default=None)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    if args.step == "candidates":
        cands, ref = build_candidates(args.subjects, out=args.out)
        print(json.dumps({"candidates": len(cands), "expert_matched": int(cands["label"].sum()),
                          "expert_events": int((ref["kind"] == "expert").sum())}))
        return 0
    cands = pd.read_csv(args.out / "candidates.csv")
    ref = pd.read_csv(args.out / "reference.csv")
    evaluate(cands, ref, out=args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
