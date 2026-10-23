# Expert feedback pilot

A first round of feedback from people who read EEG, on **public, de-identified
recordings only**. This file has three parts: the protocol for whoever runs it,
the task sheet the participant gets, and the feedback form they fill in after.

> **Status: draft, not yet approved.** The study needs a decision from NU-IREC
> before anyone is invited. Items marked **[TO CONFIRM]** are placeholders for
> that decision. Session lengths below are estimates; time the first session
> and correct them.

## What this pilot can and cannot tell us

It can tell us whether someone who reads EEG can use the reviewer without help,
which screens confuse them, whether the outputs make sense to them, and where
their verdicts on events differ from the detector's and from each other.

It cannot tell us whether the detector is clinically valid. It is a usability
and face-validity round with a handful of readers. Medical PhD students who
work with EEG are a good first audience but are not epileptologists, and any
write-up must say so. Nothing in this pilot touches a real patient.

## Part 1. For whoever runs the pilot

### Rules

* **Public data only.** The recording is the first minute of `sub-01` of
  OpenNeuro ds003498 (CC0, de-identified). Participants are not asked to bring
  or open any recording of their own.
* **Participants are identified by a code** (`P01`, `P02`, …), never by name.
  The code is what goes in the reader field, so it is what is saved in every
  verdict file. Keep the key from code to person, if you keep one, apart from
  the data.
* **No screenshots, screen recordings or click capture.** The feedback is the
  verdict files, the form, and what the participant says.
* Say out loud at the start that the software is a research tool, is not
  validated for clinical use, and that the participant is evaluating the
  software, not being tested.

### Before the session

Prepare the machine once. On Ubuntu, from a checkout:

```bash
./packaging/install-ubuntu.sh --with-sample
```

On other systems, `pip install -e ".[review]"` works, then fetch the one minute
of public data (about 24 MB):

```bash
python -m onset_hfo.cli fetch --subject sub-01 --t-start 0 --t-stop 60
```

The reviewer starts offline and will not download anything unless asked, which
is what you want in a session.

Every participant must open **the same window with the same settings**,
otherwise their events get different keys and their verdicts cannot be matched
for agreement. Use this command, changing only the code:

```bash
ONSET_REVIEW_READS="$HOME/onset-pilot-reads" \
  onset-review --subject sub-01 --window 0 60 --reader P01
```

`ONSET_REVIEW_READS` fixes where verdicts are saved, so you know where to
collect them. `--reader` skips the "who are you" question and records the code.
Use a **fresh reads folder per participant** (or per machine) and leave out
`--expert`, so the annotators' marks do not influence the first judgements.

Check that the window opens and shows a "Does any channel actually stand out?"
sentence before the participant sits down.

### Run of the session (about 60 minutes)

| Time | What |
|---|---|
| 5 min | Welcome, the rules above, consent **[TO CONFIRM wording and form]** |
| 5 min | Background questions (section A of the form) |
| 35 min | The five tasks in Part 2, thinking aloud; you write down where they hesitate |
| 10 min | The feedback form (sections B and C) |
| 5 min | Open conversation; thank them |

Do not explain the software while they work. If they are stuck for more than a
minute, note where and what they tried, then help. Those moments are the most
useful result.

### After the session: collecting and merging verdicts

Copy each participant's reads folder into one study folder, one subfolder per
participant. The file names are identical across participants, so the
subfolders matter:

```
pilot-study/
  P01/sub01-….json
  P02/sub01-….json
```

Then:

```bash
python -m onset_review.verdictmerge pilot-study -o verdicts.csv
```

This writes one row per verdict (window, event, reader, verdict, time, note)
and prints how many events each reader judged as real, not real or cannot tell,
and the agreement between each pair of readers on the events both judged.

Each subfolder is one reader. A participant who left the reader name blank is
told apart by their subfolder, and one name found in two subfolders (two
machines that both call their user `user`) counts as two readers; the summary
says under *Who is who* whenever it had to do either. Keep each participant's
files in their own subfolder and they are never merged into someone else.

Read the agreement figures with their `n`. With a few readers and a few dozen
events a kappa is a rough indication, not a measurement. Files that cannot be
read are named and skipped. Nothing is written back to the participants' files.

## Part 2. Task sheet (give this to the participant)

**What this is.** You are helping us find out whether a research program for
intracranial EEG is understandable and useful to someone who reads EEG. The
recording is one minute of a public, de-identified dataset. It is not a patient
of yours and nothing you do affects anyone's care. We are testing the
software, not you. There are no wrong answers, and "I could not tell what this
meant" is exactly the answer we want.

**What the program is.** It finds high-frequency oscillations (HFOs, ripples at
80–250 Hz) and interictal spikes, removes the ones it thinks are filter
ringing, ranks the channels by how often HFOs occur, and says how sure it is.
It is a research tool, not a medical device.

**Please think aloud**: say what you are looking at, what you expect, and what
confuses you.

### Task 1. Does any channel stand out? (about 5 minutes)

On the **Review → Recording** page, read the sentence under "Does any channel
actually stand out?".

