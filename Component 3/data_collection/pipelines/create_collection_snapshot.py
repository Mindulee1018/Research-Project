import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from data_collection.io_utils import ensure_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a timestamped pre-scrape snapshot of dataset and state counts.")
    parser.add_argument("--output-dir", default="datasets/runtime/snapshots")
    parser.add_argument("--tag", default="pre_run")
    return parser.parse_args()


def csv_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def state_count(path: Path, key: str) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get(key, [])
    if isinstance(value, list):
        return len(value)
    return 0


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["created_at", "tag", "metric", "value"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    created_at = datetime.now(timezone.utc).isoformat()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir)
    ensure_dir(out_dir)

    metrics = {
        "elakiri_rows": csv_row_count(Path("datasets/sources/elakiri_comments.csv")),
        "gossip_lanka_rows": csv_row_count(Path("datasets/sources/gossip_lanka_comments.csv")),
        "youtube_rows": csv_row_count(Path("datasets/sources/youtube_comments.csv")),
        "final_cleaned_rows": csv_row_count(Path("datasets/preprocessing/final_cleaned_dataset.csv")),
        "elakiri_processed_threads": state_count(Path("datasets/runtime/state/elakiri_comments_state.json"), "processed_threads"),
        "gossip_lanka_processed_articles": state_count(Path("datasets/runtime/state/gossip_lanka_comments_state.json"), "processed_articles"),
        "youtube_processed_videos": state_count(Path("datasets/runtime/state/youtube_comments_state.json"), "processed_videos"),
    }

    snapshot = {
        "created_at": created_at,
        "tag": args.tag,
        "metrics": metrics,
    }
    json_path = out_dir / f"collection_snapshot_{args.tag}_{ts}.json"
    csv_path = out_dir / f"collection_snapshot_{args.tag}_{ts}.csv"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(
        csv_path,
        [
            {"created_at": created_at, "tag": args.tag, "metric": key, "value": str(value)}
            for key, value in metrics.items()
        ],
    )

    print(f"Snapshot JSON: {json_path}")
    print(f"Snapshot CSV: {csv_path}")
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
