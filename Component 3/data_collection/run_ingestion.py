import argparse
import json
from pathlib import Path

from data_collection.io_utils import load_json
from data_collection.runner import run_ingestion


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run multi-source Sinhala ingestion for YouTube, Gossip Lanka, and Elakiri."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to ingestion config JSON.",
    )
    parser.add_argument("--run-id", default="", help="Optional run ID override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = load_json(config_path)
    result = run_ingestion(config=config, run_id=(args.run_id or None))
    print(json.dumps(result["manifest"], ensure_ascii=False, indent=2))
    print(f"\nOutput directory: {result['run_dir']}")


if __name__ == "__main__":
    main()
