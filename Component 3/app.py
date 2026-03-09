import os

# ===== Hide HF / Transformer warnings =====
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["PYTHONWARNINGS"] = "ignore"

import logging
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

from transformers import logging as hf_logging
hf_logging.set_verbosity_error()

import json
import html
import re
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from lime.lime_text import LimeTextExplainer
from sentence_transformers import SentenceTransformer

from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, classification_report
from moderation import get_moderation_decision
from flask import Flask
from flask_cors import CORS

from pathlib import Path
from threading import Lock
from datetime import datetime

# =====================================================
# CONFIG
# =====================================================
MODEL_DIR = os.environ.get("MODEL_DIR", "models_bert")
META_PATH = os.path.join(MODEL_DIR, "meta.json")

REWRITE_DIR = os.environ.get("REWRITE_DIR", "rewrite_index")
REWRITE_EMB_PATH = os.path.join(REWRITE_DIR, "embeddings.npy")
REWRITE_BANK_PATH = os.path.join(REWRITE_DIR, "bank.parquet")

EMBED_MODEL = os.environ.get(
    "EMBED_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# === Evaluation dataset path (CSV or Parquet)
EVAL_PATH = os.environ.get("EVAL_PATH", "").strip()
EVAL_TEXT_COL = os.environ.get("EVAL_TEXT_COL", "text").strip()
EVAL_LABEL_COL = os.environ.get("EVAL_LABEL_COL", "label").strip()



# =====================================================
# Analysis storage for moderation statistics
# =====================================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

ANALYSIS_LOG_PATH = DATA_DIR / "analysis_log.json"
analysis_log_lock = Lock()

def load_analysis_log():
    if ANALYSIS_LOG_PATH.exists():
        try:
            with open(ANALYSIS_LOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []

def save_analysis_log(records):
    with open(ANALYSIS_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def append_analysis_record(result):
    record = {
        "timestamp": datetime.now().isoformat(),
        "original": result.get("original", ""),
        "cleaned": result.get("cleaned", ""),
        "prediction": result.get("prediction", ""),
        "moderation": result.get("moderation", {}),
        "probs": result.get("probs", {}),
    }

    with analysis_log_lock:
        records = load_analysis_log()
        records.append(record)
        save_analysis_log(records)

def compute_moderation_stats(records):
    stats = {
        "BLOCK": 0,
        "FLAG": 0,
        "ALLOW": 0,
        "PENDING": 0,
        "ERROR": 0,
        "TOTAL": 0,
    }

    for rec in records:
        stats["TOTAL"] += 1

        prediction = str(rec.get("prediction", "")).upper().strip()
        moderation = rec.get("moderation") or {}
        action = str(moderation.get("action", "")).upper().strip()

        if not prediction:
            stats["PENDING"] += 1
        elif prediction == "ERROR":
            stats["ERROR"] += 1
        elif action in {"BLOCK", "FLAG", "ALLOW"}:
            stats[action] += 1
        else:
            stats["PENDING"] += 1

    return stats
# =====================================================
# STOPWORDS (match training)
# =====================================================
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
    return tok.strip()

def remove_stopwords(text: str) -> str:
    if not text:
        return ""
    tokens = text.split()
    kept = []
    for t in tokens:
        nt = normalize_si_token(t)
        if not nt:
            continue
        if nt in SI_STOPWORDS:
            continue
        nt2 = re.sub(r"(ම|ත්|වත්|ද|නේ|යි)$", "", nt)
        if nt2 in SI_STOPWORDS:
            continue
        kept.append(t)
    return " ".join(kept)

def basic_clean(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\u200d", "")
    text = " ".join(text.split()).strip()
    text = remove_stopwords(text).strip()
    return text


# =====================================================
# Load meta + model
# =====================================================
def load_meta():
    if os.path.exists(META_PATH):
        with open(META_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"labels": ["DISINFO", "HATE", "NORMAL"], "max_length": 160, "base_model": "Fine-tuned Sinhala BERT"}

meta = load_meta()
MAX_LENGTH = int(meta.get("max_length", 160))

device = "cuda" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, use_fast=True)
clf_model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
clf_model.to(device)
clf_model.eval()

def ensure_id2label():
    if not hasattr(clf_model.config, "id2label") or not clf_model.config.id2label:
        labels = meta.get("labels", None)
        if labels and isinstance(labels, list) and len(labels) == clf_model.config.num_labels:
            clf_model.config.id2label = {i: labels[i] for i in range(len(labels))}
            clf_model.config.label2id = {labels[i]: i for i in range(len(labels))}
        else:
            clf_model.config.id2label = {i: f"LABEL_{i}" for i in range(clf_model.config.num_labels)}
            clf_model.config.label2id = {v: k for k, v in clf_model.config.id2label.items()}

ensure_id2label()
CLASS_NAMES = [clf_model.config.id2label[i] for i in range(clf_model.config.num_labels)]


# =====================================================
# Startup: print model info
# =====================================================
def print_model_info():
    print("\n" + "=" * 70)
    print("🚀 Sinhala Harmful Text Classifier")
    print("=" * 70)
    print(f"Model Dir      : {MODEL_DIR}")
    print(f"Device         : {device}")
    print(f"Classes        : {CLASS_NAMES}")
    print(f"Max Length     : {MAX_LENGTH}")
    print(f"Rewrite Index  : {'READY' if (os.path.exists(REWRITE_BANK_PATH) and os.path.exists(REWRITE_EMB_PATH)) else 'NOT READY'}")
    print("=" * 70 + "\n")


# =====================================================
# Softmax
# =====================================================
def softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    e = np.exp(x - np.max(x))
    return e / (e.sum() + 1e-12)


# =====================================================
# Prediction
# =====================================================
def predict_proba_texts(texts):
    cleaned_texts = [basic_clean(t) for t in texts]

    if all(not t for t in cleaned_texts):
        out = np.zeros((len(cleaned_texts), clf_model.config.num_labels), dtype=float)
        if "NORMAL" in CLASS_NAMES:
            out[:, CLASS_NAMES.index("NORMAL")] = 1.0
        else:
            out[:] = 1.0 / clf_model.config.num_labels
        return out

    enc = tokenizer(
        cleaned_texts,
        truncation=True,
        max_length=MAX_LENGTH,
        padding=True,
        return_tensors="pt"
    )
    enc = {k: v.to(device) for k, v in enc.items()}

    with torch.no_grad():
        logits = clf_model(**enc).logits.detach().cpu().numpy()

    probs = np.apply_along_axis(softmax, 1, logits)
    return probs


def predict_text(text: str):
    original = "" if text is None else str(text)
    cleaned = basic_clean(original)

    if not cleaned:
        pred = "NORMAL" if "NORMAL" in CLASS_NAMES else CLASS_NAMES[0]
        probs = {c: 0.0 for c in CLASS_NAMES}
        probs[pred] = 1.0
        return pred, probs, original, cleaned

    probs_arr = predict_proba_texts([cleaned])[0]
    probs = {CLASS_NAMES[i]: float(probs_arr[i]) for i in range(len(probs_arr))}
    probs = dict(sorted(probs.items(), key=lambda x: x[1], reverse=True))
    pred = max(probs, key=probs.get)
    return pred, probs, original, cleaned


# =====================================================
# Evaluation (prints in terminal)
# =====================================================
def _norm_label(x: str) -> str:
    s = "" if x is None else str(x)
    s = s.strip().upper()
    # allow a few common variants
    mapping = {
        "HATE": "HATE",
        "HATE_SPEECH": "HATE",
        "HS": "HATE",
        "DISINFO": "DISINFO",
        "MISINFO": "DISINFO",
        "FAKE": "DISINFO",
        "NORMAL": "NORMAL",
        "NEUTRAL": "NORMAL",
        "OK": "NORMAL",
    }
    return mapping.get(s, s)

def load_eval_df(path: str) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()

    if not os.path.exists(path):
        print(f"⚠ EVAL_PATH not found: {path}")
        return pd.DataFrame()

    if path.lower().endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        # default CSV
        df = pd.read_csv(path)

    return df

def evaluate_and_print():
    if not EVAL_PATH:
        print("ℹ No EVAL_PATH provided, skipping evaluation.\n"
              "   (Set EVAL_PATH to a CSV/Parquet with columns text,label)\n")
        return

    df = load_eval_df(EVAL_PATH)
    if df.empty:
        print("⚠ Evaluation skipped (dataset empty or not loaded).")
        return

    if EVAL_TEXT_COL not in df.columns or EVAL_LABEL_COL not in df.columns:
        print(f"⚠ Evaluation skipped. Required columns not found.\n"
              f"   Need columns: '{EVAL_TEXT_COL}' and '{EVAL_LABEL_COL}'\n"
              f"   Found columns: {list(df.columns)}")
        return

    df = df[[EVAL_TEXT_COL, EVAL_LABEL_COL]].dropna()
    texts = df[EVAL_TEXT_COL].astype(str).tolist()
    y_true = [_norm_label(x) for x in df[EVAL_LABEL_COL].tolist()]

    # only keep rows with labels in your model class list
    keep = [i for i, y in enumerate(y_true) if y in CLASS_NAMES]
    if not keep:
        print("⚠ Evaluation skipped. None of the labels match your model classes.")
        print(f"   Model classes: {CLASS_NAMES}")
        print(f"   Example labels in file: {sorted(set(y_true))[:20]}")
        return

    texts = [texts[i] for i in keep]
    y_true = [y_true[i] for i in keep]

    # batch predict
    probs = predict_proba_texts(texts)
    y_pred_idx = probs.argmax(axis=1)
    y_pred = [CLASS_NAMES[i] for i in y_pred_idx]

    acc = accuracy_score(y_true, y_pred)
    f1_macro = f1_score(y_true, y_pred, average="macro", labels=CLASS_NAMES, zero_division=0)
    f1_weighted = f1_score(y_true, y_pred, average="weighted", labels=CLASS_NAMES, zero_division=0)

    cm = confusion_matrix(y_true, y_pred, labels=CLASS_NAMES)

    true_dist = pd.Series(y_true).value_counts().reindex(CLASS_NAMES).fillna(0).astype(int)
    pred_dist = pd.Series(y_pred).value_counts().reindex(CLASS_NAMES).fillna(0).astype(int)

    print("\n" + "=" * 70)
    print("📊 MODEL EVALUATION (Startup)")
    print("=" * 70)
    print(f"Eval File      : {EVAL_PATH}")
    print(f"Samples Used   : {len(y_true)}")
    print("-" * 70)
    print(f"Accuracy       : {acc:.4f}")
    print(f"Macro F1       : {f1_macro:.4f}")
    print(f"Weighted F1    : {f1_weighted:.4f}")
    print("-" * 70)

    print("Class distribution (True):")
    for c in CLASS_NAMES:
        print(f"  {c:<10} {int(true_dist[c])}")

    print("\nClass distribution (Pred):")
    for c in CLASS_NAMES:
        print(f"  {c:<10} {int(pred_dist[c])}")

    print("\nConfusion Matrix (rows=True, cols=Pred) order:", CLASS_NAMES)
    print(cm)

    print("\nClassification report:")
    print(classification_report(y_true, y_pred, labels=CLASS_NAMES, zero_division=0))
    print("=" * 70 + "\n")


# =====================================================
# LIME
# =====================================================
SPLIT_EXPRESSION = r"[\s,.;:!?…“”\"'()\[\]{}<>|/\\\-]+"

lime_explainer = LimeTextExplainer(
    class_names=CLASS_NAMES,
    split_expression=SPLIT_EXPRESSION,
    bow=True
)

def build_lime_highlight_html(text: str, word_weights: dict):
    """
    Positive weight => RED (supports predicted class)
    Negative weight => GREEN (pushes away from predicted class)
    """
    if not text:
        return ""
    if not word_weights:
        return html.escape(text)

    abs_vals = np.array([abs(v) for v in word_weights.values()], dtype=float)
    denom = float(abs_vals.max()) if abs_vals.max() > 0 else 1.0

    parts = []
    for tok in text.split():
        stripped = re.sub(r"^[\W_]+|[\W_]+$", "", tok, flags=re.UNICODE)
        w = stripped
        wt = float(word_weights.get(w, 0.0))
        intensity = min(abs(wt) / denom, 1.0)
        safe_tok = html.escape(tok)

        if w and w in word_weights:
            if wt >= 0:
                bg = f"rgba(220, 70, 70, {0.12 + 0.55 * intensity})"   # red
            else:
                bg = f"rgba(220, 70, 70, {0.12 + 0.55 * intensity})"   
            parts.append(f'<span class="tok" style="background:{bg}">{safe_tok}</span>')
        else:
            parts.append(safe_tok)

    return " ".join(parts)


def build_xai_sentence_lime(pred_label: str, weights_list_sorted):
    supports = [w for w, wt in weights_list_sorted if wt > 0][:3]
    opposes = [w for w, wt in weights_list_sorted if wt < 0][:2]

    if supports and opposes:
        return (
            f"The model classified this text as {pred_label} because the words "
            f"{', '.join(supports)} contributed positively to this prediction, "
            f"while {', '.join(opposes)} had a smaller negative influence."
        )
    if supports:
        return (
            f"The model classified this text as {pred_label} mainly due to the influence of "
            f"{', '.join(supports)}."
        )
    if opposes:
        return (
            f"The model classified this text as {pred_label}. However, words such as "
            f"{', '.join(opposes)} slightly reduced support for this prediction."
        )
    return f"The model classified this text as {pred_label} based on overall patterns detected in the text."


# =====================================================
# ML Retrieval Suggestion (Option B)
# =====================================================
rewrite_embedder = SentenceTransformer(EMBED_MODEL)

rewrite_bank_df = None
rewrite_bank_emb = None

def load_rewrite_index():
    global rewrite_bank_df, rewrite_bank_emb

    if os.path.exists(REWRITE_BANK_PATH) and os.path.exists(REWRITE_EMB_PATH):
        rewrite_bank_df = pd.read_parquet(REWRITE_BANK_PATH)
        rewrite_bank_emb = np.load(REWRITE_EMB_PATH).astype(np.float32)
        norms = np.linalg.norm(rewrite_bank_emb, axis=1, keepdims=True) + 1e-12
        rewrite_bank_emb = rewrite_bank_emb / norms
        return True

    rewrite_bank_df = None
    rewrite_bank_emb = None
    return False

load_rewrite_index()

def retrieve_safe_rewrites(pred_label: str, original_text: str, top_k: int = 3):
    if rewrite_bank_df is None or rewrite_bank_emb is None:
        return []

    label = (pred_label or "").upper().strip()
    if label not in {"HATE", "DISINFO"}:
        return []

    df = rewrite_bank_df[rewrite_bank_df["type"].astype(str).str.upper().str.strip() == label].copy()
    if df.empty:
        return []

    idxs = df.index.to_numpy()
    bank_emb = rewrite_bank_emb[idxs]

    q = (original_text or "").strip()
    if not q:
        return []

    q_emb = rewrite_embedder.encode([q], normalize_embeddings=True)
    q_emb = np.asarray(q_emb, dtype=np.float32)[0]

    sims = bank_emb @ q_emb
    top = np.argsort(-sims)[:top_k]

    results = []
    for j in top:
        row = df.iloc[int(j)]
        results.append({
            "similarity": float(sims[int(j)]),
            "suggestion": str(row["clean"]),
            "matched_example": str(row["unsafe"])
        })
    return results


# =====================================================
# Explain with LIME + Suggest
# =====================================================
def explain_lime(text: str, num_features=10, num_samples=1200):
    original = "" if text is None else str(text)
    cleaned = basic_clean(original)

    if not cleaned:
        return {
            "original": original,
            "cleaned": cleaned,
            "prediction": "NORMAL",
            "probs": {"NORMAL": 1.0},
            "xai_sentence": "Please enter Sinhala text to get a prediction and LIME explanation.",
            "highlight_html": html.escape(original),
            "suggestions": []
        }

    pred_label, probs, _, _ = predict_text(original)
    pred_idx = CLASS_NAMES.index(pred_label)

    exp = lime_explainer.explain_instance(
        cleaned,
        predict_proba_texts,
        labels=[pred_idx],
        num_features=num_features,
        num_samples=num_samples
    )

    weights_list = exp.as_list(label=pred_idx)
    weights_list_sorted = sorted(weights_list, key=lambda x: abs(x[1]), reverse=True)

    word_weights = {w: float(wt) for w, wt in weights_list}
    highlight_html_out = build_lime_highlight_html(cleaned, word_weights)
    xai_sentence = build_xai_sentence_lime(pred_label, weights_list_sorted)
    suggestions = retrieve_safe_rewrites(pred_label, original, top_k=3)

    moderation = get_moderation_decision(pred_label, probs)

    return {
        "original": original,
        "cleaned": cleaned,
        "prediction": pred_label,
        "probs": probs,
        "moderation": moderation,
        "xai_sentence": xai_sentence,
        "highlight_html": highlight_html_out,
        "suggestions": suggestions
    }

# =====================================================
# Flask
# =====================================================
app = Flask(__name__)
CORS(app)  # allows React dev server calls

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    index_ready = (rewrite_bank_df is not None and rewrite_bank_emb is not None)

    if request.method == "POST":
        text = request.form.get("text", "")
        result = explain_lime(text)

    return render_template(
        "index.html",
        result=result,
        model_name=meta.get("base_model", "Fine-tuned Sinhala BERT"),
        device=device,
        embed_model=EMBED_MODEL,
        suggestion_index_ready=index_ready
    )

@app.route("/api/explain_lime", methods=["POST"])
def api_explain_lime():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    result = explain_lime(text)
    result["method"] = "LIME + Semantic Retrieval Suggestions"

    append_analysis_record(result)

    return jsonify(result)

@app.route("/api/moderation_stats", methods=["GET"])
def api_moderation_stats():
    records = load_analysis_log()
    stats = compute_moderation_stats(records)
    return jsonify(stats)

@app.route("/api/recent_analyses", methods=["GET"])
def api_recent_analyses():
    limit = request.args.get("limit", default=20, type=int)

    records = load_analysis_log()
    records = list(reversed(records))[:limit]

    return jsonify(records)

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "device": device,
        "model_dir": MODEL_DIR,
        "classes": CLASS_NAMES,
        "stopwords_enabled": True,
        "rewrite_index_ready": (rewrite_bank_df is not None and rewrite_bank_emb is not None),
        "embed_model": EMBED_MODEL
    })



if __name__ == "__main__":
    print_model_info()
    evaluate_and_print()
    app.run(host="127.0.0.1", port=5000, debug=True)
