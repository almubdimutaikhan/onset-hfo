# Template: A learned second stage on this recording's candidates
# Group: Learned detection (research)
# Mirrors: the cohort study in docs/EVENTML.md, on the recording on screen
# About: Every candidate event with the ten measurements the detector makes, then a gradient-boosted model trained on the first part of the recording and scored on the rest, against the rules. Research only; nothing on screen changes.

from onset_hfo import eventml
from onset_hfo.preprocess import prepare

# %% Prepare the signal as the window did, and list the candidates
# The detector runs at the band's low candidate threshold so a second stage
# has events to choose between; the rules' own decision is kept per event.
recording = session.recording
prep = prepare(recording, request.pipeline_config().preprocess, verbose=False)
analysed = [c for c in findings["channel"] if c in prep.ch_names]
band = request.band
experts = eventml.experts_for(recording, band, analysed)
cands = eventml.candidates_from_prepared(prep, analysed, band, experts=experts)
print(f"{len(cands)} candidates on {cands['channel'].nunique() if len(cands) else 0} channels "
      f"({band}, threshold {eventml.CANDIDATE_SD[band]} SD); "
      f"{int(cands['rule_accepted'].sum()) if len(cands) else 0} kept by the rules")
print("expert markings:", "none on this recording" if experts is None
      else f"{len(experts)} {band} events; {int((cands['label'] == 1).sum())} candidates match one")
print(cands[["channel", "start", "duration_ms", "peak_frequency_hz", "spectral_prominence_db",
             "n_cycles", "rule_accepted", "label"]].head(10).round(2).to_string(index=False))

# %% Train on the first 60 % of the recording, score the rest
# Split by time, never at random: neighbouring candidates overlap, and a
# random split puts near-copies on both sides.
if experts is None or cands.empty or cands["label"].nunique() < 2:
    print("A model needs expert markings with both matched and unmatched candidates; "
          "this recording has none. Open a ds003498 window, or label events yourself.")
    model = None
else:
    boundary = cands["start"].quantile(0.6)
    train = cands[cands["start"] <= boundary]
    test = cands[cands["start"] > boundary]
    test_experts = experts[experts["start"] > boundary]
    model = eventml.fit_boosted(train)
if model is not None and len(test):
    prob = eventml.predict_boosted(model, test)
    learned = eventml.score_selection(test[prob >= 0.5], test_experts)
    rules = eventml.score_selection(test[test["rule_accepted"]], test_experts)
    print(f"after {boundary:.1f} s: learned F1 {learned.f1:.3f} "
          f"(precision {learned.precision:.2f}, recall {learned.recall:.2f}); "
          f"rules F1 {rules.f1:.3f} (precision {rules.precision:.2f}, recall {rules.recall:.2f})")
    print("One recording proves little: the cohort numbers, patient held out, are in "
          "docs/EVENTML.md (python -m onset_hfo.eventml candidates / evaluate).")

# %% Which measurements the model leans on (permutation importance on the test part)
if model is not None and len(test) and test["label"].nunique() == 2:
    from sklearn.inspection import permutation_importance

    found = permutation_importance(model, test[list(eventml.FEATURES)].to_numpy(float),
                                   test["label"].to_numpy(int), n_repeats=5, random_state=0)
    order = np.argsort(found.importances_mean)[::-1]
    for i in order:
        print(f"  {eventml.FEATURES[i]:<28} {found.importances_mean[i]:+.3f}")
