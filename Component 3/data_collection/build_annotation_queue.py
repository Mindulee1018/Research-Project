import argparse
import csv
import hashlib
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build annotation queue from ingestion outputs.")
    parser.add_argument("--output-root", default="data_collection/output")
    parser.add_argument("--target", default="data/annotation_queue/raw_candidates.csv")
    parser.add_argument("--sinhala-only", action="store_true")
    parser.add_argument(
        "--comments-only",
        action="store_true",
        help="Only include rows whose metadata mode indicates comment extraction.",
    )
    parser.add_argument(
        "--run-ids",
        default="",
        help="Comma-separated run IDs to include. Empty means include all runs.",
    )
    return parser.parse_args()


def load_rows(output_root: Path, include_run_ids: set[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for run_dir in sorted(output_root.iterdir()) if output_root.exists() else []:
        if not run_dir.is_dir():
            continue
        run_id = run_dir.name
        if include_run_ids and run_id not in include_run_ids:
            continue
        csv_path = run_dir / "records.csv"
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            rows.extend(dict(row) for row in reader)
    return rows


def dedup_rows(rows: List[Dict[str, str]], sinhala_only: bool, comments_only: bool) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    seen: set[str] = set()

    for row in rows:
        clean_text = str(row.get("clean_text", "")).strip()
        if not clean_text:
            continue
        if sinhala_only and str(row.get("is_sinhala", "")).strip().lower() != "true":
            continue
        if comments_only:
            metadata = str(row.get("metadata", "")).lower()
            if "comment" not in metadata:
                continue

        source = str(row.get("source", "")).strip()
        source_item = str(row.get("source_item_id_or_url", "")).strip()
        key = hashlib.sha256(f"{source}|{source_item}|{clean_text}".encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)

        output.append(
            {
                "candidate_id": key,
                "source": source,
                "source_item_id_or_url": source_item,
                "scraped_at": str(row.get("scraped_at", "")).strip(),
                "text": clean_text,
                "label": "",
                "annotation_status": "pending",
            }
        )
    return output


def write_queue(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "candidate_id",
        "source",
        "source_item_id_or_url",
        "scraped_at",
        "text",
        "label",
        "annotation_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    include_run_ids = {item.strip() for item in str(args.run_ids).split(",") if item.strip()}
    rows = load_rows(output_root=Path(args.output_root), include_run_ids=include_run_ids)
    deduped = dedup_rows(
        rows=rows,
        sinhala_only=args.sinhala_only,
        comments_only=args.comments_only,
    )
    target = Path(args.target)
    write_queue(path=target, rows=deduped)
    print(f"Annotation queue written: {target}")
    print(f"Rows: {len(deduped)}")


if __name__ == "__main__":
    main()
