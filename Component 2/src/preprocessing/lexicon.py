import json
from dataclasses import dataclass, asdict
from typing import Dict

@dataclass
class LexiconEntry:
    hate_count: int = 0
    total_count: int = 0
    weight: float = 0.0  # P(Hate|term) with smoothing
    first_seen_batch: str = ""
    last_updated_batch: str = ""

class LexiconStore:
    def __init__(self):
        self.entries: Dict[str, LexiconEntry] = {}

    @staticmethod
    def load(path: str) -> "LexiconStore":
        store = LexiconStore()
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            for term, d in payload.get("entries", {}).items():
                store.entries[term] = LexiconEntry(**d)
        except FileNotFoundError:
            pass
        return store

    def save(self, path: str) -> None:
        payload = {"entries": {t: asdict(e) for t, e in self.entries.items()}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def update_term(self, term: str, is_hate: int, batch_no: str, alpha: float = 1.0) -> None:
        term = term.strip()
        if not term:
            return

        if term not in self.entries:
            self.entries[term] = LexiconEntry(first_seen_batch=batch_no, last_updated_batch=batch_no)

        e = self.entries[term]
        e.total_count += 1
        if is_hate == 1:
            e.hate_count += 1

        # Laplace smoothing: (hate+alpha)/(total+2alpha)
        e.weight = (e.hate_count + alpha) / (e.total_count + 2 * alpha)
        e.last_updated_batch = batch_no
