# elakiri_fact_server.py
# NLI-based fact checker — supports both Elakiri URL and direct text claim
# Run: uvicorn elakiri_fact_server:app --host 0.0.0.0 --port 8003

import uuid
import asyncio
import sys
import os
import re
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from elakiri_scraper import fetch_elakiri_post
from sports_news_scraper import search_all_sources, filter_relevant_results
from nli_fact_checker import NLIFactChecker

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"]
)

jobs = {}

print("Loading NLI Fact Checker...")
checker = NLIFactChecker()
print("✅ Server ready!")


class ElakiriRequest(BaseModel):
    input_type:  str        # "url" or "text"
    input_value: str        # the URL or text claim


def extract_keywords_from_text(text: str) -> list:
    """Extract English keywords from a free-text claim."""
    stopwords = {
        "the", "a", "an", "is", "in", "on", "at", "to", "of", "and",
        "or", "for", "with", "this", "that", "was", "are", "has",
        "have", "its", "it", "he", "she", "they", "we", "will", "can",
        "not", "but", "from", "by", "as", "be", "do", "did",
    }
    words = re.findall(r'[A-Za-z]+', text)
    keywords = [w for w in words if len(w) > 2 and w.lower() not in stopwords]
    seen, final = set(), []
    for w in keywords:
        if w.lower() not in seen:
            seen.add(w.lower())
            final.append(w)
    return final[:10]  # ← increased from 5 to 10 for better matching


@app.post("/elakiri-factcheck")
async def elakiri_factcheck(req: ElakiriRequest):
    if req.input_type == "url" and "elakiri.com" not in req.input_value:
        return {"error": "Please enter a valid Elakiri post URL"}
    if req.input_type == "text" and len(req.input_value.strip()) < 5:
        return {"error": "Please enter a longer text claim"}

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status":   "processing",
        "stage":    0,
        "progress": 0,
        "log":      "Starting fact-check...",
        "results":  None,
        "error":    None,
    }
    asyncio.create_task(run_factcheck(job_id, req.input_type, req.input_value))
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def status(job_id: str):
    if job_id not in jobs:
        return {"status": "error", "error": "Job not found"}
    return jobs[job_id]


async def run_factcheck(job_id: str, input_type: str, input_value: str):
    job = jobs[job_id]
    try:

        # ── Stage 0: Get Claim ──────────────────────────────────
        if input_type == "url":
            job.update({"stage": 0, "progress": 10,
                        "log": "Fetching Elakiri post..."})
            await asyncio.sleep(0.1)

            post = await asyncio.to_thread(fetch_elakiri_post, input_value)

            if not post["title"] and not post["content"]:
                raise Exception("Could not fetch Elakiri post. Check the URL!")

            post_title   = post["title"]
            post_content = post["content"]
            post_url     = input_value
            keywords     = post["keywords"]
            claim        = f"{post_title} {post_content[:100]}".strip()

        else:
            # Direct text input
            job.update({"stage": 0, "progress": 10,
                        "log": "Processing text claim..."})
            await asyncio.sleep(0.1)

            post_title   = "Direct Text Claim"
            post_content = input_value.strip()
            post_url     = ""
            keywords     = extract_keywords_from_text(input_value)
            claim        = input_value.strip()[:300]

            if not keywords:
                raise Exception("Could not extract keywords. Please use English keywords in your claim.")

        job.update({
            "progress": 25,
            "log": f"Keywords: {', '.join(keywords)}"
        })

        # ── Stage 1: Search All Sources ─────────────────────────
        job.update({"stage": 1, "progress": 30,
                    "log": "Searching Ada Derana, Sunday Observer, Daily Mirror, ThePapare..."})
        await asyncio.sleep(0.1)

        source_results = await asyncio.to_thread(
            search_all_sources, keywords, 6
        )

        job.update({
            "progress": 45,
            "log": f"Raw results: Ada Derana({len(source_results.get('Ada Derana', []))}) "
                   f"Sunday Observer({len(source_results.get('Sunday Observer', []))}) "
                   f"Daily Mirror({len(source_results.get('Daily Mirror', []))}) "
                   f"ThePapare({len(source_results.get('ThePapare', []))})"
        })

        # ── Filter Relevant Articles ────────────────────────────
        job.update({"progress": 50,
                    "log": "Filtering for relevant articles only..."})
        await asyncio.sleep(0.1)

        filtered_results = await asyncio.to_thread(
            filter_relevant_results, source_results, keywords
        )

        job.update({
            "progress": 60,
            "log": f"Relevant: Ada Derana({len(filtered_results.get('Ada Derana', []))}) "
                   f"Sunday Observer({len(filtered_results.get('Sunday Observer', []))}) "
                   f"Daily Mirror({len(filtered_results.get('Daily Mirror', []))}) "
                   f"ThePapare({len(filtered_results.get('ThePapare', []))})"
        })

        # ── Stage 2: NLI Per Source ─────────────────────────────
        job.update({"stage": 2, "progress": 70,
                    "log": "Running NLI per source — SUPPORTS/REFUTES/NEUTRAL..."})
        await asyncio.sleep(0.1)

        result = await asyncio.to_thread(
            checker.check_per_source, claim, filtered_results
        )

        job.update({
            "status":   "done",
            "stage":    3,
            "progress": 100,
            "log":      f"Done! Final verdict: {result['final_verdict']}",
            "results": {
                "input_type":        input_type,
                "post_title":        post_title,
                "post_url":          post_url,
                "post_content":      post_content[:200],
                "keywords":          keywords,
                "claim_checked":     claim[:200],
                "final_verdict":     result["final_verdict"],
                "final_confidence":  result["final_confidence"],
                "final_explanation": result["final_explanation"],
                "per_source":        result["per_source"],
                "processed_at":      datetime.utcnow().isoformat(),
            },
        })

        print(f"✅ Final: {result['final_verdict']} | {result['final_confidence']}")

    except Exception as e:
        jobs[job_id].update({
            "status": "error",
            "error":  str(e),
            "log":    f"Error: {str(e)}",
        })