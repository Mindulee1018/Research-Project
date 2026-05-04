# Current Implementation Status

This document is the working-state summary for the repository after the main implementation pass. It separates:

- implemented product capabilities
- requirement items that are still evidence-pending
- delivery items that still need execution rather than new feature work

Use this document as the short reference before starting new development work.

## 1. Core Capabilities Implemented

### Data and Modeling

- Source coverage implemented for:
  - `youtube`
  - `gossip_lanka`
  - `elakiri`
- Preprocessing, labeling, split-building, and notebook-first training workflow are implemented.
- Sentence-BERT-centered moderation model is implemented.
- Three-class inference is implemented for:
  - `HATE`
  - `DISINFO`
  - `NORMAL`
- Evaluation pipeline includes validation and unseen-set reporting.

### Explainability

- Main explanation endpoint is implemented.
- Strict SHAP endpoint behavior is implemented:
  - real SHAP output is returned when available
  - explainability-unavailable error is returned when strict SHAP cannot run
- Counterfactual / what-if explanation flow is implemented.
- Attention-support evidence is implemented using real active-model transformer attention.
- Rewrite / safer-phrasing suggestions are implemented.

### Backend

- Structured FastAPI moderation API is implemented.
- Dedicated endpoints exist for:
  - moderation
  - explanation
  - SHAP
  - counterfactual
  - attention
  - moderator decision logging/export/clear
- Health endpoint exposes model and explainability capability status.

### Frontend

- Single-item moderation workflow is implemented.
- Batch moderation workflow is implemented.
- Moderator evidence tabs are implemented for:
  - Explanation
  - SHAP
  - What-if
  - Attention
- Interactive what-if editor is implemented.
- Rewrite assistance is implemented.
- Moderator decision logging is implemented.
- Recent decisions audit view is implemented.
- Background loading and per-section performance visibility are implemented.

## 2. Important Honesty Constraints

The repository should now be described with the following wording:

- SHAP:
  - strict SHAP behavior is implemented
  - if SHAP is unavailable, the backend should fail that endpoint rather than silently substitute heuristic token weights
- Attention:
  - implemented as real active-model transformer attention support
  - should not be described as a literal AllenNLP-native integration unless that path is separately implemented and validated
- Attention remains supporting evidence only, not standalone explanation truth

## 3. Requirement Items Still Open

These are not primarily missing-feature problems anymore. Most are evidence, packaging, or study execution items.

### Still In Progress

- `D-02`
  - needs finalized labeled-data release artifact and supporting release metadata
- `D-04`
  - needs fuller split-manifest / dataset-card style closure for train/validation/test/unseen reproducibility
- `X-01`
  - explanation payload exists, but explanation QA evidence pack is still incomplete
- `X-02`
  - implementation exists, but planned SHAP evidence/sample-output pack is still incomplete
- `X-05`
  - guideline and templates exist, but manual review log must be filled with real samples
- `E-01`
  - evaluation work exists, but formal evaluation pack still needs cross-source/error-slice closure
- `E-02`
  - study protocol exists, but executed trust/usability findings are still missing
- `R-01`
  - runbook exists, but clean-run evidence still needs to be completed

### Still Planned

- `M-03`
  - optional comparator baseline
- `R-02`
  - final handover package and sign-off bundle

## 4. Development Guidance

For ongoing development work:

- treat the core application as implemented enough to continue product/backend/frontend refinement
- do not reopen settled questions about whether the project has SHAP, counterfactuals, Sentence-BERT, or batch moderation; those are implemented
- treat the remaining work as:
  - evidence collection
  - packaging
  - evaluation/study execution
  - incremental product improvement

## 5. Practical Next-Step Interpretation

The repository is now in a state where development can continue without waiting for more scope-definition work.

The main categories of future work are:

1. product development and UX refinement
2. backend performance and robustness improvements
3. evaluation and evidence collection
4. final report / handover packaging
