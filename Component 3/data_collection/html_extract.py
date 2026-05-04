from html.parser import HTMLParser
import html
import json
import re
from urllib.parse import urljoin, urlparse


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ARG002
        if tag.lower() in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self._chunks)


def extract_text_from_html(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html or "")
    return parser.get_text().strip()


class _LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self._base_url = base_url
        self._links: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                full = urljoin(self._base_url, value)
                parsed = urlparse(full)
                if parsed.scheme in {"http", "https"}:
                    self._links.append(full)

    def links(self) -> list[str]:
        # Keep order and drop duplicates.
        seen: set[str] = set()
        output: list[str] = []
        for link in self._links:
            if link in seen:
                continue
            seen.add(link)
            output.append(link)
        return output


def extract_links_from_html(html: str, base_url: str) -> list[str]:
    parser = _LinkExtractor(base_url=base_url)
    parser.feed(html or "")
    return parser.links()


class _BlockExtractor(HTMLParser):
    BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "blockquote"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._active_tag_stack: list[str] = []
        self._current: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ARG002
        lower = tag.lower()
        if lower in {"script", "style"}:
            self._skip_depth += 1
            return
        if lower in self.BLOCK_TAGS:
            self._active_tag_stack.append(lower)
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if lower in self.BLOCK_TAGS and self._active_tag_stack:
            text = " ".join(self._current).strip()
            if text:
                self._chunks.append(text)
            self._active_tag_stack.pop()
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if not self._active_tag_stack:
            return
        chunk = data.strip()
        if chunk:
            self._current.append(chunk)

    def blocks(self) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for block in self._chunks:
            key = " ".join(block.split())
            if key in seen:
                continue
            seen.add(key)
            output.append(key)
        return output


def extract_text_blocks_from_html(
    html: str,
    *,
    min_chars: int = 40,
    max_chars: int = 600,
) -> list[str]:
    parser = _BlockExtractor()
    parser.feed(html or "")
    output: list[str] = []
    for block in parser.blocks():
        cleaned = " ".join(block.split()).strip()
        if len(cleaned) < min_chars:
            continue
        if len(cleaned) > max_chars:
            continue
        output.append(cleaned)
    return output


class _CommentCandidateExtractor(HTMLParser):
    def __init__(self, keywords: list[str], min_chars: int, max_chars: int) -> None:
        super().__init__()
        self._keywords = tuple(item.lower() for item in keywords if item)
        self._min_chars = min_chars
        self._max_chars = max_chars
        self._skip_depth = 0
        self._tag_stack: list[bool] = []
        self._capture_buffers: list[list[str]] = []
        self._candidates: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        lower = tag.lower()
        if lower in {"script", "style"}:
            self._skip_depth += 1
            return

        attr_values: list[str] = []
        for key, value in attrs:
            if key.lower() in {"class", "id"} and value:
                attr_values.append(str(value).lower())
        joined = " ".join(attr_values)
        matched = any(keyword in joined for keyword in self._keywords)
        self._tag_stack.append(matched)
        if matched:
            self._capture_buffers.append([])

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return

        if not self._tag_stack:
            return

        matched = self._tag_stack.pop()
        if not matched:
            return

        if not self._capture_buffers:
            return

        candidate = " ".join(" ".join(self._capture_buffers.pop()).split()).strip()
        if self._min_chars <= len(candidate) <= self._max_chars:
            self._candidates.append(candidate)

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0 or not self._capture_buffers:
            return
        chunk = data.strip()
        if chunk:
            for buffer in self._capture_buffers:
                buffer.append(chunk)

    def candidates(self) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for candidate in self._candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            output.append(candidate)
        return output


def extract_comment_candidates_from_html(
    html_text: str,
    *,
    min_chars: int = 20,
    max_chars: int = 800,
    keywords: list[str] | None = None,
) -> list[str]:
    kw = keywords or ["comment", "reply", "message", "post", "usercontent", "bbwrapper", "thread"]
    raw_candidates: list[str] = []
    parser = _CommentCandidateExtractor(
        keywords=kw,
        min_chars=min_chars,
        max_chars=max_chars,
    )
    parser.feed(html_text or "")
    raw_candidates.extend(parser.candidates())

    # JSON-like comment payload fallback (commonly in scripts).
    json_like = re.findall(r'"comment(?:Text|Body|Content)"\s*:\s*"([^"]+)"', html_text or "", flags=re.IGNORECASE)
    for item in json_like:
        candidate = html.unescape(item)
        candidate = candidate.replace("\\n", " ").replace("\\t", " ")
        try:
            # If quoted escapes remain, normalize them.
            candidate = json.loads(f'"{candidate}"')
        except Exception:
            pass
        candidate = " ".join(str(candidate).split()).strip()
        if not candidate:
            continue
        if len(candidate) < min_chars or len(candidate) > max_chars:
            continue
        raw_candidates.append(candidate)

    seen: set[str] = set()
    output: list[str] = []
    for candidate in raw_candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        output.append(candidate)
    return output
