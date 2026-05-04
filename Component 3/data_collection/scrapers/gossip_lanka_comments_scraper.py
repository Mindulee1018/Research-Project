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
from urllib.parse import quote

from data_collection.html_extract import extract_links_from_html, extract_text_from_html
from data_collection.io_utils import ensure_dir
from data_collection.normalize import clean_text, is_likely_sinhala
from data_collection.sources.common import fetch_url_content


DEFAULT_PROJECT_ROOT = Path(os.environ.get("SL_SMA_PROJECT_ROOT", r"D:/client-projects/sl-social-media-risk-analysis"))
DEFAULT_DATASETS_ROOT = Path(os.environ.get("SL_SMA_DATASETS_ROOT", str(DEFAULT_PROJECT_ROOT / "datasets")))
DEFAULT_OUTPUT_CSV = DEFAULT_DATASETS_ROOT / "sources" / "gossip_lanka_comments.csv"
DEFAULT_STATE_PATH = DEFAULT_DATASETS_ROOT / "runtime" / "state" / "gossip_lanka_comments_state.json"
DEFAULT_LOG_PATH = DEFAULT_DATASETS_ROOT / "runtime" / "logs" / "gossip_lanka_comments.log"
DEFAULT_SUMMARY_PATH = DEFAULT_DATASETS_ROOT / "runtime" / "summaries" / "gossip_lanka_comments_summary.json"
DEFAULT_START_URLS = [
    "https://www.gossiplankanews.com/",
    "https://www.gossiplankanews.com/p/more-news.html",
]
ARTICLE_URL_RE = re.compile(r"^https://www\.gossiplankanews\.com/\d{4}/\d{2}/.+\.html$")


@dataclass
class GossipLankaCommentRecord:
    source: str
    article_url: str
    article_title: str
    comment_id: str
    comment_anchor_url: str
    author_name: str
    published_at: str
    vote_score: str
    text: str
    clean_text: str
    is_sinhala: bool
    extracted_at: str


@dataclass
class GossipLankaRunSummary:
    started_at: str
    finished_at: str
    article_pages_seen: int
    articles_processed: int
    articles_skipped_by_resume: int
    articles_with_comments: int
    pages_failed: int
    comments_saved: int
    dataset_path: str
    dataset_total_rows: int
    interrupted: bool
    target_total_rows: int
    target_reached: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Gossip Lanka article comments into one resumable CSV dataset.")
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--max-pages", type=int, default=250)
    parser.add_argument("--sleep-ms", type=int, default=250)
    parser.add_argument("--min-comment-chars", type=int, default=12)
    parser.add_argument("--max-comment-chars", type=int, default=2400)
    parser.add_argument("--target-total-rows", type=int, default=0)
    parser.add_argument("--date-from", default="", help="Start date for month archive mode (YYYY-MM or YYYY-MM-DD).")
    parser.add_argument("--date-to", default="", help="End date for month archive mode (YYYY-MM or YYYY-MM-DD).")
    parser.add_argument("--start-thread", type=int, default=0, help="Start numeric thread id for blog-post_<id>.html range mode.")
    parser.add_argument("--end-thread", type=int, default=0, help="End numeric thread id for blog-post_<id>.html range mode.")
    parser.add_argument(
        "--direct-thread-range",
        action="store_true",
        help="Use direct URL template expansion for start/end thread range. Default behavior filters discovered real article URLs.",
    )
    parser.add_argument(
        "--thread-url-template",
        default="https://www.gossiplankanews.com/2026/03/blog-post_{thread}.html",
        help="URL template used in range mode. Must include '{thread}' placeholder.",
    )
    parser.add_argument("--include-non-sinhala", action="store_true")
    parser.add_argument("--ignore-resume", action="store_true")
    return parser.parse_args()


