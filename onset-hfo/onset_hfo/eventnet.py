"""A convolutional network as the second stage, on the raw candidate windows.

Step two of the deep-learning plan (step one: :mod:`onset_hfo.eventml`). The
same candidates, the same expert labels, the same scoring and the same
leave-one-patient-out protocol -- what changes is what the model sees: not
ten measurements the detectors already made, but 200 ms of signal around
each candidate, as two input channels:

* the prepared signal (bipolar, high-passed, notched), in units of its
  channel's robust SD over the minute; and
* the same signal band-passed to the candidate's band, in units of *that*
  trace's robust SD -- the scale the detectors threshold on.

The network is braindecode's EEGNet: a compact temporal-then-depthwise
convolution designed for few training examples, which is what 19 patients
are. Its bar is not the rules but the gradient-boosted model on the
detectors' features (ripple F1 0.513 leaving one patient out).

    python -m onset_hfo.eventnet windows     # 200-ms windows for every candidate
    python -m onset_hfo.eventnet evaluate    # leave one patient out, per band

Requires the ``dl`` extra (torch, braindecode). Nothing in the application
imports this module.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from onset_hfo import eventml
from onset_hfo.config import BANDS, RESULTS_DIR

__all__ = ["WINDOW_S", "extract_windows", "evaluate"]

#: The window the network sees, centred on the candidate: long enough for the
#: slowest ripple (80 Hz, 12.5 ms a cycle) to show sixteen cycles and the
#: transient that ringing comes from; short enough that two candidates rarely
#: share one.
WINDOW_S = 0.2
OUT = RESULTS_DIR / "eventnet"
#: Training: class-balanced loss, early stopping on held-out training
#: patients, an epoch capped so that the large patients do not dominate it.
EPOCHS = 20
PATIENCE = 4
BATCH = 256
PER_EPOCH = 60_000
VALIDATION_PATIENTS = 3


# -- windows ------------------------------------------------------------------

def extract_windows(candidates: pd.DataFrame, out: Path = OUT,
                    verbose: bool = True) -> dict[str, Path]:
    """One (2, n) float16 window per candidate, in candidate-table order,
    written as ``windows_<band>.npy`` beside a ``rows_<band>.npy`` of the
    candidate-table index each window belongs to."""
    from onset_hfo.datasets import fetch_slice
    from onset_hfo.detectors.base import bandpass, robust_scale
    from onset_hfo.preprocess import prepare

    out.mkdir(parents=True, exist_ok=True)
    bands = sorted(candidates["band"].unique())
    paths = {band: out / f"windows_{band}.npy" for band in bands}
    sizes = {band: int((candidates["band"] == band).sum()) for band in bands}
    # Which candidate-table row each window is, recorded as it is written,
    # so nothing depends on two orderings agreeing.
    written: dict[str, list[int]] = {band: [] for band in bands}
    filled = {band: 0 for band in bands}
    memmaps: dict[str, np.memmap] = {}
    sfreq_seen: set[float] = set()

    groups = candidates.groupby(["subject", "window_start"], sort=True)
    for (subject, w0), rows in groups:
        recording = fetch_slice(dataset=eventml.DATASET, subject=subject, run=eventml.RUN,
                                t_start=float(w0), t_stop=float(w0) + 60.0, verbose=False)
        prep = prepare(recording, verbose=False)
        sfreq_seen.add(float(prep.sfreq))
        half = int(round(WINDOW_S * prep.sfreq / 2))
        width = 2 * half
        channels = sorted(rows["channel"].unique())
        idx = [prep.ch_names.index(c) for c in channels]
        raw = prep.data[idx]
        _, raw_scale = robust_scale(raw)
        for band, band_rows in rows.groupby("band"):
            if band not in memmaps:
                memmaps[band] = np.lib.format.open_memmap(
                    paths[band], mode="w+", dtype=np.float16, shape=(sizes[band], 2, width))
            filtered = bandpass(raw, prep.sfreq, getattr(BANDS, band))
            _, band_scale = robust_scale(filtered)
            # Padded so a candidate at the edge of the minute still gets a
            # full window (zeros outside it, in both channels).
            raw_n = np.pad(raw / np.maximum(raw_scale, 1e-12), ((0, 0), (half, half)))
            band_n = np.pad(filtered / np.maximum(band_scale, 1e-12), ((0, 0), (half, half)))
            position = {c: i for i, c in enumerate(channels)}
            for row in band_rows.itertuples():
                centre = int(round((0.5 * (row.start + row.stop) - prep.t_offset)
                                   * prep.sfreq)) + half
                i = position[row.channel]
                k = filled[band]
                memmaps[band][k, 0] = np.clip(raw_n[i, centre - half:centre + half], -60, 60)
                memmaps[band][k, 1] = np.clip(band_n[i, centre - half:centre + half], -60, 60)
                written[band].append(int(row.Index))
                filled[band] += 1
        if verbose:
            print(f"[eventnet] {subject} {w0:g}-{w0 + 60:g} s: "
                  + ", ".join(f"{b} {filled[b]}" for b in filled), flush=True)
    for band, mm in memmaps.items():
        mm.flush()
        if filled[band] != sizes[band]:
            raise RuntimeError(f"{band}: filled {filled[band]} of {sizes[band]} windows")
        np.save(out / f"rows_{band}.npy", np.asarray(written[band], dtype=np.int64))
    if len(sfreq_seen) != 1:
        raise RuntimeError(f"windows at several sampling rates: {sorted(sfreq_seen)}")
    return paths


# -- the network --------------------------------------------------------------

def _network(n_times: int, sfreq: float, seed: int):
    import torch
    from braindecode.models import EEGNet

    torch.manual_seed(seed)
    return EEGNet(n_chans=2, n_outputs=2, n_times=n_times, sfreq=sfreq)


def _predict(model, X: np.ndarray, rows: np.ndarray) -> np.ndarray:
    import torch

    model.eval()
    out = np.empty(len(rows), dtype=np.float32)
    with torch.no_grad():
        for i in range(0, len(rows), 2048):
            batch = torch.from_numpy(X[rows[i:i + 2048]].astype(np.float32))
            out[i:i + 2048] = torch.softmax(model(batch), dim=1)[:, 1].numpy()
    return out


def _train(X: np.ndarray, labels: np.ndarray, train_rows: np.ndarray,
           val_rows: np.ndarray, sfreq: float, seed: int) -> tuple[object, dict]:
    """EEGNet with a class-balanced loss, early-stopped on the validation
    patients' loss. Returns the best model and the training log."""
    import copy

    import torch

    rng = np.random.default_rng(seed)
    model = _network(X.shape[-1], sfreq, seed)
    positive = labels[train_rows].mean()
    weight = torch.tensor([0.5 / (1 - positive), 0.5 / positive], dtype=torch.float32)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weight)
    optimiser = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-3)
    val_X = torch.from_numpy(X[val_rows].astype(np.float32))
    val_y = torch.from_numpy(labels[val_rows].astype(np.int64))
    best, best_loss, waited, log = None, float("inf"), 0, []
    for epoch in range(EPOCHS):
        model.train()
        chosen = rng.choice(train_rows, size=min(PER_EPOCH, len(train_rows)), replace=False)
        started = time.time()
        for i in range(0, len(chosen), BATCH):
            batch = chosen[i:i + BATCH]
            xb = torch.from_numpy(X[batch].astype(np.float32))
            yb = torch.from_numpy(labels[batch].astype(np.int64))
            optimiser.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimiser.step()
        model.eval()
        with torch.no_grad():
            val_loss = float(sum(loss_fn(model(val_X[j:j + 4096]), val_y[j:j + 4096]).item()
                                 * len(val_y[j:j + 4096])
                                 for j in range(0, len(val_y), 4096)) / max(len(val_y), 1))
        log.append({"epoch": epoch, "val_loss": val_loss,
                    "seconds": round(time.time() - started, 1)})
        if val_loss < best_loss - 1e-4:
            best, best_loss, waited = copy.deepcopy(model.state_dict()), val_loss, 0
        else:
            waited += 1
            if waited >= PATIENCE:
                break
    model.load_state_dict(best)
    return model, {"epochs": len(log), "best_val_loss": best_loss, "log": log}


