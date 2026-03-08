from __future__ import annotations
from pathlib import Path
import pandas as pd

from src.common.utils import load_yaml
from src.common.logging import get_logger

log = get_logger(__name__)

def load_inputs(repo_root: Path) -> dict:
    cfg = load_yaml(repo_root / "config" / "schema_map.yaml")

    # -------- Posts --------
    posts_path = repo_root / "data" / "raw" / "posts.csv"
    posts_raw = pd.read_csv(posts_path)

    p_cfg = cfg["posts"]
    post_id_col = p_cfg["post_id_col"]
    post_title_col = p_cfg["post_title_col"]
    post_label_col = p_cfg["post_label_col"]
    prefix = p_cfg.get("post_id_prefix", "")

    for col in [post_id_col, post_title_col, post_label_col]:
        if col not in posts_raw.columns:
            raise ValueError(f"Missing column in posts.csv: '{col}'")

    posts = posts_raw[[post_id_col, post_title_col, post_label_col]].copy()
    posts.rename(columns={
        post_id_col: "post_key",
        post_title_col: "post_title",
        post_label_col: "post_label"
    }, inplace=True)
    posts["post_id"] = prefix + posts["post_key"].astype(str)
    posts = posts[["post_id", "post_title", "post_label"]]

    # -------- Comments --------
    comments_path = repo_root / "data" / "raw" / "comments_5k.xlsx"
    comments_raw = pd.read_excel(comments_path)

    c_cfg = cfg["comments"]
    needed = [
        c_cfg["comment_id_col"],
        c_cfg["comment_author_col"],
        c_cfg["parent_post_col"],
        c_cfg["comment_text_col"],
        c_cfg["comment_likes_col"],
        c_cfg["comment_ts_col"],
        c_cfg["label_primary_col"],
        c_cfg["is_harmful_col"],
        c_cfg["topic_col"],
    ]
    for col in needed:
        if col not in comments_raw.columns:
            raise ValueError(f"Missing column in comments_5k.xlsx: '{col}'")

    comments = comments_raw[needed].copy()
    comments.rename(columns={
        c_cfg["comment_id_col"]: "comment_id",
        c_cfg["comment_author_col"]: "user_id",
        c_cfg["parent_post_col"]: "post_id",
        c_cfg["comment_text_col"]: "comment_text",
        c_cfg["comment_likes_col"]: "likes",
        c_cfg["comment_ts_col"]: "timestamp",
        c_cfg["label_primary_col"]: "label_primary",
        c_cfg["is_harmful_col"]: "is_harmful",
        c_cfg["topic_col"]: "topic",
    }, inplace=True)

    # align comment post_ids with posts file prefix for now
    # If comments already include the prefixed form, keep as-is.
    if prefix and not comments["post_id"].astype(str).str.startswith(prefix).all():
        comments["post_id"] = prefix + comments["post_id"].astype(str)

    log.info(f"Loaded posts={len(posts):,} comments={len(comments):,}")
    return {"posts": posts, "comments": comments}