# server.py
import uuid, asyncio, io, json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import sys, os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scraper import scrape_youtube_video
from cleaner import clean_comment, is_valid_comment
from predictor import SinhalaHateDetector

# ── MongoDB Atlas Integration (to be integrated with team) ────
# pip install pymongo
# from pymongo import MongoClient
# from pymongo.errors import DuplicateKeyError
#
# MONGO_URI = "mongodb+srv://imayaperera1_db_user:lN6AXSLKln3H7svR@cluster0.m6eaxvq.mongodb.net/?appName=Cluster0"
# mongo_client = MongoClient(MONGO_URI)
# db = mongo_client["sinhala_hate_db"]
# comments_col = db["comments"]
# posts_col    = db["posts"]
# posts_col.create_index("video_url", unique=True)     # prevent duplicate videos
# comments_col.create_index("comment_id", unique=True) # prevent duplicate comments
# print("✅ MongoDB Atlas connected!")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

jobs = {}

# Video ID counter
# NOTE: When MongoDB is integrated, replace with:
# def get_next_video_id():
#     last_post = posts_col.find_one(sort=[("video_id", -1)])
#     return (last_post["video_id"] + 1) if last_post else 1
COUNTER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_counter.json")

def get_next_video_id():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, "r") as f:
            return json.load(f)["count"] + 1
    return 1

def save_video_id(video_id):
    with open(COUNTER_FILE, "w") as f:
        json.dump({"count": video_id}, f)


video_counter = {"count": 0}

print("Loading models...")
detector = SinhalaHateDetector()
print("Models ready!")


class ProcessRequest(BaseModel):
    youtube_url: str
    max_comments: int = 500


@app.post("/process")
async def process(req: ProcessRequest):
    # ── MongoDB: Check duplicate video (skip if already processed) ──
    # existing = posts_col.find_one({"video_url": req.youtube_url})
    # if existing:
    #     return {
    #         "job_id": None,
    #         "already_exists": True,
    #         "video_id": existing["video_id"],
    #         "message": f"Video already processed as Video ID {existing['video_id']}"
    #     }

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "processing", "stage": 0, "progress": 0,
        "log": "Starting pipeline...", "results": None,
        "comment_csv": None, "post_csv": None, "error": None,
    }
    asyncio.create_task(run_pipeline(job_id, req.youtube_url, req.max_comments))
    return {"job_id": job_id, "already_exists": False}


@app.get("/status/{job_id}")
async def status(job_id: str):
    if job_id not in jobs:
        return {"status": "error", "error": "Job not found"}
    return jobs[job_id]


# ── MongoDB: Retrieve all processed videos ───────────────────
# @app.get("/videos")
# async def get_all_videos():
#     posts = list(posts_col.find({}, {"_id": 0}).sort("video_id", 1))
#     return {"videos": posts}

# ── MongoDB: Download comments CSV by Video ID ───────────────
# @app.get("/download/comments/{video_id}")
# async def download_comments(video_id: int):
#     comments = list(comments_col.find({"video_id": video_id}, {"_id": 0}))
#     if not comments:
#         return {"error": "No comments found for this video ID"}
#     df = pd.DataFrame(comments)
#     buf = io.StringIO()
#     df.to_csv(buf, index=False, encoding="utf-8")
#     return {"csv": buf.getvalue(), "video_id": video_id}

# ── MongoDB: Download all posts CSV ──────────────────────────
# @app.get("/download/posts")
# async def download_all_posts():
#     posts = list(posts_col.find({}, {"_id": 0}).sort("video_id", 1))
#     if not posts:
#         return {"error": "No posts found"}
#     df = pd.DataFrame(posts)
#     buf = io.StringIO()
#     df.to_csv(buf, index=False, encoding="utf-8")
#     return {"csv": buf.getvalue()}


