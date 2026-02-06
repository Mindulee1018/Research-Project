import json
import os
import re
import unicodedata
from collections import defaultdict, Counter

ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")
MULTISPACE = re.compile(r"\s+")
PUNCT = re.compile(r"[\"'“”‘’.,;:!?()\[\]{}<>|/\\]+")

# Sinhala dependent vowels + marks (used ONLY to build skeleton key)
SINHALA_DIACRITICS = re.compile(r"[\u0DCF-\u0DDF\u0DF2\u0DF3]")

def normalize_surface(term: str) -> str:
    """Clean term but keep real spelling for display."""
    if term is None:
        return ""
    s = str(term).strip()
    s = ZERO_WIDTH.sub("", s)
    s = MULTISPACE.sub(" ", s)
    s = unicodedata.normalize("NFC", s)
    s = s.lower()
    s = PUNCT.sub("", s)
    return s.strip()

def has_sinhala(s: str) -> bool:
    return any("\u0D80" <= ch <= "\u0DFF" for ch in s)

def skeleton_key(term: str) -> str:
    """
    Key used for grouping variants automatically.
    DO NOT show this to users; it’s only for matching.
    """
    s = normalize_surface(term)
    if not s:
        return ""
    if has_sinhala(s):
        s = SINHALA_DIACRITICS.sub("", s)
    return s

class VariantResolver:
    """
    Automatically groups terms by skeleton_key and picks a canonical REAL spelling
    (most frequent original form).
    Saves mapping in artifacts/variant_map.json.
    """
    def __init__(self, path: str = "artifacts/variant_map.json"):
        self.path = path
        self.key_to_counter = defaultdict(Counter)  # skeleton -> Counter({surface_form: count})
        self.key_to_canon = {}                      # skeleton -> canonical surface form
        self.term_to_canon = {}                     # normalized surface -> canonical surface
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.key_to_canon = payload.get("key_to_canon", {})
            self.term_to_canon = payload.get("term_to_canon", {})

            # counters optional (not required to run)
            saved = payload.get("key_to_counter", {})
            for k, cdict in saved.items():
                self.key_to_counter[k] = Counter(cdict)
        except FileNotFoundError:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        payload = {
            "key_to_canon": self.key_to_canon,
            "term_to_canon": self.term_to_canon,
            "key_to_counter": {k: dict(v) for k, v in self.key_to_counter.items()},
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def observe(self, term: str):
        """Feed a raw term so the resolver can learn the best canonical form."""
        surface = normalize_surface(term)
        if not surface:
            return
        key = skeleton_key(surface)
        if not key:
            return

        self.key_to_counter[key][surface] += 1
        # choose canonical = most frequent surface form
        canon, _ = self.key_to_counter[key].most_common(1)[0]
        self.key_to_canon[key] = canon

        # map this surface to canonical
        self.term_to_canon[surface] = canon

    def canonicalize(self, term: str) -> str:
        """Return canonical REAL spelling (not skeleton)."""
        surface = normalize_surface(term)
        if not surface:
            return ""
        # if we already learned mapping for this exact surface
        if surface in self.term_to_canon:
            return self.term_to_canon[surface]

        # fallback: use skeleton group
        key = skeleton_key(surface)
        if key in self.key_to_canon:
            canon = self.key_to_canon[key]
            self.term_to_canon[surface] = canon
            return canon

        # not seen before: treat itself as canonical for now
        return surface
