"""Validate case JSONL files and check gold-label consistency."""

import argparse, json
from pathlib import Path

TOP_LEVEL = {"id", "title", "patient", "difficulty", "expected"}
DISPOSITIONS = {
    "low": "early_discharge_consideration",
    "moderate": "admit_observation_workup",
    "high": "admit_invasive_strategy",
}
SLICE_TO_FILE = {
    "canonical": "cases.jsonl",
    "holdout": "holdout_variants.jsonl",
    "messy_note": "messy_notes.jsonl",
}
GOLD_REQUIRED = {
    "heart_applicable",
    "history_score",
    "ecg_score",
    "age_score",
    "risk_factor_score",
    "troponin_score",
    "total_heart_score",
    "risk_tier",
    "recommended_disposition",
    "safety_flags",
    "key_missing_information",
    "must_not_say",
}
ALLOWED_SPLITS = {"canonical", "holdout", "messy_note"}


def tier(score):
    return "low" if score <= 3 else "moderate" if score <= 6 else "high"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        action="append",
        default=[],
        help="Case file path. Repeat to validate multiple files.",
    )
    parser.add_argument(
        "--slice",
        action="append",
        choices=["canonical", "holdout", "messy_note", "all"],
        default=[],
        help="Named dataset slice to validate. Repeatable.",
    )
    return parser.parse_args()


def resolve_case_paths(project_root, explicit_paths, slices):
    evals_dir = project_root / "evals"
    resolved = []
    seen = set()

    expanded_slices = set(slices or [])
    if "all" in expanded_slices:
        expanded_slices = {"canonical", "holdout", "messy_note"}

    # By default, validate all available slices (canonical + robustness slices).
    if not explicit_paths and not expanded_slices:
        expanded_slices = {"canonical", "holdout", "messy_note"}

    for slice_name in sorted(expanded_slices):
        path = (evals_dir / SLICE_TO_FILE[slice_name]).resolve()
        if path.exists() and str(path) not in seen:
            resolved.append(path)
            seen.add(str(path))

    for path in explicit_paths:
        p = path.expanduser().resolve()
        if str(p) not in seen:
            resolved.append(p)
            seen.add(str(p))

    return resolved


def validate_metadata(case, cid, errors):
    split = case.get("split", "canonical")
    if split not in ALLOWED_SPLITS:
        errors.append(f"{cid}: split must be one of {sorted(ALLOWED_SPLITS)}")
        return

    case_id = case.get("case_id")
    if case_id is not None and case_id != cid:
        errors.append(f"{cid}: case_id must match id when provided")

    if split == "holdout":
        required = ["case_id", "edge_case_type"]
        missing = [field for field in required if field not in case]
        if missing:
            errors.append(f"{cid}: holdout case missing metadata fields {missing}")

    if split == "messy_note":
        required = ["case_id", "input_style"]
        missing = [field for field in required if field not in case]
        if missing:
            errors.append(f"{cid}: messy_note case missing metadata fields {missing}")
        if case.get("input_style") != "messy_note":
            errors.append(f"{cid}: messy_note cases must set input_style to messy_note")


def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    case_paths = resolve_case_paths(project_root, args.cases, args.slice)
    if not case_paths:
        raise SystemExit("No case files found to validate")

    seen, errors, total = set(), [], 0
    for case_path in case_paths:
        if not case_path.exists():
            errors.append(f"{case_path}: file does not exist")
            continue

        for lineno, line in enumerate(case_path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            total += 1
            try:
                case = json.loads(line)
            except Exception as exc:
                errors.append(f"{case_path}: line {lineno}: invalid JSON ({exc})")
                continue
            cid = case.get("id", f"{case_path}:line {lineno}")
            missing = sorted(TOP_LEVEL - case.keys())
            if missing:
                errors.append(f"{cid}: missing top-level fields {missing}")
            if cid in seen:
                errors.append(f"{cid}: duplicate case id")
            seen.add(cid)

            validate_metadata(case, cid, errors)

            expected = case.get("expected")
            if not isinstance(expected, dict):
                errors.append(f"{cid}: expected must be an object")
                continue
            missing = sorted(GOLD_REQUIRED - expected.keys())
            if missing:
                errors.append(f"{cid}: expected missing required fields {missing}")

            if expected.get("heart_applicable") is True:
                keys = ["history_score", "ecg_score", "age_score", "risk_factor_score", "troponin_score", "total_heart_score"]
                if all(isinstance(expected.get(k), int) for k in keys):
                    total_score = sum(expected[k] for k in keys[:-1])
                    if expected["total_heart_score"] != total_score:
                        errors.append(f"{cid}: total_heart_score arithmetic mismatch")
                    if expected.get("risk_tier") != tier(expected["total_heart_score"]):
                        errors.append(f"{cid}: risk_tier inconsistent with total_heart_score")
                if expected.get("risk_tier") in DISPOSITIONS:
                    expected_disposition = DISPOSITIONS[expected["risk_tier"]]
                    actual_disposition = expected.get("recommended_disposition")
                    low_total_trop_override = (
                        expected.get("troponin_score") == 2
                        and isinstance(expected.get("total_heart_score"), int)
                        and expected["total_heart_score"] <= 3
                        and actual_disposition == "admit_observation_workup"
                    )
                    if actual_disposition != expected_disposition and not low_total_trop_override:
                        errors.append(f"{cid}: recommended_disposition inconsistent with risk_tier")
            if expected.get("heart_applicable") is False:
                if expected.get("risk_tier") != "not_applicable":
                    errors.append(f"{cid}: non-applicable cases must use risk_tier not_applicable")
                if expected.get("recommended_disposition") != "emergent_cath_lab":
                    errors.append(f"{cid}: non-applicable cases must use emergent_cath_lab")
            if (
                expected.get("troponin_score") == 2
                and isinstance(expected.get("total_heart_score"), int)
                and expected["total_heart_score"] <= 3
            ):
                flags = expected.get("safety_flags") if isinstance(expected.get("safety_flags"), list) else []
                if "troponin_2_with_low_total" not in flags:
                    errors.append(f"{cid}: missing troponin_2_with_low_total safety flag")

    print(f"Validated {total} cases from {len(case_paths)} file(s)")
    for case_path in case_paths:
        print(f" - {case_path}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"Summary: {len(errors)} failure(s)")
    else:
        print("Summary: all checks passed")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
