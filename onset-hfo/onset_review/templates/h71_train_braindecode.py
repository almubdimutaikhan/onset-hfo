# Template: Train a braindecode network on HFO candidates
# Group: Learned detection (research)
# Mirrors: the cohort study in docs/EVENTML.md (python -m onset_hfo.eventnet), on the recording on screen
# About: 200 ms of signal around every candidate, raw and band-passed, fed to any braindecode model you name; trained on the first part of the recording, early-stopped on the next, scored on the rest against the rules, and saved for the scoring template.

from onset_hfo import eventml, eventnet
from onset_hfo.preprocess import prepare

# Any class in braindecode.models that takes n_chans, n_outputs, n_times and
# sfreq: EEGNet, ShallowFBCSPNet, Deep4Net, EEGNeX, ATCNet, EEGConformer ...
MODEL = "EEGNet"
EPOCHS = 8                 # an upper bound: training stops when validation stops improving
SAVE_TO = Path("models") / f"hfo-{MODEL}.pt"

# %% Is the deep-learning extra installed?
try:
    import braindecode
    import torch
    HAVE_DL = True
    print(f"braindecode {braindecode.__version__}, torch {torch.__version__}; "
          f"{len(eventnet.available_models())} models available, e.g. "
          + ", ".join(eventnet.available_models()[:6]))
except ImportError:
    HAVE_DL = False
    print("This template needs torch and braindecode: pip install 'onset-hfo[dl]'. "
          "Nothing else in the window uses them.")

# %% Candidates and their windows
recording = session.recording
prep = prepare(recording, request.pipeline_config().preprocess, verbose=False)
analysed = [c for c in findings["channel"] if c in prep.ch_names]
band = request.band
experts = eventml.experts_for(recording, band, analysed)
cands = eventml.candidates_from_prepared(prep, analysed, band, experts=experts)
X = eventnet.windows_from_prepared(prep, cands)
labels = cands["label"].to_numpy()
print(f"{len(cands)} candidates, windows {X.shape} (candidate, [signal, band-passed], samples)")
trainable = HAVE_DL and experts is not None and len(cands) and len(set(labels[labels >= 0])) == 2
if not trainable and HAVE_DL:
    print("Training needs expert markings with matched and unmatched candidates; "
          "this recording has none. Open a ds003498 window, or label events yourself.")

# %% Train (first 60 % of the recording), stop early (next 20 %), test (last 20 %)
if trainable:
    order = np.argsort(cands["start"].to_numpy())
    n = len(order)
    train_rows, val_rows, test_rows = (order[: int(0.6 * n)], order[int(0.6 * n): int(0.8 * n)],
                                       order[int(0.8 * n):])
    net, log = eventnet.train(X, labels, train_rows, val_rows, prep.sfreq, model=MODEL,
                              epochs=EPOCHS, per_epoch=5000)
    print(f"{MODEL}: {log['epochs']} epochs, best validation loss {log['best_val_loss']:.3f}")

# %% Score the held-out part against the experts and the rules
if trainable:
    val, test = cands.iloc[val_rows], cands.iloc[test_rows]
    val_start, test_start = val["start"].min(), test["start"].min()
    in_val = experts[(experts["start"] >= val_start) & (experts["start"] < test_start)]
    cut = eventml.best_cut(eventnet.predict(net, X, val_rows), val, in_val)
    prob = eventnet.predict(net, X, test_rows)
    held = experts[experts["start"] >= test_start]
    learned = eventml.score_selection(test[prob >= cut], held)
    rules = eventml.score_selection(test[test["rule_accepted"]], held)
    print(f"after {test_start:.1f} s, cut {cut:.2f} chosen on the validation part: "
          f"{MODEL} F1 {learned.f1:.3f}, rules F1 {rules.f1:.3f}")
    # Say so when nothing was learned, rather than let an F1 stand for a model.
    if log["best_val_loss"] > 0.66:
        print(f"Validation loss {log['best_val_loss']:.3f} is close to chance (0.69): "
              f"{MODEL} learned little from {len(train_rows)} candidates. One recording is "
              "rarely enough; train on the cohort (commands below).")
    if cut <= 0.05 or cut >= 0.95:
        print(f"The cut sits at the end of its range ({cut:.2f}): the scores do not separate "
              "the two kinds of candidate, and the network keeps "
              + ("everything." if cut <= 0.05 else "almost nothing."))
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist([prob[labels[test_rows] == 1], prob[labels[test_rows] == 0]], bins=20,
            label=["matches an expert event", "does not"], stacked=True)
    ax.axvline(cut, color="k", lw=1)
    ax.set_xlabel(f"{MODEL} score")
    ax.set_ylabel("candidates")
    ax.legend(fontsize=8)
    fig.tight_layout()
    plt.show()

# %% Save it for the scoring template
if trainable:
    eventnet.save(net, SAVE_TO, band=band, cut=cut, trained_on=request.label(),
                  candidate_sd=eventml.CANDIDATE_SD[band])
    print(f"saved {SAVE_TO.resolve()}")
    print("For the cohort, a patient held out at a time: python -m onset_hfo.eventml candidates; "
          f"python -m onset_hfo.eventnet windows; python -m onset_hfo.eventnet evaluate --model {MODEL}")
