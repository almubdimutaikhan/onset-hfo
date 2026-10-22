"""The Validation page's figures, drawn from the committed study tables. Qt-free.

Four pictures a reader takes in faster than a sentence:

* **ictal**: every patient's AUC for the Epileptogenicity Index at the
  seizure, the energy ratio alone, the index 40 s before, and the same on
  the second archive;
* **template**: how far a planned contact lands from the real one, by its
  distance from the tip, for four choices of spacing;
* **outcome**: every patient as a dot, by outcome, for the expert markings
  and the RMS detector;
* **window**: the outcome AUC as the analysed window grows, and its range
  over five separate minutes -- the result that did not hold up.

They ship as PNG files in ``onset_review/figures/`` so the page shows them on
an install without the tables (the wheel carries none). ``validation.json``
beside them records a digest of the numbers each one plots, and
``tests/test_validation.py`` recomputes those numbers from ``data/``, so a
figure cannot quietly fall behind the tables. After a table changes,
regenerate them::

    python -m onset_review.validationfigures
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

__all__ = ["FIGURES", "FIGURE_DIR", "figure_data", "digest", "draw", "build", "path_for",
           "shipped_digests"]

FIGURE_DIR = Path(__file__).resolve().parent / "figures"
DIGESTS = FIGURE_DIR / "validation.json"

#: key -> caption, as the page prints it under the picture.
FIGURES = {
    "ictal": "Each dot is one patient's AUC, onset zone against the other channels; "
             "the bar is the median with its 95% interval.",
    "template": "Median distance from a planned contact to the real one, by how far the "
                "contact is from the tip of its shaft, for four choices of spacing.",
    "outcome": "Each dot is one patient: the share of the channels tied for busiest "
               "that were resected, by outcome; the bar is each group's mean.",
    "window": "The outcome AUC as the analysed window grows from the start of the run, "
              "with its 95% interval; on the right, its range over five separate minutes.",
}


def _root(root=None) -> Path:
    if root is not None:
        return Path(root)
    from onset_review.studytables import DATA_ROOT

    return Path(DATA_ROOT)


def _numbers(values) -> list:
    return [None if v != v else round(float(v), 6) for v in values]


# -- what each figure plots ---------------------------------------------------------------------
def figure_data(key: str, root=None) -> dict:
    """The numbers figure `key` plots, read from the tables under `root`
    (the checkout's ``data/`` by default), as plain JSON-able values."""
    import pandas as pd

    root = _root(root)
    if key == "ictal":
        groups = [("ds003029\nat the seizure", root / "ictal" / "per_patient.csv", "auc_ei"),
                  ("energy ratio\nalone", root / "ictal" / "per_patient.csv", "auc_er"),
                  ("40 s before\n(control)", root / "ictal" / "control_per_patient.csv",
                   "auc_ei"),
                  ("HUP\nat the seizure", root / "hup" / "ictal" / "per_patient.csv", "auc_ei"),
                  ("HUP 40 s\nbefore", root / "hup" / "ictal" / "control_per_patient.csv",
                   "auc_ei")]
        return {"groups": [[label, _numbers(pd.read_csv(path)[column].dropna())]
                           for label, path, column in groups if path.exists()]}
    if key == "template":
        import numpy as np

        contacts = pd.read_csv(root / "template" / "per_contact.csv")
        after = contacts[contacts["index"] > 0]
        edges = np.arange(0, 65, 5.0)
        lines = {}
        for spacing in ("own", "common", "5mm", "3.5mm"):
            medians = []
            for low, high in zip(edges[:-1], edges[1:], strict=True):
                part = after[(after.from_tip_mm >= low) & (after.from_tip_mm < high)][
                    f"error_{spacing}_mm"].dropna()
                medians.append(part.median() if len(part) >= 20 else float("nan"))
            lines[spacing] = _numbers(medians)
        return {"middle": _numbers((edges[:-1] + edges[1:]) / 2), "lines": lines}
    if key == "outcome":
        from onset_review import studytables

        cohort = studytables.cohort_overview(band="fast_ripple", scope="reviewed")
        groups = pd.read_csv(root / "stability" / "outcome_groups_300s.csv").query(
            "scope == 'reviewed' and band == 'fast_ripple' and metric == 'candidates_resected'")
        out = {"seizure_free": [bool(v) for v in cohort["seizure_free"]]}
        for source in ("expert", "rms"):
            out[source] = _numbers(cohort[f"candidates_resected_{source}"])
            row = groups[groups["source"] == source].iloc[0]
            out[f"{source}_auc"] = _numbers([row["auc"], row["auc_lo"], row["auc_hi"],
                                             row["p_permutation"]])
        return out
    if key == "window":
        curve = pd.read_csv(root / "stability" / "curve.csv")
        spread = pd.read_csv(root / "stability" / "spread.csv")
        out = {}
        for source in ("expert", "rms"):
            part = curve[curve["source"] == source].sort_values("window_s")
            row = spread[spread["source"] == source].iloc[0]
            out[source] = {column: _numbers(part[column]) for column in
                           ("window_s", "auc", "auc_lo", "auc_hi")}
            out[source]["minutes"] = _numbers([row["auc_min"], row["auc_median"],
                                               row["auc_max"]])
        return out
    raise KeyError(f"no figure {key!r}; one of {list(FIGURES)}")


def digest(data: dict) -> str:
    """A short digest of a figure's numbers, independent of how they are drawn."""
    text = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def shipped_digests() -> dict:
    try:
        return json.loads(DIGESTS.read_text())
    except (OSError, ValueError):
        return {}


def path_for(key: str) -> Path | None:
    """The shipped picture for `key`, or None when it is not there."""
    path = FIGURE_DIR / f"validation-{key}.png"
    return path if path.is_file() else None


# -- drawing ------------------------------------------------------------------------------------
def _figure(width: float = 6.4, height: float = 3.4):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(width, height), dpi=130)
    FigureCanvasAgg(figure)
    return figure


