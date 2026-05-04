# elakiri_scraper.py
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def fetch_elakiri_post(url: str) -> dict:
    """Fetch title and content from a specific Elakiri post URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        title_tag = (
            soup.find("h1", class_="p-title-value") or
            soup.find("h1") or
            soup.find("title")
        )
        title = title_tag.get_text(strip=True) if title_tag else ""

        # First post content
        content_div = (
            soup.find("div", class_="bbWrapper") or
            soup.find("div", class_="message-content") or
            soup.find("div", class_="message-body") or
            soup.find("article")
        )
        content = ""
        if content_div:
            content = content_div.get_text(separator=" ", strip=True)[:500]

        # Extract English keywords
        keywords = _extract_keywords(title + " " + content)

        print(f" Fetched: {title[:80]}")
        print(f"   Keywords: {keywords}")

        return {"title": title, "content": content, "keywords": keywords, "url": url}

    except Exception as e:
        print(f"⚠️ Could not fetch Elakiri post: {e}")
        return {"title": "", "content": "", "keywords": [], "url": url}


def _extract_keywords(text: str) -> list:
    """Extract meaningful English keywords."""
    stopwords = {
        "the","a","an","is","in","on","at","to","of","and","or","for",
        "with","this","that","was","are","has","have","its","it","he",
        "she","they","we","will","can","not","but","from","by","as",
        "www","com","lk","http","https","sold","buy","get","got"
    }
    words    = re.findall(r'[A-Za-z]+', text)
    keywords = [w for w in words if len(w) > 2 and w.lower() not in stopwords]
    # Deduplicate preserving order
    seen  = set()
    final = []
    for w in keywords:
        if w.lower() not in seen:
            seen.add(w.lower())
            final.append(w)
    return final[:5]