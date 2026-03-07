# cleaner.py
import re

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002600-\U000026FF"
    "\U00002B00-\U00002BFF"
    "]+",
    flags=re.UNICODE,
)

def clean_comment(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'#\w+', '', text)
    text = EMOJI_PATTERN.sub('', text)
    text = re.sub(r'[^\u0D80-\u0DFFa-zA-Z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_valid_comment(text: str, min_length: int = 10) -> bool:
    """
    Stricter validation:
    - Minimum 10 characters
    - Must have at least 2 words
    - Must not be gibberish (random characters)
    - Must contain at least some Sinhala or meaningful English
    """
    if not text or len(text) < min_length:
        return False

    words = text.strip().split()

    # Must have at least 2 words
    if len(words) < 2:
        # Allow single Sinhala words that are long enough
        if len(text) < 5:
            return False

    # Check for gibberish — if a single word has 10+ chars with no vowels it's random
    def is_gibberish(word):
        vowels = set('aeiouAEIOU\u0DCF\u0DD0\u0DD1\u0DD2\u0DD3\u0DD4\u0DD6\u0DD8\u0DDA\u0DDC\u0DDD\u0DDE')
        if len(word) > 8:
            has_vowel = any(c in vowels for c in word)
            if not has_vowel:
                return True
        return False

    # If ALL words are gibberish → skip
    if all(is_gibberish(w) for w in words):
        return False

    # Must have at least 3 unique characters
    if len(set(text.lower())) < 3:
        return False

    return True