# ============================================================
# server.py — FastAPI Backend
# Run with: uvicorn server:app --reload
# ============================================================

import uuid
import asyncio
import io
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper import scrape_youtube_comments
from cleaner import clean_comment, is_valid_comment
from predictor import SinhalaHateDetector

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store
jobs = {}

# Load detector once at startup
print("Loading models...")
detector = SinhalaHateDetector()
print("✅ Models ready!")


class ProcessRequest(BaseModel):
    youtube_url: str
    max_comments: int = 500


@app.post("/process")
async def process(req: ProcessRequest):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status":   "processing",
        "stage":    0,
        "progress": 0,
        "log":      "🚀 Pipeline started...",
        "results":  None,
        "csv":      None,
        "error":    None,
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
        # ── Stage 0: Scraping ──
        job.update({"stage": 0, "progress": 5, "log": f"⬇ Scraping up to {max_comments} comments..."})
        await asyncio.sleep(0.1)

        raw_comments = await asyncio.to_thread(
            scrape_youtube_comments, youtube_url, max_comments
        )
        if not raw_comments:
            raise Exception("No comments found! Check the YouTube URL.")

        job.update({"progress": 20, "log": f"✅ Scraped {len(raw_comments)} comments"})

        # ── Stage 1: Cleaning ──
        job.update({"stage": 1, "progress": 25, "log": "🧹 Cleaning comments..."})
        await asyncio.sleep(0.1)

        cleaned = []
        for c in raw_comments:
            cl = clean_comment(c)
            if is_valid_comment(cl):
                cleaned.append((c, cl))

        job.update({"progress": 40, "log": f"✅ Cleaned {len(cleaned)} valid comments"})

        # ── Stage 2: Classifying ──
        job.update({"stage": 2, "progress": 45, "log": "🤖 Running XLM-R classification..."})
        await asyncio.sleep(0.1)

        results = []
        total   = len(cleaned)

        for i, (raw, cl) in enumerate(cleaned):
            label, hate_words = await asyncio.to_thread(detector.predict, cl)
            results.append({
                "Original Comment": raw,
                "Cleaned Comment":  cl,
                "Label":            label,
                "Hate":             1 if label == "HATE"    else 0,
                "Disinfo":          1 if label == "DISINFO" else 0,
                "Normal":           1 if label == "NORMAL"  else 0,
                "Hate Words":       ", ".join(hate_words) if hate_words else "",
            })

            # Update progress every 10 comments
            if (i + 1) % 10 == 0:
                pct = 45 + int((i + 1) / total * 45)
                job.update({
                    "progress": pct,
                    "log": f"🤖 Classified {i+1}/{total} comments..."
                })
                await asyncio.sleep(0)

        # ── Stage 3: Saving ──
        job.update({"stage": 3, "progress": 92, "log": "💾 Generating CSV..."})
        await asyncio.sleep(0.1)

        df = pd.DataFrame(results)

        # Convert to CSV string
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        csv_str = csv_buffer.getvalue()

        # Summary stats
        summary = {
            "total":   len(df),
            "hate":    int(df["Hate"].sum()),
            "disinfo": int(df["Disinfo"].sum()),
            "normal":  int(df["Normal"].sum()),
        }

        job.update({
            "status":   "done",
            "stage":    4,
            "progress": 100,
            "log":      f"✅ Done! {summary['total']} comments processed.",
            "results":  summary,
            "csv":      csv_str,
        })

    except Exception as e:
        jobs[job_id].update({
            "status": "error",
            "error":  str(e),
            "log":    f"❌ Error: {str(e)}",
        })
