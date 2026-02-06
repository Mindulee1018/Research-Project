import os
import json
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ARTIFACTS_DIR = os.path.join(os.getcwd(), "artifacts")

app = FastAPI(title="Component2 Dashboard API")

# If you later use Vite proxy, CORS isn't needed; but keeping it helps during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_json(path: str):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def read_jsonl(path: str):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

@app.get("/api/metrics")
def metrics():
    drift_path = os.path.join(ARTIFACTS_DIR, "drift_history.csv")
    triggers_path = os.path.join(ARTIFACTS_DIR, "triggers.jsonl")
    lex_path = os.path.join(ARTIFACTS_DIR, "lexicon_store.json")

    latest_batch = None
    row_count = 0
    if os.path.exists(drift_path):
        df = pd.read_csv(drift_path)
        row_count = int(len(df))
        if not df.empty:
            latest_batch = str(df.iloc[-1]["batch_no"])

    triggers = read_jsonl(triggers_path)
    lex = read_json(lex_path)

    return {
        "latest_batch": latest_batch,
        "batches_seen": row_count,
        "trigger_count": len(triggers),
        "lexicon_size": len(lex.get("entries", {})),
    }

@app.get("/api/drift_history")
def drift_history():
    path = os.path.join(ARTIFACTS_DIR, "drift_history.csv")
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path)
    df = df.fillna("")
    return df.to_dict(orient="records")

@app.get("/api/triggers")
def triggers():
    return read_jsonl(os.path.join(ARTIFACTS_DIR, "triggers.jsonl"))

@app.get("/api/lexicon_top")
def lexicon_top(limit: int = 25):
    lex = read_json(os.path.join(ARTIFACTS_DIR, "lexicon_store.json"))
    entries = lex.get("entries", {})
    rows = [{"term": t, **v} for t, v in entries.items()]
    rows.sort(key=lambda r: float(r.get("weight", 0.0)), reverse=True)
    return rows[:limit]

@app.get("/api/update_jobs")
def update_jobs():
    return read_jsonl(os.path.join(ARTIFACTS_DIR, "update_jobs.jsonl"))
