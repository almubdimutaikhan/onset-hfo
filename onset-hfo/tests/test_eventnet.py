"""The network second stage: training, prediction and the comparison table.

Skipped where torch or braindecode are not installed (the ``dl`` extra); the
cohort numbers come from ``python -m onset_hfo.eventnet`` and are committed
under ``data/eventml/``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")
pytest.importorskip("braindecode")

from onset_hfo import eventnet  # noqa: E402


def _windows(n: int = 1200, width: int = 400, seed: int = 0):
    """Noise, with a 150 Hz burst in the middle of the positive windows."""
    rng = np.random.default_rng(seed)
    labels = (rng.random(n) < 0.35).astype(int)
    t = np.arange(width) / 2000.0
    burst = np.sin(2 * np.pi * 150 * t) * np.exp(-((t - t.mean()) / 0.012) ** 2)
    X = rng.normal(0, 1, (n, 2, width)).astype(np.float32)
    X[labels == 1, 0] += 3 * burst
    X[labels == 1, 1] += 4 * burst
    return X.astype(np.float16), labels


def test_the_network_learns_a_burst_and_ranks_held_out_windows_by_it(monkeypatch):
    monkeypatch.setattr(eventnet, "EPOCHS", 6)
    monkeypatch.setattr(eventnet, "PER_EPOCH", 800)
    X, labels = _windows()
    rows = np.arange(len(labels))
    train, val, test = rows[:800], rows[800:1000], rows[1000:]
    model, log = eventnet._train(X, labels, train, val, sfreq=2000.0, seed=0)
    assert 1 <= log["epochs"] <= 6 and np.isfinite(log["best_val_loss"])
    prob = eventnet._predict(model, X, test)
    assert prob.shape == (len(test),) and np.all((prob >= 0) & (prob <= 1))
    assert eventnet._auc(labels[test], prob) > 0.9


def test_prediction_keeps_the_order_it_was_asked_in(monkeypatch):
    monkeypatch.setattr(eventnet, "EPOCHS", 1)
    monkeypatch.setattr(eventnet, "PER_EPOCH", 200)
    X, labels = _windows(n=300)
    rows = np.arange(300)
    model, _ = eventnet._train(X, labels, rows[:200], rows[200:250], 2000.0, 0)
    shuffled = np.random.default_rng(1).permutation(rows)
    straight = eventnet._predict(model, X, rows)
    assert np.allclose(eventnet._predict(model, X, shuffled), straight[shuffled], atol=1e-6)


def test_the_summary_pairs_each_patient_with_the_rules_and_the_boosted_model(tmp_path):
    boosted = pd.DataFrame({
        "subject": ["a", "b", "c", "a", "b", "c"], "band": ["ripple"] * 6,
        "method": ["leave one patient out"] * 3 + ["all candidates"] * 3,
        "f1": [0.5, 0.4, 0.3, 0.9, 0.9, 0.9]})
    path = tmp_path / "per_subject.csv"
    boosted.to_csv(path, index=False)
    net = pd.DataFrame({"subject": ["a", "b", "c"], "band": ["ripple"] * 3,
                        "f1": [0.6, 0.4, 0.2], "precision": [0.5] * 3, "recall": [0.5] * 3,
                        "rule_f1": [0.4, 0.4, 0.4], "auc": [0.8] * 3})
    row = eventnet.summarise(net, gbm=path).iloc[0]
    assert row["boosted_f1"] == pytest.approx(0.4), "only the leave-one-patient-out rows"
    assert row["f1_minus_boosted"] == pytest.approx(0.0)
    assert row["f1_minus_rule"] == pytest.approx(0.0)
    assert row["subjects_better_than_boosted"] == 1
