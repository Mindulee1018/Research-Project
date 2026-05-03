# Phase 3+: Annotation-to-Delivery Plan (Proposal-Aligned)

Date: 2026-03-14

## Objective
Close the remaining gap between current implementation and research-proposal requirements by executing:
- quality-controlled labeling freeze (`HATE`, `DISINFO`, `NORMAL`)
- Sentence-BERT-centered modeling
- required XAI stack (SHAP + counterfactual + attention-support)
- evaluation evidence pack (including unseen-data robustness and baseline comparisons)
- moderator-study + NFR validation for final delivery

## Entry Criteria
- Elakiri and Gossip Lanka datasets are already at large scale.
- YouTube Sinhala-focused scraping reached the current cycle threshold.
- Resume-safe source scrapers and logs are available.

## Updated Execution Plan
1. Phase A: Labeling Freeze (current active phase)
- Continue chunked LLM-assisted labeling and/or human labeling on workflow sheets.
- Merge annotator outputs and adjudicate conflicts.
- Produce versioned labeled dataset package with manifests and label distribution.
- Exit gate: D-02 can move to `done` only when conflict queue is resolved and dataset release artifacts are complete.

2. Phase B: Modeling (Sentence-BERT-centered)
- Implement training/evaluation pipeline centered on Sentence-BERT embeddings.
- Keep existing classifier-style model as comparator baseline, not primary claim.
- Store versioned train/val/test plus unseen holdout split manifests.
- Exit gate: M-01/M-02 pass with class-wise metrics and reproducible artifacts.

3. Phase C: Explainability Stack
- Implement SHAP text explanation flow.
- Implement counterfactual generation flow for harmful outputs.
- Add attention visualization as supporting evidence only (not standalone explanation proof).
- Exit gate: X-01..X-04 have API outputs, samples, and tests.

4. Phase D: Product Integration (Backend + Frontend)
- Expose structured FastAPI endpoints for moderation, SHAP, and counterfactuals.
- Frontend must support prediction, confidence, explanation tabs, and what-if interaction.
- Add decision logging schema for moderator actions.
- Exit gate: B-01/B-02 and F-01..F-05 functional acceptance checks pass.

5. Phase E: Evaluation & Final Validation
- Run baseline comparisons (SBERT primary vs comparator models).
- Run unseen-data robustness evaluation with error analysis.
- Execute moderator trust/usability study and summarize findings.
- Validate NFR evidence: single inference latency target, daily throughput target, uptime/error behavior.
- Exit gate: E-01/E-02 and delivery evidence pack (R-01/R-02) complete.

## Deliverables
- `data/datasets/labeled/<version>/` dataset release package
- SBERT model artifacts + eval report + baseline comparison table
- XAI artifact set (SHAP outputs, counterfactual outputs, attention-support samples)
- User-study report + NFR validation report
- Updated RTM status and acceptance evidence links for all closed items

## Immediate Next Actions (Operational)
- Snapshot completed: `freeze_20260314_114841`.
- Unified annotation queue completed: `data/annotation_queue/raw_candidates_freeze_20260314_114841.csv` (36,630 rows).
- Annotation workflow in use with guideline `annotation/guidelines/label-guideline-v1.0.md`.
- Auto-labeling pipeline available:
  - `./scripts/run-auto-label-gemini.ps1 -ProjectId <gcp-project-id> -MaxRows 500`
- Next required milestone: complete Phase A exit gate and freeze labeled package.

## Pre-Label Cleanup (Completed)
- Final pipeline command:
  - `./scripts/run-final-cleaned-dataset.ps1 -SinhalaThreshold 0.2 -MinTextChars 8 -MaxTextChars 1200`
- Final output:
  - `data/datasets/final_cleaned_dataset.csv`
  - `data/datasets/final_cleaned_dataset_summary.json`
