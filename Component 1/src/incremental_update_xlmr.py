# incremental_update_xlmr.py
import os
import json
import argparse
import pandas as pd
import numpy as np

from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
    set_seed,
)

def parse_args():
    ap = argparse.ArgumentParser()

    # Base model can be HF repo OR local folder path
    ap.add_argument("--base_model", required=True, help="HF repo id or local folder path")

    # Labeled batch CSV
    ap.add_argument("--batch_csv", required=True, help="Path to labeled batch CSV")

    # Column names
    ap.add_argument("--text_col", required=True, help="Text column name")
    ap.add_argument("--label_col", required=True, help="Label column name")

    # Label mapping: you can pass numeric labels directly in CSV OR pass mapping json
    ap.add_argument("--label_map_json", default="", help="Path to json mapping (optional). Example: {'HATE':0,'DISINFO':1,'NORMAL':2}")
    ap.add_argument("--num_labels", type=int, default=3)

    # Output
    ap.add_argument("--out_dir", required=True, help="Where to save updated model folder")
    ap.add_argument("--status_json", default="", help="Where to write model_status.json (optional)")

    # Training knobs (safe defaults)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch_size", type=int, default=8)
    ap.add_argument("--max_len", type=int, default=128)
    ap.add_argument("--seed", type=int, default=42)

    return ap.parse_args()

def load_label_map(path):
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_labels(df, label_col, label_map):
    """
    Supports:
      - numeric labels already in CSV (0/1/2)
      - string labels (HATE/DISINFO/NORMAL) converted via label_map
    """
    y = df[label_col]

    # If numeric, keep
    if pd.api.types.is_numeric_dtype(y):
        return y.astype(int)

    # If string, need mapping
    if label_map is None:
        raise ValueError(
            "Your label column is not numeric. Provide --label_map_json to map strings to ids."
        )

    y2 = y.astype(str).str.strip()
    bad = ~y2.isin(label_map.keys())
    if bad.any():
        bad_vals = sorted(set(y2[bad].tolist()))[:20]
        raise ValueError(f"Unknown label values found in CSV: {bad_vals}")

    return y2.map(label_map).astype(int)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)

    acc = (preds == labels).mean()

    # Simple macro F1 (no sklearn dependency)
    f1s = []
    for c in sorted(set(labels.tolist()) | set(preds.tolist())):
        tp = np.sum((preds == c) & (labels == c))
        fp = np.sum((preds == c) & (labels != c))
        fn = np.sum((preds != c) & (labels == c))
        prec = tp / (tp + fp + 1e-9)
        rec  = tp / (tp + fn + 1e-9)
        f1   = 2 * prec * rec / (prec + rec + 1e-9)
        f1s.append(f1)

    return {"accuracy": float(acc), "macro_f1": float(np.mean(f1s))}

def main():
    args = parse_args()
    set_seed(args.seed)

    os.makedirs(args.out_dir, exist_ok=True)

    # Load batch
    df = pd.read_csv(args.batch_csv, encoding="utf-8-sig")
    if args.text_col not in df.columns or args.label_col not in df.columns:
        raise ValueError(f"CSV must contain columns: {args.text_col} and {args.label_col}. Found: {list(df.columns)}")

    df = df[[args.text_col, args.label_col]].dropna()
    df[args.text_col] = df[args.text_col].astype(str)

    label_map = load_label_map(args.label_map_json)
    df["labels"] = normalize_labels(df, args.label_col, label_map)

    # Basic sanity
    if len(df) < 20:
        print("⚠️ Very small batch (<20). Training may be unstable, but continuing.")

    # Split train/val
    df = df.sample(frac=1.0, random_state=args.seed).reset_index(drop=True)
    split = int(len(df) * 0.9)
    train_df = df.iloc[:split]
    val_df   = df.iloc[split:] if split < len(df) else df.iloc[:1]

    train_ds = Dataset.from_pandas(train_df[[args.text_col, "labels"]])
    val_ds   = Dataset.from_pandas(val_df[[args.text_col, "labels"]])

    # Load base tokenizer + model
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=args.num_labels,
        ignore_mismatched_sizes=True,  # helps if head differs
    )

    def tok(batch):
        return tokenizer(batch[args.text_col], truncation=True, max_length=args.max_len)

    train_ds = train_ds.map(tok, batched=True, remove_columns=[args.text_col])
    val_ds   = val_ds.map(tok, batched=True, remove_columns=[args.text_col])

    collator = DataCollatorWithPadding(tokenizer=tokenizer)

    training_args = TrainingArguments(
        output_dir=os.path.join(args.out_dir, "_runs"),
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        logging_steps=20,
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        fp16=False,  # keep safe on most machines
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        data_collator=collator,
        compute_metrics=compute_metrics,
    )

    print("🚀 Starting incremental fine-tune...")
    train_result = trainer.train()
    eval_result = trainer.evaluate()

    # Save updated model
    print(f"💾 Saving updated model to: {args.out_dir}")
    trainer.save_model(args.out_dir)
    tokenizer.save_pretrained(args.out_dir)

    # Write status json for dashboard
    if args.status_json:
        status = {
            "base_model": args.base_model,
            "batch_csv": args.batch_csv,
            "text_col": args.text_col,
            "label_col": args.label_col,
            "epochs": args.epochs,
            "lr": args.lr,
            "batch_size": args.batch_size,
            "train_size": int(len(train_df)),
            "val_size": int(len(val_df)),
            "eval": {k: float(v) for k, v in eval_result.items() if isinstance(v, (int, float))},
            "train": {"train_runtime": float(train_result.metrics.get("train_runtime", 0.0))},
            "out_dir": args.out_dir,
        }
        os.makedirs(os.path.dirname(args.status_json), exist_ok=True)
        with open(args.status_json, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        print(f"✅ Wrote status: {args.status_json}")

    print("✅ Incremental update completed!")

if __name__ == "__main__":
    main()