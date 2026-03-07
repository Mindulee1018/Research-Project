# scraper.py
import yt_dlp
import hashlib

def scrape_youtube_video(youtube_url: str, max_comments: int = 500) -> dict:
    ydl_opts = {
        'quiet': True,
        'extract_flat': False,
        'writecomments': True,
        'getcomments': True,
        'extractor_args': {'youtube': {'max_comments': [str(max_comments)]}}
    }
    result = {'title': '', 'channel': '', 'url': youtube_url, 'comments': []}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            result['title']   = info.get('title', '')
            result['channel'] = info.get('uploader', info.get('channel', ''))

            for i, c in enumerate(info.get('comments', [])):
                text = c.get('text', '').strip()
                if text:
                    # ── Comment ID ──
                    comment_id = c.get('id', '') or f"comment_{i+1}"

                    # ── Anonymize author using hash ──
                    raw_author = c.get('author', f'user_{i+1}')
                    anon_author = "User_" + hashlib.md5(raw_author.encode()).hexdigest()[:6].upper()

                    result['comments'].append({
                        'comment_id': comment_id,
                        'text':       text,
                        'author':     anon_author,
                        'likes':      c.get('like_count', 0) or 0,
                    })

        print(f"Scraped {len(result['comments'])} comments")
    except Exception as e:
        print(f"Scraping failed: {e}")
    return result

def scrape_youtube_comments(youtube_url: str, max_comments: int = 500) -> list:
    data = scrape_youtube_video(youtube_url, max_comments)
    return [c['text'] for c in data['comments']]