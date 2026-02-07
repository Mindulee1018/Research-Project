from collections import defaultdict

def discover_suffixes(words, min_types=30, min_len=1, max_len=4):
    """
    Returns suffixes that appear at the end of many different word TYPES.
    This is automatic and corpus-driven.
    """
    suffix_to_words = defaultdict(set)

    vocab = set([w for w in words if w and len(w) >= 3])

    for w in vocab:
        Lmax = min(max_len, len(w) - 1)
        for L in range(min_len, Lmax + 1):
            suf = w[-L:]
            suffix_to_words[suf].add(w)

    # keep suffixes with enough distinct word types
    strong = [s for s, ws in suffix_to_words.items() if len(ws) >= min_types]

    # prefer longer suffixes first so we strip the longest match
    strong.sort(key=len, reverse=True)
    return strong

def strip_suffix(word: str, suffixes: list[str], min_stem_len: int = 2, max_passes: int = 3) -> str:
    """
    Iteratively strip up to max_passes suffixes.
    Helps with stacked endings like: stem + plural + case (e.g., '...න්ට').
    """
    w = word
    for _ in range(max_passes):
        changed = False
        for suf in suffixes:
            if w.endswith(suf) and len(w) - len(suf) >= min_stem_len:
                w = w[:-len(suf)]
                changed = True
                break
        if not changed:
            break
    return w

