# src/core/evaluate_model.py

import os
import json
import argparse

import pandas as pd
import torch

from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix,
)

from transformers import AutoTokenizer, AutoModelForSequenceClassification


# =========================
# Model paths
# =========================

BASE_MODEL_REPO = "Imaya2002/sinhala-hate-classifier-v2"

ADAPTIVE_MODEL_DIR = "artifacts/adaptive_models"
LATEST_MODEL_FILE = os.path.join(ADAPTIVE_MODEL_DIR, "latest_model.txt")


# =========================
# Binary evaluation labels
# =========================
# Component 2 focuses on hate speech drift.
# Therefore evaluation is binary:
#   0 = HATE
#   1 = NORMAL
#
# Component 1 classifier still outputs:
#   0 = HATE
#   1 = DISINFO
#   2 = NORMAL
#
# For this evaluation:
#   DISINFO is treated as NORMAL.

BINARY_ID2LABEL = {
    0: "HATE",
    1: "NORMAL",
}


def get_latest_adaptive_model_path() -> str:
    """
    Returns the newest locally saved adaptive model path.
    If latest_model.txt is missing or invalid, falls back to the base model.
    """
    if os.path.exists(LATEST_MODEL_FILE):
        with open(LATEST_MODEL_FILE, "r", encoding="utf-8") as f:
            latest = f.read().strip()

        if latest and os.path.exists(latest):
            return latest

    print("No valid adaptive model found. Falling back to base Hugging Face model.")
    return BASE_MODEL_REPO


def get_model_path(model_type: str) -> str:
    """
    model_type:
      - base
      - adaptive
    """
    if model_type == "base":
        return BASE_MODEL_REPO

    return get_latest_adaptive_model_path()


