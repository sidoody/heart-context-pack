"""Assemble clinical_spec/ files into a single model-facing context bundle."""

import argparse, csv
from pathlib import Path


def table_md(path):
    with path.open(newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return "(empty table)"
    head = "| " + " | ".join(rows[0]) + " |"
    rule = "| " + " | ".join(["---"] * len(rows[0])) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join([head, rule, *body])


def render_context_bundle(base=None):
    base = base or (Path(__file__).resolve().parents[1] / "clinical_spec")
    parts = [
        (base / "system_prompt.md").read_text().strip(),
        "## Scope\n\n" + (base / "scope.md").read_text().strip(),
        "## HEART Score Criteria\n\n" + (base / "heart_score_rules.md").read_text().strip(),
        "## Red Flags and Safety Override Conditions\n\n" + (base / "red_flags.md").read_text().strip(),
        "## Policy Rules\n\n```yaml\n" + (base / "policy_rules.yaml").read_text().strip() + "\n```",
        "## Decision Table\n\n" + table_md(base / "decision_table.csv"),
        "## Required Output Schema\n\n```json\n" + (base / "answer_schema.json").read_text().strip() + "\n```",
    ]
    return "\n\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = render_context_bundle()
    if args.out:
        args.out.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
