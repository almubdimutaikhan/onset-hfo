# A learned second stage for HFO candidates

**Status: experiment, not in the application.** Step one of the
deep-learning plan: before training any network, test whether a model
fitted on the measurements the detectors already make separates
expert-marked events from the rest better than the hand-written validation
rules. Code: [`onset_hfo/eventml.py`](../onset_hfo/eventml.py). Committed
results: [`data/eventml/`](../data/eventml/).

```bash
python -m onset_hfo.eventml candidates   # about 25 min, offline once the slices are cached
python -m onset_hfo.eventml evaluate     # about 40 min on four cores
```

## What was done

* **Data.** `ds003498`, run-01, all 20 subjects, the first 300 s of each, as
  five 60-s windows. Only the channels the annotators reviewed are used,
  as in [`EVALUATION.md`](EVALUATION.md).
* **Candidates.** The RMS detector at a low threshold: 1.5 SD for ripples
  and 2.5 SD for fast ripples. That gives 241,312 candidates in total
  (179,024 ripple, 62,288 fast ripple).
  * **Features.** Each candidate keeps ten measurements the detectors
    already make: score, duration, peak amplitude, peak frequency, the
    in-band peak's prominence, peak count, cycles, the 1–30 Hz deflection
    in robust SD, amplitude relative to its channel's median candidate,
    and the channel's candidate rate.
  * **Labels.** A candidate is labelled 1 when it overlaps an expert-marked
    event of the same band on the same channel within 20 ms.
  * **Scoring.** As in the benchmark: precision is counted over selected
    candidates, recall over expert events (196,378 of them).
* **Model.** Scikit-learn's gradient-boosted trees
  (`HistGradientBoostingClassifier`, depth 3, 200 iterations,
  class-balanced). It runs on one thread.
* **Baselines.**
  * **The rules as shipped:** RMS plus the validation rules, at the
    threshold that agreed best with the experts on this cohort (1.5 SD for
    ripples, 3.5 SD for fast ripples; `data/benchmark/agreement_sweep.csv`).
  * **The same rules with the threshold tuned per subject**, on the same
    labelled windows a per-subject model sees. A per-subject model has to
    beat this one, or it has only learned each patient's threshold.
* **Protocols.**
  * **Subject-specific, leave one window out:** train on four minutes of a
    patient and score the fifth. The probability cut is chosen by an inner
    leave-one-window-out over the four.
  * **Learning curve:** train on the first N candidates in time order, as a
    reader's first N verdicts, and score only what starts after the last of
    them. The cut is fixed at 0.5 in advance, because there is no held-out
    data to tune it on.
  * **Leave one patient out:** train on the other nineteen patients. The cut
    is chosen by a grouped inner cross-validation over them.
* **Statistics.** 95% intervals are percentile bootstraps over the 20
  subjects. They cover the mean F1 and each paired difference. Nothing is
  corrected for the number of comparisons.

## Results

Mean event-level F1 over 20 subjects, with paired differences:

| band | method | F1 [95% CI] | − rules [95% CI] | − tuned threshold [95% CI] | subjects above rules |
|---|---|---|---|---|---|
| ripple | rules, best threshold | 0.424 [0.344, 0.492] | — | −0.032 | — |
| ripple | rules, threshold tuned per subject | 0.457 [0.380, 0.520] | +0.032 [0.006, 0.073] | — | 15 |
| ripple | **subject-specific model** | **0.526** [0.440, 0.600] | **+0.102** [0.059, 0.156] | **+0.069** [0.049, 0.092] | 20 |
| ripple | **leave-one-patient-out model** | **0.513** [0.416, 0.597] | **+0.089** [0.037, 0.153] | +0.056 [0.026, 0.087] | 17 |
| fast ripple | rules, best threshold | 0.331 [0.236, 0.425] | — | −0.014 | — |
| fast ripple | rules, threshold tuned per subject | 0.345 [0.246, 0.446] | +0.014 [0.003, 0.024] | — | 16 |
| fast ripple | subject-specific model | 0.380 [0.266, 0.493] | +0.049 [0.024, 0.075] | +0.035 [0.012, 0.059] | 16 |
| fast ripple | leave-one-patient-out model | 0.378 [0.262, 0.494] | +0.047 [0.020, 0.075] | +0.033 [0.007, 0.058] | 12 |

The learned stage gains mostly in **precision**. For ripples it reaches
0.627 for the subject-specific model and 0.621 leaving one patient out,
against 0.440 for the rules, at about the same recall (0.470 and 0.461
against 0.467).

**Learning curve.** This is the subject-specific model trained on a reader's
first N verdicts only:

