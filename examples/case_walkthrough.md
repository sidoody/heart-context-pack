# Case Walkthrough (Run 1 to Run 2)

Run 1 was useful because it exposed debuggable failure types rather than a single aggregate miss count. Run 2 then closed those gaps and reached 14/14.

This walkthrough now labels each historical imperfect case with an explicit `failure_class` and identifies where the fix belongs (`pack`, `labels`, `grader`, or `model behavior`).

## Case: case_005 (Low total with markedly elevated troponin)

**Vignette**
- 32-year-old with atypical epigastric discomfort.
- ECG normal, no recognized risk factors.
- Troponin 0.15 ng/mL with ULN 0.04 ng/mL (>3x ULN).

**Gold label**
- HEART applicable: `true`
- Components: H0 E0 A0 R0 T2, total `2`
- Tier remains low by arithmetic, but disposition escalates to `admit_observation_workup`
- Required safety flag: `troponin_2_with_low_total`

**Run 1 model output**
- Produced low-tier framing and did not consistently align with safety-override expectations in labels.

**What was correct**
- Core component arithmetic around troponin-heavy score profiles was mostly coherent.

**What failed**
- Policy-vs-label mismatch around low-total/high-troponin disposition handling.

**failure_class**
- `pack_contradiction`

**Fix belongs in**
- `pack` and `labels` (make the override rule and gold expectation consistent).

## Case: case_011 (Known CAD with old Q waves and no acute changes)

**Vignette**
- Typical exertional angina pattern in older patient with known CAD.
- ECG documents *old* Q waves and explicitly no new ST/T changes.
- Troponin below ULN.

**Gold label**
- HEART applicable: `true`
- Components: H2 E0 A2 R2 T0, total `6`
- Disposition: `admit_observation_workup`

**Run 1 model output**
- Inconsistently interpreted old Q waves as active ischemic ECG findings.

**What was correct**
- Age/risk/history components were generally stable.

**What failed**
- Ambiguous ECG wording allowed multiple plausible interpretations.

**failure_class**
- `policy_ambiguity`

**Fix belongs in**
- `pack` (clarify old-Q-wave language in ECG criteria).

## Case: case_013 (Hemodynamic instability bypass)

**Vignette**
- Crushing chest pain plus hypotension and altered mental status.
- Instability pattern that should bypass HEART-driven disposition.

**Gold label**
- HEART applicable: `false`
- Disposition: `emergent_cath_lab` (simplified — a production system would distinguish this from STEMI bypass with a separate `emergent_stabilization` pathway)
- Required safety flag: `hemodynamic_instability`

**Run 1 model output**
- Could route correctly at times but was inconsistent about explicit instability safety-flag emission.

**What was correct**
- Recognized high-acuity presentation and urgent disposition.

**What failed**
- Missing explicit instruction to always include the instability flag.

**failure_class**
- `missing_instruction`

**Fix belongs in**
- `pack` (system prompt/policy instruction completeness).

## Case: case_004 (STEMI bypass conflict)

**Vignette**
- Definite inferior STEMI with reciprocal changes.

**Gold label**
- HEART applicable: `false`
- Disposition: `emergent_cath_lab`

**Run 1 model output**
- Exposed conflict between bypass messaging and score-oriented phrasing.

**What was correct**
- Recognized severe ACS pattern.

**What failed**
- Internal instruction conflict on whether HEART scoring should drive routing in bypass conditions.

**failure_class**
- `pack_contradiction`

**Fix belongs in**
- `pack` (remove contradictory bypass-vs-score phrasing).

## Case: case_009 (Pending troponin)

**Vignette**
- Suspicious exertional pain with normal ECG and pending first troponin.

**Gold label**
- HEART applicable: `true`
- `pending_troponin` safety flag required
- Missing info must include `troponin_result`

**Run 1 model output**
- Could prematurely finalize score language before pending labs resolved.

**What was correct**
- Base scoring and disposition trend were reasonable.

**What failed**
- Incomplete instruction for how to phrase provisional scoring with pending labs.

**failure_class**
- `missing_instruction`

**Fix belongs in**
- `pack` and `labels` (explicit pending-lab behavior and examples).

## Run 1 to Run 2 Debugging Story

- Run 1 misses were dominated by specification issues (`pack_contradiction`, `missing_instruction`, `policy_ambiguity`) instead of pure model reasoning.
- The fix loop targeted pack wording and label alignment first.
- Run 2 reached 14/14, with remaining minor variance limited to tolerated component-level differences rather than safety or disposition regressions.

## Added robustness slices: holdout and messy-note examples

The evaluation harness now supports two additional slices:

- `holdout`: targeted edge-case variants not used for pack tuning
- `messy_note`: noisier ED-style notes with the same underlying clinical logic

The tracked offline fixture (`tests/fixtures/sample_outputs/`) includes one case from each slice. Both score 8/8 with `failure_class=none`.

## Holdout example: holdout_003 (low total, high troponin)

**Why this case exists**
- Verifies that low arithmetic total does not overrule markedly elevated troponin.

**Expected behavior**
- HEART applicable: `true`
- Total score: `2` (H0 E0 A0 R0 T2)
- Risk tier: `low`
- Disposition: `admit_observation_workup`
- Required safety flag: `troponin_2_with_low_total`

**Fixture grading result**
- `8/8`, `failure_class=none`

## Messy-note example: messy_002 (pending troponin in noisy note)

**Why this case exists**
- Tests whether the model preserves pending-lab safety behavior when information is out of order and written in triage shorthand.

**Expected behavior**
- HEART applicable: `true`
- Total score: `4` (H2 E0 A1 R1 T0 provisional)
- Risk tier: `moderate`
- Disposition: `admit_observation_workup`
- Required safety flag: `pending_troponin`
- Required missing information: `troponin_result`

**Fixture grading result**
- `8/8`, `failure_class=none`
