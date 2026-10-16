"""What the window adds to the assistant's tool set, bound to its session.

The agent's own tools read a saved table. The window has more: the recording
itself, so a detector can be re-run at another threshold; and the picture
behind the selected event, so "is this one real" can be answered from the
measurements the picture is made of. Both are offered here as tools in the
same shape as the agent's, under the same validation and the same number
check, and the analyses only when the reviewer has ticked the box that
allows them, because each one costs seconds on a CPU.

Nothing here changes the window's analysis. The analyses run on a copy of
the recording through :class:`onset_agent.analysis.AnalysisSession`; the
window's own numbers are the saved table's, as before.
"""

from __future__ import annotations

from onset_agent.tools import Tool, ToolError

__all__ = ["analysis_tools", "explain_tools", "sensitivity_tools", "window_tools",
           "reader_tools", "quality_tools", "ANALYSES", "COST"]

#: The analyses a reviewer may let the assistant run, and what each costs.
#: The research registry has more; its seizure-onset probability estimate is
#: left out on purpose, as the guard refuses that question before any model.
ANALYSES = ("detect_hfo", "detect_spikes", "spectral_power", "compare_detectors",
            "propagation_lead", "channel_qc")
COST = {
    "detect_hfo": "re-runs the detector on the window: a few seconds the first time, "
                  "under a second at another threshold",
    "detect_spikes": "re-runs the discharge detector: a few seconds",
    "spectral_power": "a spectrum per named channel: under a second",
    "compare_detectors": "runs both HFO detectors: several seconds",
    "propagation_lead": "re-runs the detector and times the first event per channel: "
                        "a few seconds",
    "channel_qc": "the quality measures per contact: under a second",
}


def analysis_tools(session) -> dict[str, Tool]:
    """The analysis registry, as agent tools over this window's recording.

    The analysis session is built on first use, so a reviewer who ticks the
    box and never asks for a run pays nothing.
    """
    recording = getattr(session, "recording", None)
    if recording is None:
        return {}
    from onset_agent.analysis import ANALYSIS_TOOLS, AnalysisSession, build_registry

    holder: dict = {}

    def registry():
        if "registry" not in holder:
            analysis = AnalysisSession(recording, session.request.pipeline_config(),
                                       verbose=False)
            holder["registry"] = build_registry(analysis)
        return holder["registry"]

    tools: dict[str, Tool] = {}
    for spec in ANALYSIS_TOOLS:
        if spec.name not in ANALYSES:
            continue

        def handler(_store, _name=spec.name, **arguments):
            run = registry().run(_name, arguments)
            if not run.ok:
                raise ToolError(run.error or "the analysis failed")
            output = dict(run.output) if isinstance(run.output, dict) else {"result": run.output}
            output["run_id"] = run.run_id
            output["runtime_s"] = round(float(run.runtime_s), 2)
            return output

        tools[spec.name] = Tool(spec.name,
                                f"{spec.description} On a copy of this window's recording; "
                                f"{COST.get(spec.name, 'seconds')}.",
                                spec.parameters, handler)
    return tools


def nearest_event(session, channel: str, start: float, within: float = 0.05):
    """The event on `channel` whose onset is nearest `start` (file seconds)."""
    best, best_distance = None, float(within)
    for event in getattr(session, "events", []) or []:
        if str(event.channel) != str(channel):
            continue
        distance = abs(float(event.start) - float(start))
        if distance <= best_distance:
            best, best_distance = event, distance
    return best


def explain_tools(session) -> dict[str, Tool]:
    """One tool: the selected event's own measurements and what they read as."""
    def handler(_store, channel: str, start: float):
        from onset_review import detail

        event = nearest_event(session, channel, start)
        if event is None:
            raise ToolError(f"no event on {channel} at {float(start):.3f} s in this window")
        out = detail.read_event(detail.snapshot(session, event))
        out["start_s"] = round(float(event.start), 3)
        out["stop_s"] = round(float(event.stop), 3)
        return out

    return {"explain_event": Tool(
        "explain_event",
        "Why the event at (channel, start seconds) reads as an oscillation or as filter "
        "ringing: cycles, peak frequency, the in-band peak's prominence at that moment, "
        "and the reading (island, column, unclear). For 'is this event real', 'is this "
        "ringing'.",
        {"type": "object",
         "properties": {"channel": {"type": "string"},
                        "start": {"type": "number",
                                  "description": "onset in seconds of the original recording"}},
         "required": ["channel", "start"], "additionalProperties": False},
        handler)}


