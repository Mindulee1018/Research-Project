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
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from data_collection.html_extract import extract_links_from_html, extract_text_from_html
from data_collection.io_utils import ensure_dir
from data_collection.normalize import clean_text, is_likely_sinhala
from data_collection.sources.common import fetch_url_content


DEFAULT_PROJECT_ROOT = Path(os.environ.get("SL_SMA_PROJECT_ROOT", r"D:/client-projects/sl-social-media-risk-analysis"))
DEFAULT_DATASETS_ROOT = Path(os.environ.get("SL_SMA_DATASETS_ROOT", str(DEFAULT_PROJECT_ROOT / "datasets")))
DEFAULT_OUTPUT_CSV = DEFAULT_DATASETS_ROOT / "sources" / "elakiri_comments.csv"
DEFAULT_STATE_PATH = DEFAULT_DATASETS_ROOT / "runtime" / "state" / "elakiri_comments_state.json"
DEFAULT_LOG_PATH = DEFAULT_DATASETS_ROOT / "runtime" / "logs" / "elakiri_comments.log"
DEFAULT_SUMMARY_PATH = DEFAULT_DATASETS_ROOT / "runtime" / "summaries" / "elakiri_comments_summary.json"
DEFAULT_START_URL = "https://elakiri.com/threads/latest"


@dataclass
class ElakiriCommentRecord:
    source: str
    thread_url: str
    thread_title: str
    page_url: str
    post_id: str
    post_url: str
    author_name: str
    author_url: str
    published_at: str
    text: str
    clean_text: str
    is_sinhala: bool
    extracted_at: str


@dataclass
class ElakiriRunSummary:
    started_at: str
    finished_at: str
    listing_pages_requested: int
    max_thread_pages: int
    threads_seen: int
    threads_processed: int
    threads_skipped_by_resume: int
    pages_fetched: int
    pages_failed: int
    posts_parsed: int
    comments_saved: int
    dataset_path: str
    dataset_total_rows: int
    interrupted: bool
    target_total_rows: int
    target_reached: bool


class ElakiriThreadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.posts: list[dict[str, str | bool]] = []
        self._current_post: dict[str, str | bool] | None = None
        self._post_depth = 0
        self._body_depth = 0
        self._skip_depth = 0
        self._quote_depth = 0
        self._capture_time = False

    def handle_starttag(self, tag: str, attrs) -> None:
        attr_map = {str(key).lower(): str(value) for key, value in attrs}
        classes = attr_map.get("class", "")
        class_tokens = {token.strip() for token in classes.split() if token.strip()}

        if self._current_post is None:
            if tag.lower() == "article" and "js-post" in class_tokens and "message--post" in class_tokens:
                post_id = attr_map.get("id", "").replace("js-post-", "").strip()
                if not post_id:
                    post_id = attr_map.get("data-content", "").replace("post-", "").strip()
                self._current_post = {
                    "post_id": post_id,
                    "author_name": attr_map.get("data-author", "").strip(),
                    "author_url": "",
                    "published_at": "",
                    "body_parts": [],
                    "is_thread_starter": "message-threadstarterpost" in {token.lower() for token in class_tokens},
                }
                self._post_depth = 1
            return

        self._post_depth += 1

        if tag.lower() in {"script", "style"}:
            self._skip_depth += 1

        if tag.lower() == "a":
            href = attr_map.get("href", "").strip()
            if href.startswith("/members/") and not self._current_post["author_url"]:
                self._current_post["author_url"] = "https://elakiri.com" + href

        if tag.lower() == "time" and not self._current_post["published_at"]:
            self._capture_time = True

        if tag.lower() == "article" and "message-body" in class_tokens:
            self._body_depth = 1
            return

        if self._body_depth > 0:
            self._body_depth += 1
            if tag.lower() == "blockquote":
                self._quote_depth += 1
            if tag.lower() == "br" and self._quote_depth == 0 and self._skip_depth == 0:
                body_parts = self._current_post["body_parts"]
                if isinstance(body_parts, list):
                    body_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self._current_post is None:
            return

        lower = tag.lower()
        if self._body_depth > 0:
            if lower == "blockquote" and self._quote_depth > 0:
                self._quote_depth -= 1
            self._body_depth -= 1

        if self._capture_time and lower == "time":
            self._capture_time = False

        if lower in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1

        self._post_depth -= 1
        if self._post_depth == 0:
            body_parts = self._current_post.pop("body_parts", [])
            raw_text = "".join(body_parts) if isinstance(body_parts, list) else ""
            self._current_post["raw_text"] = raw_text
            self.posts.append(self._current_post)
            self._current_post = None
            self._body_depth = 0
            self._skip_depth = 0
            self._quote_depth = 0
            self._capture_time = False

    def handle_data(self, data: str) -> None:
        if self._current_post is None:
            return

        if self._capture_time and not self._current_post["published_at"]:
            text = " ".join(data.split()).strip()
            if text:
                self._current_post["published_at"] = text

        if self._body_depth <= 0 or self._skip_depth > 0 or self._quote_depth > 0:
            return

        text = data.strip()
        if text:
            body_parts = self._current_post["body_parts"]
            if isinstance(body_parts, list):
                body_parts.append(text + " ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Elakiri forum comments into one resumable CSV dataset.")
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--start-url", default=DEFAULT_START_URL)
    parser.add_argument("--listing-pages", type=int, default=20)
    parser.add_argument("--listing-start-page", type=int, default=0)
    parser.add_argument("--listing-end-page", type=int, default=0)
    parser.add_argument("--max-thread-pages", type=int, default=3)
    parser.add_argument("--sleep-ms", type=int, default=300)
    parser.add_argument("--min-comment-chars", type=int, default=20)
    parser.add_argument("--max-comment-chars", type=int, default=2400)
    parser.add_argument("--target-total-rows", type=int, default=0)
    parser.add_argument("--include-non-sinhala", action="store_true")
    return parser.parse_args()


