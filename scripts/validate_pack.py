"""Validate that clinical_spec/ files exist and parse correctly."""

import argparse, csv, json
from pathlib import Path

import yaml
from jsonschema.validators import validator_for

EXPECTED = [
    "scope.md",
    "heart_score_rules.md",
    "red_flags.md",
    "policy_rules.yaml",
    "decision_table.csv",
    "answer_schema.json",
    "system_prompt.md",
]
POLICY_KEYS = {"pack_name", "heart_score_components", "score_interpretation", "core_rules"}
CSV_COLUMNS = {
    "total_score_range",
    "risk_tier",
    "recommended_disposition",
    "requires_serial_troponins",
    "cardiology_consult",
}


def report(ok, label):
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-dir", type=Path, default=Path(__file__).resolve().parents[1] / "clinical_spec")
    spec = parser.parse_args().spec_dir
    failed = False
    for name in EXPECTED:
        failed |= not report((spec / name).exists(), f"{name} exists")
    try:
        policy = yaml.safe_load((spec / "policy_rules.yaml").read_text())
        ok = isinstance(policy, dict) and POLICY_KEYS <= policy.keys()
        failed |= not report(ok, "policy_rules.yaml parses and has required keys")
    except Exception as exc:
        failed |= not report(False, f"policy_rules.yaml invalid ({exc})")
    try:
        schema = json.loads((spec / "answer_schema.json").read_text())
        validator_for(schema).check_schema(schema)
        failed |= not report(True, "answer_schema.json parses and is a valid JSON Schema")
    except Exception as exc:
        failed |= not report(False, f"answer_schema.json invalid ({exc})")
    try:
        with (spec / "decision_table.csv").open(newline="") as fh:
            columns = set(csv.DictReader(fh).fieldnames or [])
        failed |= not report(CSV_COLUMNS <= columns, "decision_table.csv has expected columns")
    except Exception as exc:
        failed |= not report(False, f"decision_table.csv invalid ({exc})")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
