import argparse
import csv
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from data_collection.io_utils import ensure_dir
from data_collection.normalize import clean_text, is_likely_sinhala


URL_ONLY_RE = re.compile(r"^(https?://\S+|www\.\S+|\S+\.com\S*|\S+\.lk\S*)+$", re.IGNORECASE)
REPEATED_CHAR_RE = re.compile(r"(.)\1{6,}", re.DOTALL)
NON_TEXT_RE = re.compile(r"[\W_]+", re.UNICODE)
BOILERPLATE_PATTERNS = [
    "like and share",
    "subscribe",
    "join our channel",
    "follow us",
    "whatsapp",
    "telegram",
]

RISK_SHORT_MARKERS = {
    "පකයා",
    "කාලකන්නි",
    "වනචරයා",
    "බොරු",
    "fake",
    "liar",
    "hate",
    "අපහාස",
}

DEFAULT_PROJECT_ROOT = Path(os.environ.get("SL_SMA_PROJECT_ROOT", r"D:/client-projects/sl-social-media-risk-analysis"))
DEFAULT_DATASETS_ROOT = Path(os.environ.get("SL_SMA_DATASETS_ROOT", str(DEFAULT_PROJECT_ROOT / "datasets")))


def sinhala_normalize_text(text: str) -> str:
    # Keep this conservative: normalize punctuation/spacing/repeats while preserving semantic cues.
    value = unicodedata.normalize("NFKC", clean_text(text))
    value = value.replace("“", '"').replace("”", '"').replace("’", "'")
    value = re.sub(r"[‐‑‒–—]", "-", value)
    value = re.sub(r"[।|]+", ".", value)
    value = re.sub(r"[!?]{3,}", "!!", value)
    value = re.sub(r"\.{3,}", "..", value)
    value = re.sub(r"([^\W\d_])\1{3,}", r"\1\1", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine source datasets and build one final cleaned dataset (no intermediate queue outputs)."
    )
    parser.add_argument("--elakiri-path", default=str(DEFAULT_DATASETS_ROOT / "sources" / "elakiri_comments.csv"))
    parser.add_argument("--gossip-path", default=str(DEFAULT_DATASETS_ROOT / "sources" / "gossip_lanka_comments.csv"))
    parser.add_argument("--youtube-path", default=str(DEFAULT_DATASETS_ROOT / "sources" / "youtube_comments.csv"))
    parser.add_argument("--output-csv", default=str(DEFAULT_DATASETS_ROOT / "preprocessing" / "final_cleaned_dataset.csv"))
    parser.add_argument(
        "--summary-path",
        default=str(DEFAULT_DATASETS_ROOT / "preprocessing" / "final_cleaned_dataset_summary.json"),
    )
    parser.add_argument("--sinhala-threshold", type=float, default=0.2)
    parser.add_argument("--min-text-chars", type=int, default=8)
    parser.add_argument("--max-text-chars", type=int, default=1200)
    return parser.parse_args()


def canonical_text(text: str) -> str:
    value = sinhala_normalize_text(text).lower()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def near_duplicate_fingerprint(text: str) -> str:
    value = canonical_text(text)
    value = re.sub(r"(.)\1{2,}", r"\1\1", value)
    value = NON_TEXT_RE.sub("", value)
    return value


def detect_noise_reason(text: str, min_chars: int) -> str:
    stripped = clean_text(text)
    if not stripped:
        return "empty_text"
    if len(stripped) < min_chars:
        lower = stripped.lower()
        if not any(marker in lower for marker in RISK_SHORT_MARKERS):
            return "too_short"
    if URL_ONLY_RE.match(stripped.replace(" ", "")):
        return "url_only"
    lower = stripped.lower()
    for pattern in BOILERPLATE_PATTERNS:
        if pattern in lower:
            return "boilerplate_spam"
    letters_or_digits = "".join(ch for ch in stripped if ch.isalnum())
    if not letters_or_digits:
        return "emoji_or_symbol_only"
    if REPEATED_CHAR_RE.search(stripped):
        return "excessive_repeated_chars"
    return ""


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def sinhala_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    sinhala_count = sum(1 for ch in letters if "\u0D80" <= ch <= "\u0DFF")
    return sinhala_count / len(letters)


def derive_quality_flags(text: str) -> str:
    flags: list[str] = []
    sinhala_letters = sum(1 for ch in text if "\u0D80" <= ch <= "\u0DFF")
    latin_letters = sum(1 for ch in text if ("a" <= ch.lower() <= "z"))
    if sinhala_letters > 0 and latin_letters > 0:
        flags.append("mixed_script")
    if "?" in text:
        flags.append("question_form")
    if len(text) > 300:
        flags.append("long_context")
    return ",".join(flags)


