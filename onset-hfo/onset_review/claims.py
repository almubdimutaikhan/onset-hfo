"""Check what a drafted paragraph *says*, not only its numbers. Qt-free.

The number check proves that every figure in a draft came out of a query. It
cannot see a sentence that copies the right numbers into the wrong claim --
"AR2-AR3 led at 52 events/min" when 52 is AR1-AR2's rate -- and that is the
mistake a small model makes when it has the facts in front of it and the
wording slips. This module reads a handful of claims a findings or
limitations paragraph makes, and checks each against the analysis:

* **the busiest channel** -- "X led / is the busiest / ranks first", "the
  busiest channel is X": X must be the channel the ranking puts first;
* **standing out** -- "X stands out" needs a ranking that separates its leader
  from the median channel; "no channel stands out" needs one that does not;
* **the tied set** -- "X is tied with Y", "cannot be told apart": every channel
  named must be in the tied set; "not tied" must be true too, and "tied with
  N other channels" must count them right;
* **the quality checks** -- "no contacts were set aside / flagged";
* **the reader's verdicts** -- "the reader has not judged any events", "agreed
  with all", "judged every event";
* **the numbers given to a channel** -- a rate, an event count or an interval
  written right after a channel's name ("AR1-AR2 at 52 events/min, interval
  39-68, n=52") must be that channel's. The number check cannot see this: 52
  came out of a query either way. A number that is another channel's value
  and not the named one's is refused as given to the wrong channel; one that
  is nobody's is left to the number check.

The patterns are deliberately narrow. A sentence they do not recognise is not
checked here -- it still goes through the number and citation checks -- so a
claim this misses is unchecked, never wrongly refused. What they do recognise
is checked exactly, against `facts`, which comes from the session on screen.

Each check returns what it confirmed as well as what it refused, so the report
can say, sentence by sentence, which statements were checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["Facts", "facts_from_session", "check", "ClaimCheck"]

#: Same shape as the guard's channel token, kept local so this module reads on
#: its own; `guard.CHANNEL_TOKEN` is the one the number check uses.
_CHANNEL = r"[A-Za-z]{1,6}'?\d{1,3}(?:-[A-Za-z]{1,6}'?\d{1,3})?"
_CHANNEL_RE = re.compile(rf"\b{_CHANNEL}\b")
_NEGATION = re.compile(r"\b(?:not|no|never|neither|nor|none)\b|n't\b", re.IGNORECASE)

_LEADS = re.compile(
    r"\b(?:led|leads|is the busiest|was the busiest|has the highest rate|had the highest "
    r"rate|ranks? first|ranked first|is ranked first|is the top channel|tops the ranking)\b",
    re.IGNORECASE)
_BUSIEST_IS = re.compile(
    rf"\b(?:busiest|leading|top|top-ranked|highest-rate)\s+(?:channel|contact)"
    rf"(?:\s+(?:is|was))?[\s,:(]+({_CHANNEL})\b", re.IGNORECASE)
_STANDS_OUT = re.compile(r"\bstands? out\b", re.IGNORECASE)
_NOTHING_STANDS_OUT = re.compile(
    r"\b(?:no (?:single )?(?:channel|contact)|nothing|none of the channels)\s+stands? out\b",
    re.IGNORECASE)
_TIED = re.compile(
    r"\b(?:tied|cannot be told apart|can't be told apart|could not be told apart|"
    r"indistinguishable|overlap(?:s|ping)? (?:with )?the busiest)\b", re.IGNORECASE)
_NO_OTHER_TIED = re.compile(
    r"\bno (?:other )?(?:channels?|contacts?)\s+(?:is |are |was |were )?"
    r"(?:statistically )?(?:tied|indistinguishable)|\bnot tied with any\b|\btied with no\b",
    re.IGNORECASE)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10}
_TIED_COUNT = re.compile(
    r"\btied with (\d+|one|two|three|four|five|six|seven|eight|nine|ten) other "
    r"(?:channels?|contacts?)\b", re.IGNORECASE)
_NONE_ASIDE = re.compile(
    r"\bno (?:contacts?|channels?) (?:were|was|are|is|had to be) (?:set aside|excluded)\b|"
    r"\bnone of the (?:contacts|channels) (?:were|was) (?:set aside|excluded)\b",
    re.IGNORECASE)
_NONE_FLAGGED = re.compile(
    r"\bno (?:contacts?|channels?) (?:were|was|are|is) flagged\b|"
    r"\bnone of the (?:contacts|channels) (?:were|was) flagged\b", re.IGNORECASE)
_NOT_JUDGED = re.compile(
    r"\b(?:has not|hasn't|have not|haven't|has yet to|not yet) (?:judged|reviewed)\b|"
    r"\bno events? (?:have|has) (?:yet )?been (?:judged|reviewed)\b", re.IGNORECASE)
_AGREED_ALL = re.compile(r"\bagreed with (?:all|every)\b", re.IGNORECASE)
_JUDGED_ALL = re.compile(
    r"\b(?:judged|reviewed) (?:all|every)\b|"
    r"\ball (?:of the )?(?:accepted )?events (?:have been|were) (?:judged|reviewed)\b",
    re.IGNORECASE)
#: Clauses are checked one at a time, so the subject of "led" is the channel
#: in front of it in the same clause, not one from an earlier one.
_CLAUSE = re.compile(r";|:|\bbut\b|\bwhile\b|\bwhereas\b|\balthough\b", re.IGNORECASE)


@dataclass
class Facts:
    """What a paragraph about this window can be held to."""

    leader: str = ""                    #: the busiest channel, upper case
    distinguishable: bool = False       #: whether the ranking separates it
    tied: list[str] = field(default_factory=list)   #: the tied set, leader included
    set_aside: int | None = None        #: None: the quality checks did not run
    flagged: int | None = None
    judged: int | None = None           #: None: no read attached
    disagree: int = 0
    unsure: int = 0
    accepted: int = 0                   #: events the reader could judge
    #: Channel -> {"rate", "n", "low", "high"} from the primary detector's
    #: findings, upper-case names: what a number given to a channel is held to.
    values: dict[str, dict[str, float]] = field(default_factory=dict)
    #: Detectors other than the primary one: a clause that names one is about
    #: their numbers, not the findings', and its numbers are not checked here.
    other_detectors: list[str] = field(default_factory=list)


@dataclass
class ClaimCheck:
    problems: list[str] = field(default_factory=list)
    #: (sentence, what was checked) for every claim that held.
    confirmed: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def facts_from_session(session) -> Facts:
    """The facts, read off the session the reviewer is looking at."""
    leader = getattr(session, "leader", None) or {}
    facts = Facts()
    if leader.get("available"):
        facts.leader = str(leader.get("leader") or "").upper()
        facts.distinguishable = bool(leader.get("distinguishable"))
        facts.tied = [str(c).upper() for c in getattr(session, "candidates", []) or []]
    quality = getattr(session, "quality", None)
    if quality is not None and len(quality):
        facts.set_aside = int((~quality["good"]).sum())
        facts.flagged = int(quality["flagged"].sum()) if "flagged" in quality else 0
    findings = getattr(session, "findings", None)
    if findings is not None and len(findings) and "rate_per_min" in findings:
        for row in findings.to_dict("records"):
            entry = {"rate": row.get("rate_per_min"), "n": row.get("n_events"),
                     "low": row.get("rate_ci_low"), "high": row.get("rate_ci_high")}
            facts.values[str(row["channel"]).upper()] = {
                k: float(v) for k, v in entry.items()
                if v is not None and v == v}           # drop NaN: no clean time
    request = getattr(session, "request", None)
    primary = str(getattr(request, "primary", "") or "")
    facts.other_detectors = sorted(
        {str(e.detector) for e in getattr(session, "events", []) or []} - {primary})
    read = getattr(session, "read", None)
    if read is not None:
        counts = read.counts()
        facts.judged = int(counts["judged"])
        facts.disagree, facts.unsure = int(counts["disagree"]), int(counts["unsure"])
        primary = session.request.primary
        facts.accepted = sum(1 for e in session.events
                             if e.accepted and e.detector == primary)
    return facts


def _channels(text: str) -> list[str]:
    return [c.upper() for c in _CHANNEL_RE.findall(text)]


#: What may sit between channels that share a verb: "A, B and C led".
_JOINER = re.compile(r"^[\s,]*(?:and|&|or)?[\s,]*$", re.IGNORECASE)


_PREPOSITION = re.compile(
    r"\b(?:with|than|from|to|of|over|against|versus|vs\.?|beside|besides|unlike|like)\s*$",
    re.IGNORECASE)


def _subject(before: str) -> list[str]:
    """The channels that are the subject of a verb: the run of channel names
    immediately in front of it, joined only by commas and "and". In "compared
    with AR3-AR4, AR1-AR2 led" the subject is AR1-AR2 alone."""
    matches = list(_CHANNEL_RE.finditer(before))
    if not matches:
        return []
    # The last name must sit close to the verb: "AR1-AR2 at 52 events/min led"
    # is unusual, "AR1-AR2 has led" is not; a long gap means another subject.
    gap = before[matches[-1].end():]
    if len(gap.split()) > 6:
        return []
    run = [matches[-1]]
    for match in reversed(matches[:-1]):
        if not _JOINER.match(before[match.end():run[0].start()]):
            break
        # "Compared with AR3-AR4, AR1-AR2 led": a channel that is the object of
        # a preposition is not a subject, and neither is anything before it.
        if _PREPOSITION.search(before[:match.start()]):
            break
        run.insert(0, match)
    return list(dict.fromkeys(m.group(0).upper() for m in run))


