# server.py
import uuid, asyncio, io, json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import sys, os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scraper import scrape_youtube_video
from cleaner import clean_comment, is_valid_comment
from predictor import SinhalaHateDetector

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

jobs = {}

# Video ID counter - persists while server is running
video_counter = {"count": 0}

print("Loading models...")
detector = SinhalaHateDetector()
print("Models ready!")


class ProcessRequest(BaseModel):
    youtube_url: str
    max_comments: int = 500


@app.post("/process")
async def process(req: ProcessRequest):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "processing", "stage": 0, "progress": 0,
        "log": "Starting pipeline...", "results": None,
        "comment_csv": None, "post_csv": None, "error": None,
    }
    asyncio.create_task(run_pipeline(job_id, req.youtube_url, req.max_comments))
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def status(job_id: str):
    if job_id not in jobs:
        return {"status": "error", "error": "Job not found"}
    return jobs[job_id]


async def run_pipeline(job_id, youtube_url, max_comments):
    job = jobs[job_id]
    try:
        # ── Generate Video ID ──
        video_counter["count"] += 1
        video_id = video_counter["count"]

        # ── Stage 0: Scraping ──
        job.update({"stage": 0, "progress": 5, "log": f"Scraping up to {max_comments} comments..."})
        await asyncio.sleep(0.1)

        data = await asyncio.to_thread(scrape_youtube_video, youtube_url, max_comments)

        if not data['comments']:
            raise Exception("No comments found! Check the YouTube URL.")

        job.update({
            "progress": 20,
            "log": f"Scraped {len(data['comments'])} comments | Video: {data['title']}"
        })

        # ── Stage 1: Cleaning ──
        job.update({"stage": 1, "progress": 25, "log": "Cleaning comments..."})
        await asyncio.sleep(0.1)

        cleaned = []
        for c in data['comments']:
            cl = clean_comment(c['text'])
            if is_valid_comment(cl):
                cleaned.append({
                    'comment_id': c['comment_id'],
                    'raw':        c['text'],
                    'clean':      cl,
                    'author':     c['author'],
                    'likes':      c['likes'],
                })

        job.update({"progress": 40, "log": f"Cleaned {len(cleaned)} valid comments"})

        # ── Stage 2: Classifying Comments ──
        job.update({"stage": 2, "progress": 45, "log": "Running XLM-R classification..."})
        await asyncio.sleep(0.1)

        comment_results = []
        total = len(cleaned)

        for i, c in enumerate(cleaned):
            label, hate_words = await asyncio.to_thread(detector.predict, c['clean'])
            comment_results.append({
                "Comment ID":        c['comment_id'],
                "Video ID":          video_id,
                "Author":            c['author'],
                "Likes":             c['likes'],
                "Original Comment":  c['raw'],
                "Cleaned Comment":   c['clean'],
                "Label":             label,
                "Hate":              1 if label == "HATE"    else 0,
                "Disinfo":           1 if label == "DISINFO" else 0,
                "Normal":            1 if label == "NORMAL"  else 0,
                "Hate Words":        ", ".join(hate_words) if hate_words else "",
            })

            if (i + 1) % 10 == 0:
                pct = 45 + int((i + 1) / total * 45)
                job.update({"progress": pct, "log": f"Classified {i+1}/{total} comments..."})
                await asyncio.sleep(0)

        # ── Stage 3: Classify Video Title + Build Post Dataset ──
        job.update({"stage": 3, "progress": 92, "log": "Classifying video title..."})
        await asyncio.sleep(0.1)

        # Classify video title using same model
        title_label, _ = await asyncio.to_thread(detector.predict, data['title'])

        post_result = {
            "Video ID":    video_id,
            "Channel":     data['channel'],
            "Video Title": data['title'],
            "Video URL":   youtube_url,
            "Title Label": title_label,
        }

        # ── Build CSVs ──
        comment_df = pd.DataFrame(comment_results)
        post_df    = pd.DataFrame([post_result])

        comment_buf = io.StringIO()
        post_buf    = io.StringIO()
        comment_df.to_csv(comment_buf, index=False, encoding="utf-8")
        post_df.to_csv(post_buf,    index=False, encoding="utf-8")

        summary = {
            "video_id":    video_id,
            "title":       data['title'],
            "channel":     data['channel'],
            "total":       len(comment_df),
            "hate":        int(comment_df["Hate"].sum()),
            "disinfo":     int(comment_df["Disinfo"].sum()),
            "normal":      int(comment_df["Normal"].sum()),
            "title_label": title_label,
        }

        job.update({
            "status":      "done",
            "stage":       4,
            "progress":    100,
            "log":         f"Done! {summary['total']} comments processed.",
            "results":     summary,
            "comment_csv": comment_buf.getvalue(),
            "post_csv":    post_buf.getvalue(),
        })

    except Exception as e:
        jobs[job_id].update({
            "status": "error",
            "error":  str(e),
            "log":    f"Error: {str(e)}",
        })