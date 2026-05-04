import re


SINHALA_BLOCK_MIN = ord("\u0D80")
SINHALA_BLOCK_MAX = ord("\u0DFF")


def clean_text(text: str) -> str:
    cleaned = (text or "").replace("\u200d", "")
    cleaned = re.sub(r"\bClick to expand\.\.\.", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*[^:\n]{1,80}\s+said:\s*", " ", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split()).strip()
    return cleaned


def strip_html_tags(text: str) -> str:
    if not text:
        return ""
    stripped = re.sub(r"<[^>]+>", " ", text)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped


def is_likely_sinhala(text: str, threshold: float = 0.2) -> bool:
    cleaned = clean_text(text)
    if not cleaned:
        return False

    letters = [ch for ch in cleaned if ch.isalpha()]
    if not letters:
        return False

    sinhala_count = sum(
        1
        for ch in letters
        if SINHALA_BLOCK_MIN <= ord(ch) <= SINHALA_BLOCK_MAX
    )
    ratio = sinhala_count / max(len(letters), 1)
    return ratio >= threshold
