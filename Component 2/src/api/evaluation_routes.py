# src/api/evaluation_routes.py

import os
import json
from fastapi import APIRouter

router = APIRouter()

ARTIFACTS_DIR = "artifacts"

BASE_EVAL_PATH = os.path.join(ARTIFACTS_DIR, "evaluation_base_results.json")
ADAPTIVE_EVAL_PATH = os.path.join(ARTIFACTS_DIR, "evaluation_adaptive_results.json")
LATEST_MODEL_FILE = os.path.join(ARTIFACTS_DIR, "adaptive_models", "latest_model.txt")


def load_json_file(path):
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def percent(value):
    if value is None:
        return None
    return round(float(value) * 100, 2)


def get_latest_model_name():
    if not os.path.exists(LATEST_MODEL_FILE):
        return None

    with open(LATEST_MODEL_FILE, "r", encoding="utf-8") as f:
        model_path = f.read().strip()

    if not model_path:
        return None

    return os.path.basename(model_path.replace("\\", "/"))


@router.get("/api/evaluation/summary")
def evaluation_summary():
    base = load_json_file(BASE_EVAL_PATH)
    adaptive = load_json_file(ADAPTIVE_EVAL_PATH)

    if not base and not adaptive:
        return {
            "available": False,
            "message": "No evaluation results found. Run base and adaptive evaluation first.",
        }

    base_metrics = {
        "accuracy": percent(base.get("accuracy")) if base else None,
        "precision": percent(base.get("weighted_precision")) if base else None,
        "recall": percent(base.get("weighted_recall")) if base else None,
        "f1": percent(base.get("weighted_f1")) if base else None,
        "confusion_matrix": base.get("confusion_matrix") if base else None,
    }

    adaptive_metrics = {
        "accuracy": percent(adaptive.get("accuracy")) if adaptive else None,
        "precision": percent(adaptive.get("weighted_precision")) if adaptive else None,
        "recall": percent(adaptive.get("weighted_recall")) if adaptive else None,
        "f1": percent(adaptive.get("weighted_f1")) if adaptive else None,
        "confusion_matrix": adaptive.get("confusion_matrix") if adaptive else None,
    }

    improvement = {
        "accuracy": (
            round(adaptive_metrics["accuracy"] - base_metrics["accuracy"], 2)
            if adaptive_metrics["accuracy"] is not None and base_metrics["accuracy"] is not None
            else None
        ),
        "precision": (
            round(adaptive_metrics["precision"] - base_metrics["precision"], 2)
            if adaptive_metrics["precision"] is not None and base_metrics["precision"] is not None
            else None
        ),
        "recall": (
            round(adaptive_metrics["recall"] - base_metrics["recall"], 2)
            if adaptive_metrics["recall"] is not None and base_metrics["recall"] is not None
            else None
        ),
        "f1": (
            round(adaptive_metrics["f1"] - base_metrics["f1"], 2)
            if adaptive_metrics["f1"] is not None and base_metrics["f1"] is not None
            else None
        ),
    }

    return {
        "available": True,
        "evaluation_type": "HATE vs NORMAL",
        "latest_model": get_latest_model_name(),
        "test_rows": adaptive.get("total_rows") if adaptive else base.get("total_rows"),
        "base": base_metrics,
        "adaptive": adaptive_metrics,
        "improvement": improvement,
    }