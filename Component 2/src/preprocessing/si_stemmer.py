import re
import unicodedata

ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")
MULTISPACE = re.compile(r"\s+")

def normalize_surface(term: str) -> str:
    if term is None:
        return ""
    s = str(term).strip()
    s = ZERO_WIDTH.sub("", s)
    s = MULTISPACE.sub(" ", s)
    s = unicodedata.normalize("NFC", s)
    return s

# Common Sinhala noun suffixes / case markers (very lightweight)
# Ordered longest-first so we remove the most specific endings first
COMMON_SUFFIXES = [
    "යන්ව", "යන්ට", "යන්ගේ", "යන්ගෙන්",
    "වන්ව", "වන්ට", "වන්ගේ", "වන්ගෙන්",
    "යෝ", "යො", "යෝව", "යෝට",
    "ව", "ට", "ගේ", "ගෙන්",
    "දී", "දිය", "දීන්", "දීන්ට",
    "න්ව", "න්ට", "න්ගේ", "න්ගෙන්",
    "න්", "ය", "යෙ", "යෝ", "වෝ",
]

def is_sinhala(s: str) -> bool:
    return any("\u0D80" <= ch <= "\u0DFF" for ch in s)

def stem_si(term: str) -> str:
    """
    Very light Sinhala stemmer:
    - normalize unicode
    - strip common suffixes (case/plural markers)
    """
    s = normalize_surface(term)
    if not s:
        return ""
    if not is_sinhala(s):
        return s.lower()

    # Try stripping known suffixes
    for suf in COMMON_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf) + 2:
            return s[: -len(suf)]

    return s
