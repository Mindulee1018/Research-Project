import os
import json
from collections import defaultdict

from src.utils.io import load_batch_csv
from src.preprocessing.lexicon import LexiconStore
from src.core.variant_resolver import VariantResolver

LEXICON_PATH = "artifacts/lexicon_store.json"
UPDATE_LOG_PATH = "artifacts/update_jobs.jsonl"
VARIANT_MAP_PATH = "artifacts/variant_map.json"


def _safe_terms(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


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
            obj = json.loads(line)
            batch_no = obj.get("batch_no")
            status = obj.get("status")
            if batch_no and status in {"completed", "lexicon_updated"}:
                done.add(str(batch_no))
    return done


def append_update_log(event: dict):
    os.makedirs("artifacts", exist_ok=True)
    with open(UPDATE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _collect_recent_dataframes(processed_folder: str, baseline_window: int):
    dfs = []
    files_used = []

    if not os.path.exists(processed_folder):
        return dfs, files_used

    all_files = sorted(
        [f for f in os.listdir(processed_folder) if f.lower().endswith(".csv")]
    )

    selected = all_files[-baseline_window:]

    for fname in selected:
        path = os.path.join(processed_folder, fname)
        try:
            df = load_batch_csv(path)
            dfs.append(df)
            files_used.append(fname)
        except Exception:
            continue

    return dfs, files_used


def _term_stats_from_df(df, resolver: VariantResolver):
    """
    Returns:
      stats[term] = {
          "total": int,
          "hate": int,
          "nonhate": int
      }
    """
    stats = defaultdict(lambda: {"total": 0, "hate": 0, "nonhate": 0})

    if df is None or df.empty:
        return stats

    for _, row in df.iterrows():
        y = int(row["Hate"])
        terms = _safe_terms(row.get("terms"))

        for raw_t in terms:
            raw_t = str(raw_t).strip()
            if not raw_t:
                continue

            resolver.observe(raw_t)
            t = resolver.canonicalize(raw_t)
            if not t:
                continue

            stats[t]["total"] += 1
            if y == 1:
                stats[t]["hate"] += 1
            else:
                stats[t]["nonhate"] += 1

    return stats


def _merge_stats(dst, src):
    for term, s in src.items():
        dst[term]["total"] += int(s.get("total", 0))
        dst[term]["hate"] += int(s.get("hate", 0))
        dst[term]["nonhate"] += int(s.get("nonhate", 0))


def _filter_candidate_terms(
    aggregated_stats: dict,
    trigger_event: dict,
    min_total_count: int,
    min_hate_count: int,
    min_hate_ratio: float,
):
    """
    Only accept:
    - terms appearing in trigger_event["new_terms"]
    - enough total support
    - enough hate support
    - high enough hate ratio
    """
    trigger_new_terms = set(map(str, trigger_event.get("new_terms", [])))
    accepted = []
    rejected = []

    for term in sorted(trigger_new_terms):
        s = aggregated_stats.get(term)
        if not s:
            rejected.append({
                "term": term,
                "reason": "missing_from_aggregated_stats"
            })
            continue

        total = int(s["total"])
        hate = int(s["hate"])
        ratio = float(hate / total) if total > 0 else 0.0

        ok = (
            total >= min_total_count and
            hate >= min_hate_count and
            ratio >= min_hate_ratio
        )

        info = {
            "term": term,
            "total_count": total,
            "hate_count": hate,
            "nonhate_count": int(s["nonhate"]),
            "hate_ratio": ratio,
        }

        if ok:
            accepted.append(info)
        else:
            reason = []
            if total < min_total_count:
                reason.append("low_total_count")
            if hate < min_hate_count:
                reason.append("low_hate_count")
            if ratio < min_hate_ratio:
                reason.append("low_hate_ratio")

            info["reason"] = ",".join(reason) if reason else "rejected"
            rejected.append(info)

    return accepted, rejected


def run_incremental_update(
    trigger_event: dict,
    current_batch_df,
    processed_folder: str,
    baseline_window: int = 5,
    min_total_count: int = 2,
    min_hate_count: int = 1,
    min_hate_ratio: float = 0.60,
):
    """
    Incremental update action:
    - Uses last N processed files as baseline context
    - Also uses CURRENT triggered batch directly from memory
      so update can happen before moving the CSV to processed/
    - Filters candidate new terms
    - Updates lexicon weights P(Hate|term)
    """
    batch_no = str(trigger_event["batch_no"])

    resolver = VariantResolver(path=VARIANT_MAP_PATH)
    lex = LexiconStore.load(LEXICON_PATH)

    dfs, baseline_files = _collect_recent_dataframes(processed_folder, baseline_window)

    aggregated = defaultdict(lambda: {"total": 0, "hate": 0, "nonhate": 0})

    # old processed data
    rows_used = 0
    for df in dfs:
        rows_used += len(df)
        part = _term_stats_from_df(df, resolver)
        _merge_stats(aggregated, part)

    # current triggered batch
    if current_batch_df is not None and not current_batch_df.empty:
        rows_used += len(current_batch_df)
        current_part = _term_stats_from_df(current_batch_df, resolver)
        _merge_stats(aggregated, current_part)

    accepted_terms, rejected_terms = _filter_candidate_terms(
        aggregated_stats=aggregated,
        trigger_event=trigger_event,
        min_total_count=min_total_count,
        min_hate_count=min_hate_count,
        min_hate_ratio=min_hate_ratio,
    )

    updated_terms = []

    for item in accepted_terms:
        term = item["term"]
        stats = aggregated[term]

        # update lexicon as many times as observed, preserving label frequency
        for _ in range(int(stats["hate"])):
            lex.update_term(term, 1, batch_no=batch_no)

        for _ in range(int(stats["nonhate"])):
            lex.update_term(term, 0, batch_no=batch_no)

        updated_terms.append(term)

        # keep variant resolver aware of accepted canonical terms
        resolver.observe(term)

    lex.save(LEXICON_PATH)
    resolver.save()

    result = {
        "batch_no": batch_no,
        "status": "completed",
        "baseline_files_used": baseline_files,
        "rows_used": int(rows_used),
        "candidate_new_terms": list(map(str, trigger_event.get("new_terms", []))),
        "accepted_terms": accepted_terms,
        "accepted_terms_count": len(accepted_terms),
        "rejected_terms": rejected_terms,
        "rejected_terms_count": len(rejected_terms),
        "updated_terms": updated_terms,
        "updated_terms_count": len(updated_terms),
        "votes": trigger_event.get("votes", {}),
        "vote_count": int(trigger_event.get("vote_count", 0)),
    }

    append_update_log(result)
    return result


def run_updates(
    processed_folder="data/processed",
    baseline_window=5,
    min_total_count=2,
    min_hate_count=1,
    min_hate_ratio=0.60,
):
    """
    Optional offline replayer:
    re-runs updates for trigger events that were not processed before.
    This works only from processed data, so it is mainly for recovery/replay.
    """
    triggers = load_triggers()
    done = already_processed_updates()

    for trig in triggers:
        b = str(trig.get("batch_no", "")).strip()
        if not b or b in done:
            continue

        # best-effort fallback: try to load a processed CSV that contains this batch
        current_df = None
        processed_file = os.path.join(processed_folder, f"{b}.csv")
        if os.path.exists(processed_file):
            try:
                current_df = load_batch_csv(processed_file)
                current_df = current_df[current_df["batch_no"].astype(str) == b].copy()
            except Exception:
                current_df = None

        run_incremental_update(
            trigger_event=trig,
            current_batch_df=current_df,
            processed_folder=processed_folder,
            baseline_window=baseline_window,
            min_total_count=min_total_count,
            min_hate_count=min_hate_count,
            min_hate_ratio=min_hate_ratio,
        )

    return True