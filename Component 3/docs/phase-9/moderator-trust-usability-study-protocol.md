# Moderator Trust and Usability Study Protocol

## Purpose

This protocol defines a lightweight human-centered evaluation for the moderator-facing application. It is intended to support requirement `E-02` by providing a practical method to assess whether the application helps moderators review harmful Sinhala content with confidence, clarity, and efficiency.

This is not a clinical or large-scale UX research protocol. It is a compact project-ready evaluation design suitable for thesis/report evidence and internal validation.

## Study Goals

The study evaluates whether the application:

- helps moderators understand why a comment was flagged
- improves confidence in moderation decisions
- makes rewrite/counterfactual suggestions useful in practice
- supports batch review without excessive confusion or friction
- is usable enough for a moderator-facing workflow

## Research Questions

### RQ1. Trust

Do moderators feel the system provides enough evidence to trust or challenge a model prediction?

### RQ2. Usability

Can moderators complete the review flow with low friction using:

- prediction + confidence
- explanation tabs
- what-if editing
- rewrite suggestions
- decision logging

### RQ3. Explanation usefulness

Are SHAP/evidence/suggestion outputs actually useful for reviewing `HATE`, `DISINFO`, and `NORMAL` cases?

## Participants

Recommended minimum:

- `5` to `10` participants for a small formative study

Preferred participant profile:

- Sinhala-speaking users
- familiar with social media moderation, content review, journalism, communications, or related tasks

If expert moderators are unavailable:

- use advanced Sinhala-speaking reviewers as proxy participants
- explicitly note this limitation in the report

## Materials

Use the running application with:

- single moderation flow
- batch moderation flow
- explanation tabs
- what-if/counterfactual editor
- decision logging/export

Prepare a small review set with examples covering:

- `HATE`
- `DISINFO`
- `NORMAL`
- borderline cases
- easy cases

Recommended session set:

- `12` to `18` comments per participant

## Study Tasks

### Task 1. Single-comment review

Participant reviews a single comment and decides:

- predicted category seems acceptable or not
- explanation is helpful or not
- whether they would keep or change the final label

### Task 2. Rewrite usefulness

Participant reviews harmful examples and judges whether the rewrite or safer phrasing is actually useful for moderation assistance.

### Task 3. What-if exploration

Participant edits a comment in the what-if sandbox and checks whether the change in prediction helps them understand the model behavior.

### Task 4. Batch moderation

Participant reviews a short queue and logs decisions using the interface.

## Measures

### Quantitative measures

Collect:

- task completion status
- task completion time
- number of label overrides
- number of cases where explanation was used
- number of cases where what-if or rewrite tools were used

Use 1 to 5 Likert ratings for:

- trust in model output
- clarity of explanation
- usefulness of highlighted evidence
- usefulness of rewrite suggestions
- usefulness of what-if interface
- overall usability

### Qualitative measures

Ask short follow-up questions such as:

- What helped you most when making a decision?
- What was confusing?
- Which explanation output felt least useful?
- Did the rewrite suggestions feel natural in Sinhala?
- Would you use this in a real moderation setting?

## Suggested Session Flow

### 1. Introduction

- explain the purpose of the study
- clarify that the tool is being evaluated, not the participant
- obtain consent if required by the project process

### 2. Short walkthrough

Show:

- moderation result
- explanation tabs
- what-if editor
- decision logging

### 3. Task execution

Participant completes the task set while the observer records:

- timing
- visible hesitation/confusion
- comments/questions

### 4. Post-task survey

Have the participant fill the rating form.

### 5. Debrief

Ask open-ended questions and note recommendations.

## Rating Scale

Use:

- `1 = strongly disagree`
- `2 = disagree`
- `3 = neutral`
- `4 = agree`
- `5 = strongly agree`

Suggested statements:

- I understood why the system assigned the label.
- The highlighted evidence was useful.
- The rewrite suggestions were helpful.
- The what-if feature improved my understanding.
- I felt confident making decisions with this interface.
- The workflow was easy to use overall.

## Success Criteria

For a small internal study, treat the application as reasonably acceptable if:

- average rating is at least `4.0/5` for:
  - explanation clarity
  - evidence usefulness
  - overall usability
- average rating is at least `3.5/5` for:
  - what-if usefulness
  - rewrite usefulness
- most participants can complete the full flow without facilitator intervention

These are practical project thresholds, not universal scientific benchmarks.

## Artifacts to Collect

Store the following:

- participant task log
- participant rating form
- study summary sheet
- anonymized decision-log export if used

Use the companion templates:

- `docs/phase-9/moderator-study-results-template.csv`
- `docs/phase-9/moderator-study-summary-template.md`

## Limitations to Report

If applicable, explicitly mention:

- small sample size
- proxy participants instead of real moderators
- limited session duration
- lab/demo context rather than production deployment
- model quality limitations affecting perceived trust

## Reporting Use

This protocol can be cited in:

- evaluation chapter
- application validation section
- requirement evidence for `E-02`
- final handover package