| band | verdicts | F1, model | F1, rules | − rules [95% CI] | − tuned threshold [95% CI] |
|---|---|---|---|---|---|
| ripple | 25 | 0.468 | 0.459 | +0.009 [−0.002, 0.021] | −0.015 [−0.059, 0.016] |
| ripple | 100 | 0.470 | 0.446 | +0.024 [−0.025, 0.084] | −0.002 [−0.033, 0.029] |
| ripple | 400 | 0.482 | 0.426 | +0.056 [0.008, 0.115] | +0.029 [0.003, 0.057] |
| fast ripple | 25 | 0.303 | 0.403 | −0.100 [−0.134, −0.069] | −0.050 [−0.109, 0.017] |
| fast ripple | 100 | 0.326 | 0.366 | −0.040 [−0.091, 0.005] | −0.036 [−0.089, 0.007] |
| fast ripple | 400 | 0.376 | 0.360 | +0.016 [−0.008, 0.043] | +0.007 [−0.019, 0.033] |

The full table, including 50 and 200 verdicts, is in
`data/eventml/learning_curve.csv`.

## What it means

1. **The features carry information the rules leave unused.** With enough
   training data, the learned stage beats the shipped rules in both bands,
   and the interval excludes zero. It also beats the rules with a
   per-patient threshold, so the gain is not just threshold tuning. For
   ripples it is better in all 20 subjects.
2. **Pooling across patients works nearly as well as training per patient.**
   The leave-one-patient-out model, which needs no labels from the new
   patient, comes within about 0.01 F1 of the subject-specific model, which
   needs four labelled minutes of that patient.
3. **A few hundred verdicts on their own are not enough.**
   * **Ripples:** a model trained only on a reader's first 400 verdicts
     beats the rules (+0.056) and the tuned threshold (+0.029); at 100 or
     fewer it does not.
   * **Fast ripples:** the per-patient model is worse than the rules below
     about 100 verdicts, and no better at 400.

   A per-patient model is the wrong design for the reading workflow. The
   one to try next is the pooled model, adjusted with the reader's verdicts.
4. **The headroom is in precision, not recall.** Recall is capped by the
   candidate set: at these thresholds many densely marked events have no
   candidate at all. A second stage cannot recover them; only a different
   candidate generator, or a detector run end to end, can.

## Limits

* **The reference is one study's validated detector output, not a census
  of every oscillation.** A learned stage may be learning to imitate that
  detector (the Morphology detector) as much as to recognise HFOs.
  "Agreement" is the right word, as everywhere in this project.
* **One centre, one dataset, 300 s per patient, 20 patients.** Nothing here
  says how the model behaves on another hospital's recordings, sampling
  rate or montage.
* **The intervals are not corrected for multiple comparisons.** The three
  learned-versus-rule comparisons in each band are the pre-stated ones.
* **The learning-curve rows test different spans at different budgets:**
  each tests what comes after its own last verdict. Compare a row's model
  column with its own rules column, not one row with another.

## From the Analysis page

Learned detection stays out of the clinical pages. Ranking, events and the
report always come from the rules. For researchers, the Analysis page's
template library has a group, **Learned detection (research)**, with three
scripts that run on the recording on screen:

| Template | What it does |
|---|---|
| A learned second stage on this recording's candidates | Every candidate with its ten measurements, then the gradient-boosted stage trained on the first 60 % of the recording and scored on the rest, against the rules, with which measurements it leans on |
| Train a braindecode network on HFO candidates | The 200-ms windows of every candidate fed to **any braindecode model by name** (`MODEL = "EEGNet"`, `"ShallowFBCSPNet"`, `"Deep4Net"`, `"EEGNeX"`, `"ATCNet"`, `"EEGConformer"` …). It trains on the first 60 % of the recording, stops early on the next 20 % and is scored on the last 20 % against the rules. The network is saved to `models/hfo-<MODEL>.pt` |
| Score this recording with a saved network | Loads a saved network, refuses a recording at another sampling rate or band, scores every candidate and lists where the network and the rules decided differently |

* **Training needs labels.** They come from expert markings: `ds003498`
  windows and the synthetic recordings carry them. A single recording is
  rarely enough; the training template says so when the validation loss
  stays at chance, or when the cut it chooses keeps everything.
* **For a result that means something, use the cohort protocols**, a
  patient held out at a time:

  ```bash
  pip install 'onset-hfo[dl]'          # torch and braindecode; nothing else needs them
  python -m onset_hfo.eventml candidates
  python -m onset_hfo.eventnet windows
  python -m onset_hfo.eventnet evaluate --model ShallowFBCSPNet
  ```

* **The library calls the templates use**, so the same steps can be
  scripted elsewhere:
  * `eventml.candidates_from_prepared(prep, channels, band, experts=...)`;
  * `eventml.experts_for(recording, band, channels)`;
  * `eventml.fit_boosted` and `eventml.predict_boosted`;
  * `eventnet.windows_from_prepared(prep, candidates)`;
  * `eventnet.train(X, labels, train_rows, val_rows, sfreq, model="EEGNet")`;
  * `eventnet.predict`, `eventnet.save`, `eventnet.load`, and
    `eventnet.available_models()`.

## Next

Two steps, in this order:
1. **A pooled model adjusted with the reader's verdicts:** the
   leave-one-patient-out model, then fine-tuned on a few dozen verdicts of
   the current patient.
2. **A network on the raw windows (braindecode)**, as the second stage over
   the same candidates. The bar is the pooled model's ripple F1 of 0.513
   leaving one patient out, not the rules.
