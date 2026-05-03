# sports_news_scraper.py
# Searches 4 reliable Sri Lankan news/sports sources:
# 1. Ada Derana
# 2. Sunday Observer
# 3. Daily Mirror
# 4. ThePapare

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

SOURCES = {
    "Ada Derana": {
        "search_url": "https://www.adaderana.lk/search_results.php?mode=0&show=1&query={query}",
        "base": "https://www.adaderana.lk",
    },
    "Sunday Observer": {
        "search_url": "https://www.sundayobserver.lk/?s={query}",
        "base": "https://www.sundayobserver.lk",
    },
    "Daily Mirror": {
        "search_url": "https://www.dailymirror.lk/search?q={query}",
        "base": "https://www.dailymirror.lk",
    },
    "ThePapare": {
        "search_url": "https://www.thepapare.com/?s={query}",
        "base": "https://www.thepapare.com",
    },
}


def search_all_sources(keywords: list, max_per_source: int = 6) -> dict:
    results = {}
    queries = _build_queries(keywords)

    print(f"🔍 Queries to try: {queries}")

    for source_name, config in SOURCES.items():
        articles = _search_source(source_name, config, queries, max_per_source)
        results[source_name] = articles
        print(f"   {source_name}: {len(articles)} articles found")

    return results


def _build_queries(keywords: list) -> list:
    """Build stronger search queries using phrases first, not weak single words."""
    clean_keywords = [
        kw.strip()
        for kw in keywords
        if kw and len(kw.strip()) > 2
    ]

    queries = []

    # Best search: full phrase / main claim words
    if len(clean_keywords) >= 4:
        queries.append(" ".join(clean_keywords[:6]))

    # Entity/name combinations
    if len(clean_keywords) >= 2:
        queries.append(f"{clean_keywords[0]} {clean_keywords[1]}")

    if len(clean_keywords) >= 3:
        queries.append(f"{clean_keywords[0]} {clean_keywords[1]} {clean_keywords[2]}")

    # Avoid weak words like "Left"
    weak_words = {"left", "right", "good", "bad", "said", "says", "this", "that"}

    for kw in clean_keywords[:8]:
        if len(kw) > 4 and kw.lower() not in weak_words:
            queries.append(kw)

    return list(dict.fromkeys(queries))


def is_relevant_article(article: dict, keywords: list, min_matches: int = 2) -> bool:
    """Check whether article title/content actually matches the claim keywords."""
    text = f"{article.get('title', '')} {article.get('content', '')}".lower()

    matched = 0

    for kw in keywords:
        kw = kw.lower().strip()

        if len(kw) <= 3:
            continue

        if kw in text:
            matched += 1

    return matched >= min_matches


def filter_relevant_results(source_results: dict, keywords: list) -> dict:
    """
    Fetch article content and keep only relevant articles.
    Use this before sending results to NLI.
    """
    filtered_results = {}

    for source_name, articles in source_results.items():
        filtered_results[source_name] = []

        for article in articles:
            article["content"] = fetch_article_content(article["url"])

            if is_relevant_article(article, keywords):
                filtered_results[source_name].append(article)

        print(
            f"✅ {source_name}: {len(filtered_results[source_name])}/"
            f"{len(articles)} relevant articles kept"
        )

    return filtered_results


def _search_source(source_name: str, config: dict, queries: list, max_articles: int) -> list:
    articles = []
    seen_urls = set()

    for query in queries:
        if len(articles) >= max_articles:
            break

        try:
            url = config["search_url"].format(query=requests.utils.quote(query))
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # ── Ada Derana ─────────────────────────────────────
            if source_name == "Ada Derana":
                links = soup.find_all("a", class_="newsItemTitle")

                for a in links[:max_articles]:
                    title = a.get_text(strip=True)
                    href = a.get("href", "")

                    if href and not href.startswith("http"):
                        href = config["base"] + "/" + href.lstrip("/")

                    if title and href and href not in seen_urls:
                        seen_urls.add(href)
                        articles.append({
                            "title": title,
                            "url": href,
                            "source": source_name,
                            "content": ""
                        })

            # ── Sunday Observer ────────────────────────────────
            elif source_name == "Sunday Observer":
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "")
                    title = a.get_text(strip=True)

                    if (
                        "sundayobserver.lk" in href
                        and len(title) > 15
                        and href not in seen_urls
                        and "/20" in href
                    ):
                        seen_urls.add(href)
                        articles.append({
                            "title": title,
                            "url": href,
                            "source": source_name,
                            "content": ""
                        })

                    if len(articles) >= max_articles:
                        break

            # ── Daily Mirror ────────────────────────────────────
            elif source_name == "Daily Mirror":
                for a in soup.find_all("a", class_=lambda c: c and "ng-binding" in c):
                    href = a.get("href", "")
                    title = a.get_text(strip=True)

                    if not href.startswith("http"):
                        href = config["base"] + href

                    if (
                        title
                        and len(title) > 10
                        and href not in seen_urls
                        and "dailymirror.lk" in href
                    ):
                        seen_urls.add(href)
                        articles.append({
                            "title": title,
                            "url": href,
                            "source": source_name,
                            "content": ""
                        })

                    if len(articles) >= max_articles:
                        break

            # ── ThePapare ─────────────────────────────────────
            elif source_name == "ThePapare":
                for h3 in soup.find_all(["h2", "h3"], class_=lambda c: c and "entry-title" in c):
                    a = h3.find("a", href=True)

                    if not a:
                        continue

                    href = a.get("href", "")
                    title = a.get_text(strip=True)

                    if not href.startswith("http"):
                        href = config["base"] + "/" + href.lstrip("/")

                    if title and href and href not in seen_urls:
                        seen_urls.add(href)
                        articles.append({
                            "title": title,
                            "url": href,
                            "source": source_name,
                            "content": ""
                        })

                    if len(articles) >= max_articles:
                        break

        except requests.exceptions.Timeout:
            print(f"⚠️ {source_name} timed out for '{query}', skipping...")
            continue

        except Exception as e:
            print(f"⚠️ {source_name} error for '{query}': {e}")
            continue

        if articles:
            print(f"   '{query}' → {len(articles)} from {source_name}")
            break

    return articles[:max_articles]


def fetch_article_content(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        content_div = (
            soup.find("div", class_="news-content") or
            soup.find("div", class_="story-content") or
            soup.find("div", class_="article-body") or
            soup.find("div", class_="entry-content") or
            soup.find("article")
        )

        if content_div:
            return " ".join(
                p.get_text(strip=True)
                for p in content_div.find_all("p")
            )[:1500]

        return soup.get_text(separator=" ", strip=True)[:700]

    except Exception as e:
        print(f"⚠️ Could not fetch: {e}")
        return ""