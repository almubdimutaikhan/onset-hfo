"""Sentence by sentence: what a drafted paragraph rests on. Qt-free.

The assistant's draft of a report paragraph passes the same checks as any
answer -- every citation resolves, every number traces to a tool result --
but a passed check is a yes/no on the whole paragraph. A reader signing the
report needs it line by line: for this sentence, which windows of the signal,
and for this number, which query. This module works that out from the answer
the agent returned, with no model involved, so the report and the Report page
can show it next to the paragraph.

Each sentence gets

* ``evidence`` -- evidence ids for the channels it names: the ones the answer
  cited first, then other windows a tool returned for that channel, at most
  two per channel; and
* ``numbers`` -- each number the number check looks at, with the tool call(s)
  that returned it, or an empty source for a small count the check lets
  through ("3 channels").

When the reader edits the paragraph, sentences they did not change keep their
evidence and the rest lose it (:func:`keep_unchanged`): an edited sentence is
the reader's, and nothing here checked it.
"""

from __future__ import annotations

import re

__all__ = ["split_sentences", "annotate", "keep_unchanged", "describe_evidence",
           "markdown_lines", "analysis_basis", "DRAFT_QUESTION", "LIMITS_QUESTION",
           "quotes_verdicts", "stale_on_verdicts", "describe_verdicts"]

#: What the assistant is asked when the Report page asks for a draft. The
#: briefing already carries the leaders, their evidence and the detectors'
#: disagreements, so the question names the shape of the paragraph and
#: nothing the model could not have been given.
DRAFT_QUESTION = ("Draft the findings paragraph of this window's report in three to six "
                  "sentences: which channels led and at what rate, whether they are tied "
                  "with others, whether the two detectors agreed, what the reader's own "
                  "verdicts on the events say, if the reader has judged any, and what "
                  "limits the finding. State only numbers from the evidence, as "
                  "measurements.")

#: The limitations paragraph. Worded around the guard: it asks what limits
#: the analysis, never what a reader should do about it, so the question is
#: never refused before the model sees it. `data_quality` and
#: `reader_verdicts` are in its briefing, so every number it needs was
#: returned by a query and passes the number check.
LIMITS_QUESTION = ("Draft the limitations paragraph of this window's report in three to "
                   "five sentences: how long the analysed window is, how many contacts "
                   "the quality checks set aside or flagged, how many channels are tied "
                   "with the busiest one, whether the detectors disagree, and how much of "
                   "the window the reader has judged. State only numbers from the "
                   "evidence, as measurements.")


#: A sentence ends at . ! or ? followed by space and a capital or a digit.
#: Decimals ("52.3") and evidence ids ("sub-01|AR1-AR2|rms|12.31") have no
#: space after the point, so they are never split.
_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")
PER_CHANNEL = 2


def split_sentences(text: str) -> list[str]:
    """The sentences of a paragraph, in order, stripped; empty pieces dropped."""
    flat = " ".join(str(text or "").split())
    return [piece.strip() for piece in _END.split(flat) if piece.strip()]


def _channel(evidence_id: str) -> str:
    parts = str(evidence_id).split("|")
    return parts[1].upper() if len(parts) >= 4 else ""


def annotate(text: str, answer, facts=None) -> list[dict]:
    """One entry per sentence of `text`: the sentence, the evidence ids behind
    the channels it names, each checked number with its source, and -- with
    `facts` (`onset_review.claims.Facts`) -- each claim about the ranking, the
    tied set, the quality checks or the reader's verdicts that was checked.

    `answer` is the :class:`onset_agent.agent.AgentAnswer` the text came from;
    only its ``evidence_ids``, ``retrieved`` and ``number_sources`` are read.
    """
    from onset_agent import guard

    confirmed: dict[str, list[str]] = {}
    if facts is not None:
        from onset_review import claims

        for sentence, description in claims.check(text, facts).confirmed:
            confirmed.setdefault(sentence, [])
            if description not in confirmed[sentence]:
                confirmed[sentence].append(description)

    cited = [str(i) for i in (getattr(answer, "evidence_ids", None) or [])]
    retrieved = [str(i) for i in (getattr(answer, "retrieved", None) or [])]
    sources = dict(getattr(answer, "number_sources", None) or {})
    pool = cited + [i for i in retrieved if i not in cited]
    out: list[dict] = []
    for sentence in split_sentences(text):
        named = [token.upper() for token in guard.CHANNEL_TOKEN.findall(sentence)]
        evidence: list[str] = []
        for channel in dict.fromkeys(named):
            mine = [i for i in pool if _channel(i) == channel][:PER_CHANNEL]
            evidence += [i for i in mine if i not in evidence]
        numbers = []
        for raw, unit in guard.numbers_in(sentence):
            value = float(raw)
            # A bare small whole number ("3 channels", "0 disagree") is let
            # through by the check without being looked up, and a 3 comes back
            # from half the queries; naming one of them would be a guess.
            small = (not unit and value == int(value)
                     and abs(value) <= guard.MAX_FREE_INTEGER)
            labels = [] if small else guard.traced_to(round(value, 4), sources)
            numbers.append({"value": raw + _unit(unit), "source": "; ".join(labels)})
        out.append({"sentence": sentence, "evidence": evidence, "numbers": numbers,
                    "claims": confirmed.get(sentence, [])})
    return out


