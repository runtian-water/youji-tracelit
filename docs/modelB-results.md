# Model B annotation check

Date: 2026-10-22  
Files: `examples/judgments/modelB*.semantic.json`  
Packet: 40 records (14 materials + 13 social + 13 chinese)

## Structural check

- 40/40 records, 0 missing IDs, 0 duplicates.
- `mode=semantic`.
- audit gate: **0 errors**; all `evidence_quote` values are verbatim substrings
  of `evidence`/`title`; all `one_liner` values ≤24 characters.
- Counts: X=18, O=13, K=4, B=5, P=0, M=40.

## Agreement with development seed

| Field | Agreement | Cohen's κ |
|---|---:|---:|
| verdict | 0.875 | 0.8101 |
| reason_code | 0.875 | 0.8433 |
| category | 0.750 | — |

12 mismatches total; 5 change verdict/reason.

## Main disagreements

1. **False positive**: `W4411050059` (Science and Technology Correspondent
   System) was marked `✓`; it only matches “rural revitalization”, not “digital
   governance”. Seed says `× T1`.
2. **Background/Y1 rule**: `W2017521473`, `W2057858327` are background
   records outside the primary window. They should be `✓ B`, not `× Y1`.
3. **Category only**: several review/background records differ between
   `review` and `background`; both are non-K, so counts are unaffected.
4. **Debatable boundaries**: `W4410090818` (“A balanced view…”) and
   `W4404921314` (smallholder agriculture review) are background candidates;
   Model B excluded them as `T1`. Seed keeps them as `B`; this is a judgment
   call, not a clear model bug.

## Model B2 (re-run)

- File: `examples/judgments/modelB2.semantic.json`
- 40/40 IDs; audit gate **0 errors**.
- Counts: X=19, O=12, K=3, B=6, P=0, M=40.
- vs seed: verdict 0.875, κ 0.8097; reason 0.875, κ 0.8436; category 0.750.
- Improvement: `W4411050059` (STC system) is now correctly `× T1`.
- Remaining 5 verdict/reason mismatches:
  - `W2017521473`, `W2057858327`: still `× Y1`; **our packet bug**: these are
    background records but `background_candidate` was false. Fixed in the packet
    after this run.
  - `W2870063238`: marked `✓ B`; **our packet bug**: title contains
    “Perspectives”, which the old flag matched; now correctly false, so the next
    run should use `○ E1`.
  - `W4410090818` (A balanced view) and `W4404921314` (smallholder agriculture
    review): debatable `B` vs `T1`.
- The aggregate score is therefore confounded by the packet flag bug; re-run
  with the corrected `annotation_packet.json` for a fair comparison.

## Model B3 rerun (corrected packet)

The latest `examples/judgments/modelB3.semantic.json` (00:10) was produced with the corrected
`annotation_packet.json` and overwrote the stale-packet run.

- 40/40; audit gate **0 errors**.
- Counts: X=17, O=13, K=2, B=8, P=0, M=40.
- vs seed: verdict **0.950**, κ **0.9242**; reason 0.950, κ 0.9363;
  category 0.850.
- Only 2 verdict/reason mismatches:
  - `W4410090818` (“A balanced view…”): seed `✓ B`, model `× T1`.
  - `W4404921314` (smallholder agriculture review): seed `✓ B`, model `× T1`.
  Both are debatable B/T1 boundaries, not clear model errors.
- Fixed from earlier runs: S-26/S-27 no longer `× Y1`; S-11 no longer `✓ B`;
  M-11 Preview is now background; C-15 remains `× T1`.
- K=2 matches the seed for this stratified 40-record packet; the `K<3` audit
  warning is expected here and is not a retrieval failure.

**This is the best model run so far, but it is still model-vs-seed, not human
validation.**

## Model B3 (first V3 run, stale packet)

- File: 原始 stale-packet 结果已被覆盖；仓库中的 `examples/judgments/modelB3.semantic.json`
  是最新（修正 packet）版本，本节的数字仅作历史记录。
- 40/40; audit gate **0 errors**.
- Counts: X=19, O=13, K=3, B=5, M=40.
- vs seed: verdict 0.850, κ 0.7714; reason 0.850, κ 0.8125; category 0.725.
- C-15 (STC system) remains fixed as `× T1`.
- **Not a fair V3 test:** the model's own notes say
  `background_candidate=false` for S-26/S-27 and `true` for S-11. The current
  packet has the opposite. It read the **old packet** (pre-flag-fix), not the
  corrected `annotation_packet.json`.
- One more flag gap found: `W4289890585` (Matter Preview, 3 pages, question
  title) has `genre_warning=true`; it should be a background candidate. Fixed.
- Current packet has 9 background candidates.
- Re-run with the current packet before judging V3. Expected corrections:
  S-26/S-27 → `✓ B`; S-11 → `○ E1`; M-11 → `✓ B` (or `E1` if still empty).
  Remaining debatable: `W4410090818`, `W4404921314`.

## Verdict

**Usable as a second model annotator**, not as human validation.

- It passes the structural gate and produces valid quotes.
- Model–model / model–seed agreement is measurable.
- It does not satisfy the v1.0 human–human κ requirement.
- Before using it as a final second rater, fix the background/Y1 rule and the
  “both topic halves” check (rural revitalization **and** digital governance).

## Commands

```bash
python tests/score_annotation.py \
  --labels examples/judgments/modelB.semantic.json \
  --reference tests/gold/seed_labels.json
```

This is model-vs-seed, not human-vs-human.
