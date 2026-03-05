# ============================================================
# scraper.py — YouTube Comment Scraper
# ============================================================

import yt_dlp


def scrape_youtube_comments(youtube_url: str, max_comments: int = 500) -> list:
    """
    Scrape comments from a YouTube video URL.

    Args:
        youtube_url  : Full YouTube video URL
        max_comments : Maximum number of comments to scrape

    Returns:
        List of raw comment strings
    """
    comments = []

    ydl_opts = {
        'quiet': True,
        'extract_flat': False,
        'writecomments': True,
        'getcomments': True,
        'extractor_args': {
            'youtube': {
                'max_comments': [str(max_comments)],
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            raw_comments = info.get('comments', [])
            for c in raw_comments:
                text = c.get('text', '').strip()
                if text:
                    comments.append(text)
        print(f"✅ Scraped {len(comments)} comments from: {youtube_url}")

    except Exception as e:
        print(f"❌ Scraping failed: {e}")

    return comments
