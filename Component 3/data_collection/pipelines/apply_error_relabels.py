import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_collection.io_utils import ensure_dir
from data_collection.pipelines.auto_label_with_gemini import normalize_label


VALID_ACTIONS = {"KEEP", "CHANGE"}
VALID_LABELS = {"HATE", "DISINFO", "NORMAL"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply approved Gemini error-case relabel decisions back into the master labeled dataset."
    )
    parser.add_argument("--master-csv", required=True)
    parser.add_argument("--relabels-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--backup-csv", default="")
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--skip-manual-review", action="store_true")
    parser.add_argument("--apply-keep", action="store_true")
    parser.add_argument("--approved-only-column", default="")
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


def truthy(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "y", "approved", "accept"}


def build_relabel_index(rows: list[dict[str, str]], approved_only_column: str, skip_manual_review: bool) -> tuple[dict[str, dict[str, str]], Counter[str]]:
    index: dict[str, dict[str, str]] = {}
    counters: Counter[str] = Counter()
    for row in rows:
        candidate_id = str(row.get("candidate_id", "")).strip()
        if not candidate_id:
            counters["skipped_missing_candidate_id"] += 1
            continue

        action = str(row.get("relabel_action", "")).strip().upper()
        target_label = normalize_label(str(row.get("relabel_label", "")))
        if action not in VALID_ACTIONS or target_label not in VALID_LABELS:
            counters["skipped_invalid_action_or_label"] += 1
            continue

        if approved_only_column:
            if approved_only_column not in row:
                counters["skipped_missing_approved_column"] += 1
                continue
            if not truthy(row.get(approved_only_column, "")):
                counters["skipped_not_approved"] += 1
                continue

        if skip_manual_review and truthy(row.get("relabel_needs_manual_review", "")):
            counters["skipped_manual_review"] += 1
            continue

        index[candidate_id] = row
        counters["eligible_relabels"] += 1
    return index, counters


def main() -> None:
    args = parse_args()
    master_path = Path(args.master_csv)
    relabels_path = Path(args.relabels_csv)
    output_path = Path(args.output_csv)
    report_path = Path(args.report_out)
    backup_path = Path(args.backup_csv) if args.backup_csv else None

    if not master_path.exists():
        raise SystemExit(f"Master CSV not found: {master_path}")
    if not relabels_path.exists():
        raise SystemExit(f"Relabel CSV not found: {relabels_path}")

    master_rows = load_rows(master_path)
    relabel_rows = load_rows(relabels_path)
    if not master_rows:
        raise SystemExit(f"No rows found in master CSV: {master_path}")
    if not relabel_rows:
        raise SystemExit(f"No rows found in relabel CSV: {relabels_path}")

    fieldnames = list(master_rows[0].keys())
    extra_columns = [
        "relabel_action",
        "relabel_label",
        "relabel_confidence",
        "relabel_reason",
        "relabel_cause_words",
        "relabel_needs_manual_review",
        "relabel_model",
        "relabel_reviewed_at",
    ]
    for col in extra_columns:
        if col not in fieldnames:
            fieldnames.append(col)
    for row in master_rows:
        for col in extra_columns:
            row.setdefault(col, "")

    relabel_index, index_counters = build_relabel_index(
        relabel_rows,
        approved_only_column=args.approved_only_column,
        skip_manual_review=args.skip_manual_review,
    )

    if backup_path:
        write_rows(backup_path, fieldnames, master_rows)

    candidate_to_row = {
        str(row.get("candidate_id", "")).strip(): row
        for row in master_rows
        if str(row.get("candidate_id", "")).strip()
    }

    apply_counters: Counter[str] = Counter()
    changed_examples: list[dict[str, str]] = []

    for candidate_id, relabel in relabel_index.items():
        master_row = candidate_to_row.get(candidate_id)
        if not master_row:
            apply_counters["missing_in_master"] += 1
            continue

        action = str(relabel.get("relabel_action", "")).strip().upper()
        target_label = normalize_label(str(relabel.get("relabel_label", "")))
        old_label = normalize_label(str(master_row.get("annotator_label", "")))

        if action == "KEEP" and not args.apply_keep:
            apply_counters["skipped_keep"] += 1
            continue

        if action == "KEEP":
            final_label = old_label or target_label
        else:
            final_label = target_label

        if final_label not in VALID_LABELS:
            apply_counters["skipped_invalid_final_label"] += 1
            continue

        master_row["annotator_label"] = final_label
        master_row["llm_confidence"] = str(relabel.get("relabel_confidence", "")).strip()
        master_row["llm_model"] = str(relabel.get("relabel_model", "")).strip()
        master_row["llm_labeled_at"] = datetime.now(timezone.utc).isoformat()
        master_row["llm_cause_words"] = str(relabel.get("relabel_cause_words", "")).strip() if final_label in {"HATE", "DISINFO"} else ""
        master_row["annotator_notes"] = str(relabel.get("relabel_reason", "")).strip()

        for col in extra_columns:
            master_row[col] = str(relabel.get(col, "")).strip()

        if old_label != final_label:
            apply_counters["labels_changed"] += 1
            if len(changed_examples) < 50:
                changed_examples.append(
                    {
                        "candidate_id": candidate_id,
                        "old_label": old_label,
                        "new_label": final_label,
                        "action": action,
                        "reason": str(relabel.get("relabel_reason", "")).strip(),
                    }
                )
        else:
            apply_counters["labels_unchanged"] += 1

        apply_counters["applied_rows"] += 1

    write_rows(output_path, fieldnames, master_rows)

    final_distribution = Counter(
        normalize_label(str(row.get("annotator_label", ""))) or "UNLABELED"
        for row in master_rows
    )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "master_csv": str(master_path),
            "relabels_csv": str(relabels_path),
        },
        "outputs": {
            "output_csv": str(output_path),
            "backup_csv": str(backup_path) if backup_path else "",
            "report_out": str(report_path),
        },
        "settings": {
            "skip_manual_review": args.skip_manual_review,
            "apply_keep": args.apply_keep,
            "approved_only_column": args.approved_only_column,
        },
        "counts": {
            **dict(index_counters),
            **dict(apply_counters),
            "master_rows": len(master_rows),
            "relabel_rows": len(relabel_rows),
        },
        "final_label_distribution": dict(final_distribution),
        "changed_examples": changed_examples,
    }

    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Applied relabels to: {output_path}")
    if backup_path:
        print(f"Backup written to: {backup_path}")
    print(f"Report: {report_path}")
    print(
        "Apply counts: "
        f"eligible={index_counters.get('eligible_relabels', 0)}, "
        f"applied={apply_counters.get('applied_rows', 0)}, "
        f"changed={apply_counters.get('labels_changed', 0)}, "
        f"unchanged={apply_counters.get('labels_unchanged', 0)}"
    )


if __name__ == "__main__":
    main()
