import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from data_collection.io_utils import ensure_dir
from data_collection.pipelines.auto_label_with_gemini import normalize_label


VALID_LABELS = {"HATE", "DISINFO", "NORMAL"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge an incoming labeled CSV into the master labeled CSV.")
    parser.add_argument("--master-csv", required=True)
    parser.add_argument("--incoming-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--backup-csv", default="")
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--prefer-incoming", action="store_true")
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    master_path = Path(args.master_csv)
    incoming_path = Path(args.incoming_csv)
    output_path = Path(args.output_csv)
    backup_path = Path(args.backup_csv) if args.backup_csv else None
    report_path = Path(args.report_out)

    if not master_path.exists():
        raise SystemExit(f"Master CSV not found: {master_path}")
    if not incoming_path.exists():
        raise SystemExit(f"Incoming CSV not found: {incoming_path}")

    master_rows = load_rows(master_path)
    incoming_rows = load_rows(incoming_path)
    if not master_rows:
        raise SystemExit(f"No rows found in master CSV: {master_path}")
    if not incoming_rows:
        raise SystemExit(f"No rows found in incoming CSV: {incoming_path}")

    fieldnames = list(master_rows[0].keys())
    for row in incoming_rows:
        for col in row.keys():
            if col not in fieldnames:
                fieldnames.append(col)
    for row in master_rows:
        for col in fieldnames:
            row.setdefault(col, "")

    master_index: dict[str, dict[str, str]] = {}
    ordered_ids: list[str] = []
    counters: Counter[str] = Counter()

    for row in master_rows:
        candidate_id = str(row.get("candidate_id", "")).strip()
        if not candidate_id:
            counters["master_missing_candidate_id"] += 1
            continue
        if candidate_id not in master_index:
            ordered_ids.append(candidate_id)
        master_index[candidate_id] = row

    if backup_path:
        backup_rows = [master_index[cid] for cid in ordered_ids]
        write_rows(backup_path, fieldnames, backup_rows)

    for row in incoming_rows:
        candidate_id = str(row.get("candidate_id", "")).strip()
        label = normalize_label(str(row.get("annotator_label", "")))
        if not candidate_id:
            counters["incoming_missing_candidate_id"] += 1
            continue
        if label not in VALID_LABELS:
            counters["incoming_invalid_or_unlabeled"] += 1
            continue

        normalized_row = {col: str(row.get(col, "")).strip() for col in fieldnames}
        if candidate_id in master_index:
            counters["incoming_existing_candidate_id"] += 1
            if args.prefer_incoming:
                master_index[candidate_id] = normalized_row
                counters["overwritten_from_incoming"] += 1
            else:
                counters["kept_existing_master_row"] += 1
        else:
            master_index[candidate_id] = normalized_row
            ordered_ids.append(candidate_id)
            counters["appended_new_rows"] += 1

    merged_rows = [master_index[cid] for cid in ordered_ids]
    write_rows(output_path, fieldnames, merged_rows)

    final_distribution = Counter(
        normalize_label(str(row.get("annotator_label", ""))) or "UNLABELED"
        for row in merged_rows
    )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "master_csv": str(master_path),
            "incoming_csv": str(incoming_path),
        },
        "outputs": {
            "output_csv": str(output_path),
            "backup_csv": str(backup_path) if backup_path else "",
            "report_out": str(report_path),
        },
        "settings": {
            "prefer_incoming": args.prefer_incoming,
        },
        "counts": {
            "master_rows": len(master_rows),
            "incoming_rows": len(incoming_rows),
            **dict(counters),
            "merged_rows": len(merged_rows),
        },
        "final_label_distribution": dict(final_distribution),
    }

    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Merged CSV written to: {output_path}")
    if backup_path:
        print(f"Backup written to: {backup_path}")
    print(f"Report: {report_path}")
    print(
        "Merge counts: "
        f"appended={counters.get('appended_new_rows', 0)}, "
        f"existing={counters.get('incoming_existing_candidate_id', 0)}, "
        f"overwritten={counters.get('overwritten_from_incoming', 0)}"
    )


if __name__ == "__main__":
    main()