#: A sentence about the reader's read, when no query says so: the verdict
#: tool's numbers are the sure sign, these words the fallback.
_ABOUT_THE_READ = re.compile(r"\breader\b|\bverdicts?\b|\bjudged\b", re.IGNORECASE)


def quotes_verdicts(entry: dict) -> bool:
    """Whether a drafted sentence rests on the reader's verdicts: a number
    from `reader_verdicts`, a checked claim about them, or words about them."""
    if any("reader_verdicts" in str(n.get("source", "")) for n in entry.get("numbers", [])):
        return True
    if any("reader" in str(c) for c in entry.get("claims", [])):
        return True
    return bool(_ABOUT_THE_READ.search(str(entry.get("sentence", ""))))


def stale_on_verdicts(entries: list[dict], then: dict, now: dict) -> list[str]:
    """The sentences that quote the reader's verdicts, when those have changed
    since the paragraph was drafted; empty when they have not, or when no
    snapshot was taken (a paragraph wholly the reader's)."""
    if not then or not now or then.get("digest") == now.get("digest"):
        return []
    return [str(e.get("sentence", "")) for e in entries or [] if quotes_verdicts(e)]


def describe_verdicts(state: dict) -> str:
    """'12 judged (10 agree, 1 disagree, 1 unsure)'."""
    return (f"{state.get('judged', 0)} judged ({state.get('agree', 0)} agree, "
            f"{state.get('disagree', 0)} disagree, {state.get('unsure', 0)} unsure)")


def _unit(unit: str) -> str:
    if not unit:
        return ""
    return unit if unit.startswith(("/", "%")) else f" {unit}"


def keep_unchanged(entries: list[dict], text: str) -> list[dict]:
    """The entries whose sentence still appears, word for word, in `text`, in
    the order the new text has them. A sentence the reader rewrote has no
    entry: it is theirs, and the report says it was not checked."""
    by_sentence = {str(e.get("sentence", "")): e for e in entries or []}
    return [by_sentence[s] for s in split_sentences(text) if s in by_sentence]


def describe_evidence(evidence_id: str) -> str:
    """'AR1-AR2 at 12.31 s (rms)' for 'sub-01|AR1-AR2|rms|12.31'."""
    parts = str(evidence_id).split("|")
    if len(parts) < 4:
        return str(evidence_id)
    try:
        start = f"{float(parts[3]):.2f} s"
    except ValueError:
        start = parts[3]
    return f"{parts[1]} at {start} ({parts[2]})"


def markdown_lines(text: str, entries: list[dict], stale: list[str] = ()) -> list[str]:
    """The paragraph's sentences as a list, each with what it rests on.

    A sentence with an entry lists its windows, its numbers' sources and the
    claims that were checked; one without an entry (written or rewritten by
    the reader) says it was not checked against the analysis. A sentence in
    `stale` quotes verdicts that have changed since. Nothing is listed for an
    empty text.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []
    by_sentence = {str(e.get("sentence", "")): e for e in entries or []}
    lines = ["**What each sentence rests on**", ""]
    for number, sentence in enumerate(sentences, 1):
        short = sentence if len(sentence) <= 90 else sentence[:87].rstrip() + "…"
        entry = by_sentence.get(sentence)
        if entry is None:
            lines.append(f"{number}. “{short}” — written or edited by the reader; "
                         "not checked against the analysis.")
            continue
        parts = []
        if entry.get("evidence"):
            parts.append("windows: " + ", ".join(describe_evidence(i)
                                                 for i in entry["evidence"]))
        traced = [f"{n['value']} ← {n['source']}" for n in entry.get("numbers", [])
                  if n.get("source")]
        counts = [n["value"] for n in entry.get("numbers", []) if not n.get("source")]
        if traced:
            parts.append("numbers: " + "; ".join(traced))
        if counts:
            parts.append("small counts, not looked up: " + ", ".join(counts))
        if entry.get("claims"):
            parts.append("checked: " + "; ".join(entry["claims"]))
        if sentence in set(stale):
            parts.append("**the reader's verdicts have changed since this was drafted**")
        lines.append(f"{number}. “{short}” — " + (" · ".join(parts) if parts
                                                   else "no channel or number to trace."))
    return lines + [""]


def analysis_basis(request) -> str:
    """The settings a paragraph's numbers depend on, in one line.

    A reader's verdicts are filed under the window rather than the analysis
    (`adjudication.window_id`), so a paragraph saved with them comes back when
    the same window is re-analysed at another threshold or band. Comparing
    this line is how the report tells a paragraph about the analysis on the
    page from one about an earlier analysis of the same signal.
    """
    start, stop = request.span()
    threshold = ("default" if request.threshold_sd is None
                 else f"{float(request.threshold_sd):g} SD")
    kept = ",".join(sorted(request.keep_channels)) or "-"
    return " · ".join([
        request.band_label(), "+".join(request.detectors), threshold,
        request.preprocess_label(),
        "quality checks " + ("on" if request.check_quality else "off"),
        f"kept {kept}", f"{start:g}-{stop:g} s"])