def check(text: str, facts: Facts) -> ClaimCheck:
    """Every recognised claim in `text`, checked against `facts`."""
    from onset_review.draftevidence import split_sentences

    out = ClaimCheck()
    for sentence in split_sentences(text):
        for clause in _CLAUSE.split(sentence):
            _check_clause(sentence, clause, facts, out)
            _check_values(sentence, clause, facts, out)
    return out


# -- numbers given to a channel ----------------------------------------------
_RATE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:events?\s*)?(?:/\s*min\b|per\s+min(?:ute)?\b)", re.IGNORECASE)
_COUNT = re.compile(
    r"\bn\s*=\s*(\d+)\b|\b(\d+)\s+(?:detected\s+|accepted\s+)?events?\b(?!\s*(?:/|per\b))",
    re.IGNORECASE)
_INTERVAL = re.compile(
    r"\b(?:interval|CI|confidence interval)\b[^\d]{0,12}(\d+(?:\.\d+)?)\s*"
    r"(?:-|\u2013|\u2014|to)\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
#: Words after a channel's name that hand the sentence to something else: what
#: follows "the median channel at 5/min" is not the named channel's.
_HANDOVER = re.compile(
    r"\b(?:median|mean|average|other|others|rest|remaining|next|second|third|than|"
    r"compared|versus|vs|whereas|while|followed|ahead|behind|against|across|overall|"
    r"total|together|combined|expert|experts|annotators?|marked|threshold)\b",
    re.IGNORECASE)
#: A clause about the archive's own markings or another detector is about
#: numbers the findings do not hold.
_ELSEWHERE = re.compile(r"\b(?:expert|experts|annotators?|annotated|marked|markings)\b",
                        re.IGNORECASE)
_KINDS = {"rate": "a rate of {v}/min", "n": "{v} events",
          "low": "an interval from {v}", "high": "an interval up to {v}"}
_SHOW = {"rate": "{v:.1f}/min", "n": "{v:.0f} events", "low": "{v:.1f}", "high": "{v:.1f}"}


def _same(said: float, actual: float) -> bool:
    """The number check's rounding rule: 52 is 52.0, 12.3 is 12.345."""
    return (abs(actual - said) <= max(0.05, 0.01 * abs(actual))
            or abs(round(actual, 1) - said) <= 0.051 or abs(round(actual) - said) < 1e-9)


def _quantities(tail: str) -> list[tuple[str, float]]:
    """(kind, value) for the rates, counts and interval bounds in `tail`."""
    found: list[tuple[int, str, float]] = []
    taken: list[tuple[int, int]] = []
    for match in _INTERVAL.finditer(tail):
        found += [(match.start(1), "low", float(match.group(1))),
                  (match.start(2), "high", float(match.group(2)))]
        taken.append(match.span())
    for match in _RATE.finditer(tail):
        if any(a <= match.start() < b for a, b in taken):
            continue
        found.append((match.start(), "rate", float(match.group(1))))
        taken.append(match.span())
    for match in _COUNT.finditer(tail):
        if any(a <= match.start() < b for a, b in taken):
            continue
        found.append((match.start(), "n", float(match.group(1) or match.group(2))))
    return [(kind, value) for _, kind, value in sorted(found)]


def _check_values(sentence: str, clause: str, facts: Facts, out: ClaimCheck) -> None:
    if not facts.values or _ELSEWHERE.search(clause):
        return
    for name in facts.other_detectors:
        pattern = r"\b" + re.escape(name).replace("_", "[ _-]?") + r"\b"
        if re.search(pattern, clause, re.IGNORECASE):
            return
    names = list(_CHANNEL_RE.finditer(clause))
    for i, match in enumerate(names):
        channel = match.group(0).upper()
        own = facts.values.get(channel)
        if own is None:
            continue
        stop = names[i + 1].start() if i + 1 < len(names) else len(clause)
        tail = clause[match.end():stop]
        handover = _HANDOVER.search(tail)
        if handover:
            tail = tail[:handover.start()]
        # Close to the name only: "AR1-AR2 led the ranking at 52 events/min".
        tail = " ".join(tail.split()[:10])
        for kind, said in _quantities(tail):
            if kind not in own:
                continue
            if _same(said, own[kind]):
                out.confirmed.append(
                    (sentence, f"{channel}: {_KINDS[kind].format(v=f'{said:g}')}"))
                continue
            owners = [c for c, v in facts.values.items()
                      if c != channel and kind in v and _same(said, v[kind])]
            if owners:
                out.problems.append(
                    f'"{sentence}" gives {channel} {_KINDS[kind].format(v=f"{said:g}")}, '
                    f"which is {owners[0]}'s; {channel}'s is "
                    + _SHOW[kind].format(v=own[kind]))


def _check_clause(sentence: str, clause: str, facts: Facts, out: ClaimCheck) -> None:
    def fail(message: str) -> None:
        out.problems.append(f'"{sentence}" {message}')

    def hold(description: str) -> None:
        out.confirmed.append((sentence, description))

    # "can't be told apart" is a tie, not a negation.
    negated = bool(_NEGATION.search(_TIED.sub(" ", clause)))

    # -- the busiest channel ---------------------------------------------
    for match in _BUSIEST_IS.finditer(clause):
        named = match.group(1).upper()
        if not facts.leader:
            fail(f"names {named} as the busiest channel, but nothing was detected")
        elif named != facts.leader:
            fail(f"names {named} as the busiest channel; the ranking puts "
                 f"{facts.leader} first")
        else:
            hold(f"{named} is the busiest channel")
    lead = _LEADS.search(clause)
    if lead and not negated:
        subjects = _subject(clause[:lead.start()])
        if len(subjects) == 1:
            if not facts.leader:
                fail(f"says {subjects[0]} led, but nothing was detected")
            elif subjects[0] != facts.leader:
                fail(f"says {subjects[0]} led; the ranking puts {facts.leader} first")
            else:
                hold(f"{subjects[0]} is the busiest channel")
        elif subjects:
            # "AR1-AR2 and AR2-AR3 led": a shared lead is a claim about the
            # tied set, and it has to include the channel the ranking puts first.
            if facts.leader not in subjects:
                fail(f"says {' and '.join(subjects)} led; the ranking puts "
                     f"{facts.leader} first")
            for other in subjects:
                if other not in facts.tied:
                    fail(f"puts {other} among the leaders, but it is not tied with "
                         f"{facts.leader}")
            if facts.leader in subjects and all(c in facts.tied for c in subjects):
                hold(f"{' and '.join(subjects)} lead together (the tied set)")

    # -- standing out -----------------------------------------------------
    if _NOTHING_STANDS_OUT.search(clause):
        if facts.distinguishable:
            fail(f"says no channel stands out, but {facts.leader}'s interval is "
                 "clear of the median channel's")
        else:
            hold("no channel stands out")
    elif _STANDS_OUT.search(clause) and not negated:
        subjects = _channels(clause[:_STANDS_OUT.search(clause).start()])
        if subjects:
            if not facts.distinguishable:
                fail(f"says {subjects[-1]} stands out, but the busiest channel's "
                     "interval overlaps the median channel's: nothing stands out")
            elif subjects[-1] != facts.leader:
                fail(f"says {subjects[-1]} stands out; the channel that does is "
                     f"{facts.leader}")
            else:
                hold(f"{subjects[-1]} stands out")

    # -- the tied set -----------------------------------------------------
    if _NO_OTHER_TIED.search(clause):
        others = [c for c in facts.tied if c != facts.leader]
        if others:
            fail(f"says no other channel is tied, but {', '.join(others)} "
                 f"{'is' if len(others) == 1 else 'are'} tied with {facts.leader}")
        else:
            hold("no other channel is tied with the busiest")
    elif _TIED.search(clause):
        named = list(dict.fromkeys(_channels(clause)))
        if negated:
            wrong = [c for c in named if c != facts.leader and c in facts.tied]
            for channel in wrong:
                fail(f"says {channel} is not tied, but it is in the tied set")
            if named and not wrong:
                hold(f"{', '.join(c for c in named if c != facts.leader) or named[0]} "
                     "not tied with the busiest")
        else:
            wrong = [c for c in named if c not in facts.tied]
            for channel in wrong:
                fail(f"says {channel} is tied with the busiest channel, but it is not "
                     f"in the tied set ({', '.join(facts.tied) or 'empty'})")
            if named and not wrong:
                hold(f"{', '.join(named)} in the tied set")
        count = _TIED_COUNT.search(clause)
        if count and not negated:
            said = count.group(1).lower()
            said_n = int(said) if said.isdigit() else _WORDS[said]
            actual = max(0, len(facts.tied) - 1)
            if said_n != actual:
                fail(f"says the busiest channel is tied with {said_n} other(s); it is "
                     f"tied with {actual}")
            else:
                hold(f"tied with {actual} other channel(s)")

    # -- the quality checks -----------------------------------------------
    if _NONE_ASIDE.search(clause) and facts.set_aside is not None:
        if facts.set_aside:
            fail(f"says no contacts were set aside; the quality checks set aside "
                 f"{facts.set_aside}")
        else:
            hold("no contacts were set aside")
    if _NONE_FLAGGED.search(clause) and facts.flagged is not None:
        if facts.flagged:
            fail(f"says no contacts were flagged; the quality checks flagged "
                 f"{facts.flagged}")
        else:
            hold("no contacts were flagged")

    # -- the reader's verdicts --------------------------------------------
    if facts.judged is None:
        return
    if _NOT_JUDGED.search(clause):
        if facts.judged:
            fail(f"says the reader has not judged any events; {facts.judged} are judged")
        else:
            hold("the reader has judged no events")
    if _AGREED_ALL.search(clause) and not negated:
        if not facts.judged or facts.disagree or facts.unsure:
            fail(f"says the reader agreed with all; of {facts.judged} judged, "
                 f"{facts.disagree} disagree and {facts.unsure} unsure")
        else:
            hold("the reader agreed with every judged event")
    if _JUDGED_ALL.search(clause) and not negated:
        if facts.judged < facts.accepted:
            fail(f"says every event was judged; {facts.judged} of {facts.accepted} are")
        else:
            hold("every accepted event is judged")
