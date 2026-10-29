# Review of the 2026-10-29 run

80 verified summaries sampled (seed 7), 281 planted-error copies, judged blind by Claude Sonnet
in shuffled batches of 8. Scores are in `scores.md`; every case is in `cases.json`.

## The judge's 3 flags on original (published) summaries

Read against the official text (by Claude, in the session that built this; not an independent
human review):

| File | Verdict on the summary | What the judge found |
|---|---|---|
| BL2026-1444 | Correct | False alarm: the judge's own explanation ends "Marked faithful on re-evaluation". |
| RS2026-2150 | Defensible | A real conflict **in the source**: Section 1 sets the Sheriff's salary "no less than 10 percent lower" than the Chief of Police's (literally: at most 90%), while the Council Office analysis says "no less than 90 percent". The summary follows the analysis. |
| RS2026-2301 | Correct | A real error **in the source**: the Council Office analysis says the grant goes to Pathways Kitchen Corporation, then that the Juvenile Court "recommended the distribution of the funds to Tennessee Voices for Children", apparently carried over from another grant's analysis. |

So: no wrong summaries found in the sample; two problems found in the official record.

## The 6 swapped-name copies the judge accepted

Three aren't errors: the swap kept the meaning ("an agreement between A and B" reversed; the
order of a list of names or streets). Three are real misses:

- RS2026-2075: "a Tennessee Department of Correction grant for the State Trial Courts" became "a
  State Trial Courts grant for the Tennessee Department of Correction" (giver and receiver reversed).
- BL2026-1485: "12802 Old Hickory Boulevard" became "12802 Specific Plan".
- BL2026-1442: "Waste Management, Inc. of Tennessee" became "Inc. of Tennessee, Waste Management".

Counting only real errors, the judge caught 56 of 59 swaps.

## The 4 changed numbers the checker accepted

All four changed a house number of 0 (Metro's placeholder for unnumbered land, as in "0 Godwin
Court") to 3, and a 3 appears elsewhere in each text. A presence check can't tell which clause a
number belongs to; small numbers are the weakest case.
