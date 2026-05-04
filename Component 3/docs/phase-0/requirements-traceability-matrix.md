# Phase 0: Requirement Traceability Matrix

Status key: `planned` | `in_progress` | `done`

| Req ID | Area | Requirement | Priority | Acceptance Reference | Planned Evidence Artifact | Target Phase | Status |
|---|---|---|---|---|---|---|---|
| D-01 | Data | Collect Sinhala content from **YouTube**, **Gossip Lanka**, **Elakiri** | MUST | AC-D-01 | Source ingestion runs + source coverage report | Phase 2 | done |
| D-02 | Data | Preprocess and label data into `HATE`, `DISINFO`, `NORMAL` | MUST | AC-D-02 | Labeled dataset release + label distribution report | Phase 3 | in_progress |
| D-03 | Data | Maintain metadata (source, URL/ID, scrape timestamp, raw/clean text) | MUST | AC-D-03 | Data schema + versioned parquet/csv manifests | Phase 2 | done |
| D-04 | Data | Versioned train/val/test splits and unseen robustness sets | MUST | AC-D-04 | Split manifest files + dataset card | Phase 4 | in_progress |
| M-01 | Modeling | Build a **Sentence-BERT-centered** moderation model | MUST | AC-M-01 | Training pipeline + model artifact + metadata | Phase 5 | done |
| M-02 | Modeling | Predict `HATE` / `DISINFO` / `NORMAL` with confidence scores | MUST | AC-M-02 | Inference outputs + eval metrics report | Phase 5 | done |
| M-03 | Modeling | Optional comparator baseline model for benchmarking | NICE | AC-M-03 | Baseline comparison table | Phase 5 | planned |
| X-01 | Explainability | Provide transparent explanation for each moderation decision | MUST | AC-X-01 | Explanation payload snapshots + QA checklist | Phase 6 | in_progress |
| X-02 | Explainability | Implement **SHAP** explanation flow for text predictions | MUST | AC-X-02 | SHAP service + tests + sample outputs | Phase 6 | in_progress |
| X-03 | Explainability | Implement **counterfactual** explanation generation | MUST | AC-X-03 | Counterfactual service + tests + sample outputs | Phase 6 | done |
| X-04 | Explainability | Provide attention visualization as supporting evidence | MUST | AC-X-04 | Attention output and UI rendering samples | Phase 6 | done |
| X-05 | Explainability | Ensure culturally-contextual Sinhala explanation language | MUST | AC-X-05 | Explanation style guideline + manual review log | Phase 6 | in_progress |
| B-01 | Backend | Expose structured JSON API for moderation + explanations | MUST | AC-B-01 | OpenAPI spec + contract tests | Phase 7 | done |
| B-02 | Backend | Include dedicated endpoints for moderation, SHAP, counterfactuals | MUST | AC-B-02 | Endpoint test suite + API docs | Phase 7 | done |
| F-01 | Frontend | Moderator workflow for single and **batch** review | MUST | AC-F-01 | UI flow demo + end-to-end tests | Phase 8 | done |
| F-02 | Frontend | Show class, confidence, and explanatory word evidence | MUST | AC-F-02 | UI snapshots + usability checklist | Phase 8 | done |
| F-03 | Frontend | Support interactive what-if (counterfactual) exploration | MUST | AC-F-03 | Counterfactual UX flow + telemetry | Phase 8 | done |
| F-04 | Frontend | Provide rewrite/safer phrasing suggestions for harmful outputs | MUST | AC-F-04 | Suggestion module demo + test cases | Phase 8 | done |
| F-05 | Frontend | Log moderator decisions for later user-study analysis | MUST | AC-F-05 | Decision log export + schema doc | Phase 8 | done |
| E-01 | Evaluation | Measure class-wise quality, cross-source validity, unseen robustness | MUST | AC-E-01 | Evaluation report + confusion matrices | Phase 9 | in_progress |
| E-02 | Evaluation | Run moderator trust/usability/user-study evaluation | MUST | AC-E-02 | Study protocol + analyzed findings | Phase 9 | in_progress |
| R-01 | Delivery | Deliver reproducible end-to-end pipeline and runbooks | MUST | AC-R-01 | Repro guide + clean-run evidence | Phase 10 | in_progress |
| R-02 | Delivery | Final technical report, demo, and acceptance package | MUST | AC-R-02 | Handover package + sign-off record | Phase 11 | planned |

## Notes
- This matrix is the control document for scope. Any new requirement must be added with a new `Req ID`.
- `Acceptance Reference` values map to `acceptance-criteria-v1.md`.
- `in_progress` is used for items where the core implementation exists but the planned acceptance evidence is still incomplete.
- Current explainability status:
  - `X-02`: strict SHAP endpoint behavior is implemented in backend/frontend contract and code, but the planned evidence pack/sample outputs are still pending.
  - `X-04`: attention-support evidence is implemented using real active-model encoder attention. This should be described honestly as supporting transformer attention evidence, not as a literal AllenNLP-native integration claim.