# -- leave one patient out ----------------------------------------------------

def evaluate(candidates: pd.DataFrame, reference: pd.DataFrame, out: Path = OUT,
             bands=("ripple", "fast_ripple"), seed: int = 0, verbose: bool = True,
             subjects: list[str] | None = None) -> pd.DataFrame:
    """Leave one patient out, per band: train on the others (three of them
    held back for early stopping and for choosing the probability cut), score
    the held-out patient against the experts, and compare it, patient by
    patient, with the rules and with the gradient-boosted model."""
    import torch

    torch.set_num_threads(4)
    experts_all, rules_all = eventml._split(reference)
    rows_out, logs = [], []
    for band in bands:
        # Into memory: random access to a memory map on disk is the slow part.
        X = np.load(out / f"windows_{band}.npy")
        index = np.load(out / f"rows_{band}.npy")
        cands = candidates.loc[index].reset_index(drop=True)
        labels = cands["label"].to_numpy()
        experts_b = experts_all[experts_all["band"] == band]
        rules_b = rules_all[rules_all["band"] == band]
        sfreq = X.shape[-1] / WINDOW_S
        everyone = sorted(cands["subject"].unique())
        for held in (subjects or everyone):
            others = [s for s in everyone if s != held]
            rng = np.random.default_rng(seed + everyone.index(held))
            validation = set(rng.choice(others, size=VALIDATION_PATIENTS, replace=False))
            train_rows = np.flatnonzero(cands["subject"].isin(set(others) - validation).to_numpy())
            val_rows = np.flatnonzero(cands["subject"].isin(validation).to_numpy())
            test_rows = np.flatnonzero((cands["subject"] == held).to_numpy())
            started = time.time()
            model, log = _train(X, labels, train_rows, val_rows, sfreq, seed)
            val_prob = _predict(model, X, val_rows)
            val_frame = cands.iloc[val_rows]
            cut = eventml._best_threshold(val_prob, val_frame,
                                          experts_b[experts_b["subject"].isin(validation)])
            prob = _predict(model, X, test_rows)
            test = cands.iloc[test_rows]
            ex = experts_b[experts_b["subject"] == held]
            net = eventml.score_selection(test[prob >= cut], ex)
            rule = eventml.score_selection(rules_b[rules_b["subject"] == held], ex)
            auc = _auc(labels[test_rows], prob)
            rows_out.append({"subject": held, "band": band, "f1": net.f1,
                             "precision": net.precision, "recall": net.recall,
                             "rule_f1": rule.f1, "auc": auc, "cut": cut,
                             "epochs": log["epochs"], "validation": ",".join(sorted(validation)),
                             "minutes": round((time.time() - started) / 60, 1)})
            logs.append({"subject": held, "band": band, **log})
            if verbose:
                print(f"[eventnet] {band} {held}: F1 {net.f1:.3f} (rules {rule.f1:.3f}), "
                      f"AUC {auc:.3f}, {log['epochs']} epochs, "
                      f"{rows_out[-1]['minutes']} min", flush=True)
            pd.DataFrame(rows_out).to_csv(out / "per_subject.csv", index=False)
    per_subject = pd.DataFrame(rows_out)
    (out / "training_log.json").write_text(json.dumps(logs, indent=1, default=float))
    summary = summarise(per_subject)
    summary.to_csv(out / "summary.csv", index=False)
    if verbose:
        print(summary.round(3).to_string(index=False))
    return summary


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(y, p)) if len(set(y)) == 2 else float("nan")


