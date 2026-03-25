# HEART Score Specification

This document defines the HEART Score using the published criteria from Six et al. (2008) and Backus et al. (2010). The score is the sum of five components: History, ECG, Age, Risk Factors, and Troponin. Each component is scored as 0, 1, or 2 points for a total score ranging from 0 to 10.

## Important Applicability Rule

The HEART Score does not apply to patients with STEMI on the initial ECG. If ST elevation meets full STEMI criteria, set `heart_applicable: false` and route to the emergent cath lab or reperfusion pathway instead of computing a HEART Score.

## History (H)

Assign 0, 1, or 2 points based on how suspicious the symptom history is for acute coronary syndrome.

- `0` = Slightly suspicious. Symptoms are clearly not consistent with ACS. Examples include sharp or stabbing pain, purely pleuritic pain, fully positional pain, pain reproducible with chest wall palpation, or pain otherwise clearly non-cardiac in character.
- `1` = Moderately suspicious. The presentation has a mix of suspicious and non-suspicious features, with some features suggestive of ACS but also features that argue against it.
- `2` = Highly suspicious. The presentation is primarily typical for ACS, such as substernal pressure or squeezing quality, radiation to the arm, jaw, or shoulder, associated diaphoresis, nausea or vomiting, exertional onset, or relief with rest or nitroglycerin.

## ECG (E)

Assign 0, 1, or 2 points based on the initial ECG.

- `0` = Normal. Normal sinus rhythm with no ST-segment or T-wave abnormalities.
- `1` = Nonspecific repolarization disturbance. This includes left or right bundle branch block, left ventricular hypertrophy with strain pattern, paced rhythm, nonspecific ST-segment or T-wave changes not meeting criteria for significant deviation, early repolarization pattern, or digoxin effect.
- `2` = Significant ST deviation. This includes ST depression of 1 mm or greater, ST elevation of 1 mm or greater in a non-STEMI pattern, or new T-wave inversions in 2 or more contiguous leads suggestive of ischemia.
Old Q waves without new acute ST-segment or T-wave changes reflect prior infarct scar and should score `0` unless accompanied by new acute ischemic findings.

If ST elevation meets full STEMI criteria, do not assign ECG points. The HEART Score is not applicable and the patient should be routed to the emergent cath lab pathway.

## Age (A)

- `0` = Under 45 years old
- `1` = 45 to 64 years old
- `2` = 65 years old or older

## Risk Factors (R)

Recognized HEART Score risk factors:

- Hypertension, treated or untreated
- Hyperlipidemia or dyslipidemia
- Diabetes mellitus
- Obesity with BMI greater than 30
- Current smoking, or quit within the past 3 months
- Family history of premature coronary artery disease in a first-degree relative: male younger than 55 years or female younger than 65 years
- Active cocaine or amphetamine use

Scoring:

- `0` = No known risk factors from the list above
- `1` = 1 or 2 risk factors from the list above
- `2` = 3 or more risk factors from the list above, or any history of known atherosclerotic disease

Known atherosclerotic disease includes any of the following:

- Prior myocardial infarction
- Prior percutaneous coronary intervention (PCI) or coronary artery bypass grafting (CABG)
- Prior ischemic stroke or transient ischemic attack (TIA)
- Peripheral arterial disease
- Known coronary artery disease documented on prior angiography

If known atherosclerotic disease is present, the Risk Factor score is automatically `2` regardless of how many other risk factors are present.

## Troponin (T)

Troponin is scored relative to the assay's upper limit of normal (ULN), using the institution's reported reference range cutoff for the assay in use.

- `0` = Troponin at or below the upper limit of normal, defined as less than or equal to 1 times ULN
- `1` = Troponin above the upper limit of normal up to 3 times ULN, defined as greater than 1 times ULN and less than or equal to 3 times ULN
- `2` = Troponin greater than 3 times ULN

If troponin has been drawn but the result is not yet available, the Troponin component cannot be scored and the total HEART Score cannot be finalized. This must be flagged.

## Total Score

Add the component scores:

`total_heart_score = history + ecg + age + risk_factors + troponin`

The total score ranges from 0 to 10.

## Risk Stratification

- `0-3` = Low risk. Estimated 6-week MACE rate is approximately 1 to 2 percent. Consider early discharge with outpatient follow-up if serial troponins are negative and no other clinical concerns are present.
- `4-6` = Moderate risk. Estimated 6-week MACE rate is approximately 12 to 17 percent. Admit for observation, serial troponins, and further workup such as stress testing or coronary CT angiography.
- `7-10` = High risk. Estimated 6-week MACE rate is approximately 50 to 65 percent. Admit, obtain early cardiology consultation, and consider an invasive strategy.

## Finalization Rules

- Do not finalize the total HEART Score if troponin is pending or not drawn.
- Do not use the HEART Score for STEMI, cardiac arrest, or active hemodynamic instability.
- Low-risk disposition recommendations require negative serial troponins and no other overriding clinical concerns.
