from pathlib import Path
from typing import Dict, List

from data_collection.html_extract import (
    extract_comment_candidates_from_html,
    extract_text_blocks_from_html,
    extract_text_from_html,
)
from data_collection.models import SourceRecord
from data_collection.normalize import is_likely_sinhala
from data_collection.sources.base import SourceAdapter
from data_collection.sources.common import (
    crawl_pages,
    fetch_url_content,
    load_csv_rows,
    load_json_rows,
    load_urls,
    resolve_source_item,
    resolve_text,
)


class GossipLankaAdapter(SourceAdapter):
    source_name = "gossip_lanka"

    def load(self, config: Dict[str, str]) -> List[SourceRecord]:
        base_dir = Path(config.get("base_dir") or ".").resolve()
        urls = load_urls(config=config, base_dir=base_dir)
        if urls:
            crawl_enabled = bool(config.get("crawl", False))
            if crawl_enabled:
                max_pages = int(config.get("max_pages", 40))
                max_blocks_per_page = int(config.get("max_blocks_per_page", 15))
                sinhala_threshold = float(config.get("sinhala_threshold", 0.2))
                allow_non_sinhala_fallback = bool(config.get("allow_non_sinhala_fallback", False))
                fallback_blocks_per_page = int(config.get("fallback_blocks_per_page", 3))
                prefer_comments = bool(config.get("prefer_comments", True))
                comment_only = bool(config.get("comment_only", False))
                include_regex = str(config.get("include_url_regex", "")).strip()
                domains = config.get("allowed_domains", ["gossiplankanews.com"])
                if isinstance(domains, str):
                    domains = [domains]
                pages = crawl_pages(
                    start_urls=urls,
                    max_pages=max_pages,
                    allowed_domains=[str(item) for item in domains],
                    include_url_regex=include_regex,
                    sleep_ms=int(config.get("sleep_ms", 250)),
                )
                records: List[SourceRecord] = []
                for page in pages:
                    html = page.get("html", "")
                    comments = extract_comment_candidates_from_html(
                        html,
                        min_chars=int(config.get("min_comment_chars", 20)),
                        max_chars=int(config.get("max_comment_chars", 800)),
                        keywords=config.get(
                            "comment_keywords",
                            ["comment", "comments", "reply", "replies", "disqus"],
                        ),
                    )

                    page_added = 0
                    if comments and prefer_comments:
                        for idx, comment in enumerate(comments[:max_blocks_per_page], start=1):
                            if not is_likely_sinhala(comment, threshold=sinhala_threshold):
                                continue
                            records.append(
                                SourceRecord(
                                    source_item_id_or_url=f"{page['url']}#c{idx}",
                                    raw_text=comment,
                                    metadata={"mode": "url_crawl_comment"},
                                )
                            )
                            page_added += 1

                    if page_added > 0:
                        continue
                    if comment_only:
                        continue

                    blocks = extract_text_blocks_from_html(
                        html,
                        min_chars=int(config.get("min_block_chars", 40)),
                        max_chars=int(config.get("max_block_chars", 500)),
                    )
                    if not blocks:
                        blocks = [page.get("text", "")]

                    for idx, block in enumerate(blocks[:max_blocks_per_page], start=1):
                        if not is_likely_sinhala(block, threshold=sinhala_threshold):
                            continue
                        records.append(
                            SourceRecord(
                                source_item_id_or_url=f"{page['url']}#b{idx}",
                                raw_text=block,
                                metadata={"mode": "url_crawl_block"},
                            )
                        )
                        page_added += 1

                    if page_added == 0 and allow_non_sinhala_fallback:
                        for idx, block in enumerate(blocks[:fallback_blocks_per_page], start=1):
                            records.append(
                                SourceRecord(
                                    source_item_id_or_url=f"{page['url']}#fb{idx}",
                                    raw_text=block,
                                    metadata={"mode": "url_crawl_block_fallback_non_sinhala"},
                                )
                            )
                return records

            records: List[SourceRecord] = []
            for idx, url in enumerate(urls, start=1):
                try:
                    html = fetch_url_content(url)
                except Exception as exc:  # pragma: no cover - network variability
                    records.append(
                        SourceRecord(
                            source_item_id_or_url=url,
                            raw_text="",
                            metadata={"fetch_error": str(exc)},
                        )
                    )
                    continue

                text = extract_text_from_html(html)
                records.append(
                    SourceRecord(
                        source_item_id_or_url=url or f"gossip_lanka_url_{idx}",
                        raw_text=text,
                        metadata={"mode": "url_fetch_page_text"},
                    )
                )
            return records

        input_csv = str(config.get("input_csv", "")).strip()
        input_json = str(config.get("input_json", "")).strip()

        if not input_csv and not input_json:
            raise ValueError(
                "Gossip Lanka adapter requires URL mode ('urls'/'urls_file') "
                "or 'input_csv'/'input_json' in config."
            )

        if input_csv:
            rows = load_csv_rows(Path(input_csv))
        else:
            rows = load_json_rows(Path(input_json))

        records: List[SourceRecord] = []
        for idx, row in enumerate(rows, start=1):
            text = resolve_text(row, base_dir=base_dir)
            if not text:
                continue

            source_item = resolve_source_item(row, fallback_prefix="gossip_lanka_item", index=idx)
            published_at = str(row.get("published_at", "")).strip()
            author_id = str(row.get("author_id", "")).strip()
            title = str(row.get("title", "")).strip()

            metadata = {"title": title}
            records.append(
                SourceRecord(
                    source_item_id_or_url=source_item,
                    raw_text=text,
                    published_at=published_at,
                    author_id=author_id,
                    metadata=metadata,
                )
            )

        return records
