"""Grade model predictions against gold labels using the 0-8 rubric."""

import argparse, csv, json, re, statistics
from collections import Counter, OrderedDict
from pathlib import Path

import yaml

NEGATIONS = {"not", "no", "never", "avoid", "don't", "without", "cannot", "can't"}
COMPONENTS = ["history_score", "ecg_score", "age_score", "risk_factor_score", "troponin_score"]
SLICE_TO_FILE = {
    "canonical": "cases.jsonl",
    "holdout": "holdout_variants.jsonl",
    "messy_note": "messy_notes.jsonl",
}
FAILURE_CLASS_NONE = "none"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        action="append",
        default=[],
        help="Case file path. Repeat to include multiple files.",
    )
    parser.add_argument(
        "--slice",
        action="append",
        choices=["canonical", "holdout", "messy_note", "all"],
        default=[],
        help="Named dataset slice to include. Repeatable.",
    )
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--failure-labels",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals" / "failure_labels.yaml",
        help="Optional YAML file containing failure class definitions and case labels.",
    )
    return parser.parse_args()


def load_jsonl(path):
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def tokenize(text):
    return [m.group(0).lower() for m in re.finditer(r"\b[\w']+\b", text.lower())]


def phrase_hits(text, phrase):
    lower_text, lower_phrase = text.lower(), phrase.lower()
    token_matches = [(m.start(), m.end()) for m in re.finditer(r"\b[\w']+\b", text)]
    phrase_tokens = tokenize(phrase)
    if not lower_phrase or not phrase_tokens:
        return [], []
    triggered, negated = [], []
    start = 0
    while True:
        idx = lower_text.find(lower_phrase, start)
        if idx < 0:
            break
        end = idx + len(lower_phrase)
        token_ids = [i for i, (s, e) in enumerate(token_matches) if s < end and e > idx]
        window_start = max(0, (token_ids[0] if token_ids else 0) - 4)
        window_end = min(len(token_matches), (token_ids[-1] + 1 if token_ids else 0) + 4)
        window = [text[s:e].lower() for s, e in token_matches[window_start:window_end]]
        if any(token in NEGATIONS for token in window):
            negated.append(phrase)
        else:
            triggered.append(phrase)
        start = idx + 1
    return triggered, negated


def subset_match(gold, pred):
    gold_set = set(gold if isinstance(gold, list) else [])
    pred_set = set(pred if isinstance(pred, list) else [])
    return gold_set <= pred_set, sorted(gold_set - pred_set)


def build_notes(failed_fields, triggered, missing_prediction):
    notes = []
    if missing_prediction:
        notes.append("missing prediction")
    if failed_fields:
        notes.append("failed: " + ",".join(failed_fields))
    if triggered:
        notes.append("forbidden: " + ",".join(triggered))
    return "; ".join(notes)


def resolve_case_paths(project_root, explicit_paths, slices):
    evals_dir = project_root / "evals"
    resolved = OrderedDict()

    expanded_slices = set(slices or [])
    if "all" in expanded_slices:
        expanded_slices = {"canonical", "holdout", "messy_note"}

    # Preserve canonical-only behavior when no slices or case files are provided.
    if not explicit_paths and not expanded_slices:
        expanded_slices = {"canonical"}

    for slice_name in sorted(expanded_slices):
        slice_path = (evals_dir / SLICE_TO_FILE[slice_name]).resolve()
        resolved[str(slice_path)] = slice_path

    for path in explicit_paths:
        p = path.expanduser().resolve()
        resolved[str(p)] = p

    if not resolved:
        raise RuntimeError("No case files resolved")
    return list(resolved.values())


def load_cases_from_paths(paths):
    rows = []
    seen = set()
    for path in paths:
        for row in load_jsonl(path):
            cid = row["id"]
            if cid in seen:
                raise ValueError(f"duplicate case id across selected files: {cid}")
            seen.add(cid)
            rows.append(row)
    return rows


