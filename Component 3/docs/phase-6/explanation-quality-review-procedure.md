# Explanation Quality Review Procedure

## Purpose

This procedure explains how to produce a small manual-review evidence pack for Sinhala explanation and rewrite quality. It is intended to support requirement `X-05` and to make the explanation-quality claim auditable in the final report.

Use this together with:

- `docs/phase-6/sinhala-explanation-and-rewrite-guideline.md`
- `docs/phase-6/explanation-quality-review-log-template.csv`

## Review Goal

The goal is not to re-evaluate model accuracy. The goal is to judge whether the moderator-facing explanation and rewrite outputs are:

- understandable
- grounded in the text
- culturally appropriate for Sinhala moderation context
- useful for moderation decisions

## Recommended Sample

Review at least `20` application outputs.

Recommended mix:

- `8` `HATE`
- `8` `DISINFO`
- `4` `NORMAL`

Also try to include:

- at least `5` clearly good examples
- at least `5` borderline or difficult examples
- examples from different sources if possible

## Review Steps

### 1. Generate outputs from the application

Using the backend/frontend moderation flow, collect examples that include:

- original comment text
- predicted label
- explanation sentence
- highlighted harmful-word evidence
- rewrite suggestions
- optional LLM feedback

### 2. Copy each reviewed example into the log

For each item, record:

- `item_id`
- `source`
- `predicted_label`
- `reviewer_id`
- `review_date`
- original comment
- explanation text
- rewrite suggestion used for review

### 3. Score the explanation quality

Use the review log columns to mark:

- `explanation_clear`
- `evidence_grounded`
- `sinhala_natural`
- `rewrite_useful`
- `overclaiming_present`
- `manual_followup_needed`

Use only:

- `yes`
- `no`

### 4. Add a concise comment

In `review_notes`, write a short reason when:

- the explanation is weak
- the rewrite is unnatural
- the label-specific reasoning is incomplete
- the explanation overclaims certainty

### 5. Summarize results

After review, compute:

- total reviewed items
- count and percentage of `yes` for each quality column
- count of `manual_followup_needed = yes`
- most common explanation issues

## Suggested Acceptance Interpretation

For a small evidence pack, treat the output as reasonably acceptable if:

- at least `80%` of reviewed items are marked `yes` for:
  - `explanation_clear`
  - `evidence_grounded`
  - `sinhala_natural`
- at least `70%` are marked `yes` for `rewrite_useful`
- `overclaiming_present` is rare and explicitly noted when found

These are review heuristics for reporting, not hard scientific thresholds.

## Common Failure Patterns to Watch For

### HATE

- profanity treated as hate without clear target
- explanation says “hate” but evidence is only general anger
- rewrite removes all meaning instead of reducing abuse

### DISINFO

- suspicion or questioning treated as misinformation
- explanation says the statement is false without enough basis
- rewrite changes the factual topic instead of softening certainty

### NORMAL

- explanation is too generic
- safe text is still described with suspicious or harmful wording
- unnecessary warning tone appears in normal examples

## Reporting Use

This review artifact can be cited in:

- methodology chapter under explainability quality review
- application-evaluation section
- requirement traceability evidence for `X-05`
- final handover package
