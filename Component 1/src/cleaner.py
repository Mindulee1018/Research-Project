# ============================================================
# cleaner.py — Comment Cleaning
# ============================================================

import re


# Emoji pattern
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
    """
    Clean a raw YouTube comment.

    Steps:
        1. Remove URLs
        2. Remove mentions (@user)
        3. Remove hashtags (#tag)
        4. Remove emojis
        5. Keep Sinhala unicode + alphanumeric + spaces
        6. Normalize whitespace

    Args:
        text : Raw comment string

    Returns:
        Cleaned comment string
    """
    if not text or not isinstance(text, str):
        return ""

    text = re.sub(r'http\S+', '', text)                          # URLs
    text = re.sub(r'@\w+', '', text)                             # mentions
    text = re.sub(r'#\w+', '', text)                             # hashtags
    text = EMOJI_PATTERN.sub('', text)                           # emojis
    text = re.sub(r'[^\u0D80-\u0DFFa-zA-Z0-9\s]', '', text)     # keep Sinhala + alphanumeric
    text = re.sub(r'\s+', ' ', text).strip()                     # normalize whitespace

    return text


def is_valid_comment(text: str, min_length: int = 3) -> bool:
    """
    Check if a cleaned comment is valid for processing.

    Args:
        text       : Cleaned comment string
        min_length : Minimum character length

    Returns:
        True if valid, False otherwise
    """
    return bool(text) and len(text) >= min_length
