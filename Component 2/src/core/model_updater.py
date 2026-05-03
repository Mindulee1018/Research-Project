# src/core/model_updater.py

import os
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
)

# Component 1 Hugging Face classifier
BASE_MODEL_REPO = "Imaya2002/sinhala-hate-classifier-v2"

# Model version folders
ADAPTIVE_MODEL_DIR = "artifacts/adaptive_models"
LATEST_MODEL_FILE = os.path.join(ADAPTIVE_MODEL_DIR, "latest_model.txt")
MODEL_UPDATE_LOG = "artifacts/model_update_log.jsonl"

# Must match Component 1 predictor.py
LABEL2ID = {
    "HATE": 0,
    "DISINFO": 1,
    "NORMAL": 2,
}

ID2LABEL = {
    0: "HATE",
    1: "DISINFO",
    2: "NORMAL",
}


class CommentDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=128):
        self.texts = list(texts)
        self.labels = list(labels)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = int(self.labels[idx])

        enc = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(label, dtype=torch.long)
        return item


def _ensure_dirs():
    os.makedirs(ADAPTIVE_MODEL_DIR, exist_ok=True)
    os.makedirs("artifacts", exist_ok=True)


def get_latest_model_path() -> str:
    """
    Returns latest adaptive model path if available.
    Otherwise returns Component 1 base Hugging Face model repo.
    """
    if os.path.exists(LATEST_MODEL_FILE):
        with open(LATEST_MODEL_FILE, "r", encoding="utf-8") as f:
            latest = f.read().strip()
        if latest and os.path.exists(latest):
            return latest

    return BASE_MODEL_REPO


def _next_version_path(batch_no: str) -> str:
    """
    Creates a version folder name like:
    artifacts/adaptive_models/model_v001_batch_3
    """
    _ensure_dirs()

    existing = [
        d for d in os.listdir(ADAPTIVE_MODEL_DIR)
        if d.startswith("model_v") and os.path.isdir(os.path.join(ADAPTIVE_MODEL_DIR, d))
    ]

    version_no = len(existing) + 1
    safe_batch = str(batch_no).replace("/", "_").replace("\\", "_").replace(" ", "_")

    folder_name = f"model_v{version_no:03d}_{safe_batch}"
    return os.path.join(ADAPTIVE_MODEL_DIR, folder_name)


def _write_latest_model(model_path: str):
    _ensure_dirs()
    with open(LATEST_MODEL_FILE, "w", encoding="utf-8") as f:
        f.write(model_path)


