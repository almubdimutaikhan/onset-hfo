"""The open window scored against its expert markings, as the study scored it. Qt-free.

The detector study scored each of the archive's 20 patients against the
experts' HFO markings (`onset_hfo.benchmark`). A window that carries such
markings -- the archive's patients' do -- can be scored the same way:
`evaluate_detections` and the same rank agreement, on the reviewed channels
only. The Validation page shows that score, and the batch window gathers it
across recordings.

It is one window of one patient, not a score of the method: a 20-patient
mean and one window are different quantities, and :data:`CAVEAT` says so
wherever the score is shown.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["has_markings", "threshold_for", "score_window", "CAVEAT"]

CAVEAT = ("One window of one patient. The study's numbers are means over 20 patients' "
          "first 60 s; this is where the open window sits, measured the same way, not a "
          "score of the method.")


def _truth(session) -> pd.DataFrame | None:
    frame = getattr(getattr(session, "recording", None), "ground_truth", None)
    if frame is None or not len(frame):
        return None
    return frame


def has_markings(session) -> bool:
    return session is not None and _truth(session) is not None \
        and len(_reviewed(session)) > 0


def _reviewed(session) -> list[str]:
    names = set(session.raw.ch_names) if session.raw is not None else set()
    return [c for c in session.reviewed_channels if c in names]


def _hfo_detectors(session) -> list[str]:
    from onset_hfo.detectors import HFO_DETECTORS

    found = []
    for name in session.request.detectors:
        if name in HFO_DETECTORS and name not in found:
            found.append(name)
    return found


def threshold_for(session, detector: str) -> float:
    """The threshold this window's `detector` ran at, in robust SD."""
    cfg = session.request.pipeline_config()
    return float(getattr(cfg, detector).threshold_sd)


def score_window(session) -> pd.DataFrame | None:
    """This window scored against its expert markings, one row per detector:
    precision, recall, F1, channel-rank ρ, top-5 shared and detections per
    60 s, on the reviewed channels -- the columns of the study's sweep. None
    when the window has no markings."""
    if not has_markings(session):
        return None
    from onset_hfo.benchmark import _rank_agreement
    from onset_hfo.evaluate import evaluate_detections

    truth = _truth(session)
    reviewed = _reviewed(session)
    band = session.request.band
    seconds = float(session.span[1] - session.span[0]) if session.span else \
        float(session.raw.times[-1])
    expert = truth[truth["kind"] == band].groupby("channel").size() \
        .reindex(reviewed, fill_value=0)
    rows = []
    for detector in _hfo_detectors(session):
        events = [e for e in session.events if e.detector == detector]
        score = evaluate_detections(events, truth, kind=band, channels=reviewed)
        ours = pd.Series({c: sum(1 for e in events if e.accepted and e.channel == c)
                          for c in reviewed})
        ranks = _rank_agreement(expert, ours, top_k=5)
        detections = float(ours.sum()) / max(seconds, 1e-9) * 60.0
        rows.append({"detector": detector, "band": band,
                     "threshold_sd": threshold_for(session, detector),
                     "precision": float(score.precision), "recall": float(score.recall),
                     "f1": float(score.f1), "rank_rho": float(ranks["spearman_rho"]),
                     "top5_overlap": float(ranks["top5_overlap"]),
                     "detections": detections, "n_reviewed": len(reviewed),
                     "n_expert": int(expert.sum()), "seconds": seconds})
    return pd.DataFrame(rows) if rows else None
