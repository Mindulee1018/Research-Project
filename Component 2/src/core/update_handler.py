import os
import json
import pandas as pd
from src.utils.io import load_batch_csv
from src.preprocessing.lexicon import LexiconStore
from .variant_resolver import VariantResolver
from src.preprocessing.normalize import canonical_term

resolver = VariantResolver(path="artifacts/variant_map.json")
LEXICON_PATH = "artifacts/lexicon_store.json"
UPDATE_LOG_PATH = "artifacts/update_jobs.jsonl"

def load_triggers(path="artifacts/triggers.jsonl"):
    if not os.path.exists(path):
        return []
    triggers = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                triggers.append(json.loads(line))
    return triggers

def already_processed_updates(path=UPDATE_LOG_PATH) -> set[str]:
    done = set()
    if not os.path.exists(path):
        return done
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            done.add(json.loads(line).get("batch_no"))
    return done

def append_update_log(event: dict):
    os.makedirs("artifacts", exist_ok=True)
    with open(UPDATE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def update_lexicon_for_trigger(trigger_event: dict, processed_folder: str, baseline_window: int = 5):
    """
    Incremental update action:
    - Load last N processed batch CSVs (including current batch if present)
    - Update lexicon weights P(Hate|term)
    """
    batch_no = trigger_event["batch_no"]

    # Load last N processed csv files
    all_files = sorted([f for f in os.listdir(processed_folder) if f.lower().endswith(".csv")])

    # keep only files up to and including the trigger batch
    trigger_file = f"{batch_no}.csv"
    usable = []
    for f in all_files:
        usable.append(f)
        if f == trigger_file:
            break

    files = usable[-baseline_window:]

    lex = LexiconStore.load(LEXICON_PATH)

    updated_terms = set()
    total_rows = 0

    for fname in files:
        df = load_batch_csv(os.path.join(processed_folder, fname))
        total_rows += len(df)

        for _, row in df.iterrows():
            y = int(row["Hate"])
            for t in row["terms"]:
                resolver.observe(t)
                t = resolver.canonicalize(t)
                if not t:
                    continue
                lex.update_term(t, y, batch_no=batch_no)
                updated_terms.add(t)
                resolver.observe(t)

    lex.save(LEXICON_PATH)

    return {
        "batch_no": batch_no,
        "status": "lexicon_updated",
        "baseline_files_used": files,
        "rows_used": total_rows,
        "unique_terms_updated": len(updated_terms),
        "new_terms": trigger_event.get("new_terms", []),
        "votes": trigger_event.get("votes", {}),
        "vote_count": trigger_event.get("vote_count", 0),
    }

def run_updates(processed_folder="data/processed", baseline_window=5):
    triggers = load_triggers()
    done = already_processed_updates()

    for trig in triggers:
        b = trig.get("batch_no")
        if not b or b in done:
            continue

        result = update_lexicon_for_trigger(trig, processed_folder, baseline_window=baseline_window)
        append_update_log(result)

    return True