def _append_model_log(event: dict):
    _ensure_dirs()
    with open(MODEL_UPDATE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _find_text_column(df: pd.DataFrame) -> str:
    """
    Supports both:
    - Component 1 output: Cleaned Comment
    - Component 2 sample batches: text
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
        f"No text column found. Expected one of {candidates}. Found: {list(df.columns)}"
    )


def _create_label_id(row) -> int:
    """
    Converts different dataset formats into Component 1 label ids.

    Component 1 model:
      HATE    -> 0
      DISINFO -> 1
      NORMAL  -> 2

    Supports:
    - Label column: HATE / DISINFO / NORMAL
    - Label column: OFF / NOT
    - One-hot columns: Hate / Disinfo / Normal
    """
    # Format 1: direct label column
    if "Label" in row and pd.notna(row["Label"]):
        label = str(row["Label"]).strip().upper()

        if label in LABEL2ID:
            return LABEL2ID[label]

        if label == "OFF":
            return LABEL2ID["HATE"]

        if label == "NOT":
            return LABEL2ID["NORMAL"]

    # Format 2: lowercase label column from sample batches
    if "label" in row and pd.notna(row["label"]):
        label = str(row["label"]).strip().upper()

        if label in LABEL2ID:
            return LABEL2ID[label]

        if label == "OFF":
            return LABEL2ID["HATE"]

        if label == "NOT":
            return LABEL2ID["NORMAL"]

    # Format 3: one-hot / binary columns
    hate = int(row.get("Hate", 0) or 0)
    disinfo = int(row.get("Disinfo", 0) or 0)
    normal = int(row.get("Normal", 0) or 0)

    if hate == 1:
        return LABEL2ID["HATE"]

    if disinfo == 1:
        return LABEL2ID["DISINFO"]

    if normal == 1:
        return LABEL2ID["NORMAL"]

    # Default fallback
    return LABEL2ID["NORMAL"]


def load_training_data_from_files(files: list[str]) -> pd.DataFrame:
    """
    Loads training data from triggered/recent batch files.
    Keeps only text + label_id.
    """
    frames = []

    for path in files:
        if not os.path.exists(path):
            continue

        df = pd.read_csv(path, encoding="utf-8-sig")
        if df.empty:
            continue

        text_col = _find_text_column(df)

        out = pd.DataFrame()
        out["text"] = df[text_col].fillna("").astype(str)
        out["label_id"] = df.apply(_create_label_id, axis=1)

        # remove empty/too-short text
        out["text"] = out["text"].str.strip()
        out = out[out["text"].str.len() >= 3]

        frames.append(out)

    if not frames:
        return pd.DataFrame(columns=["text", "label_id"])

    result = pd.concat(frames, ignore_index=True)
    result = result.drop_duplicates(subset=["text"])
    return result


def _resolve_training_files(
    trigger_event: dict,
    processed_folder: str,
    baseline_window: int,
) -> list[str]:
    """
    Uses recent processed files up to the triggered batch.
    Example:
      batch_1.csv, batch_2.csv, batch_3.csv
    """
    batch_no = str(trigger_event.get("batch_no", "")).strip()

    if not os.path.exists(processed_folder):
        return []

    all_files = sorted([
        f for f in os.listdir(processed_folder)
        if f.lower().endswith(".csv")
    ])

    if not all_files:
        return []

    trigger_file = f"{batch_no}.csv"

    usable = []

    for fname in all_files:
        usable.append(fname)
        if fname == trigger_file:
            break

    selected = usable[-baseline_window:]
    return [os.path.join(processed_folder, f) for f in selected]


def fine_tune_for_trigger(
    trigger_event: dict,
    processed_folder: str = "data/processed",
    baseline_window: int = 5,
    min_train_rows: int = 20,
    epochs: int = 1,
    batch_size: int = 8,
) -> dict:
    """
    Incremental learning step.

    Called only when drift trigger exists.
    It:
    - loads latest adaptive model or base Component 1 model
    - fine-tunes on recent triggered batches
    - saves a new model version
    - updates latest_model.txt
    """
    _ensure_dirs()

    batch_no = str(trigger_event.get("batch_no", "unknown"))

    training_files = _resolve_training_files(
        trigger_event=trigger_event,
        processed_folder=processed_folder,
        baseline_window=baseline_window,
    )

    train_df = load_training_data_from_files(training_files)

    if len(train_df) < min_train_rows:
        result = {
            "batch_no": batch_no,
            "status": "skipped",
            "reason": f"Not enough training rows. Found {len(train_df)}, required {min_train_rows}.",
            "training_files": training_files,
            "timestamp": datetime.utcnow().isoformat(),
        }
        _append_model_log(result)
        return result

    source_model = get_latest_model_path()
    new_model_path = _next_version_path(batch_no)

    print(f"Loading source model: {source_model}")
    tokenizer = AutoTokenizer.from_pretrained(source_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        source_model,
        num_labels=3,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    dataset = CommentDataset(
        texts=train_df["text"].tolist(),
        labels=train_df["label_id"].tolist(),
        tokenizer=tokenizer,
        max_length=128,
    )

    temp_output_dir = os.path.join("artifacts", "trainer_tmp")

    if os.path.exists(temp_output_dir):
        shutil.rmtree(temp_output_dir)

    training_args = TrainingArguments(
        output_dir=temp_output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        learning_rate=2e-5,
        weight_decay=0.01,
        logging_steps=10,
        save_strategy="no",
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
    )

    trainer.train()

    os.makedirs(new_model_path, exist_ok=True)

    model.save_pretrained(new_model_path)
    tokenizer.save_pretrained(new_model_path)

    _write_latest_model(new_model_path)

    if os.path.exists(temp_output_dir):
        shutil.rmtree(temp_output_dir)

    label_counts = train_df["label_id"].value_counts().to_dict()
    readable_counts = {
        ID2LABEL[int(k)]: int(v)
        for k, v in label_counts.items()
    }

    result = {
        "batch_no": batch_no,
        "status": "model_updated",
        "source_model": source_model,
        "new_model_path": new_model_path,
        "training_rows": int(len(train_df)),
        "label_counts": readable_counts,
        "training_files": training_files,
        "epochs": epochs,
        "batch_size": batch_size,
        "timestamp": datetime.utcnow().isoformat(),
    }

    _append_model_log(result)
    return result