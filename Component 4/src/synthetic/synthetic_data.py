from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
from src.common.logging import get_logger

log = get_logger(__name__)

def load_synthetic_dataset(repo_root: Path, cfg: dict) -> dict:
    """
    Synthetic FAILSAFE dataset:
    - Generates users + minimal posts + interactions purely to keep pipeline runnable.
    - Clearly labeled synthetic.
    - No claim of real-world validity.
    """
    s = cfg["synthetic_follow_graph"]
    n_users = int(s["num_users"])
    rng = np.random.default_rng(int(s.get("seed", 42)))

    users = [f"synth_{i}" for i in range(n_users)]

    # Minimal posts (small number)
    n_posts = 200
    posts = pd.DataFrame({
        "post_id": [f"yt_video_synth_{i}" for i in range(n_posts)],
        "post_title": ["(synthetic post)" for _ in range(n_posts)],
        "post_label": ["Unknown" for _ in range(n_posts)],
    })

    # Minimal comments interactions: user -> post
    n_comments = 5000
    comments = pd.DataFrame({
        "comment_id": [f"c_synth_{i}" for i in range(n_comments)],
        "user_id": rng.choice(users, size=n_comments, replace=True),
        "post_id": rng.choice(posts["post_id"].tolist(), size=n_comments, replace=True),
        "comment_text": ["(synthetic comment)" for _ in range(n_comments)],
        "likes": rng.integers(0, 50, size=n_comments),
        "timestamp": rng.integers(1_700_000_000, 1_700_500_000, size=n_comments),  # plausible unix range
        "label_primary": rng.choice(["Normal", "Disinfo", "Hate", "Hate+Disinfo"], size=n_comments, p=[0.75,0.1,0.1,0.05]),
        "is_harmful": 0,
        "topic": rng.integers(0, 10, size=n_comments).astype(str),
    })

    log.info(f"Loaded synthetic failsafe dataset: users~{n_users}, posts={len(posts)}, comments={len(comments)}")
    return {"posts": posts, "comments": comments}