async def run_pipeline(job_id, youtube_url, max_comments):
    job = jobs[job_id]
    try:
        # ── Generate Video ID ──
        # MongoDB version: video_id = get_next_video_id()
        #video_counter["count"] += 1
        # video_id = video_counter["count"]

        # ── Generate Video ID ──
        # MongoDB version: video_id = get_next_video_id()
        video_id = get_next_video_id()   # ← replace video_counter lines
        save_video_id(video_id)          # ← add this

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
                "Processed At":      datetime.utcnow().isoformat(),
            })

            if (i + 1) % 10 == 0:
                pct = 45 + int((i + 1) / total * 45)
                job.update({"progress": pct, "log": f"Classified {i+1}/{total} comments..."})
                await asyncio.sleep(0)

        # ── Stage 3: Classify Video Title ──
        job.update({"stage": 3, "progress": 92, "log": "Classifying video title..."})
        await asyncio.sleep(0.1)

        title_label, _ = await asyncio.to_thread(detector.predict, data['title'])

        post_result = {
            "Video ID":       video_id,
            "Channel":        data['channel'],
            "Video Title":    data['title'],
            "Video URL":      youtube_url,
            "Title Label":    title_label,
            "Total Comments": len(comment_results),
            "Hate Count":     sum(1 for c in comment_results if c['Label'] == 'HATE'),
            "Disinfo Count":  sum(1 for c in comment_results if c['Label'] == 'DISINFO'),
            "Normal Count":   sum(1 for c in comment_results if c['Label'] == 'NORMAL'),
            "Processed At":   datetime.utcnow().isoformat(),
        }

        # ── MongoDB: Save to Atlas in real-time ──────────────────
        # job.update({"progress": 95, "log": "Saving to MongoDB Atlas..."})
        # if comment_results:
        #     try:
        #         comments_col.insert_many(comment_results, ordered=False)
        #     except Exception as e:
        #         print(f"Some comments may be duplicates: {e}")
        # try:
        #     posts_col.insert_one(post_result)
        # except DuplicateKeyError:
        #     print(f"Post already exists for {youtube_url}")
        # print(f"✅ Saved Video ID {video_id} to MongoDB!")

        # ── Build CSVs for download ──
        comment_df = pd.DataFrame(comment_results)
        post_df    = pd.DataFrame([post_result])

        comment_buf = io.StringIO()
        post_buf    = io.StringIO()
        comment_df.to_csv(comment_buf, index=False, encoding="utf-8")
        post_df.to_csv(post_buf,    index=False, encoding="utf-8")
        
        # ── Auto-save CSVs to Component 1 data/batches folder ──
        COMPONENT1_DATA_PATH = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "..","Component 1","Data", "batches"
        )
        try:
            os.makedirs(COMPONENT1_DATA_PATH, exist_ok=True)
            comment_path1 = os.path.join(COMPONENT1_DATA_PATH, "all_comments.csv")
            post_path1    = os.path.join(COMPONENT1_DATA_PATH, "all_posts.csv")

            # Append if file exists, write header only if new file
            comment_df.to_csv(comment_path1, mode="a", index=False, encoding="utf-8-sig",
                                header=not os.path.exists(comment_path1))
            post_df.to_csv(post_path1,    mode="a", index=False, encoding="utf-8-sig",
                                header=not os.path.exists(post_path1))

            print(f"✅ CSVs updated in Component 1 batches: Video ID {video_id}")
        except Exception as e:
            print(f"⚠️ Could not save to Component 1 batches: {e}")


        # ── Auto-save CSVs to teammate's Component 2 data folder ──
        TEAMMATE_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "Component 2", "data", "batches")
        try:
            os.makedirs(TEAMMATE_DATA_PATH, exist_ok=True)
            comment_path = os.path.join(TEAMMATE_DATA_PATH, f"batch_{video_id}.csv")
            comment_df.to_csv(comment_path, index=False, encoding="utf-8-sig")
            print(f"CSVs saved to teammate's folder: Video ID {video_id}")
        except Exception as e:
            print(f"Could not save to teammate's folder: {e}")

       

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

        
