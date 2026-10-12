# Analyses the assistant evaluation asks about

Four saved analyses that `onset_agent/qa_eval.py` asks its question bank over,
together with the worked example in `../example_analysis/` (ds003029 sub-pt01).
See `docs/AGENT.md`, *Measuring it with a real model*.

| folder | recording | why it is here |
|---|---|---|
| `ds003498_sub-01` | ds003498 sub-01 run-01, 0–60 s | a depth implant; one detector disagreement |
| `ds003498_sub-08` | ds003498 sub-08 run-01, 0–60 s | rates that are not whole numbers (per-channel clean time) |
| `ds003498_sub-10` | ds003498 sub-10 run-01, 0–60 s | a grid whose two detectors pick different leaders |
| `ds003498_sub-17` | ds003498 sub-17 run-01, 0–60 s | the most detector disagreements in the cohort |

Each was produced by the standard pipeline at the measured interictal-agreement
threshold (2 robust SD, `onset_hfo.config.THRESHOLDS`), with the tables
gzipped. Re-create them with:

    python -m onset_agent.qa_eval --build-stores

Data: OpenNeuro ds003498 (interictal iEEG with expert HFO markings, Fedele et
al.), released under CC0. The expert markings are not used here; only the
pipeline's own output is.
