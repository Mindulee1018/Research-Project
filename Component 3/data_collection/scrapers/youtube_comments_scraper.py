import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from data_collection.io_utils import ensure_dir
from data_collection.normalize import clean_text, is_likely_sinhala
from data_collection.sources.common import fetch_url_content, parse_youtube_video_id


DEFAULT_PROJECT_ROOT = Path(os.environ.get("SL_SMA_PROJECT_ROOT", r"D:/client-projects/sl-social-media-risk-analysis"))
DEFAULT_DATASETS_ROOT = Path(os.environ.get("SL_SMA_DATASETS_ROOT", str(DEFAULT_PROJECT_ROOT / "datasets")))
DEFAULT_OUTPUT_CSV = DEFAULT_DATASETS_ROOT / "sources" / "youtube_comments.csv"
DEFAULT_STATE_PATH = DEFAULT_DATASETS_ROOT / "runtime" / "state" / "youtube_comments_state.json"
DEFAULT_LOG_PATH = DEFAULT_DATASETS_ROOT / "runtime" / "logs" / "youtube_comments.log"
DEFAULT_SUMMARY_PATH = DEFAULT_DATASETS_ROOT / "runtime" / "summaries" / "youtube_comments_summary.json"
DEFAULT_SEED_URLS_FILE = Path("data_collection/configs/youtube_seed_urls.txt")
DEFAULT_SEED_URLS = [
    "https://www.youtube.com/results?search_query=hiru+news+sinhala",
    "https://www.youtube.com/results?search_query=ada+derana+sinhala",
    "https://www.youtube.com/results?search_query=sirasa+news+sinhala",
    "https://www.youtube.com/results?search_query=swarnavahini+news+sinhala",
]
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


@dataclass
class YouTubeCommentRecord:
    source: str
    video_id: str
    video_url: str
    comment_id: str
    author_name: str
    published_at: str
    like_count: str
    text: str
    clean_text: str
    is_sinhala: bool
    extracted_at: str


@dataclass
class YouTubeRunSummary:
    started_at: str
    finished_at: str
    seeds_seen: int
    videos_discovered: int
    videos_processed: int
    videos_skipped_by_resume: int
    pages_failed: int
    comments_saved: int
    dataset_path: str
    dataset_total_rows: int
    interrupted: bool
    target_total_rows: int
    target_reached: bool
    max_comments_per_video: int
    related_seed_videos_scanned: int
    related_videos_discovered: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape YouTube comments into one resumable CSV dataset (no API key).")
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--seed-urls-file", default=str(DEFAULT_SEED_URLS_FILE))
    parser.add_argument("--seed-url", action="append", default=[])
    parser.add_argument("--no-default-seeds", action="store_true")
    parser.add_argument("--max-seed-pages", type=int, default=20)
    parser.add_argument("--max-videos", type=int, default=100)
    parser.add_argument("--discovery-overscan-multiplier", type=int, default=5)
    parser.add_argument("--related-discovery", action="store_true")
    parser.add_argument("--related-frontier-size", type=int, default=120)
    parser.add_argument("--max-related-seed-videos", type=int, default=80)
    parser.add_argument("--max-comments-per-video", type=int, default=300)
    parser.add_argument("--max-continuation-pages", type=int, default=40)
    parser.add_argument("--sleep-ms", type=int, default=350)
    parser.add_argument("--min-comment-chars", type=int, default=8)
    parser.add_argument("--max-comment-chars", type=int, default=2400)
    parser.add_argument("--sinhala-threshold", type=float, default=0.2)
    parser.add_argument("--target-total-rows", type=int, default=0)
    parser.add_argument("--include-non-sinhala", action="store_true")
    parser.add_argument("--ignore-resume", action="store_true")
    return parser.parse_args()


