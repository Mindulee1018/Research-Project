import re
import unicodedata

ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")
MULTISPACE = re.compile(r"\s+")
PUNCT = re.compile(r"[\"'“”‘’.,;:!?()\[\]{}<>|/\\]+")

# Sinhala vowel signs (dependent vowels) and some marks.
# We remove/normalize these to reduce spelling variants.
SINHALA_DIACRITICS = re.compile(r"[\u0DCF-\u0DDF\u0DF2\u0DF3]")

def normalize_term(term: str) -> str:
    if term is None:
        return ""
    s = str(term).strip()
    s = ZERO_WIDTH.sub("", s)
    s = MULTISPACE.sub(" ", s)
    s = unicodedata.normalize("NFC", s)
    s = s.lower()
    s = PUNCT.sub("", s)
    return s.strip()

def canonical_term(term: str) -> str:
    """
    Canonicalize Sinhala variants automatically by stripping Sinhala vowel signs/diacritics.
    This merges variants like: තමුසෙ / තමුසේ into the same canonical form.
    """
    s = normalize_term(term)
    if not s:
        return ""
    # apply only if Sinhala script exists
    has_si = any("\u0D80" <= ch <= "\u0DFF" for ch in s)
    if has_si:
        s = SINHALA_DIACRITICS.sub("", s)
    return s
