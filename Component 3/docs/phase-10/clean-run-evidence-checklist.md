# Clean-Run Evidence Checklist

## Purpose

This checklist is used to record evidence that the application and core research pipeline can be executed cleanly from the documented environment and artifact paths. It supports requirement `R-01`.

Use this together with:

- `docs/phase-10/application-runbook.md`

## Run Metadata

- Date:
- Operator:
- Machine/Server:
- OS:
- Python version:
- Node version:
- Repo commit:
- Active model run id:
- External data root:

## A. Environment Setup

Mark each as:

- `pass`
- `fail`
- `n/a`

| Step | Status | Notes |
|---|---|---|
| Python virtual environment available |  |  |
| Backend requirements installed |  |  |
| Notebook/training requirements installed |  |  |
| Frontend dependencies installed |  |  |
| Backend `.env` configured |  |  |
| Frontend `.env.local` configured |  |  |

## B. Data and Artifact Readiness

| Step | Status | Notes |
|---|---|---|
| Labeled dataset available at expected external path |  |  |
| Current train split available |  |  |
| Current unseen split available |  |  |
| Selected model artifact directory exists |  |  |
| `latest_run.txt` points to valid run |  |  |
| Rewrite index exists if suggestions enabled |  |  |

## C. Split / Training Pipeline

| Step | Status | Notes |
|---|---|---|
| Phase 4 split notebook runs successfully |  |  |
| Phase 5 training notebook runs successfully |  |  |
| Validation report generated |  |  |
| Unseen report generated |  |  |

## D. Backend Runtime

| Step | Status | Notes |
|---|---|---|
| Backend starts without initialization failure |  |  |
| `GET /health` returns success |  |  |
| `POST /api/moderate` returns prediction |  |  |
| `POST /api/explain` returns explanation payload |  |  |
| `POST /api/explain/shap` returns contributor payload |  |  |
| `POST /api/explain/counterfactual` returns candidate payload |  |  |
| `POST /api/explain/attention` returns supporting evidence |  |  |
| `POST /api/moderation/decision` logs successfully |  |  |
| Decision export works |  |  |

## E. Frontend Runtime

| Step | Status | Notes |
|---|---|---|
| Frontend starts successfully |  |  |
| Overview route loads |  |  |
| Moderate route loads |  |  |
| Batch route loads |  |  |
| Decisions route loads |  |  |
| Single-comment moderation works |  |  |
| Batch moderation works |  |  |
| What-if editor works |  |  |
| Final-label selection works before decision save |  |  |
| Decision list refresh/export works from UI |  |  |

## F. Smoke Example Evidence

Record at least one example for each:

- one single moderation request
- one harmful case with explanation + suggestion
- one what-if flow
- one decision log save/export

| Example | Status | Notes |
|---|---|---|
| Single comment example captured |  |  |
| Harmful explanation example captured |  |  |
| What-if comparison example captured |  |  |
| Decision export example captured |  |  |

## G. Outcome

- Overall result:
  - `pass`
  - `pass with notes`
  - `fail`

- Blocking issues:
  - 

- Non-blocking issues:
  - 

- Recommended follow-up:
  - 
