import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict


DEFAULT_OUTPUT_ROOT = Path("data_collection/output")
DEFAULT_TARGETS = Path("data_collection/configs/collection_targets.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report collected data progress vs target tiers.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--targets", default=str(DEFAULT_TARGETS))
    parser.add_argument("--tier", default="minimum", choices=["minimum", "better", "strong"])
    return parser.parse_args()


def load_targets(path: Path, tier: str) -> Dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    classes = payload.get("classes", ["HATE", "DISINFO", "NORMAL"])
    raw_multiplier = int(payload.get("raw_multiplier", 4))
    tier_cfg = payload.get("tiers", {}).get(tier, {})
    labeled_per_class_per_source = int(tier_cfg.get("labeled_per_class_per_source", 1000))
    labeled_target_per_source = labeled_per_class_per_source * len(classes)
    raw_target_per_source = labeled_target_per_source * raw_multiplier
    return {
        "classes": classes,
        "raw_multiplier": raw_multiplier,
        "labeled_per_class_per_source": labeled_per_class_per_source,
        "labeled_target_per_source": labeled_target_per_source,
        "raw_target_per_source": raw_target_per_source,
    }


def scan_records(output_root: Path) -> Dict[str, Dict[str, int]]:
    counts = defaultdict(lambda: {"total": 0, "sinhala": 0})

    if not output_root.exists():
        return counts

    for run_dir in sorted(output_root.iterdir()):
        if not run_dir.is_dir():
            continue
        csv_path = run_dir / "records.csv"
        if not csv_path.exists():
            continue

        with csv_path.open("r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                source = str(row.get("source", "")).strip() or "unknown"
                counts[source]["total"] += 1
                if str(row.get("is_sinhala", "")).strip().lower() == "true":
                    counts[source]["sinhala"] += 1

    return counts


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    targets = load_targets(path=Path(args.targets), tier=args.tier)
    counts = scan_records(output_root=output_root)

    print(f"Progress tier: {args.tier}")
    print(f"Target labeled per class per source: {targets['labeled_per_class_per_source']}")
    print(f"Target labeled per source (3 classes): {targets['labeled_target_per_source']}")
    print(f"Raw collection multiplier: {targets['raw_multiplier']}")
    print(f"Raw target per source: {targets['raw_target_per_source']}\n")

    if not counts:
        print("No records found in output root.")
        return

    print("Source progress:")
    for source, source_counts in sorted(counts.items()):
        total = source_counts["total"]
        sinhala = source_counts["sinhala"]
        gap = max(targets["raw_target_per_source"] - total, 0)
        pct = (total / targets["raw_target_per_source"]) * 100 if targets["raw_target_per_source"] > 0 else 0
        print(
            f"- {source}: total={total}, sinhala={sinhala}, "
            f"progress={pct:.2f}%, remaining_to_raw_target={gap}"
        )


if __name__ == "__main__":
    main()