def setup_logger(log_path: Path) -> logging.Logger:
    ensure_dir(log_path.parent)
    logger = logging.getLogger("youtube_comments_scraper")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"processed_videos": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def save_summary(path: Path, summary: YouTubeRunSummary) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(summary.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")


def load_seen_comment_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return {str(row.get("comment_id", "")).strip() for row in reader if str(row.get("comment_id", "")).strip()}


def append_rows(path: Path, rows: Iterable[YouTubeCommentRecord]) -> int:
    rows_list = list(rows)
    if not rows_list:
        return 0

    ensure_dir(path.parent)
    fieldnames = list(YouTubeCommentRecord.__annotations__.keys())
    write_header = not path.exists()

    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in rows_list:
            writer.writerow(row.__dict__)
    return len(rows_list)


def load_seed_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []

    for item in args.seed_url:
        value = str(item).strip()
        if value:
            urls.append(value)

    seed_file = Path(args.seed_urls_file)
    if seed_file.exists():
        for line in seed_file.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                urls.append(value)

    if not args.no_default_seeds:
        for item in DEFAULT_SEED_URLS:
            value = str(item).strip()
            if value:
                urls.append(value)

    output: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        output.append(url)
    return output


def extract_video_ids_from_html(html: str) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    patterns = [
        r"watch\?v=([A-Za-z0-9_-]{11})",
        r"shorts/([A-Za-z0-9_-]{11})",
        r"\"videoId\":\"([A-Za-z0-9_-]{11})\"",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, html):
            video_id = str(match).strip()
            if not VIDEO_ID_RE.match(video_id):
                continue
            if video_id in seen:
                continue
            seen.add(video_id)
            output.append(video_id)
    return output


def select_frontier_videos(
    *,
    processed_videos: set[str],
    discovered_video_ids: list[str],
    frontier_size: int,
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    # Prioritize already discovered videos first because they align with current seeds.
    for video_id in discovered_video_ids:
        if video_id in seen:
            continue
        seen.add(video_id)
        ordered.append(video_id)
        if len(ordered) >= frontier_size:
            return ordered

    # Then include most recently processed videos from state to branch into new related videos.
    for video_id in reversed(sorted(processed_videos)):
        if video_id in seen:
            continue
        seen.add(video_id)
        ordered.append(video_id)
        if len(ordered) >= frontier_size:
            return ordered

    return ordered


def discover_related_videos(
    *,
    frontier_video_ids: list[str],
    discovered_set: set[str],
    discovery_cap: int,
    max_related_seed_videos: int,
    sleep_ms: int,
    logger: logging.Logger,
) -> tuple[list[str], int, int]:
    related_discovered: list[str] = []
    pages_failed = 0
    scanned = 0

    for video_id in frontier_video_ids:
        if scanned >= max_related_seed_videos:
            break
        if len(discovered_set) >= discovery_cap:
            break

        scanned += 1
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            html = fetch_url_content(url)
        except Exception as exc:  # pragma: no cover - network variability
            pages_failed += 1
            logger.warning("Failed to fetch related frontier video: %s | %s", url, exc)
            continue

        for related_id in extract_video_ids_from_html(html):
            if related_id in discovered_set:
                continue
            discovered_set.add(related_id)
            related_discovered.append(related_id)
            if len(discovered_set) >= discovery_cap:
                break

        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)

    return related_discovered, scanned, pages_failed


def find_first_json_object(text: str, start_index: int) -> dict | None:
    start = text.find("{", start_index)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False

    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                segment = text[start : idx + 1]
                try:
                    payload = json.loads(segment)
                except json.JSONDecodeError:
                    return None
                if isinstance(payload, dict):
                    return payload
                return None
    return None


def extract_ytcfg(html: str) -> dict:
    marker = "ytcfg.set("
    index = html.find(marker)
    if index < 0:
        return {}
    payload = find_first_json_object(html, index + len(marker))
    if isinstance(payload, dict):
        return payload
    return {}


def extract_initial_data(html: str) -> dict:
    markers = [
        "var ytInitialData =",
        'window["ytInitialData"] =',
        "ytInitialData =",
    ]
    for marker in markers:
        index = html.find(marker)
        if index < 0:
            continue
        payload = find_first_json_object(html, index + len(marker))
        if isinstance(payload, dict):
            return payload
    return {}


def extract_bootstrap_values_from_html(html: str) -> dict[str, str]:
    def match_string(key: str) -> str:
        patterns = [
            rf'"{re.escape(key)}"\s*:\s*"([^"]+)"',
            rf"'{re.escape(key)}'\s*:\s*'([^']+)'",
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()
        return ""

    def match_number(key: str) -> str:
        match = re.search(rf'"{re.escape(key)}"\s*:\s*(\d+)', html)
        if match:
            return match.group(1).strip()
        return ""

    return {
        "INNERTUBE_API_KEY": match_string("INNERTUBE_API_KEY"),
        "INNERTUBE_CLIENT_NAME": match_string("INNERTUBE_CLIENT_NAME") or match_number("INNERTUBE_CLIENT_NAME"),
        "INNERTUBE_CLIENT_VERSION": match_string("INNERTUBE_CLIENT_VERSION"),
        "HL": match_string("HL"),
        "GL": match_string("GL"),
    }


def iter_nodes(value):
    stack = [value]
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, dict):
            for child in node.values():
                stack.append(child)
        elif isinstance(node, list):
            for child in node:
                stack.append(child)


def extract_text_from_runs(value) -> str:
    if isinstance(value, dict):
        simple = str(value.get("simpleText", "")).strip()
        if simple:
            return simple
        runs = value.get("runs", [])
        if isinstance(runs, list):
            parts: list[str] = []
            for item in runs:
                if isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                    if text:
                        parts.append(text)
            return "".join(parts).strip()
    return ""


def parse_comment_renderers(payload: dict) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in parse_comment_entities(payload):
        comment_id = str(item.get("comment_id", "")).strip()
        if not comment_id or comment_id in seen:
            continue
        seen.add(comment_id)
        comments.append(item)

    for node in iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        renderer = node.get("commentRenderer")
        if not isinstance(renderer, dict):
            continue
        comment_id = str(renderer.get("commentId", "")).strip()
        text = extract_text_from_runs(renderer.get("contentText"))
        if not comment_id or not text:
            continue
        if comment_id in seen:
            continue
        seen.add(comment_id)
        comments.append(
            {
                "comment_id": comment_id,
                "author_name": extract_text_from_runs(renderer.get("authorText")),
                "published_at": extract_text_from_runs(renderer.get("publishedTimeText")),
                "like_count": extract_text_from_runs(renderer.get("voteCount")),
                "text": clean_text(text),
            }
        )
    return comments


def parse_comment_entities(payload: dict) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    mutations = (
        payload.get("frameworkUpdates", {})
        .get("entityBatchUpdate", {})
        .get("mutations", [])
    )
    if not isinstance(mutations, list):
        return comments

    for mutation in mutations:
        if not isinstance(mutation, dict):
            continue
        comment_payload = mutation.get("payload", {}).get("commentEntityPayload")
        if not isinstance(comment_payload, dict):
            continue
        properties = comment_payload.get("properties", {})
        author = comment_payload.get("author", {})
        toolbar = comment_payload.get("toolbar", {})
        if not isinstance(properties, dict):
            continue

        comment_id = str(properties.get("commentId", "")).strip()
        content = properties.get("content", {})
        text = ""
        if isinstance(content, dict):
            text = str(content.get("content", "")).strip()
        if not comment_id or not text:
            continue

        author_name = ""
        if isinstance(author, dict):
            author_name = str(author.get("displayName", "")).strip()

        like_count = ""
        if isinstance(toolbar, dict):
            like_count = str(toolbar.get("likeCountNotliked", "")).strip()

        comments.append(
            {
                "comment_id": comment_id,
                "author_name": author_name,
                "published_at": str(properties.get("publishedTime", "")).strip(),
                "like_count": like_count,
                "text": clean_text(text),
            }
        )

    return comments


def extract_continuation_tokens(payload: dict) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for node in iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        command = node.get("continuationCommand")
        if isinstance(command, dict):
            token = str(command.get("token", "")).strip()
            if token and token not in seen:
                seen.add(token)
                output.append(token)
        next_data = node.get("nextContinuationData")
        if isinstance(next_data, dict):
            token = str(next_data.get("continuation", "")).strip()
            if token and token not in seen:
                seen.add(token)
                output.append(token)
        reload_data = node.get("reloadContinuationData")
        if isinstance(reload_data, dict):
            token = str(reload_data.get("continuation", "")).strip()
            if token and token not in seen:
                seen.add(token)
                output.append(token)
    return output


def fetch_json_post(url: str, payload: dict, timeout_sec: int = 25) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url=url,
        data=body,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://www.youtube.com",
            "Referer": "https://www.youtube.com/",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_sec) as response:
        raw = response.read().decode("utf-8", errors="ignore")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object response.")
    return parsed


