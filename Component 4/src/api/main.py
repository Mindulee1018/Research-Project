from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.pipeline.file_watcher import start_watcher

REPO_ROOT = Path(__file__).resolve().parents[2]
WATCH_OBSERVER = None

app = FastAPI(title="Disinfo Risk Graph API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.on_event("startup")
def startup_event():
    global WATCH_OBSERVER
    watch_dir = REPO_ROOT / "data" / "raw"
    target_files = ["comments_5k.xlsx", "posts.csv"]   # or change to actual upstream output names
    WATCH_OBSERVER = start_watcher(REPO_ROOT, watch_dir, target_files)

@app.on_event("shutdown")
def shutdown_event():
    global WATCH_OBSERVER
    if WATCH_OBSERVER:
        WATCH_OBSERVER.stop()
        WATCH_OBSERVER.join()