def _ictal(figure, data: dict) -> None:
    import numpy as np

    from onset_hfo.ictal_study import bootstrap_median
    from onset_review.studycharts import GRID, MUTED, SERIES, _quiet

    axis = figure.add_subplot(111)
    _quiet(axis)
    axis.yaxis.grid(True, color=GRID, linewidth=0.8)
    rng = np.random.default_rng(0)
    colours = [SERIES[0], SERIES[1], MUTED, SERIES[0], MUTED]
    groups = data["groups"]
    for i, (_label, values) in enumerate(groups):
        values = [v for v in values if v is not None]
        axis.scatter(i + rng.uniform(-0.12, 0.12, len(values)), values, s=14,
                     color=colours[i % len(colours)], alpha=0.75, linewidths=0)
        median, low, high = bootstrap_median(values)
        axis.plot([i + 0.25, i + 0.25], [low, high], color="black", linewidth=1.3)
        axis.plot([i + 0.18, i + 0.32], [median, median], color="black", linewidth=2.0)
        axis.text(i + 0.36, median, f"{median:.2f}\nn={len(values)}", fontsize=7,
                  va="center")
    axis.axhline(0.5, color=MUTED, linestyle="--", linewidth=1.0)
    axis.set_xticks(range(len(groups)))
    axis.set_xticklabels([g[0] for g in groups], fontsize=7)
    axis.set_ylim(0, 1.02)
    axis.set_xlim(-0.5, len(groups) - 0.2)
    axis.set_ylabel("AUC per patient", fontsize=8)


def _template(figure, data: dict) -> None:
    from onset_review.studycharts import GRID, MUTED, SERIES, _quiet

    axis = figure.add_subplot(111)
    _quiet(axis)
    axis.grid(True, color=GRID, linewidth=0.8)
    for key, label, colour, style in (("own", "each shaft's own spacing", SERIES[0], "-"),
                                      ("common", "one spacing for all", SERIES[0], "--"),
                                      ("5mm", "5 mm", SERIES[1], "-"),
                                      ("3.5mm", "3.5 mm", SERIES[1], "--")):
        values = [float("nan") if v is None else v for v in data["lines"][key]]
        axis.plot(data["middle"], values, style, color=colour, linewidth=1.8, label=label)
    axis.axhline(5, color=MUTED, linestyle=":", linewidth=0.9)
    axis.set_xlabel("distance of the contact from the tip (mm)", fontsize=8)
    axis.set_ylabel("median distance, planned to real (mm)", fontsize=8)
    axis.set_xlim(0, 62)
    axis.set_ylim(bottom=0)
    axis.legend(fontsize=7, frameon=False, title="spacing used", title_fontsize=7)


