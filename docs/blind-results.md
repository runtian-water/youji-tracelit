# Blind semantic evaluation — materials

Date: 2026-10-22  
Input: 28 materials records, title + evidence only, no labels  
Runs: 3 independent annotator agents, same prompt, no access to `tests/gold`,
`tests/make_semantic_*`, or `runs/*.semantic*`.

## Gate

All 3 blind outputs passed `audit` with `mode=semantic`:

- 0 `evidence_quote` errors.
- All quotes are verbatim substrings of `evidence`/`title`.

This validates the quote gate mechanically, not the semantic correctness.

## Against seed labels (revised)

| Run | verdict | reason_code | category | exact triple |
|---|---:|---:|---:|---:|
| 1 | 0.929 | 0.786 | 0.929 | 0.714 |
| 2 | 0.893 | 0.821 | 0.929 | 0.750 |
| 3 | 0.857 | 0.750 | 0.929 | 0.679 |

Exact triple = verdict + reason_code + category all match.

## Three-run stability

| Pair | exact agreement | drift | verdict agreement |
|---|---:|---:|---:|
| 1 vs 2 | 0.893 | 10.7% | 0.964 |
| 1 vs 3 | 0.929 | 7.1% | 0.929 |
| 2 vs 3 | 0.929 | 7.1% | 0.964 |

Reason-code agreement: 0.893–0.929. Category agreement: 1.000.

## What the disagreements revealed

1. **Empty evidence was labeled too generously.** Two materials records
   (`W4406772389`, `W4280619312`) had empty abstracts and were initially `✓`;
   the blind runs correctly used `E1`. Four Chinese records were revised the
   same way. This is a rule-driven correction, not score tuning.
2. **Remaining reason-code disagreements cluster at M1/T1 and S1/D1.**
   - Examples: surface doping, defect engineering, carrier management were
     sometimes called T1 instead of M1.
   - A no-DOI memristor record was called D1 instead of S1; first-fail says S1.
   - Review articles were sometimes categorized as `background` instead of
     `review`; both are non-K, so this does not change counts.
3. **No quote fabrication.** Every quote was found in the source text.

## Verdict

- Verdict-level accuracy is near the 0.80 target (0.857–0.929).
- Exact triple accuracy is 0.68–0.75, below the 0.80 target.
- Drift is 7.1–10.7%; one pair is slightly above the 10% target.
- Human–model κ is not measured; independent human labels are still required.

**Not v1.0 by the criteria in `docs/acceptance.md`.** Boundary examples were
added to `references/reason-codes.md` §6 (T1 vs S1 vs M1 vs C1 vs I1); the next
step is independent human annotation and a re-run of the blind experiment.
