# Seed gold labels

`seed_labels.json` contains 84 records from the three development runs
(materials/social/chinese). It is a **regression set**, not independent
validation: the labels were authored during development, so an eval against
them is circular if the same judgments are used.

Use it to prevent regressions in verdict/reason/category after refactors:

```bash
python tests/eval_gold.py --run materials --judgments examples/judgments/materials.semantic.json
python tests/eval_gold.py --run social    --judgments examples/judgments/social.semantic.json
python tests/eval_gold.py --run chinese   --judgments examples/judgments/chinese.semantic.json
```

Before making quality claims, replace or extend this set with independent
human labels (ideally two annotators, report agreement), then report
precision/recall for the semantic exclusion codes.
