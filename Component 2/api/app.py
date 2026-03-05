# api/app.py
import os
import json
import pandas as pd
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

ARTIFACTS_DIR = os.path.join(os.getcwd(), "artifacts")
MANUAL_ALIASES_PATH = os.path.join(ARTIFACTS_DIR, "manual_aliases.json")

app = FastAPI(title="Component2 Dashboard API")

# If you later use Vite proxy, CORS isn't needed; but keeping it helps during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure artifacts dir + manual aliases file exist
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
if not os.path.exists(MANUAL_ALIASES_PATH):
    with open(MANUAL_ALIASES_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)


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


def read_manual_aliases():
    if not os.path.exists(MANUAL_ALIASES_PATH):
        return {}
    with open(MANUAL_ALIASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_manual_aliases(data: dict):
    with open(MANUAL_ALIASES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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


@app.get("/api/variant_groups")
def variant_groups(limit: int = 50, min_variants: int = 2):
    """
    Returns groups where multiple surface forms map to one canonical term.
    Use this to verify automatic merging (canonical + variants + counts).
    """
    path = os.path.join(ARTIFACTS_DIR, "variant_map.json")
    if not os.path.exists(path):
        return []

    payload = read_json(path)

    key_to_counter = payload.get("key_to_counter", {})
    key_to_canon = payload.get("key_to_canon", {})

    groups = []
    for key, counter_dict in key_to_counter.items():
        if not counter_dict:
            continue

        # counter_dict is {surface_form: count}
        items = sorted(counter_dict.items(), key=lambda x: int(x[1]), reverse=True)
        canon = key_to_canon.get(key, items[0][0])

        variants = [{"term": t, "count": int(c)} for t, c in items]
        if len(variants) < min_variants:
            continue

        groups.append({
            "group_key": key,
            "canonical": canon,
            "variants": variants,
            "variant_count": len(variants),
            "total_count": int(sum(int(c) for _, c in items)),
        })

    # biggest groups first
    groups.sort(key=lambda g: (g["variant_count"], g["total_count"]), reverse=True)
    return groups[:limit]


@app.get("/api/debug_artifacts")
def debug_artifacts():
    variant_path = os.path.join(ARTIFACTS_DIR, "variant_map.json")
    return {
        "cwd": os.getcwd(),
        "ARTIFACTS_DIR": ARTIFACTS_DIR,
        "files": os.listdir(ARTIFACTS_DIR) if os.path.exists(ARTIFACTS_DIR) else [],
        "variant_map_exists": os.path.exists(variant_path),
        "variant_map_size": os.path.getsize(variant_path) if os.path.exists(variant_path) else 0,
    }


@app.get("/api/canonical_lookup")
def canonical_lookup(term: str):
    path = os.path.join(ARTIFACTS_DIR, "variant_map.json")
    if not os.path.exists(path):
        return {"term": term, "canonical": term}

    payload = read_json(path)
    term_to_canon = payload.get("term_to_canon", {})
    return {"term": term, "canonical": term_to_canon.get(term, term)}


# ------------------------
# Manual aliases (override)
# ------------------------

@app.get("/api/manual_aliases")
def manual_aliases():
    return read_manual_aliases()


@app.post("/api/manual_aliases")
def add_manual_alias(payload: dict = Body(...)):
    """
    payload: {"from": "අන්තවාදීන්ට", "to": "අන්තවාදී"}
    """
    src = (payload.get("from") or "").strip()
    dst = (payload.get("to") or "").strip()
    if not src or not dst:
        return {"ok": False, "error": "from/to required"}

    m = read_manual_aliases()
    m[src] = dst
    write_manual_aliases(m)
    return {"ok": True, "count": len(m)}


@app.delete("/api/manual_aliases")
def delete_manual_alias(term: str):
    m = read_manual_aliases()
    if term in m:
        del m[term]
        write_manual_aliases(m)
    return {"ok": True, "count": len(m)}
