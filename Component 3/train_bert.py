import os
import json
import re
import random
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix

import torch
from datasets import Dataset
import transformers
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
)

# =========================
# CONFIG
# =========================
DATA_PATH = "data/sinhala_harmful_xai_dataset_5000_flagwords_research_v2.csv"  # <-- your new dataset
BASE_MODEL = "Ransaka/sinhala-bert-medium-v2"
OUT_DIR = "models_bert"

LABEL_ORDER = ["DISINFO", "HATE", "NORMAL"]
MAX_LENGTH = 192
TEST_SIZE = 0.2
RANDOM_STATE = 42
ALLOWED_LABELS = set(LABEL_ORDER)

# =========================
# REPRODUCIBILITY
# =========================
def seed_everything(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

seed_everything(RANDOM_STATE)

# =========================
# STOPWORDS (edit/expand)
# =========================
# These will be REMOVED from text before training & prediction
SI_STOPWORDS = {
    "ඔයා", "ඔබ", "ඔයාට", "ඔබට", "ඔයාලා", "ඔයාලට", "ඔයාලගේ", "ඔයාගේ", "ඔබගේ",
    "මම", "මට", "මගේ", "අපි", "අපට", "අපේ", "අපගේ", "ඔවුන්", "එයාලා", "එයාලට",
    "මේ", "මේක", "ඒ", "ඒක", "අර", "එක", "එකක්", "එකට",
    "වගේ", "නම්", "ද", "දේ", "නේ", "ත්", "මත්", "වත්",
    "කියලා", "කියන්නේ", "කිව්වා", "කියනවා",
    "ඉතා", "ගොඩක්", "නිතර", "හරි", "නිකං",
    "අද", "හෙට", "ඊයේ",
    "ට", "දී", "ගෙන", "වල", "වලින්", "ගේ", "කට", "පිළිබඳ", "අසල",
}

def normalize_si_token(tok: str) -> str:
    tok = re.sub(r"^[\W_]+|[\W_]+$", "", tok, flags=re.UNICODE)
    tok = tok.replace("\u200d", "")
    tok = tok.strip()
    return tok

def remove_stopwords(text: str) -> str:
    if not text:
        return ""
    tokens = text.split()
    kept = []
    for t in tokens:
        nt = normalize_si_token(t)
        if not nt:
            continue

        # exact stopwords
        if nt in SI_STOPWORDS:
            continue

        # common suffix-style filtering (simple)
        # ex: "ඔයාලටම", "ඔබගේත්", "වගේම"
        nt2 = re.sub(r"(ම|ත්|වත්|ද|නේ|යි)$", "", nt)
        if nt2 in SI_STOPWORDS:
            continue

        kept.append(t)
    return " ".join(kept)

# =========================
# CLEANING
# =========================
def clean_text(x):
    if pd.isna(x):
        return ""
    x = str(x)
    x = x.replace("\u200d", "")  # remove ZWJ
    x = " ".join(x.split())
    x = x.strip()
    # REMOVE stopwords so they do NOT affect prediction
    x = remove_stopwords(x)
    return x.strip()

def clean_label(x):
    x = str(x).strip().upper()
    x = re.sub(r"[,\s]+$", "", x)
    return x

# =========================
# METRICS
# =========================
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc = accuracy_score(labels, preds)
    f1m = f1_score(labels, preds, average="macro")
    return {"accuracy": acc, "macro_f1": f1m}

class WeightedTrainer(Trainer):
    def __init__(self, *args, class_weights=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.get("labels")
        outputs = model(**{k: v for k, v in inputs.items() if k != "labels"})
        logits = outputs.get("logits")

        if self.class_weights is not None:
            loss_fct = torch.nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device))
        else:
            loss_fct = torch.nn.CrossEntropyLoss()

        loss = loss_fct(logits.view(-1, model.config.num_labels), labels.view(-1))
        return (loss, outputs) if return_outputs else loss

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df = pd.read_csv(DATA_PATH)

    # Must have at least text,label (flag_words can exist)
    if "text" not in df.columns or "label" not in df.columns:
        raise ValueError(f"CSV must contain columns: text,label. Found: {list(df.columns)}")

    df["text"] = df["text"].apply(clean_text)
    df["label"] = df["label"].apply(clean_label)

    df = df[df["text"].str.len() > 0].copy()
    df = df[df["label"].isin(ALLOWED_LABELS)].copy()

    print("Label distribution:")
    print(df["label"].value_counts())

    # Force consistent mapping
    labels_sorted = [lab for lab in LABEL_ORDER if lab in df["label"].unique().tolist()]
    label2id = {lab: i for i, lab in enumerate(labels_sorted)}
    id2label = {i: lab for lab, i in label2id.items()}

    df["labels"] = df["label"].map(label2id).astype(int)

    train_df, test_df = train_test_split(
        df[["text", "labels"]],
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df["labels"],
    )

    train_ds = Dataset.from_pandas(train_df.reset_index(drop=True))
    eval_ds = Dataset.from_pandas(test_df.reset_index(drop=True))

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)

    def tok(batch):
        return tokenizer(batch["text"], truncation=True, max_length=MAX_LENGTH)

    train_ds = train_ds.map(tok, batched=True, remove_columns=["text"])
    eval_ds = eval_ds.map(tok, batched=True, remove_columns=["text"])

    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(labels_sorted),
        label2id=label2id,
        id2label=id2label,
    )

    # class weights (inverse frequency)
    counts = df["label"].value_counts().to_dict()
    total = sum(counts.values())
    weights = [total / max(counts.get(lab, 1), 1) for lab in labels_sorted]
    class_weights = torch.tensor(weights, dtype=torch.float)

    ver = transformers.__version__.split(".")
    major = int(ver[0]) if len(ver) > 0 else 0
    minor = int(ver[1]) if len(ver) > 1 else 0

    ta_kwargs = dict(
        output_dir=OUT_DIR,
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=50,

        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        num_train_epochs=8,

        warmup_ratio=0.1,
        weight_decay=0.01,
        max_grad_norm=1.0,

        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,

        save_total_limit=2,
        fp16=torch.cuda.is_available(),
        report_to="none",
        seed=RANDOM_STATE,
    )

    if (major, minor) >= (4, 46):
        ta_kwargs["eval_strategy"] = "epoch"
    else:
        ta_kwargs["evaluation_strategy"] = "epoch"

    args = TrainingArguments(**ta_kwargs)

    trainer = WeightedTrainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
        class_weights=class_weights,
    )

    trainer.train()

    preds = trainer.predict(eval_ds)
    logits = preds.predictions
    y_true = preds.label_ids
    y_pred = np.argmax(logits, axis=-1)

    acc = accuracy_score(y_true, y_pred)
    f1m = f1_score(y_true, y_pred, average="macro")

    print("\n=== Accuracy ===", acc)
    print("=== Macro F1 ===", f1m)

    print("\n=== Confusion Matrix ===")
    print(confusion_matrix(y_true, y_pred))

    print("\n=== Classification Report ===")
    print(classification_report(y_true, y_pred, target_names=[id2label[i] for i in range(len(id2label))]))

    trainer.save_model(OUT_DIR)
    tokenizer.save_pretrained(OUT_DIR)

    meta = {
        "base_model": BASE_MODEL,
        "labels": labels_sorted,
        "label2id": label2id,
        "id2label": {str(k): v for k, v in id2label.items()},
        "accuracy": float(acc),
        "macro_f1": float(f1m),
        "dataset": DATA_PATH,
        "max_length": MAX_LENGTH,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "stopwords_enabled": True,
        "stopwords_count": len(SI_STOPWORDS),
    }

    with open(os.path.join(OUT_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved model to: {OUT_DIR}")
    print(f"✅ Saved meta.json to: {os.path.join(OUT_DIR, 'meta.json')}")

if __name__ == "__main__":
    main()