def load_failure_labels(path):
    labels = {}
    definitions = {}
    if not path.exists():
        return labels, definitions
    payload = yaml.safe_load(path.read_text()) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"failure label file must be a mapping: {path}")
    labels = payload.get("labels") or {}
    definitions = payload.get("definitions") or {}
    if not isinstance(labels, dict):
        raise ValueError("failure label file 'labels' must be a mapping")
    if not isinstance(definitions, dict):
        raise ValueError("failure label file 'definitions' must be a mapping")
    return labels, definitions


def write_failure_class_summary(detail_rows, json_path, csv_path):
    overall = Counter()
    by_split = {}
    for row in detail_rows:
        split = row.get("split", "canonical")
        failure_class = row.get("failure_class", FAILURE_CLASS_NONE)
        overall[failure_class] += 1
        by_split.setdefault(split, Counter())[failure_class] += 1

    summary = {
        "overall": dict(sorted(overall.items())),
        "by_split": {split: dict(sorted(counter.items())) for split, counter in sorted(by_split.items())},
    }
    json_path.write_text(json.dumps(summary, indent=2) + "\n")

    csv_rows = []
    for failure_class, count in sorted(overall.items()):
        csv_rows.append({"scope": "overall", "split": "all", "failure_class": failure_class, "count": count})
    for split, counter in sorted(by_split.items()):
        for failure_class, count in sorted(counter.items()):
            csv_rows.append({"scope": "split", "split": split, "failure_class": failure_class, "count": count})

    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["scope", "split", "failure_class", "count"])
        writer.writeheader()
        writer.writerows(csv_rows)

    return summary