def setup_logger(log_path: Path) -> logging.Logger:
    ensure_dir(log_path.parent)
    logger = logging.getLogger("elakiri_comments_scraper")
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
        return {"processed_threads": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_seen_post_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return {str(row.get("post_id", "")).strip() for row in reader if str(row.get("post_id", "")).strip()}


def save_summary(path: Path, summary: ElakiriRunSummary) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(summary.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")


def append_rows(path: Path, rows: Iterable[ElakiriCommentRecord]) -> int:
    rows_list = list(rows)
    if not rows_list:
        return 0

    ensure_dir(path.parent)
    fieldnames = list(ElakiriCommentRecord.__annotations__.keys())
    write_header = not path.exists()

    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in rows_list:
            writer.writerow(row.__dict__)
    return len(rows_list)


def normalize_thread_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc and not parsed.netloc.endswith("elakiri.com"):
        return ""

    path = parsed.path.rstrip("/")
    if not path.startswith("/threads/"):
        return ""
    if path in {"/threads/latest", "/threads/newest", "/threads/trending"}:
        return ""
    if "/post-" in path:
        return ""

    path = re.sub(r"/latest$", "", path)
    path = re.sub(r"/page-\d+$", "", path)
    if not re.search(r"\.\d+$", path):
        return ""
    return "https://elakiri.com" + path + "/"


def build_listing_urls(
    *,
    start_url: str,
    listing_pages: int,
    listing_start_page: int,
    listing_end_page: int,
) -> list[str]:
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    if not base:
        base = start_url.split("?", 1)[0].rstrip("/")

    if listing_start_page > 0 and listing_end_page > 0:
        step = 1 if listing_end_page >= listing_start_page else -1
        page_numbers = list(range(listing_start_page, listing_end_page + step, step))
    else:
        page_numbers = list(range(1, listing_pages + 1))

    urls: list[str] = []
    seen: set[str] = set()
    for page in page_numbers:
        if page <= 1:
            url = base
        else:
            url = f"{base}?page={page}"
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def extract_thread_links_from_listing(html: str, base_url: str) -> list[str]:
    links = extract_links_from_html(html=html, base_url=base_url)
    output: list[str] = []
    seen: set[str] = set()
    for link in links:
        normalized = normalize_thread_url(link)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def extract_thread_title(html: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return clean_text(extract_text_from_html(match.group(1)))


def extract_thread_page_links(html: str, canonical_thread_url: str) -> list[str]:
    links = extract_links_from_html(html=html, base_url=canonical_thread_url)
    output: list[str] = []
    seen: set[str] = set()
    prefix = canonical_thread_url.rstrip("/")

    for link in links:
        parsed = urlparse(link)
        if parsed.netloc and not parsed.netloc.endswith("elakiri.com"):
            continue
        normalized = "https://elakiri.com" + parsed.path.rstrip("/") + "/"
        if not normalized.startswith(prefix + "/page-"):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)

    # When a thread is currently on its latest page, prefer the most recent
    # numbered pages first so low `max_thread_pages` values stay near the newest replies.
    output.sort(key=lambda item: int(re.search(r"/page-(\d+)/?$", item).group(1)), reverse=True)
    return output


def clean_comment_text(raw_text: str) -> str:
    cleaned = clean_text(raw_text)
    cleaned = re.sub(r"-+\s*Post added on.*$", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def parse_thread_posts(html: str) -> list[dict[str, str | bool]]:
    parser = ElakiriThreadParser()
    parser.feed(html)
    return parser.posts


def scrape_elakiri_comments(args: argparse.Namespace) -> None:
    output_csv = Path(args.output_csv)
    state_path = Path(args.state_path)
    log_path = Path(args.log_path)
    summary_path = Path(args.summary_path)

    logger = setup_logger(log_path)
    state = load_state(state_path)
    processed_threads = set(str(item).strip() for item in state.get("processed_threads", []))
    seen_post_ids = load_seen_post_ids(output_csv)

    logger.info("Starting Elakiri comments scrape.")
    logger.info("Output CSV: %s", output_csv)
    logger.info("State file: %s", state_path)
    logger.info("Log file: %s", log_path)
    logger.info("Summary file: %s", summary_path)
    logger.info("Existing rows: %s", len(seen_post_ids))
    logger.info("Already processed threads: %s", len(processed_threads))
    if args.target_total_rows > 0:
        logger.info("Target total rows: %s", args.target_total_rows)

    started_at = now_iso()
    total_new_comments = 0
    threads_seen = 0
    threads_processed = 0
    pages_fetched = 0
    pages_failed = 0
    posts_parsed = 0
    interrupted = False
    target_reached = args.target_total_rows > 0 and len(seen_post_ids) >= args.target_total_rows

    if target_reached:
        logger.info("Dataset already meets target total rows. Nothing to do.")

    listing_urls = build_listing_urls(
        start_url=args.start_url,
        listing_pages=args.listing_pages,
        listing_start_page=args.listing_start_page,
        listing_end_page=args.listing_end_page,
    )
    if args.listing_start_page > 0 and args.listing_end_page > 0:
        logger.info(
            "Listing range mode enabled. start_page=%s end_page=%s total_listing_pages=%s",
            args.listing_start_page,
            args.listing_end_page,
            len(listing_urls),
        )
    try:
        for page_index, listing_url in enumerate(listing_urls, start=1):
            if target_reached:
                break
            logger.info("Listing page %s/%s: %s", page_index, len(listing_urls), listing_url)
            try:
                listing_html = fetch_url_content(listing_url)
            except Exception as exc:
                logger.warning("Failed to fetch listing page: %s | %s", listing_url, exc)
                continue

            thread_urls = extract_thread_links_from_listing(listing_html, listing_url)
            new_thread_urls = [url for url in thread_urls if url not in processed_threads]
            threads_seen += len(thread_urls)
            logger.info(
                "Found %s thread URLs on listing page. %s remaining after resume filter.",
                len(thread_urls),
                len(new_thread_urls),
            )

            for thread_index, thread_url in enumerate(new_thread_urls, start=1):
                if target_reached:
                    break
                logger.info("Thread %s/%s: %s", thread_index, len(new_thread_urls), thread_url)

                page_queue = [thread_url.rstrip("/") + "/latest"]
                seen_pages: set[str] = set()
                page_html_map: dict[str, str] = {}

                while page_queue and len(page_html_map) < args.max_thread_pages:
                    page_url = page_queue.pop(0)
                    if page_url in seen_pages:
                        continue
                    seen_pages.add(page_url)

                    try:
                        thread_html = fetch_url_content(page_url)
                        pages_fetched += 1
                    except Exception as exc:
                        pages_failed += 1
                        logger.warning("Failed to fetch thread page: %s | %s", page_url, exc)
                        continue

                    page_html_map[page_url] = thread_html
                    for discovered_url in extract_thread_page_links(thread_html, thread_url):
                        if discovered_url not in seen_pages and discovered_url not in page_queue:
                            page_queue.append(discovered_url)

                thread_title = ""
                thread_records: list[ElakiriCommentRecord] = []

                for page_number, page_url in enumerate(page_html_map.keys(), start=1):
                    thread_html = page_html_map[page_url]
                    if not thread_title:
                        thread_title = extract_thread_title(thread_html)

                    parsed_posts = parse_thread_posts(thread_html)
                    posts_parsed += len(parsed_posts)
                    logger.info("Parsed %s posts from %s", len(parsed_posts), page_url)

                    for parsed_post in parsed_posts:
                        is_thread_starter = bool(parsed_post.get("is_thread_starter", False))
                        if is_thread_starter:
                            continue

                        post_id = str(parsed_post.get("post_id", "")).strip()
                        if not post_id or post_id in seen_post_ids:
                            continue

                        comment_text = clean_comment_text(str(parsed_post.get("raw_text", "")))
                        if not comment_text:
                            continue
                        if len(comment_text) < args.min_comment_chars or len(comment_text) > args.max_comment_chars:
                            continue

                        is_sinhala = is_likely_sinhala(comment_text, threshold=0.05)
                        if not args.include_non_sinhala and not is_sinhala:
                            continue

                        record = ElakiriCommentRecord(
                            source="elakiri",
                            thread_url=thread_url,
                            thread_title=thread_title,
                            page_url=page_url,
                            post_id=post_id,
                            post_url=f"{thread_url.rstrip('/')}/post-{post_id}",
                            author_name=str(parsed_post.get("author_name", "")).strip(),
                            author_url=str(parsed_post.get("author_url", "")).strip(),
                            published_at=str(parsed_post.get("published_at", "")).strip(),
                            text=comment_text,
                            clean_text=comment_text,
                            is_sinhala=is_sinhala,
                            extracted_at=now_iso(),
                        )
                        thread_records.append(record)
                        seen_post_ids.add(post_id)

                    if args.sleep_ms > 0:
                        time.sleep(args.sleep_ms / 1000.0)

                written = append_rows(output_csv, thread_records)
                total_new_comments += written
                threads_processed += 1
                if args.target_total_rows > 0 and len(seen_post_ids) >= args.target_total_rows:
                    target_reached = True
                logger.info("Thread complete: %s | new comments saved=%s | total saved this run=%s", thread_url, written, total_new_comments)
                if args.target_total_rows > 0:
                    logger.info("Dataset progress: %s/%s rows", len(seen_post_ids), args.target_total_rows)

                processed_threads.add(thread_url)
                state["processed_threads"] = sorted(processed_threads)
                state["last_completed_at"] = now_iso()
                save_state(state_path, state)

                if args.sleep_ms > 0:
                    time.sleep(args.sleep_ms / 1000.0)
    except KeyboardInterrupt:
        interrupted = True
        logger.warning("Scrape interrupted by user. Partial progress has been saved.")

    finished_at = now_iso()
    dataset_total_rows = len(load_seen_post_ids(output_csv))
    summary = ElakiriRunSummary(
        started_at=started_at,
        finished_at=finished_at,
        listing_pages_requested=len(listing_urls),
        max_thread_pages=args.max_thread_pages,
        threads_seen=threads_seen,
        threads_processed=threads_processed,
        threads_skipped_by_resume=max(threads_seen - threads_processed, 0),
        pages_fetched=pages_fetched,
        pages_failed=pages_failed,
        posts_parsed=posts_parsed,
        comments_saved=total_new_comments,
        dataset_path=str(output_csv),
        dataset_total_rows=dataset_total_rows,
        interrupted=interrupted,
        target_total_rows=args.target_total_rows,
        target_reached=target_reached,
    )
    save_summary(summary_path, summary)

    logger.info("Elakiri scrape finished. New comments saved this run: %s", total_new_comments)
    logger.info("Threads processed: %s | pages fetched: %s | posts parsed: %s", threads_processed, pages_fetched, posts_parsed)
    logger.info("Dataset total rows: %s", dataset_total_rows)
    if args.target_total_rows > 0:
        logger.info("Target reached: %s", target_reached)
    logger.info("Final dataset path: %s", output_csv)
    logger.info("Run summary path: %s", summary_path)


def main() -> None:
    scrape_elakiri_comments(parse_args())


if __name__ == "__main__":
    main()
