from dataclasses import dataclass, field
from typing import Dict


@dataclass
class SourceRecord:
    source_item_id_or_url: str
    raw_text: str
    published_at: str = ""
    author_id: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class IngestedRecord:
    record_id: str
    run_id: str
    source: str
    source_item_id_or_url: str
    scraped_at: str
    published_at: str
    author_id: str
    raw_text: str
    clean_text: str
    is_sinhala: bool
    metadata: Dict[str, str]

