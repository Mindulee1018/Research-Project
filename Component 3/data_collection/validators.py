from typing import Iterable, Tuple

from data_collection.models import IngestedRecord


def validate_record(record: IngestedRecord) -> Tuple[bool, str]:
    if not record.source.strip():
        return False, "missing source"
    if not record.source_item_id_or_url.strip():
        return False, "missing source_item_id_or_url"
    if not record.raw_text.strip():
        return False, "missing raw_text"
    if not record.clean_text.strip():
        return False, "missing clean_text"
    if not record.scraped_at.strip():
        return False, "missing scraped_at"
    return True, ""


def deduplicate(records: Iterable[IngestedRecord]) -> tuple[list[IngestedRecord], int]:
    seen: set[str] = set()
    output: list[IngestedRecord] = []
    dropped = 0

    for item in records:
        key = f"{item.source}|{item.source_item_id_or_url}|{item.clean_text}"
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        output.append(item)

    return output, dropped