def _outcome(figure, data: dict) -> None:
    import numpy as np

    from onset_review.studycharts import GRID, MUTED, SERIES, _quiet

    free = np.asarray(data["seizure_free"], dtype=bool)
    rows = [("recurrence", ~free, SERIES[1]), ("seizure-free", free, SERIES[0])]
    rng = np.random.default_rng(7)
    panels = figure.subplots(1, 2, sharex=True, sharey=True)
    for axis, (source, title) in zip(panels, (("expert", "Expert markings"),
                                              ("rms", "RMS detector")), strict=True):
        _quiet(axis)
        axis.xaxis.grid(True, color=GRID, linewidth=0.8)
        axis.yaxis.grid(False)
        values_all = np.asarray([np.nan if v is None else v for v in data[source]], dtype=float)
        for level, (_label, mask, colour) in enumerate(rows):
            values = values_all[mask]
            values = values[np.isfinite(values)]
            y = level + rng.uniform(-0.26, 0.26, size=len(values))
            axis.scatter(values, y, s=36, color=colour, edgecolor="white", linewidth=1.2,
                         alpha=0.9, zorder=4)
            if len(values):
                mean = float(values.mean())
                axis.plot([mean, mean], [level - 0.32, level + 0.32], color=colour,
                          linewidth=2.5, zorder=5)
                axis.annotate(f"mean {mean:.2f}", (mean, level + 0.36), ha="center",
                              va="bottom", fontsize=7.5)
        axis.set_yticks([0, 1])
        axis.set_yticklabels([f"{label} ({int(mask.sum())})" for label, mask, _ in rows],
                             fontsize=8)
        axis.set_ylim(-0.6, 1.8)
        axis.set_xlim(-0.05, 1.05)
        auc, low, high, p = data[f"{source}_auc"]
        axis.set_title(f"{title}\nAUC {auc:.2f} ({low:.2f}–{high:.2f}), p = {p:.2f}",
                       loc="left", fontsize=8.5, linespacing=1.4)
        axis.set_xlabel("share of the tied busiest channels resected", color=MUTED,
                        fontsize=7.5)


def _window(figure, data: dict) -> None:
    from onset_review.studycharts import MUTED, SERIES, _quiet

    axis = figure.add_subplot(111)
    _quiet(axis)
    for (source, label), colour, shift in zip((("expert", "expert markings"),
                                               ("rms", "RMS detector")),
                                              SERIES, (-6, 6), strict=True):
        part = data[source]
        axis.fill_between(part["window_s"], part["auc_lo"], part["auc_hi"], color=colour,
                          alpha=0.13, linewidth=0)
        axis.plot(part["window_s"], part["auc"], "-o", color=colour, markersize=4,
                  linewidth=1.8, label=label)
        low, median, high = part["minutes"]
        x = 340 + shift
        axis.plot([x, x], [low, high], color=colour, linewidth=2.2)
        axis.plot([x], [median], "o", color=colour, markersize=4)
    axis.axhline(0.5, color=MUTED, linewidth=1, linestyle=":")
    axis.axhline(0.85, color=MUTED, linewidth=1, linestyle="--")
    axis.text(300, 0.86, "smallest AUC 13 vs 7 patients can detect", ha="right",
              va="bottom", fontsize=7, color=MUTED)
    axis.text(300, 0.51, "chance", ha="right", va="bottom", fontsize=7, color=MUTED)
    axis.set_xticks([30, 60, 120, 180, 240, 300, 340])
    axis.set_xticklabels(["30", "60", "120", "180", "240", "300", "5 single\nminutes"],
                         fontsize=7.5)
    axis.set_xlim(15, 360)
    axis.set_ylim(0.2, 1.02)
    axis.set_xlabel("seconds analysed from the start of the run", fontsize=8)
    axis.set_ylabel("AUC, seizure-free vs recurrence", fontsize=8)
    axis.legend(fontsize=7, frameon=False, loc="lower left")


_DRAW = {"ictal": (_ictal, (6.4, 3.4)), "template": (_template, (6.4, 3.4)),
         "outcome": (_outcome, (7.2, 3.0)), "window": (_window, (6.4, 3.4))}


def draw(key: str, path, root=None) -> Path:
    """Figure `key` from the tables under `root`, as a PNG at `path`."""
    import matplotlib

    matplotlib.use("Agg", force=False)
    painter, size = _DRAW[key]
    figure = _figure(*size)
    painter(figure, figure_data(key, root))
    figure.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, bbox_inches="tight", metadata={"Software": None})
    return path


def build(root=None, out=None) -> dict:
    """Draw every figure into `out` (the package's ``figures/``) with the
    digest of the numbers it plots; returns {key: digest}."""
    out = Path(out) if out is not None else FIGURE_DIR
    digests = {}
    for key in FIGURES:
        draw(key, out / f"validation-{key}.png", root)
        digests[key] = digest(figure_data(key, root))
    (out / "validation.json").write_text(json.dumps(digests, indent=1, sort_keys=True) + "\n")
    return digests


if __name__ == "__main__":       # pragma: no cover - the regeneration command
    for key, value in build().items():
        print(f"{key}: {value}")
