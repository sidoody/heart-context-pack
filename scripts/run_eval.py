"""Run HEART Score inference across case slices via the Anthropic API."""

import argparse, hashlib, json, os, time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from render_context_bundle import render_context_bundle


SLICE_TO_FILE = {
    "canonical": "cases.jsonl",
    "holdout": "holdout_variants.jsonl",
    "messy_note": "messy_notes.jsonl",
}


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
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    parser.add_argument("--effort", default="low", choices=["low", "medium", "high", "max"])
    return parser.parse_args()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(path.read_bytes())


def serialize_response(response):
    if hasattr(response, "model_dump"):
        try:
            return response.model_dump(mode="json")
        except TypeError:
            return response.model_dump()
    if hasattr(response, "model_dump_json"):
        return json.loads(response.model_dump_json())
    if hasattr(response, "to_dict"):
        return response.to_dict()
    return {"repr": repr(response)}


def normalize_json(candidate):
    if isinstance(candidate, dict):
        return candidate
    if not isinstance(candidate, str):
        raise ValueError("candidate is not JSON-like")
    text = candidate.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:] if lines else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        text = "\n".join(lines).strip()
    return json.loads(text)


def get_block_value(block, key, default=None):
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def extract_structured_output(response):
    text_blocks = []
    for block in getattr(response, "content", []):
        block_type = get_block_value(block, "type")
        if block_type == "tool_use":
            return normalize_json(get_block_value(block, "input"))
        if block_type == "text":
            text = get_block_value(block, "text")
            if text:
                text_blocks.append(text)
    if text_blocks:
        return normalize_json("\n".join(text_blocks))
    raise ValueError("no structured output found")


def is_rate_limit_error(exc):
    return getattr(exc, "status_code", None) == 429 or exc.__class__.__name__ == "RateLimitError"


def supports_structured_outputs(model_info):
    capabilities = getattr(model_info, "capabilities", None)
    structured_outputs = getattr(capabilities, "structured_outputs", None)
    return getattr(structured_outputs, "supported", False)


def resolve_model_id(client, requested_model):
    if requested_model != "auto":
        return client.models.retrieve(requested_model).id
    page = client.models.list(limit=50)
    for model_info in getattr(page, "data", []):
        if supports_structured_outputs(model_info):
            return model_info.id
    raise RuntimeError("no available Anthropic model with structured outputs support was found")


def call_anthropic(client, model, effort, system_prompt, user_prompt, schema):
    for attempt in range(3):
        try:
            return client.messages.create(
                model=model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=1200,
                temperature=0,
                output_config={"effort": effort},
                thinking={"type": "disabled"},
                tools=[
                    {
                        "name": "heart_score_assessment",
                        "description": "Return the HEART Score assessment as structured JSON.",
                        "input_schema": schema,
                    }
                ],
                tool_choice={"type": "tool", "name": "heart_score_assessment"},
            )
        except Exception as exc:
            if attempt < 2 and is_rate_limit_error(exc):
                time.sleep(2 * (2 ** attempt))
                continue
            raise


def write_jsonl(path, rows):
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def log(message):
    print(message, flush=True)


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
        slice_path = evals_dir / SLICE_TO_FILE[slice_name]
        resolved[str(slice_path.resolve())] = {
            "path": slice_path.resolve(),
            "slice_name": slice_name,
            "source": "slice",
        }

    for path in explicit_paths:
        p = path.expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Cases file does not exist: {p}")
        resolved[str(p)] = {"path": p, "slice_name": None, "source": "explicit"}

    if not resolved:
        raise RuntimeError("No case files resolved")
    return list(resolved.values())


def load_cases(case_sources):
    loaded = []
    seen_ids = set()
    for source in case_sources:
        case_path = source["path"]
        for line in case_path.read_text().splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            case_id = case["id"]
            if case_id in seen_ids:
                raise ValueError(f"Duplicate case id across selected files: {case_id}")
            seen_ids.add(case_id)
            loaded.append(
                {
                    "case": case,
                    "case_id": case_id,
                    "split": case.get("split", source["slice_name"] or "canonical"),
                    "source_cases_file": str(case_path),
                }
            )
    return loaded


def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    case_sources = resolve_case_paths(project_root, args.cases, args.slice)
    selected_case_files = [source["path"] for source in case_sources]
    schema_path = project_root / "clinical_spec" / "answer_schema.json"
    script_path = Path(__file__).resolve()
    rendered_context = render_context_bundle()
    schema = json.loads(schema_path.read_text())
    client = Anthropic()
    log(f"Resolving model: {args.model}")
    model = resolve_model_id(client, args.model)
    log(f"Using model: {model}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = project_root / "runs" / timestamp
    raw_dir = run_dir / "raw"
    normalized_dir = run_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    raw_rows, structured_rows, parse_failures = [], [], []
    loaded_cases = load_cases(case_sources)
    case_count = len(loaded_cases)
    log(f"Loaded {case_count} cases from {len(selected_case_files)} case file(s)")
    for source in case_sources:
        log(f" - {source['path']}")
    log(f"Writing run outputs to {run_dir}")
    for index, loaded in enumerate(loaded_cases, 1):
        case = loaded["case"]
        case_id = loaded["case_id"]
        split = loaded["split"]
        log(f"Case {index} of {case_count}: {case_id}")
        user_prompt = (
            f"Case ID: {case_id}\n\n"
            f"Patient presentation:\n{case['patient']}\n\n"
            "Provide your HEART Score assessment as JSON matching the required output schema."
        )
        response = call_anthropic(client, model, args.effort, rendered_context, user_prompt, schema)
        raw_rows.append(
            {
                "case_id": case_id,
                "split": split,
                "source_cases_file": loaded["source_cases_file"],
                "response": serialize_response(response),
            }
        )
        try:
            structured = extract_structured_output(response)
            if "case_id" not in structured:
                structured["case_id"] = case_id
            structured["split"] = split
            structured["source_cases_file"] = loaded["source_cases_file"]
            structured_rows.append(structured)
            log(f"Completed case {index} of {case_count}: {case_id}")
        except Exception as exc:
            parse_failures.append({"case_id": case_id, "error": str(exc)})
            structured_rows.append(
                {
                    "case_id": case_id,
                    "split": split,
                    "source_cases_file": loaded["source_cases_file"],
                    "parse_failure": str(exc),
                }
            )
            log(f"Parse failure for case {index} of {case_count}: {case_id} ({exc})")

    write_jsonl(raw_dir / "model_outputs.jsonl", raw_rows)
    write_jsonl(normalized_dir / "structured_outputs.jsonl", structured_rows)

    metadata = {
        "timestamp": timestamp,
        "model": model,
        "requested_model": args.model,
        "effort": args.effort,
        "cases_path": str(selected_case_files[0]) if len(selected_case_files) == 1 else None,
        "cases_paths": [str(path) for path in selected_case_files],
        "slices_used": sorted({row["split"] for row in loaded_cases}),
        "case_count": case_count,
        "parse_failures": parse_failures,
    }
    manifest = {
        "cases_files_sha256": {str(path): sha256_file(path) for path in selected_case_files},
        "rendered_context_bundle_sha256": sha256_bytes(rendered_context.encode()),
        "run_eval_script_sha256": sha256_file(script_path),
        "answer_schema_sha256": sha256_file(schema_path),
    }
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (run_dir / "reproducibility_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    log(f"Cases run: {case_count}")
    log(f"Parse failures: {len(parse_failures)}")
    log(f"Model: {model}")
    log(f"Run directory: {run_dir}")


if __name__ == "__main__":
    main()
