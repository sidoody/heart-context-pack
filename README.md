# Compiling Clinical Decision Rules into Model-Facing Artifacts

**A HEART Score reference implementation for context engineering**

Using a simple prompt-plus-context setup when building clinical LLM workflows can work for straightforward tasks. It can start to fail when there is rigorous policy logic: rule criteria, exceptions, and safety overrides all blurred into one prompt, where it becomes difficult to tell whether an error is due to a model reasoning failure, an underspecified rule, or an inconsistent grading rubric.

This repository takes the HEART Score for adult ED chest pain and compiles it into a structured, model-facing policy artifact. The HEART Score was chosen because it is simple enough to fully specify but still has real edge cases, for example STEMI bypass, hemodynamic instability, high troponin with low overall score, old Q waves, and pending troponins.

## Why compile a rule?

A clinical decision rule like HEART exists in prose. When that prose is embedded directly in a prompt, the model is forced to infer structure from wording which can lead to errors that can be difficult to evaluate.

By compiling the rule, each decision is pulled into a named, independent component:

- **Scope Layer** (`scope.md`) — explicitly defines when the rule applies and when it does not (population inclusion/exclusion criteria).
- **Policy Layer** (`policy_rules.yaml`, `decision_table.csv`, `red_flags.md`) — hard-codes tiers, dispositions, safety overrides, and bypass conditions as machine-readable artifacts.
- **Output Contract** (`answer_schema.json`) — a strict JSON Schema that forces the model to return structured, inspectable fields rather than free-text prose.

This separation creates a cleaner failure surface. When the model misses, the error is localized to a specific field (component scoring, risk-tier mapping, or a safety-flag omission) rather than buried in an opaque narrative response.

## Coherent specifications

The initial run on a 14-case canonical slice did not come back clean: 9/14 perfect (mean 7.57/8).

In a prompt engineering workflow, the instinct is to reach for a more powerful model or turn up reasoning effort. In this workflow, you look at the specification. The harness surfaced that the misses were not model hallucinations, but were internal contradictions in the pack itself:

- A gold label that conflicted with the pack's own safety-flag logic
- Ambiguity in how to score old Q waves without acute changes
- Conflicting instructions around STEMI bypass overrides
- Missing safety-flag instructions in the system prompt

Once those logic gaps were closed in the source artifacts, the rerun achieved 14/14 perfect. The system became stable because the specification became internally coherent.

A worked example of this iteration is in `examples/case_walkthrough.md`.

## Handling subjective components

Not every part of a clinical rule compiles cleanly. While Age, Troponin, and Risk Factors can be made mechanical, the History component (how suspicious is this presentation for ACS?) is inherently a judgment call. Two physicians can look at the same presentation and disagree on whether it is "moderately" or "highly" suspicious.

The approach taken here:

- **Anchor the extremes.** The specification pins concrete symptom patterns to boundary scores (e.g., sharp pleuritic pain anchors a 0; substernal pressure with diaphoresis anchors a 2) while accepting the middle as a gray zone.
- **Tolerance in grading.** The harness grades `total_heart_score` with a ±1 tolerance rather than demanding exact per-component agreement.
- **Clinical reasoning over arithmetic.** My design choice was to focus on if the model reaches the correct risk tier and disposition vs if it scored 1 or a 2 to a genuinely ambiguous history.

Other strategies for subjective components include few-shot exemplar chains for boundary cases, clinician calibration sets to establish inter-rater ranges, or explicit uncertainty fields for low-confidence components. The point is to recognize which parts of a rule are deterministic and which require judgment, and then design the failure analysis to reflect that.

## Resilience against messy data

To test robustness, the revised pack was run against a `messy_note` slice: noisier, shorthand ED-style inputs with the same underlying clinical logic. Despite the drop in input quality, the system stayed at 100%, suggesting that once the policy artifact was internally coherent, behavior remained stable under messier surface forms of the same task.

Current snapshot across all slices: 14/14 canonical, 10/10 holdout, 6/6 messy-note.

## Clinical safety flags

The HEART score can be mathematically "Low Risk" while the clinical picture is concerning.  For example, a low total score sitting next to a high troponin. In practice, a physician would pursue further workup for an elevated troponin regardless of the total score. Without explicit rules, a clinical LLM could miss this.

The `troponin_2_with_low_total` flag is built into the pack to force the model to surface this tension explicitly. The approach is to encode the safety logic as a testable rule rather than hope the model catches it on its own.

## Building for auditability

For high-stakes clinical workflows, you should be able to specify the logic well enough that failures point to the right layer. This repository is a reference architecture for what a compact clinical rule looks like when it is treated as an explicit policy artifact, paired with a strict output contract, and exercised under a deterministic harness.


