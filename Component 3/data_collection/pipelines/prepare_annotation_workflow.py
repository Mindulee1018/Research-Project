import argparse
import csv
import hashlib
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

from data_collection.io_utils import ensure_dir


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
        description="Prepare dual-annotation workflow assets with duplicate groups and hard-example mining."
    )
    parser.add_argument("--input-csv", default="datasets/preprocessing/final_cleaned_dataset.csv")
    parser.add_argument("--output-dir", default="annotation/workflow/current")
    parser.add_argument("--hard-threshold", type=int, default=3)
    parser.add_argument("--hard-top-percent", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def near_duplicate_fingerprint(text: str) -> str:
    normalized = text.lower()
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

    # Ambiguous directional cues that often trigger disagreement.
    if "?" in text:
        score += 1
        reasons.append("question_form")

    return score, reasons


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_csv)
    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")

    output_dir = Path(args.output_dir)
    ensure_dir(output_dir)

    with input_path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    if not rows:
        raise SystemExit("Input dataset has no rows.")

    duplicate_group_map: dict[str, str] = {}
    master_rows: list[dict[str, str]] = []

    for row in rows:
        text = str(row.get("text", "")).strip()
        fp = near_duplicate_fingerprint(text)
        source = str(row.get("source", "")).strip()
        group_key = f"{source}|{fp}"
        group_id = duplicate_group_map.get(group_key)
        if not group_id:
            group_id = "dup_" + hashlib.sha256(group_key.encode("utf-8")).hexdigest()[:16]
            duplicate_group_map[group_key] = group_id

        score, reasons = hard_score_and_reasons(text)
        hard_reasons = ",".join(reasons)

        master_rows.append(
            {
                "candidate_id": str(row.get("candidate_id", "")).strip(),
                "source": source,
                "source_item_id_or_url": str(row.get("source_item_id_or_url", "")).strip(),
                "scraped_at": str(row.get("scraped_at", "")).strip(),
                "text": text,
                "duplicate_group_id": group_id,
                "hard_score": str(score),
                "hard_reasons": hard_reasons,
            }
        )

    random.seed(args.seed)
    shuffled_rows = list(master_rows)
    random.shuffle(shuffled_rows)

    hard_candidates = [row for row in master_rows if int(row["hard_score"]) >= args.hard_threshold]
    top_k = int(max(1, len(master_rows) * max(min(args.hard_top_percent, 1.0), 0.0)))
    top_sorted = sorted(master_rows, key=lambda item: int(item["hard_score"]), reverse=True)[:top_k]
    hard_id_set = {row["candidate_id"] for row in hard_candidates}
    for row in top_sorted:
        hard_id_set.add(row["candidate_id"])
    hard_rows = [row for row in master_rows if row["candidate_id"] in hard_id_set]

    annotator_fields = [
        "candidate_id",
        "source",
        "source_item_id_or_url",
        "scraped_at",
        "text",
        "duplicate_group_id",
        "hard_score",
        "hard_reasons",
        "annotator_label",
        "annotator_notes",
    ]
    annotator_a = [{**row, "annotator_label": "", "annotator_notes": ""} for row in shuffled_rows]
    annotator_b = [{**row, "annotator_label": "", "annotator_notes": ""} for row in shuffled_rows]

    adjudication_template = [
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

    master_path = output_dir / "annotation_master.csv"
    hard_path = output_dir / "hard_examples.csv"
    annotator_a_path = output_dir / "annotator_a.csv"
    annotator_b_path = output_dir / "annotator_b.csv"
    adjudication_path = output_dir / "adjudication_template.csv"
    summary_path = output_dir / "workflow_summary.json"

    write_csv(master_path, list(master_rows[0].keys()), master_rows)
    write_csv(hard_path, list(master_rows[0].keys()), hard_rows)
    write_csv(annotator_a_path, annotator_fields, annotator_a)
    write_csv(annotator_b_path, annotator_fields, annotator_b)
    write_csv(adjudication_path, list(adjudication_template[0].keys()), adjudication_template)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_csv": str(input_path),
        "output_dir": str(output_dir),
        "counts": {
            "master_rows": len(master_rows),
            "hard_examples": len(hard_rows),
            "duplicate_groups": len(set(duplicate_group_map.values())),
        },
        "hard_selection": {
            "hard_threshold": args.hard_threshold,
            "hard_top_percent": args.hard_top_percent,
        },
        "artifacts": {
            "master": str(master_path),
            "hard_examples": str(hard_path),
            "annotator_a": str(annotator_a_path),
            "annotator_b": str(annotator_b_path),
            "adjudication_template": str(adjudication_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Annotation workflow prepared: {output_dir}")
    print(f"Master rows: {len(master_rows)}")
    print(f"Hard examples: {len(hard_rows)}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
