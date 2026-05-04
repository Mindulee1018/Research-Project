import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from data_collection.io_utils import ensure_dir


VALID_LABELS = {"HATE", "DISINFO", "NORMAL"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge two annotator files and build adjudication queue + agreement report.")
    parser.add_argument("--annotator-a", required=True)
    parser.add_argument("--annotator-b", required=True)
    parser.add_argument("--merged-out", required=True)
    parser.add_argument("--adjudication-out", required=True)
    parser.add_argument("--report-out", required=True)
    return parser.parse_args()


def load_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    return {str(row.get("candidate_id", "")).strip(): row for row in rows if str(row.get("candidate_id", "")).strip()}


def normalize_label(value: str) -> str:
    label = str(value or "").strip().upper()
    return label if label in VALID_LABELS else ""


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    a_path = Path(args.annotator_a)
    b_path = Path(args.annotator_b)
    if not a_path.exists() or not b_path.exists():
        raise SystemExit("Annotator input file missing.")

    a_rows = load_rows(a_path)
    b_rows = load_rows(b_path)

    common_ids = sorted(set(a_rows.keys()) & set(b_rows.keys()))
    if not common_ids:
        raise SystemExit("No overlapping candidate_id values between annotator files.")

    merged_rows: list[dict[str, str]] = []
    adjudication_rows: list[dict[str, str]] = []
    agreement_count = 0
    valid_pair_count = 0
    label_counter_a: Counter[str] = Counter()
    label_counter_b: Counter[str] = Counter()

    for candidate_id in common_ids:
        a = a_rows[candidate_id]
        b = b_rows[candidate_id]
        label_a = normalize_label(a.get("annotator_label", ""))
        label_b = normalize_label(b.get("annotator_label", ""))
        label_counter_a[label_a or "UNLABELED"] += 1
        label_counter_b[label_b or "UNLABELED"] += 1

        conflict = ""
        final_label = ""
        if label_a and label_b:
            valid_pair_count += 1
            if label_a == label_b:
                agreement_count += 1
                final_label = label_a
            else:
                conflict = "label_disagreement"
                adjudication_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "source": str(a.get("source", "")).strip(),
                        "text": str(a.get("text", "")).strip(),
                        "annotator_a_label": label_a,
                        "annotator_b_label": label_b,
                        "final_label": "",
                        "adjudicator_notes": "",
                    }
                )
        elif label_a or label_b:
            conflict = "single_sided_label"
            adjudication_rows.append(
                {
                    "candidate_id": candidate_id,
                    "source": str(a.get("source", "")).strip(),
                    "text": str(a.get("text", "")).strip(),
                    "annotator_a_label": label_a,
                    "annotator_b_label": label_b,
                    "final_label": "",
                    "adjudicator_notes": "",
                }
            )

        merged_rows.append(
            {
                "candidate_id": candidate_id,
                "source": str(a.get("source", "")).strip(),
                "source_item_id_or_url": str(a.get("source_item_id_or_url", "")).strip(),
                "text": str(a.get("text", "")).strip(),
                "annotator_a_label": label_a,
                "annotator_b_label": label_b,
                "conflict_type": conflict,
                "final_label": final_label,
                "adjudication_status": "pending" if conflict else "not_required",
            }
        )

    agreement_rate = (agreement_count / valid_pair_count) if valid_pair_count else 0.0

    merged_fields = list(merged_rows[0].keys()) if merged_rows else [
        "candidate_id",
        "source",
        "source_item_id_or_url",
        "text",
        "annotator_a_label",
        "annotator_b_label",
        "conflict_type",
        "final_label",
        "adjudication_status",
    ]
    adjudication_fields = list(adjudication_rows[0].keys()) if adjudication_rows else [
        "candidate_id",
        "source",
        "text",
        "annotator_a_label",
        "annotator_b_label",
        "final_label",
        "adjudicator_notes",
    ]
    write_csv(Path(args.merged_out), merged_fields, merged_rows)
    write_csv(Path(args.adjudication_out), adjudication_fields, adjudication_rows)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "annotator_a": str(a_path),
            "annotator_b": str(b_path),
        },
        "counts": {
            "common_candidates": len(common_ids),
            "valid_pair_count": valid_pair_count,
            "agreement_count": agreement_count,
            "adjudication_queue_count": len(adjudication_rows),
        },
        "agreement_rate": agreement_rate,
        "label_distribution": {
            "annotator_a": dict(label_counter_a),
            "annotator_b": dict(label_counter_b),
        },
        "outputs": {
            "merged": args.merged_out,
            "adjudication_queue": args.adjudication_out,
        },
    }
    report_path = Path(args.report_out)
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Merged output: {args.merged_out}")
    print(f"Adjudication queue: {args.adjudication_out}")
    print(f"Agreement rate: {agreement_rate:.4f}")
    print(f"Report: {args.report_out}")


if __name__ == "__main__":
    main()
