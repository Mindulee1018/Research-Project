import os, json, joblib
import pandas as pd
from datetime import datetime

from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import f1_score, precision_score, recall_score

# ---------------- CONFIG ----------------
TEXT_COL = "text"          # change if your column is different
LABEL_COL = "label"        # 1=hate, 0=non-hate (change if needed)

NMIN_NEW = 100             # minimum new labeled samples to update
REPLAY_SIZE = 400          # how many old samples to keep
REPLAY_FRAC = 0.30         # 30% replay, 70% new

VEC_FEATURES = 2**20       # ~1M hashed features
RANDOM_STATE = 42

BASE_TRAIN = "data/base_train.csv"
REPLAY_PATH = "data/replay_buffer.csv"

MODELS_DIR = "models"
ART_DIR = "artifacts"
UPDATE_LOG = os.path.join(ART_DIR, "update_log.json")
PERF_HIST = os.path.join(ART_DIR, "perf_history.json")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(ART_DIR, exist_ok=True)

# -------------- helpers -----------------
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def ensure_binary_labels(y):
    # makes sure labels are 0/1 ints
    return pd.Series(y).astype(int).clip(0, 1).to_numpy()

def eval_metrics(clf, vec, df):
    X = vec.transform(df[TEXT_COL].astype(str).tolist())
    y = ensure_binary_labels(df[LABEL_COL])
    pred = clf.predict(X)
    return {
        "f1": float(f1_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "n": int(len(df)),
    }

# -------------- main logic --------------
def main(batch_file: str, batch_no: str):
    # Load new labeled batch data
    new_df = pd.read_csv(batch_file)
    new_df = new_df[[TEXT_COL, LABEL_COL]].dropna()
    if len(new_df) < NMIN_NEW:
        print(f"❌ Not enough new labels ({len(new_df)}) < {NMIN_NEW}. Skipping update.")
        return

    # Load or init vectorizer + model
    vec = HashingVectorizer(
        n_features=VEC_FEATURES,
        alternate_sign=False,
        ngram_range=(1, 2),
        norm="l2"
    )

    # Find latest model version
    existing = [f for f in os.listdir(MODELS_DIR) if f.startswith("model_v") and f.endswith(".joblib")]
    if not existing:
        # train base model first time
        base_df = pd.read_csv(BASE_TRAIN)[[TEXT_COL, LABEL_COL]].dropna()
        clf = SGDClassifier(loss="log_loss", random_state=RANDOM_STATE)
        Xb = vec.transform(base_df[TEXT_COL].astype(str).tolist())
        yb = ensure_binary_labels(base_df[LABEL_COL])

        # partial_fit needs classes on first call
        clf.partial_fit(Xb, yb, classes=[0, 1])
        v = 1
        joblib.dump({"clf": clf}, os.path.join(MODELS_DIR, f"model_v{v}.joblib"))
        print(f"✅ Trained base model -> model_v{v}.joblib")
    else:
        # load latest
        latest = sorted(existing, key=lambda x: int(x.replace("model_v","").replace(".joblib","")))[-1]
        v = int(latest.replace("model_v","").replace(".joblib",""))
        clf = joblib.load(os.path.join(MODELS_DIR, latest))["clf"]
        print(f"✅ Loaded {latest}")

    # Load/update replay buffer
    if os.path.exists(REPLAY_PATH):
        replay_df = pd.read_csv(REPLAY_PATH)[[TEXT_COL, LABEL_COL]].dropna()
    else:
        # initialize replay buffer from base train
        base_df = pd.read_csv(BASE_TRAIN)[[TEXT_COL, LABEL_COL]].dropna()
        replay_df = base_df.sample(min(REPLAY_SIZE, len(base_df)), random_state=RANDOM_STATE)

    # Build training mix: 70% new + 30% replay (approx)
    n_replay = int(len(new_df) * REPLAY_FRAC / (1 - REPLAY_FRAC))
    replay_sample = replay_df.sample(min(n_replay, len(replay_df)), random_state=RANDOM_STATE)
    train_df = pd.concat([new_df, replay_sample], ignore_index=True).sample(frac=1, random_state=RANDOM_STATE)

    # Evaluate before update (on new batch only — simple)
    before = eval_metrics(clf, vec, new_df)

    # Incremental update
    Xt = vec.transform(train_df[TEXT_COL].astype(str).tolist())
    yt = ensure_binary_labels(train_df[LABEL_COL])
    clf.partial_fit(Xt, yt)

    # Evaluate after update (on new batch only — simple)
    after = eval_metrics(clf, vec, new_df)

    # Save new model version
    new_version = v + 1
    model_path = os.path.join(MODELS_DIR, f"model_v{new_version}.joblib")
    joblib.dump({"clf": clf}, model_path)

    # Update replay buffer (keep most recent + some old)
    merged_replay = pd.concat([replay_df, new_df], ignore_index=True)
    merged_replay = merged_replay.sample(min(REPLAY_SIZE, len(merged_replay)), random_state=RANDOM_STATE)
    merged_replay.to_csv(REPLAY_PATH, index=False)

    # Log update
    log = load_json(UPDATE_LOG, [])
    log.append({
        "time": datetime.now().isoformat(timespec="seconds"),
        "batch_no": batch_no,
        "batch_file": batch_file,
        "from_model": f"model_v{v}",
        "to_model": f"model_v{new_version}",
        "n_new": int(len(new_df)),
        "n_replay_used": int(len(replay_sample)),
        "metrics_before": before,
        "metrics_after": after,
        "saved_model": model_path.replace("\\", "/"),
    })
    save_json(UPDATE_LOG, log)

    # Perf history (for chart)
    perf = load_json(PERF_HIST, [])
    perf.append({
        "batch_no": batch_no,
        "model": f"model_v{new_version}",
        "f1": after["f1"],
        "precision": after["precision"],
        "recall": after["recall"],
    })
    save_json(PERF_HIST, perf)

    print(f"✅ Updated -> model_v{new_version} | F1 {before['f1']:.3f} -> {after['f1']:.3f}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch_file", required=True)
    ap.add_argument("--batch_no", required=True)
    args = ap.parse_args()
    main(args.batch_file, args.batch_no)