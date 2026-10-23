# Examples

Three semantic-mode reports generated from the 2026-10-22 development runs:

- `materials.semantic.report.md`
- `social.semantic.report.md`
- `chinese.semantic.report.md`

They demonstrate the report format (audit table, B/P sections, repro block, GB/T,
tail, Chinese coverage note). They are **not a benchmark** and their semantic
labels are the seed labels in `tests/gold/seed_labels.json`, authored during
development. Replace with independent human labels before making quality claims.

## Judgments

`judgments/` holds the semantic-mode JSON behind these reports, plus the three
model-B reruns:

- `materials.semantic.json`, `social.semantic.json`, `chinese.semantic.json`
- `modelB.semantic.json`, `modelB2.semantic.json`, `modelB3.semantic.json`

See `judgments/README.md` for provenance and scoring commands. All of these are
development artifacts or model annotations, never human validation.