def build_youtube_context(ytcfg: dict, html_bootstrap: dict[str, str]) -> dict:
    client_name = str(ytcfg.get("INNERTUBE_CLIENT_NAME", "")).strip() or html_bootstrap.get("INNERTUBE_CLIENT_NAME", "") or "WEB"
    client_version = str(ytcfg.get("INNERTUBE_CLIENT_VERSION", "")).strip() or html_bootstrap.get("INNERTUBE_CLIENT_VERSION", "")
    if not client_version:
        client_version = "2.20260301.00.00"
    hl = str(ytcfg.get("HL", "")).strip() or html_bootstrap.get("HL", "") or "en"
    gl = str(ytcfg.get("GL", "")).strip() or html_bootstrap.get("GL", "") or "US"
    return {
        "client": {
            "clientName": client_name,
            "clientVersion": client_version,
            "hl": hl,
            "gl": gl,
            "utcOffsetMinutes": 0,
        }
    }


def scrape_video_comments(
    *,
    video_id: str,
    args: argparse.Namespace,
    logger: logging.Logger,
) -> tuple[list[dict[str, str]], int]:
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    html = fetch_url_content(video_url)
    ytcfg = extract_ytcfg(html)
    bootstrap = extract_bootstrap_values_from_html(html)
    initial_data = extract_initial_data(html)

    api_key = str(ytcfg.get("INNERTUBE_API_KEY", "")).strip() or bootstrap.get("INNERTUBE_API_KEY", "")
    if not api_key:
        logger.info("No INNERTUBE API key found in video page: %s", video_url)
        return [], 0

    records: list[dict[str, str]] = []
    pages_failed = 0

    initial_comments = parse_comment_renderers(initial_data)
    if initial_comments:
        records.extend(initial_comments)

    tokens = extract_continuation_tokens(initial_data)
    if not tokens:
        logger.info("No comment continuation token found on video: %s", video_url)
        return records, pages_failed

    context = build_youtube_context(ytcfg, bootstrap)
    next_url = "https://www.youtube.com/youtubei/v1/next?" + urlencode({"key": api_key})
    continuation_pages = 0

    while tokens and len(records) < args.max_comments_per_video and continuation_pages < args.max_continuation_pages:
        continuation = tokens.pop(0)
        continuation_pages += 1
        payload = {
            "context": context,
            "continuation": continuation,
        }

        try:
            response = fetch_json_post(next_url, payload)
        except Exception as exc:  # pragma: no cover - network variability
            pages_failed += 1
            logger.warning("Continuation fetch failed for video %s | %s", video_id, exc)
            continue

        parsed_comments = parse_comment_renderers(response)
        if parsed_comments:
            records.extend(parsed_comments)

        next_tokens = extract_continuation_tokens(response)
        for token in next_tokens:
            if token and token not in tokens:
                tokens.append(token)

        if args.sleep_ms > 0:
            time.sleep(args.sleep_ms / 1000.0)

    return records[: args.max_comments_per_video], pages_failed


