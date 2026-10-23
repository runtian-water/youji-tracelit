# Blind semantic judgment task

You are an independent literature-screening annotator. Read:

- `C:/Users/zxzyc/Desktop/tracelit/tests/blind/materials_input.json`
- `C:/Users/zxzyc/Desktop/tracelit/SKILL.md` (semantic rules)
- `C:/Users/zxzyc/Desktop/tracelit/references/reason-codes.md`

Do **not** read `tests/gold`, `tests/make_semantic_*`, or `runs/*.semantic*`.
Those contain reference labels and would invalidate the blind test.

## Task

Topic: perovskite interface passivation. Judge every one of the 28 records in
`materials_input.json`.

Use the materials track:

```text
主题 → 体系 → 手段 → 条件 → 指标
```

Apply first-fail and record one primary reason:

- Exclusion codes: R1/P1/Y1/L1/V1/T1/S1/M1/C1/I1
- Pending codes: D1/D2/D3/D4/E1
- Include: ✓

Rules:

- `✓` and semantic `×` (T1/S1/M1/C1/I1) require `evidence_quote`, a verbatim
  substring of the record's `evidence` (or `title` when evidence is empty).
- Metadata `×` (R1/P1/Y1/L1/V1) and `○` may omit the quote.
- `one_liner` must be non-empty and ≤24 characters.
- `category` is one of `primary|review|background|preprint`. Reviews and
  perspectives should be `background`, not `primary`.
- Do not invent papers, years, or evidence.

## Output

Write exactly this shape to the output path given by the caller:

```json
{
  "mode": "semantic",
  "records": [
    {
      "openalex_id": "W...",
      "verdict": "✓|×|○",
      "reason_code": "",
      "category": "primary|review|background|preprint",
      "evidence_quote": "verbatim substring",
      "one_liner": "≤24 chars"
    }
  ]
}
```

Cover all 28 `openalex_id` values. When done, report only: `done: <output path>`.
