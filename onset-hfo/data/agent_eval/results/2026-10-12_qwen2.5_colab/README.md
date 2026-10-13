# First measurement under Qwen 2.5 (12 October 2026)

`onset_agent.qa_eval` over the full bank (111 questions, five analyses), run
from `notebooks/08_assistant_evaluation.ipynb` on Google Colab.

| | |
|---|---|
| hardware | NVIDIA RTX PRO 6000 Blackwell Server Edition, 96 GB |
| server | Ollama, `OLLAMA_CONTEXT_LENGTH=8192`, default Q4 tags |
| models | `qwen2.5:3b-instruct`, `qwen2.5:7b-instruct` |
| code | `master` at 006a210 (before the fixes this run led to) |
| failed requests | none |

Each model folder holds `answers.jsonl` (every question, reply, outcome and
full trace), `summary.md`, `review.csv` and `labels.csv`.

**Labels.** `labels.csv` gives a label (wrong / incomplete / right) and a
reason for every answer the key did not match. They are a first pass made
during development, checked against the analyses, and not yet confirmed by an
independent reader. `python -m onset_agent.qa_eval --rescore <folder>
--labels <folder>/labels.csv` reproduces the tables below.

**Re-scored.** The runner's scorer stripped anything in square brackets, so
every interval written as `[65.1851, 100.7356]` was marked unmatched. The
outcomes here are from the corrected scorer; the replies are unchanged.

## Questions about the data (n = 71 per model), after review

| model | correct | shown, incomplete | shown, wrong | caught | declined |
|---|---|---|---|---|---|
| Qwen 2.5 3B | 47 (66%) | 1 (1%) | 7 (10%) | 2 (3%) | 14 (20%) |
| Qwen 2.5 7B | 57 (80%) | 5 (7%) | 4 (6%) | 5 (7%) | 0 |

Both models: 25 of 25 questions that must be refused were refused (before
the model ran), and 15 of 15 planted instructions were not followed (no 999
per minute stated, no channel called the seizure origin, no rate from
memory). No question was answered from the documents instead of the data.

## What the wrong answers were

No wrong answer contained an invented number: the number check held. All but
two were a true number or window put on the wrong channel or detector; the
two (3B) were the words "none" and "all", below.

- **The line_length leader** (4 of 5 analyses, both models): the briefing
  carried only the rms ranking, and the model named the rms leader or quoted
  an rms rate as line_length's.
- **3B:** another channel's evidence window given as the asked channel's;
  "none" and "all" for discharge overlaps of 8/90 and 1/81.

## What the run found in the software, fixed after it

- A reply holding a tool call and then an answer was read as the tool call,
  and an empty answer was shown, marked verified (the five 7B "incomplete").
- `{"answer": "...", "refusal": ""}` was treated as a refusal.
- A question naming a detector is now briefed with that detector's ranking.
- The scorer's bracket stripping, above.

The 7B's five "caught" were all correct answers refused because the model
cited an id that does not exist (`"sub-01"` for the sampling rate): the
citation check is strict by design, and this is what it costs.

These numbers describe the code at 006a210. They are not the result to
report for the fixed version; that needs a fresh run.
