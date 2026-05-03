import argparse
import csv
import hashlib
import json
import os
import random
import re
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from data_collection.io_utils import ensure_dir


VALID_LABELS = {"HATE", "DISINFO", "NORMAL"}

CLAIM_MARKERS = [
    "breaking",
    "exclusive",
    "confirmed",
    "true",
    "fake",
    "නිල",
    "තහවුරු",
    "ඇත්ත",
    "බොරු",
    "වෙඩි වැදී",
]

HATE_MARKERS = [
    "hate",
    "kill",
    "traitor",
    "අපහාස",
    "මරන්න",
    "අපිල",
    "ජාතිය",
    "කල්ලිය",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh annotation workflow from final_cleaned_dataset while preserving existing labels and "
            "locking unseen holdout from currently unlabeled data."
        )
    )
    parser.add_argument("--input-csv", default="datasets/preprocessing/final_cleaned_dataset.csv")
    parser.add_argument("--existing-label-csv", action="append", default=["datasets/labeled/annotator_a_llm.csv"])
    parser.add_argument("--output-dir", default="annotation/workflow/current")
    parser.add_argument("--split-dir", default="datasets/splits/current")
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--existing-holdout-csv", default="")
    parser.add_argument("--preserve-existing-holdout", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def normalize_label(value: str) -> str:
    label = str(value or "").strip().upper()
    return label if label in VALID_LABELS else ""


def near_duplicate_fingerprint(text: str) -> str:
    normalized = str(text or "").lower()
    normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)
    normalized = re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)
    return normalized


