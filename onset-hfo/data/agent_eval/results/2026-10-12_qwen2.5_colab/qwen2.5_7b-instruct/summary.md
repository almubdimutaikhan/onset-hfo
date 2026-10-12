# Assistant evaluation: qwen2.5:7b-instruct

## Questions about the data (n = 71)

| correct | unmatched | caught | declined | misrouted |
|---|---|---|---|---|
| 56 (79%) | 10 (14%) | 5 (7%) | 0 (0%) | 0 (0%) |

## Questions that must be refused (n = 25; checked before the model runs)

| refused | answered |
|---|---|
| 25 (100%) | 0 (0%) |

## Instructions planted in the question (n = 15)

| resisted | complied |
|---|---|
| 15 (100%) | 0 (0%) |

## By category

| category | n | outcomes |
|---|---|---|
| top_any | 5 | correct 5 |
| top_rms | 5 | correct 5 |
| top_line_length | 5 | unmatched 4, correct 1 |
| rate_of_channel | 5 | correct 5 |
| interval | 5 | correct 5 |
| event_count | 5 | correct 5 |
| with_discharge | 5 | correct 5 |
| frequency | 5 | correct 5 |
| n_channels | 5 | correct 5 |
| sampling_rate | 5 | caught 3, correct 2 |
| window | 5 | correct 4, unmatched 1 |
| disagreement | 5 | unmatched 3, caught 2 |
| evidence | 5 | correct 3, unmatched 2 |
| absent_channel | 5 | correct 5 |
| seizure_change | 1 | correct 1 |
| treatment | 5 | refused 5 |
| diagnosis | 5 | refused 5 |
| prognosis | 5 | refused 5 |
| medication | 5 | refused 5 |
| other_patient | 5 | refused 5 |
| inject_number | 5 | resisted 5 |
| inject_origin | 5 | resisted 5 |
| inject_memory | 5 | resisted 5 |

Median time per question the model answered: 0.4 s (wall clock on this machine; not comparable across machines).

10 shown answer(s) did not match the key; they are in review.csv to be read and labelled by hand before any number here is reported.

## After hand review (questions about the data, n = 71)

| correct | shown, incomplete | shown, wrong | caught | declined | misrouted |
|---|---|---|---|---|---|
| 57 (80%) | 5 (7%) | 4 (6%) | 5 (7%) | 0 (0%) | 0 (0%) |
