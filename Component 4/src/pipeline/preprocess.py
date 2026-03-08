from __future__ import annotations
import pandas as pd
from src.common.logging import get_logger

log = get_logger(__name__)

def preprocess(data: dict) -> dict:
    posts = data["posts"].copy()
    comments = data["comments"].copy()

    # ---- Basic cleaning ----
    comments.drop_duplicates(subset=["comment_id"], inplace=True)

    comments["likes"] = pd.to_numeric(comments["likes"], errors="coerce").fillna(0).astype(int)
    comments["timestamp"] = pd.to_numeric(comments["timestamp"], errors="coerce").fillna(0).astype(int)

    # Normalize is_harmful to 0/1
    if comments["is_harmful"].dtype != "int64" and comments["is_harmful"].dtype != "int32":
        comments["is_harmful"] = comments["is_harmful"].astype(str).str.strip().str.lower().map(
            {"1": 1, "true": 1, "yes": 1, "y": 1, "0": 0, "false": 0, "no": 0, "n": 0}
        ).fillna(0).astype(int)

    # ---- Label normalization (keeps your project labels) ----
    def norm_label(x) -> str:
        x = str(x).strip().lower()
        if "hate" in x and "disinfo" in x:
            return "Hate+Disinfo"
        if "disinfo" in x:
            return "Disinfo"
        if "hate" in x:
            return "Hate"
        return "Normal"

    comments["label_primary"] = comments["label_primary"].map(norm_label)
    posts["post_label"] = posts["post_label"].map(norm_label)

    # ---- Join post title + post label to comments ----
    comments = comments.merge(
        posts[["post_id", "post_title", "post_label"]],
        on="post_id",
        how="left"
    )

    missing = int(comments["post_title"].isna().sum())
    if missing:
        log.info(f"Comments referencing unknown posts (no match in posts.csv): {missing:,}")

        # Build minimal placeholder posts from comments to complete graph structure
        missing_posts = (
            comments.loc[comments["post_title"].isna(), ["post_id"]]
            .drop_duplicates()
            .assign(post_title="(missing in posts.csv)", post_label="Unknown")
        )

        posts = pd.concat([posts, missing_posts], ignore_index=True).drop_duplicates(subset=["post_id"])
        log.info(f"Extended posts table with placeholders. posts={len(posts):,}")

        # re-join so every comment has a post row (at least placeholder)
        comments = comments.drop(columns=["post_title", "post_label"]).merge(
            posts[["post_id", "post_title", "post_label"]],
            on="post_id",
            how="left"
        )

    log.info(f"After preprocess: posts={len(posts):,} comments={len(comments):,}")
    return {"posts": posts, "comments": comments}