1. Which channel does it name, and which other channels are tied with it?
2. In your own words, what does "tied" mean here?
3. Would you trust this ranking? What would you want to check first?

### Task 2. Judge events (about 15 minutes)

First open the **Events** tab and set the first box to **Ripples only**, so the
list holds HFO candidates and not interictal discharges. Then press **Review
events** in the toolbar. One event fills the screen: the signal as recorded,
the same signal in the HFO band, and a time-frequency picture.

For each of the first **12 events**, give your verdict with one key:

| Key | Meaning |
|---|---|
| `A` | a real event |
| `D` | not real: an artifact, filter ringing, or not an oscillation |
| `U` | you cannot tell |

`←` and `→` step between events, `Backspace` takes a verdict back, and `Esc`
leaves. Your verdicts are saved as you give them.

Tell us how you decided. What did you look at first? Was anything missing from
the screen that you wanted?

### Task 3. Events the program rejected (about 8 minutes)

The program removes some candidate events and keeps the reason. In the
**Events** tab, with **Ripples only** still set, tick **Show rejected**.

Pick **five** rejected events and open each one. For each, read the stated
reason and decide whether you agree with the rejection. Give your own verdict
the same way (`A` means "this was a real event and should not have been
rejected").

Was the reason understandable? Is this the information you would want?

### Task 4. Ask the assistant (about 7 minutes)

Open **Assistant**. It is running in its rule-based mode (no language model),
so its answers are limited. Try the suggested questions, then ask these three:

1. "Which channels have the highest ripple rate?"
2. "Anything stand out?" (one of the suggested buttons)
3. "Which channels should be resected?"

Did the answers help? Was there a question you wanted to ask that it could not answer? What did the third one do, and what did you think of it?

### Task 5. Read the report (about 5 minutes)

Open **Report**. Skim it as you would a report you were given by a colleague.

What is missing? What is unclear? What would you not want to appear?

### Finally

Say in one sentence what you would use this for, and one thing you would never
use it for.

## Part 3. Feedback form

Fill in after the session. Codes only, no names.

**Participant code:** ______   **Date:** ______

### A. Background (before the session)

1. Current role: ☐ medical PhD student ☐ resident ☐ epileptologist /
   neurophysiologist ☐ researcher ☐ other: ______
2. Years working with EEG: ______
3. Experience with intracranial EEG: ☐ none ☐ read it ☐ read and mark it
4. Experience with HFOs: ☐ none ☐ know the concept ☐ have marked them
5. Operating system you normally use: ______

### B. Usability (System Usability Scale)

Mark how much you agree, from 1 (strongly disagree) to 5 (strongly agree).

| # | Statement | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| 1 | I think that I would like to use this system frequently | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2 | I found the system unnecessarily complex | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3 | I thought the system was easy to use | ☐ | ☐ | ☐ | ☐ | ☐ |
| 4 | I think that I would need the support of a technical person to be able to use this system | ☐ | ☐ | ☐ | ☐ | ☐ |
| 5 | I found the various functions in this system were well integrated | ☐ | ☐ | ☐ | ☐ | ☐ |
| 6 | I thought there was too much inconsistency in this system | ☐ | ☐ | ☐ | ☐ | ☐ |
| 7 | I would imagine that most people would learn to use this system very quickly | ☐ | ☐ | ☐ | ☐ | ☐ |
| 8 | I found the system very cumbersome to use | ☐ | ☐ | ☐ | ☐ | ☐ |
| 9 | I felt very confident using the system | ☐ | ☐ | ☐ | ☐ | ☐ |
| 10 | I needed to learn a lot of things before I could get going with this system | ☐ | ☐ | ☐ | ☐ | ☐ |

*Scoring (for whoever analyses it): for odd items subtract 1 from the score; for
even items subtract the score from 5; add the ten results and multiply by 2.5.
The result is 0–100. The scale is Brooke (1986). With so few participants,
report each score and the median, not a mean with an interval.*

### C. What you thought

1. In the "Does any channel stand out?" sentence, was anything unclear?
   ______
2. When you judged events, how often did the picture give you enough to decide?
   ☐ almost always ☐ often ☐ sometimes ☐ rarely
3. What information did you want that the screen did not show? ______
4. Did the reasons given for rejected events make sense? ☐ yes ☐ some ☐ no.
   Which did not? ______
5. How did you feel about the assistant refusing to say which channels to
   resect? ______
6. Is there anything in the program or the report that you think could
   mislead a reader? ______
7. What would you use this for? ______
8. What would you never use it for? ______
9. What one change would make the biggest difference? ______
10. Anything else? ______

## Notes for the people reading the results

* Every participant who found something confusing is telling us about the
  software, not about themselves. Count the confusions and group them before
  deciding what to fix.
* The assistant in this pilot is the deterministic backend. Feedback about it
  is feedback about the guards and the wording, not about a language model.
* The verdicts are on one minute of one public recording. They say nothing
  about how the detector performs on other patients.
* The task sheet above has not been tried with a real participant. Expect to
  revise it after the first session.
