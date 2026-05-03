# Application Runbook

## Purpose

This runbook describes how to start the moderation application end to end using the current external dataset/model layout.

This runbook assumes:

- code repository path is the project repo
- datasets and model artifacts are stored outside the repo
- backend and frontend run from the repository working tree

## Current External Storage Layout

Expected external root:

- Linux/server: `/root/separate_volume`
- Windows/local example: `D:\\client-projects\\sl-social-media-risk-analysis`

Important external paths:

- labeled dataset:
  - `datasets/labeled/annotator_a_llm.csv`
- current split outputs:
  - `datasets/splits/current/train_labeled_331.csv`
  - `datasets/splits/current/unseen_labeled_rest.csv`
- training runs:
  - `training/artifacts/runs/run_<timestamp>/`
- active run pointer:
  - `training/artifacts/runs/latest_run.txt`

## 1. Environment Setup

### Backend Python environment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
pip install -r notebooks/requirements.txt
```

### Frontend Node environment

```powershell
cd frontend
npm install
cd ..
```

## 2. Required Backend Environment Variables

Create `backend/.env` from `backend/.env.example` and set the following:

```env
MODEL_DIR=D:/client-projects/sl-social-media-risk-analysis/training/artifacts/runs/run_YYYYMMDD_HHMMSS/model
REWRITE_DIR=D:/client-projects/sl-social-media-risk-analysis/training/artifacts/runs/run_YYYYMMDD_HHMMSS/rewrite_index
DECISION_LOG_PATH=D:/client-projects/sl-social-media-risk-analysis/backend/runtime/moderator_decisions.jsonl

GCP_CREDENTIALS_PATH=D:/Desktop/Projects/client/sl-social-media-risk-analysis/credential.json
GCP_LOCATION=us-central1
GENAI_MODEL=gemini-2.5-flash-lite
LLM_SUGGESTIONS_ENABLED=true
```

Notes:

- `MODEL_DIR` must point to the selected run’s `model/` folder.
- `REWRITE_DIR` must point to the selected run’s `rewrite_index/` folder if rewrite suggestions are enabled.
- `GCP_PROJECT_ID` can be omitted if it is present inside the service-account JSON.
- If LLM feedback is not needed, set `LLM_SUGGESTIONS_ENABLED=false`.

## 3. Required Frontend Environment Variables

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE=http://127.0.0.1:5000
NEXT_PUBLIC_MODERATOR_ID=ui_moderator
```

## 4. Dataset / Split Preparation

If labeled data has changed, rebuild the train and unseen split first.

```powershell
jupyter nbconvert --to notebook --execute notebooks/phase4_build_train_unseen_331.ipynb --ExecutePreprocessor.timeout=-1 --log-level=INFO --output phase4_build_train_unseen_331.executed.ipynb
```

This uses:

- labeled source: `datasets/labeled/annotator_a_llm.csv`
- current target ratios defined in the notebook
- preprocessing-aware filtering before train/unseen generation

## 5. Model Training

Train the current Sentence-BERT pipeline:

```powershell
jupyter nbconvert --to notebook --execute notebooks/phase5_train_classifier_sbert.ipynb --ExecutePreprocessor.timeout=-1 --log-level=INFO --output phase5_train_classifier_sbert.executed.ipynb
```

Background Linux/server example:

```bash
nohup jupyter nbconvert --to notebook --execute notebooks/phase5_train_classifier_sbert.ipynb --ExecutePreprocessor.timeout=-1 --log-level=INFO --output phase5_train_classifier_sbert.executed.ipynb > /tmp/phase5_train.log 2>&1 &
tail -f /tmp/phase5_train.log
```

Training outputs are written under:

- `training/artifacts/runs/run_<timestamp>/model`
- `training/artifacts/runs/run_<timestamp>/reports`

The active run is referenced by:

- `training/artifacts/runs/latest_run.txt`

## 6. Backend Startup

Start the API from the `backend/` directory:

```powershell
cd backend
python main.py
```

Expected local base URL:

- `http://127.0.0.1:5000`

Check health:

- `GET /health`
- OpenAPI docs: `GET /docs`

## 7. Frontend Startup

Start the Next.js app:

```powershell
cd frontend
npm run dev
```

Default local frontend:

- `http://127.0.0.1:3000`

Available moderator views:

- `/`
- `/moderate`
- `/batch`
- `/decisions`

## 8. Core App Workflow

### Single moderation

1. Open `/moderate`
2. Enter a Sinhala comment
3. Add it to the queue
4. Run analysis
5. Inspect:
   - predicted class
   - confidence
   - explanation and suggestion output
   - SHAP token evidence
   - counterfactual candidates
   - attention-supporting evidence
6. Log moderator decision with final label and notes

### Batch moderation

1. Open `/batch`
2. Paste one comment per line
3. Queue the batch
4. Run queued batch
5. Review items individually

### What-if workflow

1. Open a reviewed queue item
2. Go to `Counterfactual (What-if)`
3. Edit the text in the sandbox
4. Run what-if analysis
5. Compare original vs edited outcome
6. Optionally reuse a generated candidate rewrite and rerun

## 9. Decision Logging and Export

The moderator console supports:

- final-label selection
- approve/reject/escalate/rewrite actions
- optional notes
- recent-decision refresh
- JSON export
- CSV export

Decision log backend endpoint set:

- `POST /api/moderation/decision`
- `GET /api/moderation/decision`
- `GET /api/moderation/decision/export`

## 10. Evaluation Commands

Validation error extraction:

```powershell
jupyter nbconvert --to notebook --execute notebooks/phase5_extract_error_cases.ipynb --ExecutePreprocessor.timeout=-1 --log-level=INFO --output phase5_extract_error_cases.executed.ipynb
```

Unseen evaluation:

```powershell
jupyter nbconvert --to notebook --execute notebooks/phase5_evaluate_unseen_sbert.ipynb --ExecutePreprocessor.timeout=-1 --log-level=INFO --output phase5_evaluate_unseen_sbert.executed.ipynb
```

Leaderboard comparison:

- `notebooks/phase5_evaluate_sbert_leaderboard.ipynb`

## 11. Common Failure Checks

### Backend says model not initialized

Check:

- `MODEL_DIR` points to a valid run `model/` directory
- the selected run contains:
  - `model/meta.json`
  - `model/sbert_model/`
  - `model/embedding_classifier.pkl`

### LLM feedback disabled

Check:

- service-account JSON path exists
- location is correct
- project id is in the credential file or explicitly set
- outbound access to Vertex AI is available

### Frontend loads but cannot call backend

Check:

- `NEXT_PUBLIC_API_BASE`
- backend is actually running on the configured port
- browser console for CORS or fetch errors

### What-if or explanation tabs fail

Check:

- `/api/moderate`
- `/api/explain`
- `/api/explain/shap`
- `/api/explain/counterfactual`
- `/api/explain/attention`

If one of these fails, the frontend panel will show an error state.

## 12. Handover Minimum Checklist

Before treating the application build as handover-ready:

- backend starts from documented env
- frontend starts from documented env
- `/health` succeeds
- one single-comment moderation works
- one batch moderation flow works
- moderator decision can be logged and exported
- what-if flow can compare original vs edited text
- selected model run id is recorded in project notes/report
