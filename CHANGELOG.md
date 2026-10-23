# Changelog

## Unreleased

- Repository layout prepared for GitHub: `docs/` index, per-file structure map,
  publishing guide, contribution and security policies, citation metadata.
- Annotation manual moved to `docs/annotation-manual.md` / `.docx`.
- Selected development judgment JSON published under `examples/judgments/` so
  `eval_gold.py` and `score_annotation.py` examples run out of the box.
- Community health files: code of conduct, pull request template, bug report
  template, and clone-based install command in the README.

## 0.5.0 — 2026-10-22

- `evidence_quote` required for `✓` and semantic `×`; audit verifies it is a
  verbatim substring of `evidence`/`title`.
- Seed gold regression set (`tests/gold/seed_labels.json`, 84 records) and
  `tests/eval_gold.py`; explicitly marked as non-independent.
- Prompt-injection guard: control characters stripped from metadata; SKILL
  declares evidence/title untrusted.
- `run` command: search → verify → judgments template; optional audit + docx.
- `docx` command: Markdown report → minimal A4 Word document (stdlib only).
- Gap threshold: `hits < 50` or `share < 5%`; no hard-filled gap candidates.
- 溯迹 report: no gap caveat when no gaps; lexical labels for Top5/representatives.
- CI workflow, MIT license, examples, name unified to `tracelit`.
- Blind evaluation (materials, 3 runs) and drift report in `docs/blind-results.md`;
  boundary examples added to `references/reason-codes.md`.
- `run` and `docx` commands; A4 quickstart and acceptance criteria.

## 0.4.0 — 2026-10-22

- Semantic mode whitelist (`semantic`/`mechanical_smoke`), judgments contract.
- Background/foundational passes; 溯迹 facets/Top5/gaps.
- GB/T rendering, background/preprint sections, fixed tail, Chinese coverage note.
- 8-column audit table, B/P labels, cost/repro block.
- 429 budget/rate split, retry handling, keyless fallback.
