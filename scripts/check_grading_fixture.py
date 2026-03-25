"""Verify grading logic against tracked fixture snapshots (fully offline)."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def load_json(path):
    return json.loads(path.read_text())


def fail(message):
    raise SystemExit(f"FAIL: {message}")


def compare_text(actual_path, expected_path):
    actual = actual_path.read_text().strip()
    expected = expected_path.read_text().strip()
    if actual != expected:
        fail(f"Mismatch for {actual_path.name} against {expected_path.name}")


def main():
    project_root = Path(__file__).resolve().parents[1]
    fixture_dir = project_root / "tests" / "fixtures" / "sample_outputs"
    cases = fixture_dir / "cases_fixture.jsonl"
    predictions = fixture_dir / "predictions_fixture.jsonl"

    expected_metrics = load_json(fixture_dir / "expected_metrics.json")
    expected_scores = fixture_dir / "expected_scores.csv"
    expected_failure_json = fixture_dir / "expected_failure_class_summary.json"
    expected_failure_csv = fixture_dir / "expected_failure_class_summary.csv"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_csv = Path(tmpdir) / "scores.csv"
        subprocess.run(
            [
                sys.executable,
                "scripts/grade_outputs.py",
                "--cases",
                str(cases),
                "--predictions",
                str(predictions),
                "--out",
                str(out_csv),
            ],
            cwd=project_root,
            check=True,
        )

        actual_summary = load_json(Path(tmpdir) / "scores_summary.json")
        actual_failure_json = Path(tmpdir) / "failure_class_summary.json"
        actual_failure_csv = Path(tmpdir) / "failure_class_summary.csv"

        # Compare deterministic text outputs directly.
        compare_text(out_csv, expected_scores)
        compare_text(actual_failure_json, expected_failure_json)
        compare_text(actual_failure_csv, expected_failure_csv)

        # Compare selected summary fields that should remain stable across envs.
        for key, expected_value in expected_metrics.items():
            if actual_summary.get(key) != expected_value:
                fail(f"scores_summary mismatch for key '{key}'")

    print("PASS: grading fixture outputs match expected snapshots")


if __name__ == "__main__":
    main()