## Quickstart

```bash
# Clone and set up
git clone https://github.com/sidoody/heart-context-pack.git
cd heart-context-pack
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your ANTHROPIC_API_KEY

# Validate inputs
python scripts/validate_pack.py
python scripts/validate_cases.py

# Render model-facing bundle
python scripts/render_context_bundle.py --out rendered_context_bundle.md

# Run canonical only (default behavior)
python scripts/run_eval.py

# Run a specific robustness slice
python scripts/run_eval.py --slice holdout
python scripts/run_eval.py --slice messy_note

# Run all slices together
python scripts/run_eval.py --slice all

# Grade outputs
python scripts/grade_outputs.py \
  --slice canonical \
  --predictions runs/<timestamp>/normalized/structured_outputs.jsonl \
  --out runs/<timestamp>/graded/scores.csv

# Grade all slices together
python scripts/grade_outputs.py \
  --slice all \
  --predictions runs/<timestamp>/normalized/structured_outputs.jsonl \
  --out runs/<timestamp>/graded/scores.csv

# Offline grading fixture check (no model APIs)
python scripts/check_grading_fixture.py
```

## What the harness checks

The harness validates whether the model can:

- score each HEART component from the vignette
- compute the correct total (within ±1 tolerance)
- assign the right risk tier and disposition
- bypass HEART scoring for STEMI or hemodynamic instability
- emit required safety flags
- flag pending or incomplete troponin when applicable
- avoid forbidden phrases in the clinician rationale

It supports three dataset slices:

- `canonical` — 14 clean synthetic cases
- `holdout` — 10 targeted edge-case variants not used for pack tuning
- `messy_note` — 6 noisier ED-style note variants with the same clinical logic

## Outputs produced per evaluation

`run_eval.py` writes inference artifacts and `grade_outputs.py` writes grading artifacts. A complete evaluation produces:

- raw model responses at `raw/model_outputs.jsonl`
- normalized structured outputs at `normalized/structured_outputs.jsonl`
- per-case grading details at `graded/scores_details.jsonl`
- aggregate metrics at `graded/scores_summary.json`
- failure-class breakdowns at `graded/failure_class_summary.json` and `.csv`

## Repository structure

```text
clinical_spec/              # Compiled policy artifact source files
  scope.md                  # Population inclusion/exclusion
  heart_score_rules.md      # HEART component scoring criteria
  red_flags.md              # Safety override / bypass conditions
  policy_rules.yaml         # Machine-readable clinical rules
  decision_table.csv        # Risk tier → disposition mapping
  answer_schema.json        # JSON Schema output contract
  system_prompt.md          # Model-facing system instructions

evals/                      # Evaluation datasets and grading spec
  cases.jsonl               # 14 canonical synthetic cases with gold labels
  holdout_variants.jsonl    # 10 held-out edge-case variants
  messy_notes.jsonl         # 6 noisy note-style variants
  failure_labels.yaml       # Failure-class labels and definitions
  rubric.md                 # Deterministic grading rubric (0–8 scale)

scripts/                    # Validation, inference, and grading pipeline
  render_context_bundle.py  # Assembles spec files into one model-facing bundle
  validate_pack.py          # Validates spec structure, YAML keys, schema, CSV
  validate_cases.py         # Validates cases and gold-label consistency
  run_eval.py               # Runs inference across canonical/holdout/messy slices
  grade_outputs.py          # Deterministic grading with failure-class tagging
  check_grading_fixture.py  # Offline grading snapshot check for CI

tests/fixtures/sample_outputs/
  ...                       # Tracked offline grading fixtures and expected outputs

runs/                       # Timestamped eval outputs (gitignored)

examples/
  case_walkthrough.md       # Annotated walkthrough of iteration and failure analysis
```

## Limitations
- Synthetic cases and variants
- Single model family in the current run snapshot
- Holdout and messy-note slices remain close to the same decision surface, not generalization proof
- History scoring still includes inherent clinical judgment
- Disposition enum is simplified: both STEMI and hemodynamic instability map to `emergent_cath_lab`. A production system would distinguish these (e.g., separate `emergent_stabilization` pathway for hemodynamic instability).

## CI

GitHub Actions runs on push and pull request:

- dependency install
- `scripts/validate_pack.py`
- `scripts/validate_cases.py`
- `scripts/check_grading_fixture.py` (fully offline)

Keeps validation and grading regressions visible without depending on provider APIs.

## Disclaimer

Reference implementation for context engineering on synthetic cases.

Not medical advice, not a validated clinical tool, and not intended for patient care.

## Author

Saud Siddiqui, MD

## License

MIT