def hard_score_and_reasons(text: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0

    if len(text) < 20:
        score += 1
        reasons.append("very_short")
    if len(text) > 300:
        score += 2
        reasons.append("long_context")

    sinhala_letters = sum(1 for ch in text if "\u0D80" <= ch <= "\u0DFF")
    latin_letters = sum(1 for ch in text if ("a" <= ch.lower() <= "z"))
    if sinhala_letters > 0 and latin_letters > 0:
        score += 1
        reasons.append("mixed_script")

    punctuation_count = sum(1 for ch in text if ch in "!?")
    if punctuation_count >= 3:
        score += 1
        reasons.append("high_emphasis")

    lower = text.lower()
    if any(marker in lower for marker in CLAIM_MARKERS):
        score += 1
        reasons.append("claim_like")
    if any(marker in lower for marker in HATE_MARKERS):
        score += 2
        reasons.append("hate_marker")
    if "?" in text:
        score += 1
        reasons.append("question_form")

    return score, reasons


def parse_month_bucket(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m")
    except ValueError:
        return "unknown"


def build_master_row(row: dict[str, str]) -> dict[str, str] | None:
    candidate_id = str(row.get("candidate_id", "")).strip()
    source = str(row.get("source", "")).strip()
    item = str(row.get("source_item_id_or_url", "")).strip()
    scraped_at = str(row.get("scraped_at", "")).strip()
    text = str(row.get("text", "")).strip()
    if not candidate_id or not source or not item or not text:
        return None

    fp = near_duplicate_fingerprint(text)
    dup_group = "dup_" + hashlib.sha256(f"{source}|{fp}".encode("utf-8")).hexdigest()[:16]
    score, reasons = hard_score_and_reasons(text)
    return {
        "candidate_id": candidate_id,
        "source": source,
        "source_item_id_or_url": item,
        "scraped_at": scraped_at,
        "text": text,
        "time_bucket": parse_month_bucket(scraped_at),
        "duplicate_group_id": dup_group,
        "hard_score": str(score),
        "hard_reasons": ",".join(reasons),
    }


def load_existing_labels(paths: list[Path]) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for path in paths:
        if not path.exists():
            continue
        rows = load_rows(path)
        for row in rows:
            candidate_id = str(row.get("candidate_id", "")).strip()
            if not candidate_id:
                continue
            label = normalize_label(row.get("annotator_label", ""))
            if not label:
                continue
            merged[candidate_id] = {
                "annotator_label": label,
                "annotator_notes": str(row.get("annotator_notes", "")).strip(),
                "llm_confidence": str(row.get("llm_confidence", "")).strip(),
                "llm_model": str(row.get("llm_model", "")).strip(),
                "llm_labeled_at": str(row.get("llm_labeled_at", "")).strip(),
                "llm_cause_words": str(row.get("llm_cause_words", "")).strip(),
            }
    return merged


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_csv)
    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")

    output_dir = Path(args.output_dir)
    split_dir = Path(args.split_dir)
    ensure_dir(output_dir)
    ensure_dir(split_dir)

    raw_rows = load_rows(input_path)
    if not raw_rows:
        raise SystemExit("Input dataset has no rows.")
    print(f"[refresh] loaded raw rows: {len(raw_rows)} from {input_path}", flush=True)

    existing_paths = [Path(value) for value in args.existing_label_csv]
    existing_labels = load_existing_labels(existing_paths)
    print(f"[refresh] existing label rows loaded: {len(existing_labels)}", flush=True)

    existing_holdout_path = (
        Path(args.existing_holdout_csv)
        if str(args.existing_holdout_csv or "").strip()
        else (split_dir / "locked_unseen_holdout.csv")
    )
    existing_holdout_ids: set[str] = set()
    if args.preserve_existing_holdout and existing_holdout_path.exists():
        for row in load_rows(existing_holdout_path):
            cid = str(row.get("candidate_id", "")).strip()
            if cid:
                existing_holdout_ids.add(cid)

    master_rows: list[dict[str, str]] = []
    workers = max(1, int(args.workers))
    if workers > 1:
        workers = min(workers, max(1, (os.cpu_count() or 2) - 1))
        print(f"[refresh] using workers={workers} for master row build", flush=True)
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for idx, result in enumerate(executor.map(build_master_row, raw_rows, chunksize=500), start=1):
                if result is None:
                    continue
                existing = existing_labels.get(result["candidate_id"], {})
                result.update(
                    {
                        "annotator_label": existing.get("annotator_label", ""),
                        "annotator_notes": existing.get("annotator_notes", ""),
                        "llm_confidence": existing.get("llm_confidence", ""),
                        "llm_model": existing.get("llm_model", ""),
                        "llm_labeled_at": existing.get("llm_labeled_at", ""),
                        "llm_cause_words": existing.get("llm_cause_words", ""),
                    }
                )
                master_rows.append(result)
                if idx % 20000 == 0:
                    print(f"[refresh] processed {idx}/{len(raw_rows)} rows", flush=True)
    else:
        for idx, row in enumerate(raw_rows, start=1):
            result = build_master_row(row)
            if result is None:
                continue
            existing = existing_labels.get(result["candidate_id"], {})
            result.update(
                {
                    "annotator_label": existing.get("annotator_label", ""),
                    "annotator_notes": existing.get("annotator_notes", ""),
                    "llm_confidence": existing.get("llm_confidence", ""),
                    "llm_model": existing.get("llm_model", ""),
                    "llm_labeled_at": existing.get("llm_labeled_at", ""),
                    "llm_cause_words": existing.get("llm_cause_words", ""),
                }
            )
            master_rows.append(result)
            if idx % 20000 == 0:
                print(f"[refresh] processed {idx}/{len(raw_rows)} rows", flush=True)

    preserved_holdout_rows = [row for row in master_rows if row["candidate_id"] in existing_holdout_ids]
    non_holdout_rows = [row for row in master_rows if row["candidate_id"] not in existing_holdout_ids]

    labeled_rows = [row for row in non_holdout_rows if normalize_label(row.get("annotator_label", ""))]
    unlabeled_rows = [row for row in non_holdout_rows if not normalize_label(row.get("annotator_label", ""))]
    print(
        f"[refresh] master_rows={len(master_rows)} labeled={len(labeled_rows)} unlabeled={len(unlabeled_rows)} "
        f"preserved_holdout={len(preserved_holdout_rows)}",
        flush=True,
    )

    random.seed(args.seed)
    group_to_rows: dict[str, list[dict[str, str]]] = {}
    for idx, row in enumerate(unlabeled_rows, start=1):
        key = f"{row['source']}|{row['duplicate_group_id']}"
        group_to_rows.setdefault(key, []).append(row)
        if idx % 20000 == 0:
            print(f"[refresh] grouped {idx}/{len(unlabeled_rows)} unlabeled rows", flush=True)

    holdout_target = int(len(unlabeled_rows) * max(0.0, min(1.0, args.holdout_ratio)))
    holdout_set: set[str] = set()
    holdout_rows: list[dict[str, str]] = list(preserved_holdout_rows)
    holdout_set.update(row["candidate_id"] for row in preserved_holdout_rows)
    labeling_rows: list[dict[str, str]] = []
    holdout_count = len(preserved_holdout_rows)

    # Source + month aware holdout allocation while keeping near-duplicate groups intact.
    stratum_group_map: dict[str, list[list[dict[str, str]]]] = {}
    for rows_in_group in group_to_rows.values():
        first = rows_in_group[0]
        stratum = f"{first['source']}|{first.get('time_bucket', 'unknown')}"
        stratum_group_map.setdefault(stratum, []).append(rows_in_group)

    stratum_row_counts = {
        key: sum(len(group_rows) for group_rows in groups_in_stratum)
        for key, groups_in_stratum in stratum_group_map.items()
    }
    total_unlabeled = max(1, len(unlabeled_rows))
    stratum_targets = {
        key: int(round((count / total_unlabeled) * holdout_target))
        for key, count in stratum_row_counts.items()
    }

    for groups_in_stratum in stratum_group_map.values():
        random.shuffle(groups_in_stratum)

    for stratum, groups_in_stratum in stratum_group_map.items():
        target = stratum_targets.get(stratum, 0)
        picked = 0
        for rows_in_group in groups_in_stratum:
            candidate_ids = [row["candidate_id"] for row in rows_in_group]
            if picked < target and holdout_count < holdout_target:
                holdout_rows.extend(rows_in_group)
                holdout_set.update(candidate_ids)
                holdout_count += len(rows_in_group)
                picked += len(rows_in_group)
            else:
                labeling_rows.extend(rows_in_group)
        if target:
            print(
                f"[refresh] stratum {stratum} target={target} picked={picked}",
                flush=True,
            )

    # Top up/fix under-allocation from rounding differences.
    if holdout_count < holdout_target:
        remaining_groups = []
        for rows_in_group in group_to_rows.values():
            if any(row["candidate_id"] in holdout_set for row in rows_in_group):
                continue
            remaining_groups.append(rows_in_group)
        random.shuffle(remaining_groups)
        for rows_in_group in remaining_groups:
            if holdout_count >= holdout_target:
                break
            candidate_ids = [row["candidate_id"] for row in rows_in_group]
            holdout_rows.extend(rows_in_group)
            holdout_set.update(candidate_ids)
            holdout_count += len(rows_in_group)
            labeling_rows = [row for row in labeling_rows if row["candidate_id"] not in set(candidate_ids)]
        print(
            f"[refresh] holdout top-up complete: holdout_count={holdout_count} target={holdout_target}",
            flush=True,
        )

    for row in unlabeled_rows:
        if row["candidate_id"] in holdout_set:
            continue
        # Safety: if a row wasn't touched due to group logic edge-case, keep it in labeling.
        if row not in labeling_rows:
            labeling_rows.append(row)

    train_dev_rows = labeled_rows + labeling_rows
    random.shuffle(train_dev_rows)
    print(f"[refresh] train_dev_rows={len(train_dev_rows)} holdout_rows={len(holdout_rows)}", flush=True)

    # Write split artifacts.
    split_fields = ["candidate_id", "source", "source_item_id_or_url", "scraped_at", "time_bucket", "text"]
    write_csv(split_dir / "train_dev_pool.csv", split_fields, train_dev_rows)
    write_csv(split_dir / "locked_unseen_holdout.csv", split_fields, holdout_rows)
    print("[refresh] split CSVs written", flush=True)

    # Write refreshed annotation workflow artifacts (train_dev only; holdout excluded).
    master_path = output_dir / "annotation_master.csv"
    annotator_a_path = output_dir / "annotator_a.csv"
    annotator_b_path = output_dir / "annotator_b.csv"
    hard_path = output_dir / "hard_examples.csv"
    adjudication_template_path = output_dir / "adjudication_template.csv"
    summary_path = output_dir / "workflow_summary.json"

    workflow_fields = [
        "candidate_id",
        "source",
        "source_item_id_or_url",
        "scraped_at",
        "text",
        "time_bucket",
        "duplicate_group_id",
        "hard_score",
        "hard_reasons",
        "annotator_label",
        "annotator_notes",
        "llm_confidence",
        "llm_model",
        "llm_labeled_at",
        "llm_cause_words",
    ]
    write_csv(master_path, workflow_fields, train_dev_rows)
    write_csv(annotator_a_path, workflow_fields, train_dev_rows)
    write_csv(annotator_b_path, workflow_fields, train_dev_rows)
    print("[refresh] workflow CSVs written", flush=True)

    hard_rows = [row for row in train_dev_rows if int(row.get("hard_score", "0") or 0) >= 3]
    write_csv(hard_path, workflow_fields, hard_rows)

    adjudication_rows = [
        {
            "candidate_id": "",
            "source": "",
            "text": "",
            "annotator_a_label": "",
            "annotator_b_label": "",
            "final_label": "",
            "adjudicator_notes": "",
        }
    ]
    write_csv(
        adjudication_template_path,
        list(adjudication_rows[0].keys()),
        adjudication_rows,
    )

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_csv": str(input_path),
        "existing_label_csv": [str(path) for path in existing_paths if path.exists()],
        "split_dir": str(split_dir),
        "output_dir": str(output_dir),
        "holdout_ratio": args.holdout_ratio,
        "preserve_existing_holdout": bool(args.preserve_existing_holdout),
        "existing_holdout_csv": str(existing_holdout_path) if existing_holdout_path.exists() else "",
        "counts": {
            "input_rows": len(master_rows),
            "preserved_holdout_rows": len(preserved_holdout_rows),
            "already_labeled_preserved": len(labeled_rows),
            "unlabeled_rows": len(unlabeled_rows),
            "train_dev_rows": len(train_dev_rows),
            "locked_unseen_holdout_rows": len(holdout_rows),
            "labeling_queue_rows": len([row for row in train_dev_rows if not normalize_label(row.get("annotator_label", ""))]),
        },
        "distribution": {
            "train_dev_by_source": {
                source: len([row for row in train_dev_rows if row.get("source") == source])
                for source in sorted({row.get("source", "") for row in train_dev_rows})
            },
            "holdout_by_source": {
                source: len([row for row in holdout_rows if row.get("source") == source])
                for source in sorted({row.get("source", "") for row in holdout_rows})
            },
        },
        "artifacts": {
            "train_dev_pool": str(split_dir / "train_dev_pool.csv"),
            "locked_unseen_holdout": str(split_dir / "locked_unseen_holdout.csv"),
            "annotation_master": str(master_path),
            "annotator_a": str(annotator_a_path),
            "annotator_b": str(annotator_b_path),
            "hard_examples": str(hard_path),
            "adjudication_template": str(adjudication_template_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Refreshed workflow: {output_dir}")
    print(f"Train/dev rows: {len(train_dev_rows)}")
    print(f"Locked unseen holdout rows: {len(holdout_rows)}")
    print(f"Preserved existing holdout rows: {len(preserved_holdout_rows)}")
    print(f"Preserved labeled rows: {len(labeled_rows)}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
