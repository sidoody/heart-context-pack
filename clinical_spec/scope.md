# Scope

This specification applies to adult emergency department patients presenting with acute chest pain when the HEART Score is being used to risk-stratify for major adverse cardiac events (MACE) at 6 weeks.

## Included

- Adults age 18 years or older
- Emergency department patients with acute chest pain
- Encounters where the HEART Score is being applied for ACS risk stratification
- Use of the HEART Score to estimate short-term MACE risk and guide disposition planning

## Excluded

- STEMI on the initial ECG
- Cardiac arrest
- Active hemodynamic instability
- Trauma-related chest pain
- Patients already admitted for ACS workup
- Pediatric patients under age 18

## Key Scope Boundary

If the ECG shows a STEMI pattern, the HEART Score does not drive disposition. The output must set `heart_applicable: false` and route the patient to the emergent cath lab or reperfusion pathway. HEART component scores are still computed and reported for documentation consistency, but the bypass condition determines disposition, not the score.
