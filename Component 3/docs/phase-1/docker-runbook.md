# Docker Runbook

This is the simplest way to run the application.

## 1. Prepare the environment file

Copy the template:

```powershell
Copy-Item .env.compose.example .env.compose
```

Open `.env.compose` and set these paths:

- `MODEL_DIR_HOST`
- `REWRITE_DIR_HOST`
- `GCP_CREDENTIALS_HOST`

If you do not want AI feedback, set:

```env
LLM_SUGGESTIONS_ENABLED=false
```

If `GCP_PROJECT_ID` is empty, the backend will try to read it from `credentials.json`.

## 2. Start the application

```powershell
docker compose --env-file .env.compose up --build
```

## 3. Open it

- Frontend: `http://localhost:3000`
- Backend API docs: `http://localhost:5000/docs`

## 4. Stop it

```powershell
docker compose --env-file .env.compose down
```

## Notes

- Model files and credentials are mounted from your machine. They are not copied into Docker images.
- Moderator decisions are stored in a Docker volume named `backend_runtime`.
- If SHAP is too slow, reduce `SHAP_MAX_EVALS_FAST` in `.env.compose`.
