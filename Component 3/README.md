# Sinhala Harmful Content Moderation Console

This project provides a web application for reviewing Sinhala social media comments and identifying:

- `HATE`
- `DISINFO`
- `NORMAL`

The system includes:

- a backend API for moderation and explainability
- a frontend moderation dashboard
- AI feedback support using Google Vertex AI
- Docker deployment for easy setup

## What This Application Does

Moderators can:

- submit single comments
- review comments in batch
- see the predicted label and confidence
- inspect explanation evidence
- test safer rewrites
- log moderation decisions

## Recommended Deployment: Docker

This application is designed to be started with Docker.

### Before You Start

You need these items on your machine:

1. A trained model folder
2. A rewrite index folder
3. A Google Cloud `credentials.json` file if AI feedback is needed
4. Docker Desktop

### Setup

Copy the Docker environment template:

```powershell
Copy-Item .env.compose.example .env.compose
```

Then edit `.env.compose` and set:

- `MODEL_DIR_HOST`
- `REWRITE_DIR_HOST`
- `GCP_CREDENTIALS_HOST`

Notes:

- `GCP_PROJECT_ID` is optional in this project.
- If left empty, the backend will try to read the project id from `credentials.json`.
- If you do not want AI feedback, set `LLM_SUGGESTIONS_ENABLED=false`.

### Start

```powershell
docker compose --env-file .env.compose up --build
```

### Open the Application

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5000`
- Backend API docs: `http://localhost:5000/docs`

### Stop

```powershell
docker compose --env-file .env.compose down
```

## Main Files for Deployment

- Docker compose: `compose.yaml`
- Docker environment template: `.env.compose.example`
- Backend Docker image: `backend/Dockerfile`
- Frontend Docker image: `frontend/Dockerfile`
- Docker run guide: `docs/phase-1/docker-runbook.md`

## Important Notes

- The model and credentials are mounted as external volumes. They are not stored inside the Docker images.
- AI feedback is available only when:
  - `LLM_SUGGESTIONS_ENABLED=true`
  - the mounted `credentials.json` is valid
  - Vertex AI access is configured correctly
- SHAP and attention are supporting explainability features. They may take longer than the main moderation prediction.
