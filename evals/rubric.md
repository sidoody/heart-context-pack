# Grading Rubric

Each prediction is graded on two components for a total of 0-8.

## 1. Structured field agreement (0-6)

The grader checks whether the prediction matches the gold label for
these six fields, awarding 1 point for each match:

- heart_applicable (exact match)
- risk_tier (exact match)
- recommended_disposition (exact match)
- total_heart_score (match within plus or minus 1 tolerance)
- safety_flags (all gold-label flags must be present in prediction)
- key_missing_information (all gold-label items must be present)

## 2. Forbidden statement check (0-2)

The grader checks the clinician_rationale field for statements
from the gold label's must_not_say list using case-insensitive
substring matching with negation detection.

- 0 forbidden hits = 2 points
- 1 forbidden hit = 1 point
- 2 or more forbidden hits = 0 points

If the forbidden phrase appears within 4 tokens of a negation word
(not, no, never, avoid, don't, without), the hit is not penalized.

## Component diagnostics

Individual HEART component scores (H, E, A, R, T) are logged in the
detailed grading output for diagnostic inspection. They do not
contribute to the total score. If the model reaches the correct total
through a different component breakdown, the structured match still
passes on total_heart_score.

## Interpretation

Total = structured agreement + forbidden check = 0-8.
