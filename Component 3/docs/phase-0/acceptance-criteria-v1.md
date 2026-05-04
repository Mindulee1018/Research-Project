# Phase 0: Acceptance Criteria (v1 Draft)

This file defines measurable pass/fail criteria for each requirement in the traceability matrix.

## Data

### AC-D-01
- All three required data sources are present in the ingested dataset: `youtube`, `gossip_lanka`, `elakiri`.
- Each source has at least one verified ingestion run recorded with timestamp and run ID.

### AC-D-02
- Final labeled dataset contains only `HATE`, `DISINFO`, `NORMAL`.
- Label distribution report is generated for each data release.
- Annotation guideline version is referenced in the release metadata.

### AC-D-03
- Each record includes: `source`, `source_item_id_or_url`, `scraped_at`, `raw_text`, `clean_text`.
- Schema validation passes with zero missing mandatory fields.

### AC-D-04
- Reproducible split manifests exist for `train`, `validation`, `test`, plus at least one unseen/robustness split.
- A rerun with the same split seed reproduces identical record IDs.

## Modeling

### AC-M-01
- Sentence-BERT-centered training pipeline is implemented and reproducible from config.
- Model artifact includes versioned metadata: model ID, training dataset version, label map, training timestamp.

### AC-M-02
- Inference produces class probabilities for all three classes and top prediction.
- Evaluation report includes per-class precision, recall, F1, and macro-F1.

### AC-M-03 (NICE)
- Comparator baseline is trained and evaluated on the same split.
- Comparison table shows key metrics and relative deltas.

## Explainability

### AC-X-01
- Every prediction response can return an explanation payload.
- Explanation payload includes method metadata and confidence context.

### AC-X-02
- SHAP explanation endpoint returns top contributing features/tokens and contribution values.
- SHAP outputs are renderable in UI without manual post-processing.

### AC-X-03
- Counterfactual endpoint returns at least one valid text variant that changes model decision or confidence in the intended direction.
- Counterfactual payload includes edit rationale and score delta.

### AC-X-04
- Attention evidence (supporting only) is available in API and displayed in UI.
- Documentation explicitly states attention is not used as sole explanation.

### AC-X-05
- Explanation language guideline for Sinhala context is documented.
- Manual review sample confirms explanations are culturally understandable and not template-only.

## Backend

### AC-B-01
- OpenAPI docs cover all moderation and explanation endpoints with request/response schemas.
- Contract tests pass for success and failure paths.

### AC-B-02
- Dedicated endpoints exist for moderation, SHAP, and counterfactual functionality.
- Endpoint-level tests pass with stable response shapes.

## Frontend

### AC-F-01
- Moderator can submit one item and review batch items in a queue workflow.
- Batch progress state is visible and recoverable on refresh.

### AC-F-02
- UI shows predicted class, confidence, and explanatory evidence for each reviewed item.

### AC-F-03
- Moderator can run what-if analysis and compare original vs counterfactual outputs.

### AC-F-04
- Harmful predictions include rewrite suggestions with selectable alternatives.

### AC-F-05
- Moderator actions are persisted to decision logs with timestamps and item IDs.
- Logs can be exported in a structured format (CSV or JSON).

## Evaluation

### AC-E-01
- Evaluation report includes:
  - per-class metrics
  - cross-source validation
  - unseen robustness results
  - error analysis slices

### AC-E-02
- User-study protocol is documented and executed with captured outcomes.
- Final report includes trust/usability findings and actionable improvements.

## Delivery

### AC-R-01
- A documented clean-run procedure reproduces training, backend startup, and frontend startup on a fresh environment.

### AC-R-02
- Handover package includes architecture, setup, API docs, evaluation report, and demo script.
- Client sign-off checklist is completed.

## Thresholds To Confirm In Sign-Off
- Inter-annotator agreement minimum (recommended default): `kappa >= 0.70`.
- Minimum model quality gate (recommended default): `macro-F1 >= 0.75` with harmful-class floors.
- API latency gate (recommended default): define `p95` target for deployment hardware.
