# src/consumer.py
import os
import json
import shutil
import pandas as pd

from .io import load_batch_csv
from .term_store import TermStore
from .drift import DriftEngine
from .config import Config

from .concept_proxy import (
    term_label_stats,
    p_hate_given_term,
    concept_proxy_drift,
)

from .variant_resolver import VariantResolver

MANIFEST_PATH = "artifacts/processed_manifest.json"
TERM_STORE_PATH = "artifacts/term_store.json"
DRIFT_HISTORY_PATH = "artifacts/drift_history.csv"
TRIGGERS_PATH = "artifacts/triggers.jsonl"


def _load_manifest() -> set[str]:
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f).get("processed_files", []))
    except FileNotFoundError:
        return set()


def _save_manifest(processed_files: set[str]) -> None:
    os.makedirs("artifacts", exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump({"processed_files": sorted(list(processed_files))}, f, ensure_ascii=False, indent=2)


def _baseline_batches(window: int) -> list[str]:
    """
    Baseline is last N batch_nos recorded in drift_history.csv.
    Used for target/data drift methods.
    """
    if not os.path.exists(DRIFT_HISTORY_PATH):
        return []
    hist = pd.read_csv(DRIFT_HISTORY_PATH)
    if hist.empty:
        return []
    return hist["batch_no"].astype(str).tolist()[-window:]


def _append_drift_row(batch_no: str, drift: dict, new_term_rate: float, concept_report: dict, trigger: bool) -> None:
    os.makedirs("artifacts", exist_ok=True)
    row = pd.DataFrame([{
        "batch_no": str(batch_no),
        "hate_rate": drift["hate_rate"],
        "hate_rate_drift": drift["hate_rate_drift"],
        "jsd": drift["jsd"] if drift["jsd"] is not None else "",
        "jsd_drift": drift["jsd_drift"],
        "new_term_rate": float(new_term_rate),
        "concept_mean_abs_delta": concept_report.get("mean_abs_delta", ""),
        "concept_frac_delta_gt_0_2": concept_report.get("frac_delta_gt_0_2", ""),
        "concept_shared_terms": concept_report.get("shared_terms", 0),
        "trigger": bool(trigger),
    }])

    if os.path.exists(DRIFT_HISTORY_PATH):
        row.to_csv(DRIFT_HISTORY_PATH, mode="a", header=False, index=False)
    else:
        row.to_csv(DRIFT_HISTORY_PATH, index=False)


def _append_trigger(event: dict) -> None:
    os.makedirs("artifacts", exist_ok=True)
    with open(TRIGGERS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _load_last_processed_for_baseline(processed_folder: str, n: int) -> pd.DataFrame | None:
    """
    Loads last n processed CSVs from processed_folder and concatenates them for concept drift proxy baseline.
    Returns None if no files.
    """
    if not os.path.exists(processed_folder):
        return None

    files = sorted([f for f in os.listdir(processed_folder) if f.lower().endswith(".csv")])
    if not files:
        return None

    files = files[-n:]
    dfs = []
    for fname in files:
        path = os.path.join(processed_folder, fname)
        try:
            dfs.append(load_batch_csv(path))
        except Exception:
            continue

    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


class BatchConsumer:
    """
    Consumes batch CSVs produced by Component 1.
    Performs:
      - Automatic term variant merging (VariantResolver) -> canonical real spelling
      - New term detection (hate-only new_term_rate)
      - Target drift (label drift): hate_rate drift via ADWIN
      - Data/feature drift: hate-term distribution drift via JSD + ADWIN (+ hard threshold)
      - Concept drift proxy: drift in P(Hate=1 | term) vs baseline window
      - Triggers incremental update using voting rule (2-of-4)
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = TermStore.load(TERM_STORE_PATH)
        self.drift = DriftEngine()
        self.processed_files = _load_manifest()

        # Automatic canonical term resolver (no manual alias list)
        self.variants = VariantResolver("artifacts/variant_map.json")

        os.makedirs(cfg.batch_folder, exist_ok=True)
        os.makedirs(cfg.processed_folder, exist_ok=True)
        os.makedirs("artifacts", exist_ok=True)

    def run_once(self) -> None:
        files = sorted([f for f in os.listdir(self.cfg.batch_folder) if f.lower().endswith(".csv")])

        for fname in files:
            if fname in self.processed_files:
                continue

            path = os.path.join(self.cfg.batch_folder, fname)
            df = load_batch_csv(path)

            # each file should be a single batch, but groupby supports multiple batches safely
            for batch_no, g in df.groupby("batch_no"):
                if len(g) < self.cfg.min_rows_in_batch:
                    continue

                batch_no = str(batch_no)
                hate_rate = float(g["Hate"].mean())

                # --------------------------
                # Build term-label pairs with canonical terms
                # --------------------------
                term_label_pairs: list[tuple[str, int]] = []
                hate_terms: list[str] = []
                unique_hate_terms: set[str] = set()

                for _, row in g.iterrows():
                    label = int(row["Hate"])
                    for raw_t in row["terms"]:
                        # Learn mapping from raw term (automatic)
                        self.variants.observe(raw_t)

                        # Use canonical REAL spelling (not skeleton)
                        t = self.variants.canonicalize(raw_t)
                        if not t:
                            continue

                        term_label_pairs.append((t, label))
                        if label == 1:
                            hate_terms.append(t)
                            unique_hate_terms.add(t)

                # Persist variant map so canonicalization is stable across runs
                self.variants.save()

                # Update term store
                term_report = self.store.update(batch_no, term_label_pairs)

                # New-term-rate among Hate=1 terms ONLY
                new_terms_set = set(term_report["new_terms"])
                new_terms_in_hate = len(new_terms_set.intersection(unique_hate_terms))
                new_term_rate = new_terms_in_hate / max(1, len(unique_hate_terms))
                new_term_flag = new_term_rate >= self.cfg.new_term_rate_threshold

                # --------------------------
                # Target + Data drift
                # --------------------------
                baseline = _baseline_batches(self.cfg.baseline_window)
                drift_report = self.drift.update(batch_no, hate_rate, hate_terms, baseline)

                # Warm-up: need at least 2 previous batches
                enough_history = len(baseline) >= 2

                jsd_val = drift_report["jsd"]
                hard_jsd = (jsd_val is not None) and (jsd_val >= self.cfg.jsd_hard_threshold)

                # --------------------------
                # Concept drift proxy
                # (relationship drift): P(Hate | term)
                # --------------------------
                concept_report = {"mean_abs_delta": None, "frac_delta_gt_0_2": None, "shared_terms": 0}
                concept_flag = False

                baseline_df = _load_last_processed_for_baseline(
                    processed_folder=self.cfg.processed_folder,
                    n=self.cfg.baseline_window
                )

                if baseline_df is not None and not baseline_df.empty:
                    # NOTE: baseline_df already contains canonical terms if it was processed by this consumer.
                    base_tc, base_th = term_label_stats(baseline_df)
                    cur_tc, cur_th = term_label_stats(g)

                    cur_p = p_hate_given_term(cur_tc, cur_th, alpha=1.0)
                    base_p = p_hate_given_term(base_tc, base_th, alpha=1.0)

                    concept_report = concept_proxy_drift(cur_p, base_p)

                    if concept_report["mean_abs_delta"] is not None:
                        concept_flag = (
                            concept_report["mean_abs_delta"] >= self.cfg.concept_delta_threshold
                            or concept_report["frac_delta_gt_0_2"] >= self.cfg.concept_bigfrac_threshold
                        )

                # --------------------------
                # Voting trigger (persistent drift)
                # 2-of-4 rule
                # --------------------------
                votes = {
                    # Target drift (label drift)
                    "target_drift": bool(drift_report["hate_rate_drift"]),
                    # Data/feature drift
                    "data_drift": bool(drift_report["jsd_drift"] or hard_jsd),
                    # Concept drift proxy
                    "concept_proxy": bool(concept_flag),
                    # New term emergence among hateful terms
                    "new_term_flag": bool(new_term_flag),
                }
                vote_count = sum(votes.values())

                trigger = bool(enough_history and vote_count >= 2)

                # Save drift history
                _append_drift_row(batch_no, drift_report, new_term_rate, concept_report, trigger)

                # Save trigger event
                if trigger:
                    _append_trigger({
                        "batch_no": batch_no,
                        "new_terms": term_report["new_terms"],
                        "new_terms_in_hate": int(new_terms_in_hate),
                        "new_term_rate": float(new_term_rate),
                        "hate_rate": float(hate_rate),
                        "jsd": jsd_val,
                        "concept_proxy": concept_report,
                        "votes": votes,
                        "vote_count": int(vote_count),
                        "baseline_batches": drift_report.get("baseline_batches", []),
                    })

            # Persist term store + manifest + move file
            self.store.save(TERM_STORE_PATH)
            self.processed_files.add(fname)
            _save_manifest(self.processed_files)

            shutil.move(path, os.path.join(self.cfg.processed_folder, fname))