def summarise(per_subject: pd.DataFrame,
              gbm: Path = Path(__file__).resolve().parent.parent / "data" / "eventml"
              / "per_subject.csv") -> pd.DataFrame:
    """Mean F1 with intervals, and paired differences against the rules and
    against the gradient-boosted model, patient by patient."""
    boosted = pd.read_csv(gbm)
    boosted = boosted[boosted["method"] == "leave one patient out"]
    out = []
    for band, rows in per_subject.groupby("band"):
        mine = rows.set_index("subject")
        gb = boosted[boosted["band"] == band].set_index("subject")["f1"].reindex(mine.index)
        vs_rule = mine["f1"] - mine["rule_f1"]
        vs_gbm = mine["f1"] - gb
        low, high = eventml._bootstrap_mean(mine["f1"].to_numpy())
        rlow, rhigh = eventml._bootstrap_mean(vs_rule.to_numpy())
        glow, ghigh = eventml._bootstrap_mean(vs_gbm.to_numpy())
        out.append({"band": band, "subjects": len(mine), "f1": mine["f1"].mean(),
                    "f1_ci_low": low, "f1_ci_high": high,
                    "precision": mine["precision"].mean(), "recall": mine["recall"].mean(),
                    "auc": mine["auc"].mean(), "rule_f1": mine["rule_f1"].mean(),
                    "boosted_f1": gb.mean(),
                    "f1_minus_rule": vs_rule.mean(), "rule_ci_low": rlow, "rule_ci_high": rhigh,
                    "f1_minus_boosted": vs_gbm.mean(), "boosted_ci_low": glow,
                    "boosted_ci_high": ghigh,
                    "subjects_better_than_boosted": int((vs_gbm > 0).sum())})
    return pd.DataFrame(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m onset_hfo.eventnet",
                                     description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=("windows", "evaluate"))
    parser.add_argument("--candidates", type=Path, default=eventml.OUT)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--bands", nargs="*", default=["ripple", "fast_ripple"])
    parser.add_argument("--subjects", nargs="*", default=None)
    args = parser.parse_args(argv)
    candidates = pd.read_csv(args.candidates / "candidates.csv")
    if args.step == "windows":
        extract_windows(candidates, out=args.out)
        return 0
    reference = pd.read_csv(args.candidates / "reference.csv")
    evaluate(candidates, reference, out=args.out, bands=tuple(args.bands),
             subjects=args.subjects)
    return 0


if __name__ == "__main__":
    sys.exit(main())
