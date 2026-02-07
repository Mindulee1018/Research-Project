# src/variant_resolver.py
import json
import os
from collections import defaultdict, Counter

from .morph import stem_with_morfessor, normalize_surface
from .suffix_miner import strip_suffix

MAP_PATH = "artifacts/variant_map.json"
MANUAL_ALIASES_PATH = "artifacts/manual_aliases.json"


def load_manual_aliases():
    if not os.path.exists(MANUAL_ALIASES_PATH):
        return {}
    try:
        with open(MANUAL_ALIASES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class VariantResolver:
    """
    Hybrid canonicalizer:
      - Morfessor stem key (learns morphology automatically)
      - + auto-mined suffix stripping (no manual suffix list)
      - + manual override aliases (dashboard-driven)

    Output (canonical term) is always a REAL surface form (most frequent),
    so your dashboard doesn't show broken stems.
    """

    def __init__(self, morfessor_model=None, path: str = MAP_PATH):
        self.path = path
        self.model = morfessor_model

        # manual overrides (from dashboard)
        self.manual = load_manual_aliases()

        # suffixes discovered automatically from your vocabulary
        self.suffixes: list[str] = []

        self.key_to_counter = defaultdict(Counter)  # group_key -> Counter(surface_form)
        self.key_to_canon = {}                      # group_key -> canonical surface
        self.term_to_canon = {}                     # surface -> canonical surface

        self._load()

    def reload_manual(self):
        """Reload manual aliases from disk (so dashboard edits apply without restart)."""
        self.manual = load_manual_aliases()

    def set_suffixes(self, suffixes: list[str]):
        """Set automatically discovered suffix list (longest-first)."""
        self.suffixes = suffixes or []

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.key_to_canon = payload.get("key_to_canon", {})
            self.term_to_canon = payload.get("term_to_canon", {})
            saved = payload.get("key_to_counter", {})
            for k, cdict in saved.items():
                self.key_to_counter[k] = Counter(cdict)
        except FileNotFoundError:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {
            "key_to_canon": self.key_to_canon,
            "term_to_canon": self.term_to_canon,
            "key_to_counter": {k: dict(v) for k, v in self.key_to_counter.items()},
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _key(self, term: str) -> str:
        surface = normalize_surface(term)
        if not surface:
            return ""

        # strip on surface first (helps Morfessor give same base)
        s1 = strip_suffix(surface, self.suffixes, min_stem_len=2, max_passes=3)

        # then Morfessor stem
        base = stem_with_morfessor(self.model, s1)

        # strip again (handles stacked endings and what Morfessor kept)
        base2 = strip_suffix(base, self.suffixes, min_stem_len=2, max_passes=3)

        return base2

    def observe(self, term: str):
        surface = normalize_surface(term)
        if not surface:
            return

        key = self._key(surface)
        if not key:
            return

        self.key_to_counter[key][surface] += 1
        canon, _ = self.key_to_counter[key].most_common(1)[0]
        self.key_to_canon[key] = canon
        self.term_to_canon[surface] = canon

    def canonicalize(self, term: str) -> str:
        surface = normalize_surface(term)
        if not surface:
            return ""

        # reload manual each call so dashboard changes apply immediately
        # (cheap because file is small)
        self.reload_manual()

        # manual override first
        if surface in self.manual:
            return self.manual[surface]

        if surface in self.term_to_canon:
            return self.term_to_canon[surface]

        key = self._key(surface)
        if key in self.key_to_canon:
            canon = self.key_to_canon[key]
            self.term_to_canon[surface] = canon
            return canon

        return surface
