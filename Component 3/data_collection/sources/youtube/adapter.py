from pathlib import Path
from typing import Dict, List
from urllib.parse import urlencode

from data_collection.html_extract import extract_text_from_html
from data_collection.models import SourceRecord
from data_collection.sources.base import SourceAdapter
from data_collection.sources.common import (
    fetch_json,
    fetch_url_content,
    get_env_or_config,
    load_csv_rows,
    load_urls,
    load_values,
    parse_youtube_video_id,
)


class YouTubeAdapter(SourceAdapter):
    source_name = "youtube"

    def load(self, config: Dict[str, str]) -> List[SourceRecord]:
        base_dir = Path(config.get("base_dir") or ".").resolve()

        # Preferred mode: YouTube Data API comment collection.
        api_key = get_env_or_config(config, key="api_key", env_key="YOUTUBE_API_KEY")
        video_values = load_values(
            config=config,
            field="video_ids",
            file_field="video_ids_file",
            base_dir=base_dir,
        )
        video_ids = [parse_youtube_video_id(value) for value in video_values]
        video_ids = [item for item in video_ids if item]
        if api_key and video_ids:
            max_comments_per_video = int(config.get("max_comments_per_video", 200))
            records: List[SourceRecord] = []
            for video_id in video_ids:
                records.extend(
                    self._load_video_comments(
                        api_key=api_key,
                        video_id=video_id,
                        max_comments=max_comments_per_video,
                    )
                )
            if records:
                return records

        urls = load_urls(config=config, base_dir=base_dir)
        if urls:
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
                        source_item_id_or_url=url or f"youtube_url_{idx}",
                        raw_text=text,
                        metadata={"mode": "url_fetch_page_text"},
                    )
                )
            return records

        input_csv = str(config.get("input_csv", "")).strip()
        if not input_csv:
            raise ValueError(
                "YouTube adapter requires API mode ('api_key' + 'video_ids') "
                "or URL mode ('urls'/'urls_file') or 'input_csv' in config."
            )

        csv_path = Path(input_csv)
        if not csv_path.exists():
            raise FileNotFoundError(f"YouTube CSV not found: {csv_path}")

        rows = load_csv_rows(csv_path)
        records: List[SourceRecord] = []

        for idx, row in enumerate(rows, start=1):
            text = str(row.get("text", "")).strip()
            if not text:
                continue

            source_item = (
                str(row.get("url", "")).strip()
                or str(row.get("comment_id", "")).strip()
                or str(row.get("video_id", "")).strip()
                or f"youtube_row_{idx}"
            )
            published_at = str(row.get("published_at", "")).strip()
            author_id = str(row.get("author_id", "")).strip()

            metadata = {
                "video_id": str(row.get("video_id", "")).strip(),
                "comment_id": str(row.get("comment_id", "")).strip(),
            }

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

    @staticmethod
    def _load_video_comments(api_key: str, video_id: str, max_comments: int) -> List[SourceRecord]:
        records: List[SourceRecord] = []
        page_token = ""
        page_size = 100

        while len(records) < max_comments:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": str(min(page_size, max_comments - len(records))),
                "textFormat": "plainText",
                "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            url = "https://www.googleapis.com/youtube/v3/commentThreads?" + urlencode(params)
            payload = fetch_json(url)
            items = payload.get("items", [])
            if not isinstance(items, list) or not items:
                break

            for item in items:
                snippet = (
                    item.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet", {})
                )
                text = str(snippet.get("textDisplay", "")).strip()
                if not text:
                    continue

                comment_id = (
                    str(item.get("snippet", {}).get("topLevelComment", {}).get("id", "")).strip()
                    or f"{video_id}_{len(records) + 1}"
                )
                published_at = str(snippet.get("publishedAt", "")).strip()
                author_id = str(snippet.get("authorChannelId", {}).get("value", "")).strip()
                source_item = f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"

                records.append(
                    SourceRecord(
                        source_item_id_or_url=source_item,
                        raw_text=text,
                        published_at=published_at,
                        author_id=author_id,
                        metadata={
                            "mode": "youtube_api_comment",
                            "video_id": video_id,
                            "comment_id": comment_id,
                        },
                    )
                )
                if len(records) >= max_comments:
                    break

            page_token = str(payload.get("nextPageToken", "")).strip()
            if not page_token:
                break

        return records
