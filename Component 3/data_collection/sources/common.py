import csv
import json
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from data_collection.html_extract import extract_links_from_html, extract_text_from_html


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader]


def load_json_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError(f"JSON input must be a list of records: {path}")
    return [dict(item) for item in payload]


def resolve_text(record: Dict[str, str], base_dir: Path) -> str:
    direct_text = str(record.get("text", "")).strip()
    if direct_text:
        return direct_text

    inline_html = str(record.get("html", "")).strip()
    if inline_html:
        return extract_text_from_html(inline_html)

    html_path = str(record.get("html_path", "")).strip()
    if html_path:
        full_path = Path(html_path)
        if not full_path.is_absolute():
            full_path = base_dir / full_path
        html_content = full_path.read_text(encoding="utf-8")
        return extract_text_from_html(html_content)

    return ""


def resolve_source_item(record: Dict[str, str], fallback_prefix: str, index: int) -> str:
    for key in ("url", "source_item_id_or_url", "item_id", "id"):
        value = str(record.get(key, "")).strip()
        if value:
            return value
    return f"{fallback_prefix}_{index}"


def load_urls(config: Dict[str, str], base_dir: Path) -> List[str]:
    urls = config.get("urls", [])
    if isinstance(urls, str):
        urls = [urls]

    urls_file = str(config.get("urls_file", "")).strip()
    if urls_file:
        file_path = Path(urls_file)
        if not file_path.is_absolute():
            file_path = base_dir / file_path
        for line in file_path.read_text(encoding="utf-8").splitlines():
            item = line.strip()
            if item and not item.startswith("#"):
                urls.append(item)

    resolved: List[str] = []
    for url in urls:
        item = str(url).strip()
        if item:
            resolved.append(item)
    return resolved


def fetch_url_content(url: str, timeout_sec: int = 25) -> str:
    request = Request(
        url=url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout_sec) as response:
        content_type = response.headers.get("Content-Type", "")
        raw = response.read()
        encoding = "utf-8"
        if "charset=" in content_type:
            encoding = content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        return raw.decode(encoding, errors="ignore")


def fetch_json(url: str, timeout_sec: int = 25) -> dict:
    content = fetch_url_content(url=url, timeout_sec=timeout_sec)
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object response.")
    return payload


def get_env_or_config(config: Dict[str, str], key: str, env_key: str) -> str:
    value = str(config.get(key, "")).strip()
    if value:
        return value
    return str(os.environ.get(env_key, "")).strip()


def load_values(
    config: Dict[str, str],
    *,
    field: str,
    file_field: str,
    base_dir: Path,
) -> List[str]:
    values = config.get(field, [])
    if isinstance(values, str):
        values = [values]

    path_value = str(config.get(file_field, "")).strip()
    if path_value:
        file_path = Path(path_value)
        if not file_path.is_absolute():
            file_path = base_dir / file_path
        for line in file_path.read_text(encoding="utf-8").splitlines():
            item = line.strip()
            if item and not item.startswith("#"):
                values.append(item)

    output: List[str] = []
    for item in values:
        value = str(item).strip()
        if value:
            output.append(value)
    return output


def parse_youtube_video_id(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if "/" not in text and len(text) >= 6:
        return text

    parsed = urlparse(text)
    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.strip("/")
    query = parse_qs(parsed.query)
    if "v" in query and query["v"]:
        return query["v"][0]
    return ""


def crawl_pages(
    *,
    start_urls: List[str],
    max_pages: int,
    allowed_domains: List[str] | None = None,
    include_url_regex: str = "",
    sleep_ms: int = 250,
) -> List[Dict[str, str]]:
    if max_pages <= 0:
        return []

    compiled = re.compile(include_url_regex) if include_url_regex else None
    allowed = {item.lower().strip() for item in (allowed_domains or []) if item.strip()}

    queue: deque[str] = deque()
    for url in start_urls:
        if url:
            queue.append(url)

    visited: set[str] = set()
    pages: List[Dict[str, str]] = []

    while queue and len(pages) < max_pages:
        url = queue.popleft().strip()
        if not url or url in visited:
            continue
        visited.add(url)

        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if allowed and not any(host.endswith(domain) for domain in allowed):
            continue
        if compiled and not compiled.search(url):
            continue

        try:
            html = fetch_url_content(url)
        except Exception:
            continue

        text = extract_text_from_html(html)
        if text:
            pages.append({"url": url, "text": text, "html": html})

        for link in extract_links_from_html(html=html, base_url=url):
            if link in visited:
                continue
            queue.append(link)

        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)

    return pages
