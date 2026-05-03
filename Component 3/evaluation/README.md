# Evaluation

Contains evaluation plans and outputs:

- `reports/` for model, robustness, and user-study reports

Store only lightweight reports/metadata in git. Keep large binary outputs out of version control.

## SBERT Leaderboard Evaluation

Use notebook `notebooks/phase5_evaluate_sbert_leaderboard.ipynb` to evaluate a trained SBERT model on unseen data, calibrate thresholds across all three classes, and append results to a leaderboard CSV.

Set these params in the first cell before running:
- `PROJECT_ROOT`
- `RUN_NAME` (optional)
- `MODEL_ROOT` / `REPORT_DIR` (optional overrides)

By default it auto-loads the latest training run from:
- `training/artifacts/runs/latest_run.txt`

Outputs:
- run summary JSON + per-source metrics CSV in `training/artifacts/runs/<run_id>/reports/`
- leaderboard append in `evaluation/reports/model_leaderboard.csv`
