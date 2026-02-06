import json
from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class TermStats:
    total_count: int = 0
    hate_count: int = 0
    nonhate_count: int = 0
    first_seen_batch: str = ""
    last_seen_batch: str = ""

class TermStore:
    def __init__(self):
        self.terms: Dict[str, TermStats] = {}

    def update(self, batch_no: str, term_label_pairs: list[tuple[str,int]]) -> Dict[str, Any]:
        batch_no = str(batch_no)
        new_terms = set()
        uniq_terms = set()

        for term, label in term_label_pairs:
            term = str(term).strip()
            if not term:
                continue
            uniq_terms.add(term)

            if term not in self.terms:
                self.terms[term] = TermStats(
                    total_count=0, hate_count=0, nonhate_count=0,
                    first_seen_batch=batch_no, last_seen_batch=batch_no
                )
                new_terms.add(term)

            ts = self.terms[term]
            ts.total_count += 1
            ts.last_seen_batch = batch_no
            if label == 1:
                ts.hate_count += 1
            else:
                ts.nonhate_count += 1

        return {
            "batch_no": batch_no,
            "unique_terms_in_batch": len(uniq_terms),
            "new_terms": sorted(list(new_terms)),
            "new_terms_count": len(new_terms),
        }

    def save(self, path: str) -> None:
        payload = {"terms": {t: asdict(s) for t, s in self.terms.items()}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> "TermStore":
        store = TermStore()
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            for t, s in payload.get("terms", {}).items():
                store.terms[t] = TermStats(**s)
        except FileNotFoundError:
            pass
        return store
