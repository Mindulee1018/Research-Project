# Final Evidence Collection Sequence

## Purpose

This document gives the fastest practical order for collecting the remaining application-delivery evidence.

It assumes the codebase, model artifacts, and external dataset paths are already in place. The goal is to finish the remaining closure work with minimal repetition.

## Recommended Order

1. Clean-run reproducibility evidence
2. Explanation-quality sample review
3. Moderator trust/usability study
4. Final evidence summary and report integration

This order is intentional:

- first confirm the system runs end to end
- then review explanation quality on the actual running app
- then use the same running app for the moderator study
- then package the evidence once instead of rewriting it later

## Step 1: Clean-Run Reproducibility Evidence

### Objective

Prove the application and core pipeline can be run cleanly from the documented setup.

### Use

- `docs/phase-10/application-runbook.md`
- `docs/phase-10/clean-run-evidence-checklist.md`
- `docs/phase-10/clean-run-evidence-summary-template.md`

### Actions

1. Verify environment setup
   - backend Python environment
   - frontend Node environment
   - backend `.env`
   - frontend `.env.local`

2. Verify external data/model paths
   - labeled dataset exists
   - current train/unseen split exists
   - selected run model exists
   - `latest_run.txt` points to a valid run

3. Start backend
   - confirm `/health`
   - confirm moderation and explanation endpoints

4. Start frontend
   - confirm `/`, `/moderate`, `/batch`, `/decisions`

5. Capture smoke evidence
   - one single moderation example
   - one harmful explanation example
   - one what-if comparison example
   - one decision log/export example

6. Fill the clean-run checklist
7. Write the clean-run summary

### Output

- completed clean-run checklist
- completed clean-run summary

## Step 2: Explanation-Quality Review

### Objective

Produce auditable evidence that the moderator-facing Sinhala explanations and rewrites are understandable, grounded, and useful.

### Use

- `docs/phase-6/sinhala-explanation-and-rewrite-guideline.md`
- `docs/phase-6/explanation-quality-review-procedure.md`
- `docs/phase-6/explanation-quality-review-log-template.csv`

### Actions

1. Run the application with the selected model run
2. Collect at least `20` explanation outputs
   - recommended mix:
     - `8` HATE
     - `8` DISINFO
     - `4` NORMAL
3. For each item, record:
   - comment text
   - predicted label
   - explanation text
   - rewrite text if available
4. Fill the review log columns:
   - `explanation_clear`
   - `evidence_grounded`
   - `sinhala_natural`
   - `rewrite_useful`
   - `overclaiming_present`
   - `manual_followup_needed`
5. Summarize recurring strengths and failures

### Output

- completed explanation-quality review log
- short explanation-quality summary paragraph for the report

## Step 3: Moderator Trust/Usability Study

### Objective

Generate a small but structured user-study evidence pack for the moderator-facing application.

### Use

- `docs/phase-9/moderator-trust-usability-study-protocol.md`
- `docs/phase-9/moderator-study-results-template.csv`
- `docs/phase-9/moderator-study-summary-template.md`

### Actions

1. Recruit a small set of Sinhala-speaking reviewers
   - recommended: `5` to `10`

2. Prepare a task set
   - single moderation examples
   - harmful examples with explanations
   - what-if editing examples
   - short batch queue

3. Run each session
   - observe completion
   - record timing
   - collect ratings
   - capture qualitative comments

4. Fill the participant results CSV
5. Write the study summary

### Output

- completed moderator-study results CSV
- completed moderator-study summary

## Step 4: Final Packaging

### Objective

Bring the three evidence tracks into the report and final delivery package.

### Actions

1. Link the clean-run evidence in the reproducibility/delivery section
2. Link the explanation-quality review in the explainability section
3. Link the moderator study in the evaluation/usability section
4. Update the requirement traceability matrix status notes if final evidence is complete

### Minimum Final Package

Include:

- clean-run checklist
- clean-run summary
- explanation-quality review log
- moderator-study results CSV
- moderator-study summary
- selected model run id and main metrics

## Fastest Practical Execution Plan

If time is tight, do this:

### Day 1

1. run clean validation
2. fill clean-run checklist
3. collect 20 explanation samples
4. fill explanation-quality review log

### Day 2

1. run 5-participant moderator study
2. fill results CSV
3. write summary
4. integrate all evidence into the report

## Final Note

At this stage, the remaining work is evidence collection, not system design. Avoid creating more framework docs unless the report specifically demands them. The fastest route to closure is to execute the existing artifacts and fill them with real outputs.
