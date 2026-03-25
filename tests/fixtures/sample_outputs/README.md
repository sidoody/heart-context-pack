# Offline Grading Fixture

This directory stores deterministic fixtures used to test grading in CI without
calling any model API.

## Files

- `cases_fixture.jsonl`: Small mixed-slice gold case set (`canonical`,
  `holdout`, `messy_note`).
- `predictions_fixture.jsonl`: Precomputed structured model outputs.
- `expected_scores.csv`: Expected per-case CSV grading output.
- `expected_failure_class_summary.json`: Expected failure-class JSON summary.
- `expected_failure_class_summary.csv`: Expected failure-class CSV summary.
- `expected_metrics.json`: Stable subset of aggregate summary metrics used for
  snapshot checks.

## How it is used

Run:

```bash
python scripts/check_grading_fixture.py
```

The checker runs `scripts/grade_outputs.py` on the fixture files and compares
the generated outputs against the tracked snapshots.
