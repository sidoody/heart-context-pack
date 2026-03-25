# Red Flags and Safety Override Conditions

These conditions either bypass the HEART Score pathway entirely or require additional safety flags regardless of the computed score.

## 1. STEMI on ECG

Initial ECG shows an ST-elevation myocardial infarction pattern.

Action:

- HEART Score does not drive disposition
- Set `heart_applicable: false`
- Route to the emergent cath lab or reperfusion pathway
- Still compute and report HEART component scores for documentation consistency

## 2. Hemodynamic Instability

The patient has hypotension with systolic blood pressure below 90 mmHg, cardiogenic shock, cardiac arrest, or other acute hemodynamic compromise.

Action:

- HEART Score does not apply
- Set `heart_applicable: false`
- Route to emergent stabilization
- Include `hemodynamic_instability` in `safety_flags`

## 3. High Troponin With Low Total Score

The total HEART Score is `0-3` but the Troponin component score is `2`, meaning troponin is greater than 3 times the upper limit of normal.

Action:

- Raise the safety flag `troponin_2_with_low_total`
- Do not reflexively recommend early discharge
- Require explicit clinical review of the discrepancy between the low total score and the markedly elevated troponin

## 4. Troponin Pending or Not Drawn

The troponin result is not yet available.

Action:

- Raise the safety flag `pending_troponin`
- Do not finalize the HEART Score
- Do not recommend a final disposition from an incomplete score

## 5. Serial Troponins Not Completed

The patient is low risk by score (`0-3`) and early discharge is being considered, but serial troponins have not been completed.

Action:

- Raise the safety flag `incomplete_serial_troponins`
- Do not recommend discharge until the serial troponin protocol is complete
- Serial troponins should typically include testing at 0 and 3 to 6 hours

## 6. Alternative Urgent Diagnosis (Pulmonary Embolism Concern)

The clinical presentation suggests a non-ACS diagnosis that requires urgent evaluation, such as pulmonary embolism.

Action:

- Raise the safety flag `consider_alternative_diagnosis_pe`
- Do not anchor only on a low HEART Score when an urgent non-ACS diagnosis is plausible
- Recommend urgent parallel workup for the alternative diagnosis as clinically indicated
