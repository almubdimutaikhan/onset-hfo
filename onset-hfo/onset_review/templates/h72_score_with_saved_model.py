# Template: Score this recording with a saved network
# Group: Learned detection (research)
# Mirrors: nothing on screen: a research view beside the Events list
# About: Load a network saved by the training template, score this recording's candidates, and list where it and the rules decide differently. The window's analysis is not changed.

from onset_hfo import eventml, eventnet
from onset_hfo.preprocess import prepare

MODEL_PATH = Path("models") / "hfo-EEGNet.pt"

# %% Load the network
try:
    import braindecode  # noqa: F401
    HAVE_DL = True
except ImportError:
    HAVE_DL = False
    print("This template needs torch and braindecode: pip install 'onset-hfo[dl]'.")
net = meta = None
if HAVE_DL and MODEL_PATH.exists():
    net, meta = eventnet.load(MODEL_PATH)
    print(f"{meta['class']} trained on {meta.get('trained_on', 'unknown')}, band "
          f"{meta.get('band')}, {meta['sfreq']:g} Hz, cut {meta.get('cut', 0.5):.2f}")
elif HAVE_DL:
    print(f"No network at {MODEL_PATH.resolve()}: run 'Train a braindecode network on HFO "
          "candidates' first, or point MODEL_PATH at one.")

# %% Is this recording what it was trained on?
recording = session.recording
prep = prepare(recording, request.pipeline_config().preprocess, verbose=False)
if net is not None:
    problems = []
    if abs(meta["sfreq"] - prep.sfreq) > 1e-6:
        problems.append(f"sampled at {prep.sfreq:g} Hz, trained at {meta['sfreq']:g} Hz")
    if meta.get("band") and meta["band"] != request.band:
        problems.append(f"band {request.band}, trained on {meta['band']}")
    print("Outside what it was trained on: " + "; ".join(problems) if problems
          else "Same sampling rate and band as the training data.")
    if problems:
        net = None

# %% Score every candidate and compare with the rules
if net is not None:
    analysed = [c for c in findings["channel"] if c in prep.ch_names]
    cands = eventml.candidates_from_prepared(prep, analysed, request.band,
                                             threshold_sd=meta.get("candidate_sd"))
    cands["score_net"] = eventnet.predict(net, eventnet.windows_from_prepared(prep, cands))
    cands["kept_net"] = cands["score_net"] >= float(meta.get("cut", 0.5))
    print(f"{len(cands)} candidates: rules keep {int(cands['rule_accepted'].sum())}, "
          f"the network keeps {int(cands['kept_net'].sum())}")
    differ = cands[cands["kept_net"] != cands["rule_accepted"]]
    print(f"{len(differ)} decided differently -- the ones most worth a look:")
    print(differ[["channel", "start", "duration_ms", "peak_frequency_hz", "rule_accepted",
                  "kept_net", "score_net"]].sort_values("start").head(20).round(3)
          .to_string(index=False))
    per_channel = cands.groupby("channel")[["rule_accepted", "kept_net"]].sum() \
        .sort_values("kept_net", ascending=False)
    print(per_channel.head(10).rename(columns={"rule_accepted": "rules",
                                               "kept_net": "network"}).to_string())