def setup_logger(log_path: Path) -> logging.Logger:
    ensure_dir(log_path.parent)
    logger = logging.getLogger("gossip_lanka_comments_scraper")
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
        return {"processed_articles": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def save_summary(path: Path, summary: GossipLankaRunSummary) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(summary.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")


def load_seen_comment_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return {str(row.get("comment_id", "")).strip() for row in reader if str(row.get("comment_id", "")).strip()}


def append_rows(path: Path, rows: Iterable[GossipLankaCommentRecord]) -> int:
    rows_list = list(rows)
    if not rows_list:
        return 0

    ensure_dir(path.parent)
    fieldnames = list(GossipLankaCommentRecord.__annotations__.keys())
    write_header = not path.exists()

    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in rows_list:
            writer.writerow(row.__dict__)
    return len(rows_list)


def normalize_article_url(url: str) -> str:
    cleaned = str(url).strip()
    if not cleaned:
        return ""
    cleaned = cleaned.split("#", 1)[0]
    if cleaned.endswith("/"):
        cleaned = cleaned[:-1]
    if not ARTICLE_URL_RE.match(cleaned):
        return ""
    if re.search(r"/(contact-us|about|privacy|terms)\.html$", cleaned):
        return ""
    return cleaned


def extract_article_links(html: str, base_url: str) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for link in extract_links_from_html(html=html, base_url=base_url):
        normalized = normalize_article_url(link)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def append_new_article_links(
    *,
    source_html: str,
    base_url: str,
    article_queue: list[str],
    queued_articles: set[str],
) -> int:
    added = 0
    for article_url in extract_article_links(source_html, base_url):
        if article_url in queued_articles:
            continue
        queued_articles.add(article_url)
        article_queue.append(article_url)
        added += 1
    return added


def extract_comment_bootstrap(article_html: str) -> tuple[str, str, str, str] | None:
    acct_match = re.search(r"var\s+idcomments_acct\s*=\s*'([^']+)'", article_html)
    post_id_match = re.search(r"var\s+idcomments_post_id\s*=\s*'([^']+)'", article_html)
    post_url_match = re.search(r"var\s+idcomments_post_url\s*=\s*'([^']+)'", article_html)
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", article_html, flags=re.IGNORECASE | re.DOTALL)

    if not acct_match or not post_id_match or not post_url_match:
        return None

    title = clean_text(extract_text_from_html(title_match.group(1))) if title_match else ""
    return (
        acct_match.group(1).strip(),
        post_id_match.group(1).strip(),
        title,
        post_url_match.group(1).strip(),
    )


def build_wrapper_url(*, acct: str, post_id: str, title: str, post_url: str) -> str:
    return (
        "https://intensedebate.com/js/genericCommentWrapper2.php"
        f"?acct={quote(acct, safe='')}"
        f"&postid={quote(post_id, safe='')}"
        f"&title={quote(title, safe='')}"
        f"&url={quote(post_url, safe='')}"
    )


def extract_generic_comment_script_url(wrapper_js: str) -> str:
    match = re.search(r'IDCommentScript\.src\s*=\s*"([^"]+)"', wrapper_js)
    if not match:
        return ""
    return match.group(1).strip()


def parse_gossip_comments(generic_comment_js: str) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    pattern = re.compile(
        r'<div id=\\"IDComment(?P<comment_id>\d+)\\".*?'
        r'<span class=\\"idc-v-total\\"[^>]*>(?P<vote_score>[^<]*)</span>.*?'
        r'<p class=\\"idc-i\\">.*?<span>\s*(?P<author_name>.*?)\s*</span>.*?'
        r'<a[^>]+id=\\"IDCommentTime(?P<time_id>\d+)\\"[^>]*>(?P<published_at>.*?)</a>.*?'
        r'<div id=\\"IDComment-CommentText(?P<text_id>\d+)\\"[^>]*>(?P<comment_html>.*?)</div>',
        flags=re.DOTALL,
    )

    for match in pattern.finditer(generic_comment_js):
        comment_id = match.group("comment_id").strip()
        if comment_id != match.group("time_id").strip() or comment_id != match.group("text_id").strip():
            continue

        author_name = clean_text(match.group("author_name"))
        published_at = clean_text(match.group("published_at"))
        vote_score = clean_text(match.group("vote_score"))
        comment_html = match.group("comment_html")
        comment_text = clean_text(extract_text_from_html(comment_html))

        comments.append(
            {
                "comment_id": comment_id,
                "author_name": author_name,
                "published_at": published_at,
                "vote_score": vote_score,
                "text": comment_text,
            }
        )

    return comments


def discover_article_urls(*, max_pages: int, sleep_ms: int, logger: logging.Logger) -> list[str]:
    queue = list(DEFAULT_START_URLS)
    visited: set[str] = set()
    article_urls: list[str] = []
    seen_articles: set[str] = set()

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            html = fetch_url_content(url)
        except Exception as exc:
            logger.warning("Failed to fetch listing page: %s | %s", url, exc)
            continue

        for article_url in extract_article_links(html, url):
            if article_url in seen_articles:
                continue
            seen_articles.add(article_url)
            article_urls.append(article_url)

        for link in extract_links_from_html(html=html, base_url=url):
            if "gossiplankanews.com" not in link:
                continue
            if "/search/label/" in link or link.endswith("/p/more-news.html") or link == DEFAULT_START_URLS[0]:
                if link not in visited and link not in queue:
                    queue.append(link)

        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)

    return article_urls


def parse_year_month(value: str) -> tuple[int, int]:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Date value is empty.")
    for fmt in ("%Y-%m", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.year, parsed.month
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {value}. Use YYYY-MM or YYYY-MM-DD.")


def month_range(date_from: str, date_to: str) -> list[tuple[int, int]]:
    start_y, start_m = parse_year_month(date_from)
    end_y, end_m = parse_year_month(date_to)
    start = start_y * 12 + start_m
    end = end_y * 12 + end_m
    if start > end:
        start, end = end, start

    output: list[tuple[int, int]] = []
    for value in range(start, end + 1):
        year = (value - 1) // 12
        month = (value - 1) % 12 + 1
        output.append((year, month))
    return output


def build_month_archive_url(year: int, month: int) -> str:
    return f"https://www.gossiplankanews.com/{year:04d}/{month:02d}"


def discover_article_urls_by_months(
    *,
    months: list[tuple[int, int]],
    sleep_ms: int,
    logger: logging.Logger,
) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for year, month in months:
        archive_url = build_month_archive_url(year, month)
        logger.info("Archive month page: %s", archive_url)
        try:
            html = fetch_url_content(archive_url)
        except Exception as exc:
            logger.warning("Failed to fetch archive month page: %s | %s", archive_url, exc)
            continue

        for article_url in extract_article_links(html, archive_url):
            if article_url in seen:
                continue
            seen.add(article_url)
            output.append(article_url)

        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)

    return output


def extract_article_year_month(url: str) -> tuple[int, int] | None:
    match = re.search(r"/(\d{4})/(\d{2})/", str(url).strip())
    if not match:
        return None
    try:
        return int(match.group(1)), int(match.group(2))
    except ValueError:
        return None


def filter_article_urls_by_months(
    *,
    article_urls: list[str],
    months: list[tuple[int, int]],
) -> list[str]:
    month_set = set(months)
    output: list[str] = []
    seen: set[str] = set()
    for url in article_urls:
        ym = extract_article_year_month(url)
        if ym is None or ym not in month_set:
            continue
        if url in seen:
            continue
        seen.add(url)
        output.append(url)
    return output


def build_range_article_urls(
    *,
    start_thread: int,
    end_thread: int,
    template: str,
) -> list[str]:
    template_value = str(template or "").strip()
    if "{thread}" not in template_value:
        raise ValueError("thread_url_template must include '{thread}' placeholder.")
    if start_thread <= 0 or end_thread <= 0:
        return []

    step = 1 if end_thread >= start_thread else -1
    output: list[str] = []
    for thread_id in range(start_thread, end_thread + step, step):
        url = template_value.format(thread=thread_id)
        normalized = normalize_article_url(url)
        if normalized:
            output.append(normalized)
    return output


def extract_blog_post_id(url: str) -> int | None:
    match = re.search(r"/blog-post_(\d+)\.html$", str(url).strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def filter_discovered_by_thread_range(
    *,
    article_urls: list[str],
    start_thread: int,
    end_thread: int,
) -> list[str]:
    if start_thread <= 0 or end_thread <= 0:
        return article_urls
    low = min(start_thread, end_thread)
    high = max(start_thread, end_thread)
    output: list[str] = []
    seen: set[str] = set()
    for url in article_urls:
        post_id = extract_blog_post_id(url)
        if post_id is None:
            continue
        if post_id < low or post_id > high:
            continue
        if url in seen:
            continue
        seen.add(url)
        output.append(url)
    return output


def scrape_gossip_lanka_comments(args: argparse.Namespace) -> None:
    output_csv = Path(args.output_csv)
    state_path = Path(args.state_path)
    log_path = Path(args.log_path)
    summary_path = Path(args.summary_path)

    logger = setup_logger(log_path)
    state = load_state(state_path)
    processed_articles = set(str(item).strip() for item in state.get("processed_articles", []))
    seen_comment_ids = load_seen_comment_ids(output_csv)

    logger.info("Starting Gossip Lanka comments scrape.")
    logger.info("Output CSV: %s", output_csv)
    logger.info("State file: %s", state_path)
    logger.info("Log file: %s", log_path)
    logger.info("Summary file: %s", summary_path)
    logger.info("Existing rows: %s", len(seen_comment_ids))
    logger.info("Already processed articles: %s", len(processed_articles))
    if args.ignore_resume:
        logger.info("Ignore resume: enabled (will reprocess previously completed article URLs).")
    if args.target_total_rows > 0:
        logger.info("Target total rows: %s", args.target_total_rows)

    started_at = now_iso()
    article_pages_seen = 0
    articles_processed = 0
    articles_with_comments = 0
    pages_failed = 0
    total_new_comments = 0
    interrupted = False
    target_reached = args.target_total_rows > 0 and len(seen_comment_ids) >= args.target_total_rows

    if target_reached:
        logger.info("Dataset already meets target total rows. Nothing to do.")

    try:
        if args.date_from and args.date_to:
            months = month_range(args.date_from, args.date_to)
            logger.info(
                "Date range mode enabled. date_from=%s date_to=%s months=%s",
                args.date_from,
                args.date_to,
                len(months),
            )
            article_urls = discover_article_urls_by_months(
                months=months,
                sleep_ms=args.sleep_ms,
                logger=logger,
            )
            before = len(article_urls)
            article_urls = filter_article_urls_by_months(article_urls=article_urls, months=months)
            logger.info("Date range filtering complete. URLs before=%s after=%s", before, len(article_urls))
        elif args.start_thread > 0 and args.end_thread > 0 and args.direct_thread_range:
            article_urls = build_range_article_urls(
                start_thread=args.start_thread,
                end_thread=args.end_thread,
                template=args.thread_url_template,
            )
            logger.info(
                "Direct range mode enabled. start_thread=%s end_thread=%s template=%s | URLs=%s",
                args.start_thread,
                args.end_thread,
                args.thread_url_template,
                len(article_urls),
            )
        else:
            article_urls = discover_article_urls(max_pages=args.max_pages, sleep_ms=args.sleep_ms, logger=logger)
            if args.start_thread > 0 and args.end_thread > 0:
                before = len(article_urls)
                article_urls = filter_discovered_by_thread_range(
                    article_urls=article_urls,
                    start_thread=args.start_thread,
                    end_thread=args.end_thread,
                )
                logger.info(
                    "Discovery range mode enabled. start_thread=%s end_thread=%s | URLs before filter=%s after=%s",
                    args.start_thread,
                    args.end_thread,
                    before,
                    len(article_urls),
                )
        article_queue = list(article_urls)
        queued_articles = set(article_queue)
        logger.info("Discovered %s seed article URLs.", len(article_urls))

        index = 0
        while index < len(article_queue):
            article_url = article_queue[index]
            index += 1
            article_pages_seen = len(article_queue)
            if target_reached:
                break
            if not args.ignore_resume and article_url in processed_articles:
                continue

            logger.info("Article %s/%s: %s", index, len(article_queue), article_url)
            try:
                article_html = fetch_url_content(article_url)
            except Exception as exc:
                pages_failed += 1
                logger.warning("Failed to fetch article page: %s | %s", article_url, exc)
                continue

            if not (args.start_thread > 0 and args.end_thread > 0):
                added_links = append_new_article_links(
                    source_html=article_html,
                    base_url=article_url,
                    article_queue=article_queue,
                    queued_articles=queued_articles,
                )
                if added_links > 0:
                    logger.info("Discovered %s additional article links from article page.", added_links)

            bootstrap = extract_comment_bootstrap(article_html)
            if not bootstrap:
                logger.info("No comment bootstrap found on article: %s", article_url)
                processed_articles.add(article_url)
                state["processed_articles"] = sorted(processed_articles)
                state["last_completed_at"] = now_iso()
                save_state(state_path, state)
                continue

            acct, post_id, article_title, post_url = bootstrap
            wrapper_url = build_wrapper_url(acct=acct, post_id=post_id, title=article_title, post_url=post_url)

            try:
                wrapper_js = fetch_url_content(wrapper_url)
                generic_comment_url = extract_generic_comment_script_url(wrapper_js)
                if not generic_comment_url:
                    logger.info("No generic comment script URL found for article: %s", article_url)
                    processed_articles.add(article_url)
                    state["processed_articles"] = sorted(processed_articles)
                    state["last_completed_at"] = now_iso()
                    save_state(state_path, state)
                    continue

                generic_comment_js = fetch_url_content(generic_comment_url)
            except Exception as exc:
                pages_failed += 1
                logger.warning("Failed to fetch comment payload for article: %s | %s", article_url, exc)
                continue

            parsed_comments = parse_gossip_comments(generic_comment_js)
            logger.info("Parsed %s comments from %s", len(parsed_comments), article_url)

            article_records: list[GossipLankaCommentRecord] = []
            for parsed_comment in parsed_comments:
                comment_id = parsed_comment["comment_id"]
                if not comment_id or comment_id in seen_comment_ids:
                    continue

                comment_text = parsed_comment["text"]
                if not comment_text:
                    continue
                if len(comment_text) < args.min_comment_chars or len(comment_text) > args.max_comment_chars:
                    continue

                is_sinhala = is_likely_sinhala(comment_text, threshold=0.05)
                if not args.include_non_sinhala and not is_sinhala:
                    continue

                article_records.append(
                    GossipLankaCommentRecord(
                        source="gossip_lanka",
                        article_url=article_url,
                        article_title=article_title,
                        comment_id=comment_id,
                        comment_anchor_url=f"{article_url}#IDComment{comment_id}",
                        author_name=parsed_comment["author_name"],
                        published_at=parsed_comment["published_at"],
                        vote_score=parsed_comment["vote_score"],
                        text=comment_text,
                        clean_text=comment_text,
                        is_sinhala=is_sinhala,
                        extracted_at=now_iso(),
                    )
                )
                seen_comment_ids.add(comment_id)

            written = append_rows(output_csv, article_records)
            total_new_comments += written
            articles_processed += 1
            if written > 0:
                articles_with_comments += 1
            if args.target_total_rows > 0 and len(seen_comment_ids) >= args.target_total_rows:
                target_reached = True
            logger.info("Article complete: %s | new comments saved=%s | total saved this run=%s", article_url, written, total_new_comments)
            if args.target_total_rows > 0:
                logger.info("Dataset progress: %s/%s rows", len(seen_comment_ids), args.target_total_rows)

            processed_articles.add(article_url)
            state["processed_articles"] = sorted(processed_articles)
            state["last_completed_at"] = now_iso()
            save_state(state_path, state)

            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)
    except KeyboardInterrupt:
        interrupted = True
        logger.warning("Scrape interrupted by user. Partial progress has been saved.")

    finished_at = now_iso()
    dataset_total_rows = len(load_seen_comment_ids(output_csv))
    summary = GossipLankaRunSummary(
        started_at=started_at,
        finished_at=finished_at,
        article_pages_seen=article_pages_seen,
        articles_processed=articles_processed,
        articles_skipped_by_resume=max(article_pages_seen - articles_processed, 0),
        articles_with_comments=articles_with_comments,
        pages_failed=pages_failed,
        comments_saved=total_new_comments,
        dataset_path=str(output_csv),
        dataset_total_rows=dataset_total_rows,
        interrupted=interrupted,
        target_total_rows=args.target_total_rows,
        target_reached=target_reached,
    )
    save_summary(summary_path, summary)

    logger.info("Gossip Lanka scrape finished. New comments saved this run: %s", total_new_comments)
    logger.info("Articles processed: %s | articles with comments: %s | failures: %s", articles_processed, articles_with_comments, pages_failed)
    logger.info("Dataset total rows: %s", dataset_total_rows)
    if args.target_total_rows > 0:
        logger.info("Target reached: %s", target_reached)
    logger.info("Final dataset path: %s", output_csv)
    logger.info("Run summary path: %s", summary_path)


def main() -> None:
    scrape_gossip_lanka_comments(parse_args())


if __name__ == "__main__":
    main()