def find_text_column(df: pd.DataFrame) -> str:
    """
    Supports different CSV formats.
    """
    candidates = [
        "Cleaned Comment",
        "cleaned_comment",
        "text",
        "comment",
        "Original Comment",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    raise ValueError(
        f"No text column found. Expected one of {candidates}. "
        f"Found columns: {list(df.columns)}"
    )


def get_true_label(row) -> int:
    """
    Convert dataset label into binary label:
      HATE   -> 0
      NORMAL -> 1

    DISINFO is treated as NORMAL.
    """

    # Format 1: direct Label column
    # Example: HATE, DISINFO, NORMAL, OFF, NOT
    if "Label" in row and pd.notna(row["Label"]):
        label = str(row["Label"]).strip().upper()

        if label in ["HATE", "OFF"]:
            return 0

        if label in ["NORMAL", "DISINFO", "NOT"]:
            return 1

    # Format 2: lowercase label column
    # Example: HATE, NORMAL, OFF, NOT
    if "label" in row and pd.notna(row["label"]):
        label = str(row["label"]).strip().upper()

        if label in ["HATE", "OFF"]:
            return 0

        if label in ["NORMAL", "DISINFO", "NOT"]:
            return 1

    # Format 3: one-hot columns
    # Example: Hate, Disinfo, Normal
    hate = int(row.get("Hate", 0) or 0)

    if hate == 1:
        return 0

    return 1


def predict_binary_label(text: str, tokenizer, model) -> int:
    """
    Predict using the 3-class model, then convert to binary.

    Original model output:
      0 = HATE
      1 = DISINFO
      2 = NORMAL

    Binary output:
      0 = HATE
      1 = NORMAL
    """

    inputs = tokenizer(
        str(text),
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=128,
    )

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        pred_id = int(torch.argmax(logits, dim=-1).item())

    if pred_id == 0:
        return 0

    return 1


def evaluate_model(
    test_csv_path: str = "data/test/test_set.csv",
    output_path: str = "artifacts/evaluation_results.json",
    model_type: str = "adaptive",
) -> dict:
    """
    Evaluate either:
      - base Hugging Face model
      - latest adaptive model

    Supported test CSV formats:

    Format 1:
      Cleaned Comment, Label

    Format 2:
      text, label

    Format 3:
      Cleaned Comment, Hate, Disinfo, Normal
    """

    if model_type not in ["base", "adaptive"]:
        raise ValueError("model_type must be either 'base' or 'adaptive'.")

    if not os.path.exists(test_csv_path):
        raise FileNotFoundError(f"Test file not found: {test_csv_path}")

    df = pd.read_csv(test_csv_path, encoding="utf-8-sig")

    if df.empty:
        raise ValueError("Test dataset is empty.")

    text_col = find_text_column(df)

    df = df.copy()
    df["text_for_eval"] = df[text_col].fillna("").astype(str).str.strip()

    # Remove empty / very short rows
    df = df[df["text_for_eval"].str.len() >= 3]

    if df.empty:
        raise ValueError("No valid text rows found after cleaning.")

    df["true_label_id"] = df.apply(get_true_label, axis=1)

    model_path = get_model_path(model_type)

    print(f"Loading {model_type} model from: {model_path}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        fix_mistral_regex=True,
    )

    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.eval()

    predictions = []

    texts = df["text_for_eval"].tolist()

    for i, text in enumerate(texts):
        pred = predict_binary_label(text, tokenizer, model)
        predictions.append(pred)

        if (i + 1) % 50 == 0:
            print(f"Evaluated {i + 1}/{len(texts)} rows...")

    df["pred_label_id"] = predictions

    df["true_label"] = df["true_label_id"].map(BINARY_ID2LABEL)
    df["pred_label"] = df["pred_label_id"].map(BINARY_ID2LABEL)

    y_true = df["true_label_id"].tolist()
    y_pred = df["pred_label_id"].tolist()

    accuracy = accuracy_score(y_true, y_pred)

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=[0, 1],
        average="weighted",
        zero_division=0,
    )

    report = classification_report(
        y_true,
        y_pred,
        labels=[0, 1],
        target_names=["HATE", "NORMAL"],
        zero_division=0,
        output_dict=True,
    )

    cm = confusion_matrix(
        y_true,
        y_pred,
        labels=[0, 1],
    )

    result = {
        "model_type": model_type,
        "model_path": model_path,
        "test_file": test_csv_path,
        "evaluation_type": "binary_hate_vs_normal",
        "note": "DISINFO is treated as NORMAL for Component 2 evaluation.",
        "total_rows": int(len(df)),
        "accuracy": float(accuracy),
        "weighted_precision": float(precision),
        "weighted_recall": float(recall),
        "weighted_f1": float(f1),
        "confusion_matrix_labels": ["HATE", "NORMAL"],
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    predictions_path = f"artifacts/evaluation_predictions_{model_type}.csv"

    df[
        [
            "text_for_eval",
            "true_label",
            "pred_label",
        ]
    ].to_csv(
        predictions_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n========== Evaluation Results ==========")
    print(f"Model type: {model_type}")
    print(f"Model path: {model_path}")
    print(f"Test file: {test_csv_path}")
    print(f"Rows: {len(df)}")
    print("Evaluation type: HATE vs NORMAL")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Weighted Precision: {precision:.4f}")
    print(f"Weighted Recall: {recall:.4f}")
    print(f"Weighted F1-score: {f1:.4f}")

    print("\nConfusion Matrix labels: HATE, NORMAL")
    print(cm)

    print(f"\nSaved result JSON: {output_path}")
    print(f"Saved predictions CSV: {predictions_path}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate base or adaptive Sinhala hate speech classifier."
    )

    parser.add_argument(
        "--model",
        choices=["base", "adaptive"],
        default="adaptive",
        help="Choose model to evaluate: base or adaptive.",
    )

    parser.add_argument(
        "--test",
        default="data/test/test_set.csv",
        help="Path to labelled test CSV file.",
    )

    args = parser.parse_args()

    output_file = (
        "artifacts/evaluation_base_results.json"
        if args.model == "base"
        else "artifacts/evaluation_adaptive_results.json"
    )

    evaluate_model(
        test_csv_path=args.test,
        output_path=output_file,
        model_type=args.model,
    )


if __name__ == "__main__":
    main()