def make_source_item_id(row: dict[str, str], source: str) -> str:
    if source == "elakiri":
        return str(row.get("post_url") or row.get("post_id") or row.get("thread_url") or "").strip()
    if source == "gossip_lanka":
        return str(row.get("comment_anchor_url") or row.get("article_url") or row.get("comment_id") or "").strip()
    if source == "youtube":
        video_url = str(row.get("video_url", "")).strip()
        comment_id = str(row.get("comment_id", "")).strip()
        if video_url and comment_id:
            return f"{video_url}&lc={comment_id}"
        return video_url or comment_id
    return ""


def iter_source_rows(path: Path, source_name: str):
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            text = sinhala_normalize_text(str(row.get("clean_text") or row.get("text") or "").strip())
            if not text:
                continue
            source_item = make_source_item_id(row, source_name)
            if not source_item:
                continue
            yield {
                "source": source_name,
                "source_item_id_or_url": source_item,
                "scraped_at": str(row.get("extracted_at") or row.get("published_at") or "").strip(),
                "text": text,
                "is_sinhala_flag": truthy(row.get("is_sinhala", "")),
            }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    fieldnames = [
        "candidate_id",
        "source",
        "source_item_id_or_url",
        "scraped_at",
        "text",
        "text_len",
        "sinhala_ratio",
        "quality_flags",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    sources = {
        "elakiri": Path(args.elakiri_path),
        "gossip_lanka": Path(args.gossip_path),
        "youtube": Path(args.youtube_path),
    }
    for name, path in sources.items():
        if not path.exists():
            raise SystemExit(f"Missing source dataset for {name}: {path}")

    kept_rows: list[dict[str, str]] = []
    exact_seen: set[str] = set()
    near_seen: set[str] = set()

    stats = {
        "input_rows": 0,
        "kept_rows": 0,
        "dropped_non_sinhala": 0,
        "dropped_long_rows": 0,
        "dropped_noise": 0,
        "dropped_exact_duplicates": 0,
        "dropped_near_duplicates": 0,
    }
    kept_by_source = {"elakiri": 0, "gossip_lanka": 0, "youtube": 0}

    for source_name, source_path in sources.items():
        for row in iter_source_rows(source_path, source_name):
            stats["input_rows"] += 1
            normalized = canonical_text(row["text"])
            if not normalized:
                stats["dropped_noise"] += 1
                continue

            exact_key = hashlib.sha256(
                f"{row['source']}|{row['source_item_id_or_url']}|{normalized}".encode("utf-8")
            ).hexdigest()
            if exact_key in exact_seen:
                stats["dropped_exact_duplicates"] += 1
                continue
            exact_seen.add(exact_key)

            near_fp = near_duplicate_fingerprint(row["text"])
            near_key = hashlib.sha256(f"{row['source']}|{near_fp}".encode("utf-8")).hexdigest()
            if near_fp and near_key in near_seen:
                stats["dropped_near_duplicates"] += 1
                continue
            if near_fp:
                near_seen.add(near_key)

            noise_reason = detect_noise_reason(row["text"], min_chars=args.min_text_chars)
            if noise_reason:
                stats["dropped_noise"] += 1
                continue

            if len(normalized) > args.max_text_chars:
                stats["dropped_long_rows"] += 1
                continue

            sinhala = row["is_sinhala_flag"] or is_likely_sinhala(normalized, threshold=args.sinhala_threshold)
            if not sinhala:
                stats["dropped_non_sinhala"] += 1
                continue

            kept_rows.append(
                {
                    "candidate_id": exact_key,
                    "source": row["source"],
                    "source_item_id_or_url": row["source_item_id_or_url"],
                    "scraped_at": row["scraped_at"],
                    "text": normalized,
                    "text_len": str(len(normalized)),
                    "sinhala_ratio": f"{sinhala_ratio(normalized):.4f}",
                    "quality_flags": derive_quality_flags(normalized),
                }
            )
            stats["kept_rows"] += 1
            kept_by_source[source_name] += 1

    output_path = Path(args.output_csv)
    write_csv(output_path, kept_rows)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_csv": str(output_path),
        "summary_path": str(args.summary_path),
        "sources": {name: str(path) for name, path in sources.items()},
        "constraints": {
            "sinhala_threshold": args.sinhala_threshold,
            "min_text_chars": args.min_text_chars,
            "max_text_chars": args.max_text_chars,
        },
        "stats": stats,
        "kept_by_source": kept_by_source,
    }
    summary_path = Path(args.summary_path)
    ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Final cleaned dataset: {output_path}")
    print(f"Rows: {stats['kept_rows']}")
    print(f"Summary: {summary_path}")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
