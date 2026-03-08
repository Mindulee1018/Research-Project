import os
import json
import shutil
import pandas as pd
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.utils.io import load_batch_csv
from src.core.term_store import TermStore
from src.drift.drift import DriftEngine
from src.config.config import Config
from src.core.concept_proxy import term_label_stats, p_hate_given_term, concept_proxy_drift

# Morfessor + variant resolver
from src.preprocessing.morph import load_vocab, save_vocab, train_morfessor, load_morfessor
from src.core.variant_resolver import VariantResolver
from src.preprocessing.suffix_miner import discover_suffixes

# incremental update
from src.core.update_handler import run_incremental_update

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


def _load_last_processed_for_concept_baseline(processed_folder: str, n_files: int) -> pd.DataFrame | None:
    if not os.path.exists(processed_folder):
        return None
    files = sorted([f for f in os.listdir(processed_folder) if f.lower().endswith(".csv")])
    if not files:
        return None
    files = files[-n_files:]
    dfs = []
    for fname in files:
        try:
            dfs.append(load_batch_csv(os.path.join(processed_folder, fname)))
        except Exception:
            continue
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


class BatchConsumer:
    def __init__(self, cfg: Config):
        self.cfg = cfg

        self.store = TermStore.load(TERM_STORE_PATH)
        self.drift = DriftEngine()
        self.processed_files = _load_manifest()

        # Morfessor state
        self.vocab = load_vocab()
        self.morfessor = load_morfessor()
        self.variants = VariantResolver(self.morfessor, "artifacts/variant_map.json")

        suffixes = discover_suffixes(list(self.vocab.keys()), min_types=6, min_len=1, max_len=6)
        self.variants.set_suffixes(suffixes)
        print("suffixes learned:", len(suffixes), "top:", suffixes[:10])

        os.makedirs(cfg.batch_folder, exist_ok=True)
        os.makedirs(cfg.processed_folder, exist_ok=True)
        os.makedirs("artifacts", exist_ok=True)

        self._last_vocab_size = len(self.vocab)
        self._retrain_step = 300

    def _maybe_retrain_morfessor(self) -> None:
        current_size = len(self.vocab)
        if current_size >= self._last_vocab_size + self._retrain_step:
            self.morfessor = train_morfessor(self.vocab)
            self._last_vocab_size = current_size

    def run_once(self) -> None:
        files = sorted([f for f in os.listdir(self.cfg.batch_folder) if f.lower().endswith(".csv")])

        for fname in files:
            if fname in self.processed_files:
                continue

            path = os.path.join(self.cfg.batch_folder, fname)
            df = load_batch_csv(path)

            for batch_no, g in df.groupby("batch_no"):
                batch_no = str(batch_no)
                if len(g) < self.cfg.min_rows_in_batch:
                    continue

                g = g.copy()
                hate_rate = float(g["Hate"].mean())

                suffixes = discover_suffixes(list(self.vocab.keys()), min_types=6, min_len=1, max_len=6)
                self.variants.set_suffixes(suffixes)

                term_label_pairs: list[tuple[str, int]] = []
                hate_terms: list[str] = []
                unique_hate_terms: set[str] = set()

                for _, row in g.iterrows():
                    label = int(row["Hate"])
                    for raw_t in row["terms"]:
                        raw_t = str(raw_t).strip()
                        if not raw_t:
                            continue

                        self.vocab[raw_t] = int(self.vocab.get(raw_t, 0)) + 1

                        self.variants.observe(raw_t)
                        t = self.variants.canonicalize(raw_t)
                        if not t:
                            continue

                        term_label_pairs.append((t, label))
                        if label == 1:
                            hate_terms.append(t)
                            unique_hate_terms.add(t)

                save_vocab(self.vocab)

                self._maybe_retrain_morfessor()
                self.variants.model = self.morfessor

                self.variants.save()
                suffixes = discover_suffixes(list(self.vocab.keys()), min_types=6, min_len=1, max_len=6)
                self.variants.set_suffixes(suffixes)
                print("suffixes learned:", len(suffixes), "top:", suffixes[:15])

                # ---- New term rate (hate-only) ----
                term_report = self.store.update(batch_no, term_label_pairs)
                new_terms_set = set(term_report["new_terms"])
                new_terms_in_hate = len(new_terms_set.intersection(unique_hate_terms))
                new_term_rate = new_terms_in_hate / max(1, len(unique_hate_terms))
                new_term_flag = new_term_rate >= self.cfg.new_term_rate_threshold

                # ---- Target + data drift ----
                baseline = _baseline_batches(self.cfg.baseline_window)
                drift_report = self.drift.update(batch_no, hate_rate, hate_terms, baseline)

                enough_history = len(baseline) >= 2

                jsd_val = drift_report["jsd"]
                hard_jsd = (jsd_val is not None) and (jsd_val >= self.cfg.jsd_hard_threshold)

                # ---- Concept drift proxy ----
                concept_report = {"mean_abs_delta": None, "frac_delta_gt_0_2": None, "shared_terms": 0}
                concept_flag = False

                baseline_df = _load_last_processed_for_concept_baseline(
                    processed_folder=self.cfg.processed_folder,
                    n_files=self.cfg.baseline_window
                )

                if baseline_df is not None and not baseline_df.empty:
                    def _canon_terms_list(lst):
                        out = []
                        for x in lst:
                            self.variants.observe(x)
                            c = self.variants.canonicalize(x)
                            if c:
                                out.append(c)
                        return out

                    base2 = baseline_df.copy()
                    cur2 = g.copy()
                    base2["terms"] = base2["terms"].apply(_canon_terms_list)
                    cur2["terms"] = cur2["terms"].apply(_canon_terms_list)

                    base_tc, base_th = term_label_stats(base2)
                    cur_tc, cur_th = term_label_stats(cur2)

                    cur_p = p_hate_given_term(cur_tc, cur_th, alpha=1.0)
                    base_p = p_hate_given_term(base_tc, base_th, alpha=1.0)

                    concept_report = concept_proxy_drift(cur_p, base_p)

                    if concept_report["mean_abs_delta"] is not None:
                        concept_flag = (
                            concept_report["mean_abs_delta"] >= self.cfg.concept_delta_threshold
                            or concept_report["frac_delta_gt_0_2"] >= self.cfg.concept_bigfrac_threshold
                        )

                # ---- Trigger (vote_count>=2 OR new_term_flag) ----
                votes = {
                    "target_drift": bool(drift_report["hate_rate_drift"]),
                    "data_drift": bool(drift_report["jsd_drift"] or hard_jsd),
                    "concept_proxy": bool(concept_flag),
                    "new_term_flag": bool(new_term_flag),
                }
                vote_count = sum(votes.values())

                trigger = bool(enough_history and (vote_count >= 2 or new_term_flag))

                _append_drift_row(batch_no, drift_report, new_term_rate, concept_report, trigger)

                if trigger:
                    trigger_event = {
                        "batch_no": batch_no,
                        "new_terms": term_report["new_terms"],
                        "new_terms_in_hate": int(new_terms_in_hate),
                        "new_term_rate": float(new_term_rate),
                        "hate_rate": float(hate_rate),
                        "jsd": jsd_val,
                        "concept_proxy": concept_report,
                        "votes": votes,
                        "vote_count": int(vote_count),
                        "baseline_batches": baseline,
                    }

                    _append_trigger(trigger_event)

                    update_result = run_incremental_update(
                        trigger_event=trigger_event,
                        current_batch_df=g,
                        processed_folder=self.cfg.processed_folder,
                        baseline_window=self.cfg.baseline_window,
                        min_total_count=self.cfg.incremental_min_term_total_count,
                        min_hate_count=self.cfg.incremental_min_hate_count,
                        min_hate_ratio=self.cfg.incremental_min_hate_ratio,
                    )

                    print(
                        f"[incremental] batch={batch_no} "
                        f"accepted={update_result.get('accepted_terms_count', 0)} "
                        f"updated={update_result.get('updated_terms_count', 0)}"
                    )

            self.store.save(TERM_STORE_PATH)
            self.processed_files.add(fname)
            _save_manifest(self.processed_files)

            shutil.move(path, os.path.join(self.cfg.processed_folder, fname))