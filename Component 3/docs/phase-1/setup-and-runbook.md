# Phase 1: Setup and Runbook

## Prerequisites
- Python 3.11+ available as `python`
- Node.js 20+ with `npm`
- PowerShell 7+ (recommended on Windows)

## One-Time Setup
```powershell
./scripts/setup-dev.ps1
```

## Daily Smoke Check
```powershell
./scripts/smoke.ps1
```

## Manual Run Commands
### Backend
```powershell
cd backend
copy .env.example .env
python main.py
```

### Frontend
```powershell
cd frontend
npm run dev
```

### Training Evaluation
Open and run:
- `notebooks/phase5_evaluate_sbert_leaderboard.ipynb`

## Notes
- Use notebooks under `notebooks/` for training and model-building workflows.
- CI currently enforces structure/syntax/lint smoke only; deeper tests are added in later phases.