def sensitivity_tools(session, allow_run: bool = False) -> dict[str, Tool]:
    """One tool: the threshold re-test, as the Threshold panel computed it.

    Free when the panel has run (the result is kept on the session); otherwise
    it re-runs the detector, which is only offered when the reviewer has
    allowed analyses, since it costs a few seconds.
    """
    cached = getattr(session, "sensitivity", None)
    if cached is None and not allow_run:
        return {}

    def handler(_store):
        from onset_review import sensitivity

        result = getattr(session, "sensitivity", None)
        if result is None:
            result = sensitivity.compute(session)
            try:
                session.sensitivity = result
            except Exception:       # noqa: BLE001
                pass
        return sensitivity.as_dict(result)

    cost = ("already computed by the Threshold panel: free" if cached is not None
            else "re-runs the detector at four thresholds: a few seconds")
    return {"threshold_sensitivity": Tool(
        "threshold_sensitivity",
        "The leading channels re-tested at 1.25x, 1.5x and 2x the detection threshold: "
        f"rates at each, who leads at each, how far the leader holds ({cost}). For "
        "'does this survive a stricter threshold', 'is the ranking robust'.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        handler)}


def window_tools(session, allow_run: bool = False, cache_dir=None, lister=None,
                 loader=None) -> dict[str, Tool]:
    """Two tools over the other cached windows of this recording: list them
    (free), and analyse one with this window's settings and compare the
    leaders (tens of seconds, so only with the reviewer's consent)."""
    from onset_review import windows

    others = windows.other_windows(session, cache_dir=cache_dir, lister=lister)
    if not others:
        return {}

    def list_handler(_store):
        here = windows.summarise(session)
        return {"this_window_s": here["window_s"], "leader_this_window": here["leader"],
                "other_windows": windows.other_windows(session, cache_dir=cache_dir,
                                                       lister=lister),
                "note": ("Each row is another stretch of the same recording on this "
                         "machine. compare_window analyses one with this window's "
                         "settings" + ("." if allow_run else
                                       "; it is offered when the reviewer allows "
                                       "analyses."))}

    tools = {"other_windows": Tool(
        "other_windows",
        "The other windows of this recording on this machine, with start and stop in "
        "seconds and whether each is analysed. Free. For 'is there an earlier minute'; "
        "call before compare_window.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        list_handler)}
    if not allow_run:
        return tools

    def compare_handler(_store, t_start: float, t_stop: float):
        match = [o for o in others if abs(o["t_start"] - float(t_start)) < 1e-6
                 and abs(o["t_stop"] - float(t_stop)) < 1e-6]
        if not match:
            raise ToolError(f"no cached window {float(t_start):g}-{float(t_stop):g} s of this "
                            "recording; other_windows lists the ones there are")
        there = windows.analyse_window(session, t_start, t_stop, cache_dir=cache_dir,
                                       loader=loader)
        out = windows.compare(windows.summarise(session), there)
        out["cached"] = bool(there.get("cached"))
        return out

    tools["compare_window"] = Tool(
        "compare_window",
        "Analyse another window of this recording (t_start, t_stop from other_windows) "
        "with this window's settings and compare leaders and tied sets. Seconds to half "
        "a minute the first time, free after. For 'did the leader change between minutes'.",
        {"type": "object",
         "properties": {"t_start": {"type": "number"}, "t_stop": {"type": "number"}},
         "required": ["t_start", "t_stop"], "additionalProperties": False},
        compare_handler)
    return tools


#: How many channels `reader_verdicts` lists one by one: the busiest, as the
#: ranking orders them. A findings paragraph names a handful, and a long list
#: would crowd the model's context for nothing.
READER_CHANNELS = 8


def reader_tools(session) -> dict[str, Tool]:
    """One tool: what the reader has said about this window's events so far.

    Free -- it reads the verdicts already recorded -- and read-only: the
    assistant can report the reader's read, never add to it. A paragraph that
    says "the reader agreed with 12 of 14 events on AR1-AR2" can only say it
    if this returned those numbers, because they pass the same number check.
    """
    def handler(_store):
        read = getattr(session, "read", None)
        if read is None:
            raise ToolError("no reader's verdicts are attached to this window")
        primary = session.request.primary
        accepted = [e for e in session.events if e.accepted and e.detector == primary]
        progress = read.progress(accepted)
        counts = read.counts()
        order = [str(c) for c in session.findings["channel"]] if len(session.findings) else []
        listed = [c for c in order if c in progress][:READER_CHANNELS]
        channels = [{"channel": c, "judged": progress[c]["judged"],
                     "of_accepted": progress[c]["total"],
                     "agree": progress[c]["agree"], "disagree": progress[c]["disagree"],
                     "unsure": progress[c]["unsure"],
                     "all_judged": progress[c]["complete"],
                     "channel_verdict": progress[c]["verdict"] or "none"}
                    for c in listed]
        verdicts = {str(c): j.verdict for c, j in sorted(read.channels.items())}
        return {
            "reader": read.reader or "not named",
            "accepted_events": len(accepted),
            "judged": counts["judged"], "agree": counts["agree"],
            "disagree": counts["disagree"], "unsure": counts["unsure"],
            "verdicts_from_an_earlier_analysis": counts["orphans"],
            "busiest_channels": channels,
            "channel_verdicts": verdicts,
            "note": ("The reader's own verdicts, as recorded. A channel's confirmed "
                     "rate exists only where all_judged is true; elsewhere say how "
                     "many of its events were judged."),
        }

    return {"reader_verdicts": Tool(
        "reader_verdicts",
        "What the reader decided: events judged agree, disagree or unsure, overall and "
        "for the busiest channels, how many each channel has left, and the channels "
        "the reader accepted or set aside. Free. For 'what did the reader conclude', "
        "'how much has been reviewed'.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        handler)}


def quality_tools(session) -> dict[str, Tool]:
    """One tool: how much of the window the quality stage let through.

    Free. The limitations paragraph is mostly made of these numbers -- how
    long the window is, which contacts were set aside, how many seconds each
    analysed contact kept -- and without a tool returning them the number
    check would refuse every sentence that states one.
    """
    def handler(_store):
        from onset_hfo.quality import REASONS

        start, stop = session.span
        out = {"analysed_s": round(float(stop - start), 3),
               "channels_ranked": int(len(session.findings)),
               "quality_checks": "off"}
        quality = getattr(session, "quality", None)
        if quality is None or not len(quality):
            out["note"] = ("The data-quality checks did not run: every contact was "
                           "analysed and every rate divided by the whole span.")
            return out
        aside = quality[~quality["good"]]
        flagged = quality[quality["flagged"]] if "flagged" in quality else quality.iloc[0:0]
        clean = [float(v) for v in (session.clean_seconds or {}).values()]
        out.update({
            "quality_checks": "on",
            "channels_checked": int(len(quality)),
            "n_set_aside": int(len(aside)),
            "n_flagged": int(len(flagged)),
            "set_aside": [{"channel": str(r.channel),
                           "why": REASONS.get(r.reason, str(r.reason))}
                          for r in aside.itertuples()],
            "analysed_but_flagged": [{"channel": str(r.channel),
                                      "why": REASONS.get(r.reason, str(r.reason))}
                                     for r in flagged.itertuples()],
            "reinstated_by_reader": sorted(str(c) for c in session.request.keep_channels),
        })
        if clean:
            ordered = sorted(clean)
            middle = ordered[len(ordered) // 2] if len(ordered) % 2 else \
                (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2.0
            out["usable_s_per_channel"] = {"min": round(ordered[0], 2),
                                           "median": round(middle, 2),
                                           "max": round(ordered[-1], 2)}
        return out

    return {"data_quality": Tool(
        "data_quality",
        "How much of this window was analysed: its length in seconds, how many "
        "contacts the quality checks set aside or flagged and why, and the usable "
        "seconds per contact. Free. For 'what limits this analysis', 'which contacts "
        "were left out'.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        handler)}