def scrape_youtube_comments(args: argparse.Namespace) -> None:
    output_csv = Path(args.output_csv)
    state_path = Path(args.state_path)
    log_path = Path(args.log_path)
    summary_path = Path(args.summary_path)

    logger = setup_logger(log_path)
    started_at = now_iso()

    state = load_state(state_path)
    processed_videos = {str(item).strip() for item in state.get("processed_videos", []) if str(item).strip()}
    seen_comment_ids = load_seen_comment_ids(output_csv)

    logger.info("Starting YouTube comments scrape.")
    logger.info("Existing rows: %s", len(seen_comment_ids))
    logger.info("Processed videos in resume state: %s", len(processed_videos))

    seed_urls = load_seed_urls(args)
    logger.info("Seed URLs loaded: %s", len(seed_urls))

    pages_failed = 0
    discovered_video_ids: list[str] = []
    discovered_set: set[str] = set()
    discovery_cap = max(args.max_videos, 1) * max(args.discovery_overscan_multiplier, 1)
    related_seed_videos_scanned = 0
    related_videos_discovered = 0

    for seed_url in seed_urls[: args.max_seed_pages]:
        seed_video_id = parse_youtube_video_id(seed_url)
        if seed_video_id and VIDEO_ID_RE.match(seed_video_id):
            if seed_video_id not in discovered_set:
                discovered_set.add(seed_video_id)
                discovered_video_ids.append(seed_video_id)
            continue

        try:
            html = fetch_url_content(seed_url)
        except Exception as exc:  # pragma: no cover - network variability
            pages_failed += 1
            logger.warning("Failed to fetch seed URL: %s | %s", seed_url, exc)
            continue

        for video_id in extract_video_ids_from_html(html):
            if video_id in discovered_set:
                continue
            discovered_set.add(video_id)
            discovered_video_ids.append(video_id)
            if len(discovered_video_ids) >= discovery_cap:
                break
        if len(discovered_video_ids) >= discovery_cap:
            break

    if args.related_discovery and len(discovered_video_ids) < discovery_cap:
        frontier = select_frontier_videos(
            processed_videos=processed_videos,
            discovered_video_ids=discovered_video_ids,
            frontier_size=max(args.related_frontier_size, 1),
        )
        if frontier:
            logger.info("Related discovery enabled. Frontier videos: %s", len(frontier))
            related_ids, scanned, related_failures = discover_related_videos(
                frontier_video_ids=frontier,
                discovered_set=discovered_set,
                discovery_cap=discovery_cap,
                max_related_seed_videos=max(args.max_related_seed_videos, 1),
                sleep_ms=args.sleep_ms,
                logger=logger,
            )
            pages_failed += related_failures
            related_seed_videos_scanned = scanned
            related_videos_discovered = len(related_ids)
            discovered_video_ids.extend(related_ids)
            logger.info(
                "Related discovery added %s video ids (scanned frontier videos=%s).",
                len(related_ids),
                scanned,
            )

    logger.info(
        "Discovered videos total: %s (cap=%s, seed pages=%s)",
        len(discovered_video_ids),
        discovery_cap,
        min(len(seed_urls), args.max_seed_pages),
    )

    videos_processed = 0
    videos_skipped_by_resume = 0
    total_new_comments = 0
    interrupted = False
    target_reached = args.target_total_rows > 0 and len(seen_comment_ids) >= args.target_total_rows

    try:
        for idx, video_id in enumerate(discovered_video_ids, start=1):
            if target_reached:
                break

            if not args.ignore_resume and video_id in processed_videos:
                videos_skipped_by_resume += 1
                continue

            logger.info("Video %s/%s: %s", idx, len(discovered_video_ids), video_id)
            try:
                parsed_comments, fail_count = scrape_video_comments(video_id=video_id, args=args, logger=logger)
                pages_failed += fail_count
            except Exception as exc:  # pragma: no cover - network variability
                pages_failed += 1
                logger.warning("Video scrape failed: %s | %s", video_id, exc)
                continue

            rows_to_append: list[YouTubeCommentRecord] = []
            for parsed in parsed_comments:
                comment_id = parsed["comment_id"]
                if not comment_id or comment_id in seen_comment_ids:
                    continue

                comment_text = str(parsed.get("text", "")).strip()
                if not comment_text:
                    continue
                if len(comment_text) < args.min_comment_chars or len(comment_text) > args.max_comment_chars:
                    continue

                sinhala = is_likely_sinhala(comment_text, threshold=args.sinhala_threshold)
                if not args.include_non_sinhala and not sinhala:
                    continue

                rows_to_append.append(
                    YouTubeCommentRecord(
                        source="youtube",
                        video_id=video_id,
                        video_url=f"https://www.youtube.com/watch?v={video_id}",
                        comment_id=comment_id,
                        author_name=str(parsed.get("author_name", "")).strip(),
                        published_at=str(parsed.get("published_at", "")).strip(),
                        like_count=str(parsed.get("like_count", "")).strip(),
                        text=comment_text,
                        clean_text=comment_text,
                        is_sinhala=sinhala,
                        extracted_at=now_iso(),
                    )
                )
                seen_comment_ids.add(comment_id)

            written = append_rows(output_csv, rows_to_append)
            total_new_comments += written
            videos_processed += 1
            processed_videos.add(video_id)

            state["processed_videos"] = sorted(processed_videos)
            save_state(state_path, state)

            logger.info("Video complete: %s | new comments saved=%s | total saved this run=%s", video_id, written, total_new_comments)

            if args.target_total_rows > 0 and len(seen_comment_ids) >= args.target_total_rows:
                target_reached = True
                logger.info("Dataset progress: %s/%s rows", len(seen_comment_ids), args.target_total_rows)
                break

            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)
    except KeyboardInterrupt:
        interrupted = True
        logger.warning("Interrupted by user. Progress has been saved.")

    dataset_total_rows = len(load_seen_comment_ids(output_csv))

    summary = YouTubeRunSummary(
        started_at=started_at,
        finished_at=now_iso(),
        seeds_seen=min(len(seed_urls), args.max_seed_pages),
        videos_discovered=len(discovered_video_ids),
        videos_processed=videos_processed,
        videos_skipped_by_resume=videos_skipped_by_resume,
        pages_failed=pages_failed,
        comments_saved=total_new_comments,
        dataset_path=str(output_csv),
        dataset_total_rows=dataset_total_rows,
        interrupted=interrupted,
        target_total_rows=args.target_total_rows,
        target_reached=target_reached,
        max_comments_per_video=args.max_comments_per_video,
        related_seed_videos_scanned=related_seed_videos_scanned,
        related_videos_discovered=related_videos_discovered,
    )
    save_summary(summary_path, summary)

    logger.info("YouTube scrape finished. New comments saved this run: %s", total_new_comments)
    logger.info("Videos processed: %s | skipped by resume: %s | failures: %s", videos_processed, videos_skipped_by_resume, pages_failed)
    logger.info("Dataset total rows: %s", dataset_total_rows)
    logger.info("Summary written to: %s", summary_path)


if __name__ == "__main__":
    scrape_youtube_comments(parse_args())