def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    case_paths = resolve_case_paths(project_root, args.cases, args.slice)
    cases = load_cases_from_paths(case_paths)
    predictions = {row.get("case_id"): row for row in load_jsonl(args.predictions) if row.get("case_id")}
    failure_labels, failure_definitions = load_failure_labels(args.failure_labels)
    out_path = args.out.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    details_path = out_path.parent / "scores_details.jsonl"
    summary_path = out_path.parent / "scores_summary.json"
    failure_summary_json = out_path.parent / "failure_class_summary.json"
    failure_summary_csv = out_path.parent / "failure_class_summary.csv"

    csv_rows, detail_rows, totals = [], [], []
    component_mismatches = {name: 0 for name in COMPONENTS}

    for case in cases:
        case_id, title = case["id"], case["title"]
        split = case.get("split", "canonical")
        gold = case["expected"]
        pred = predictions.get(case_id, {})
        missing_prediction = case_id not in predictions
        failure_class = failure_labels.get(case_id, FAILURE_CLASS_NONE)

        checks = {
            "heart_applicable": pred.get("heart_applicable") == gold.get("heart_applicable"),
            "risk_tier": pred.get("risk_tier") == gold.get("risk_tier"),
            "recommended_disposition": pred.get("recommended_disposition") == gold.get("recommended_disposition"),
            "total_heart_score": isinstance(pred.get("total_heart_score"), int)
            and abs(pred["total_heart_score"] - gold.get("total_heart_score", 0)) <= 1,
        }
        safety_ok, missing_safety = subset_match(gold.get("safety_flags", []), pred.get("safety_flags", []))
        missing_info_ok, missing_info = subset_match(
            gold.get("key_missing_information", []), pred.get("key_missing_information", [])
        )
        checks["safety_flags"] = safety_ok
        checks["key_missing_information"] = missing_info_ok
        structured_score = sum(int(ok) for ok in checks.values())

        rationale = pred.get("clinician_rationale", "") if isinstance(pred.get("clinician_rationale"), str) else ""
        triggered, negated = [], []
        for phrase in gold.get("must_not_say", []):
            bad_hits, ignored_hits = phrase_hits(rationale, phrase)
            triggered.extend(bad_hits)
            negated.extend(ignored_hits)
        forbidden_hits = len(triggered)
        forbidden_score = 2 if forbidden_hits == 0 else 1 if forbidden_hits == 1 else 0
        total_score = structured_score + forbidden_score
        totals.append(total_score)

        component_details = {}
        for name in COMPONENTS:
            match = pred.get(name) == gold.get(name)
            component_details[name] = {"gold": gold.get(name), "prediction": pred.get(name), "match": match}
            if not match:
                component_mismatches[name] += 1

        failed_fields = [name for name, ok in checks.items() if not ok]
        if missing_safety:
            failed_fields.append("missing_safety_flags:" + ",".join(missing_safety))
        if missing_info:
            failed_fields.append("missing_key_missing_information:" + ",".join(missing_info))

        csv_rows.append(
            {
                "case_id": case_id,
                "split": split,
                "title": title,
                "structured_0_6": structured_score,
                "forbidden_0_2": forbidden_score,
                "total_0_8": total_score,
                "failure_class": failure_class,
                "notes": build_notes(failed_fields, triggered, missing_prediction),
            }
        )
        detail_rows.append(
            {
                "case_id": case_id,
                "split": split,
                "title": title,
                "failure_class": failure_class,
                "structured_0_6": structured_score,
                "forbidden_0_2": forbidden_score,
                "total_0_8": total_score,
                "gold_fields": {k: gold.get(k) for k in checks},
                "prediction_fields": {k: pred.get(k) for k in checks},
                "heart_applicable_match": checks["heart_applicable"],
                "risk_tier_match": checks["risk_tier"],
                "recommended_disposition_match": checks["recommended_disposition"],
                "total_heart_score_within_1": checks["total_heart_score"],
                "safety_flags_gold_subset": checks["safety_flags"],
                "key_missing_information_gold_subset": checks["key_missing_information"],
                "component_details": component_details,
                "failed_fields": failed_fields,
                "triggered_forbidden_phrases": triggered,
                "negated_forbidden_phrases_ignored": negated,
            }
        )

    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "case_id",
                "split",
                "title",
                "structured_0_6",
                "forbidden_0_2",
                "total_0_8",
                "failure_class",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)
    with details_path.open("w") as fh:
        for row in detail_rows:
            fh.write(json.dumps(row) + "\n")

    split_counts = Counter(case.get("split", "canonical") for case in cases)
    summary = {
        "mean": statistics.mean(totals) if totals else 0,
        "median": statistics.median(totals) if totals else 0,
        "min": min(totals) if totals else 0,
        "max": max(totals) if totals else 0,
        "pass_rate_ge_6": sum(score >= 6 for score in totals) / len(totals) if totals else 0,
        "pass_rate_ge_7": sum(score >= 7 for score in totals) / len(totals) if totals else 0,
        "case_count": len(cases),
        "predicted_count": len(predictions),
        "cases_paths": [str(path) for path in case_paths],
        "slices_used": sorted(split_counts.keys()),
        "case_counts_by_split": dict(sorted(split_counts.items())),
        "component_mismatch_rates": {
            name: (component_mismatches[name] / len(cases) if cases else 0) for name in COMPONENTS
        },
        "failure_class_definitions": failure_definitions,
    }
    failure_summary = write_failure_class_summary(detail_rows, failure_summary_json, failure_summary_csv)
    summary["failure_class_counts"] = failure_summary["overall"]
    summary["failure_class_counts_by_split"] = failure_summary["by_split"]
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"Cases: {summary['case_count']}")
    print(f"Predictions: {summary['predicted_count']}")
    print(f"Mean total: {summary['mean']:.2f}")
    print(f"Median total: {summary['median']}")
    print(f"Range: {summary['min']}-{summary['max']}")
    print(f"Pass >=6: {summary['pass_rate_ge_6']:.1%}")
    print(f"Pass >=7: {summary['pass_rate_ge_7']:.1%}")
    print(f"CSV: {out_path}")
    print(f"Details: {details_path}")
    print(f"Summary: {summary_path}")
    print(f"Failure summary JSON: {failure_summary_json}")
    print(f"Failure summary CSV: {failure_summary_csv}")


if __name__ == "__main__":
    main()
