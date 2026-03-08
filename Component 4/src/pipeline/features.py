import numpy as np
import pandas as pd
import networkx as nx
from src.common.logging import get_logger

log = get_logger(__name__)

def _safe_div(a, b):
    b = np.where(b == 0, 1.0, b)
    return a / b

def build_features(data: dict, graphs: dict, comm: dict, cfg: dict) -> pd.DataFrame:
    comments: pd.DataFrame = data["comments"]
    G_u: nx.DiGraph = graphs["user_graph"]
    cmap = comm.get("community_map", {})

    # --- activity ---
    comments_made = comments.groupby("user_id").size().rename("comments_made")

    # --- engagement proxy ---
    likes_sum = comments.groupby("user_id")["likes"].sum().rename("likes_sum")
    likes_avg = comments.groupby("user_id")["likes"].mean().rename("likes_avg")

    # --- label ratios ---
    label_counts = pd.crosstab(comments["user_id"], comments["label_primary"])
    for col in ["Normal", "Hate", "Disinfo", "Hate+Disinfo"]:
        if col not in label_counts.columns:
            label_counts[col] = 0
    label_counts = label_counts[["Normal", "Hate", "Disinfo", "Hate+Disinfo"]]
    label_counts.columns = [f"cnt_{c}" for c in label_counts.columns]
    label_counts["cnt_total"] = label_counts.sum(axis=1)

    disinfo_ratio = (
        (label_counts["cnt_Disinfo"] + label_counts["cnt_Hate+Disinfo"])
        / label_counts["cnt_total"].replace(0, 1)
    ).rename("disinfo_ratio")

    hate_ratio = (
        (label_counts["cnt_Hate"] + label_counts["cnt_Hate+Disinfo"])
        / label_counts["cnt_total"].replace(0, 1)
    ).rename("hate_ratio")

    # --- harmful ratio (binary) ---
    harmful_ratio = comments.groupby("user_id")["is_harmful"].mean().rename("harmful_ratio")

    # --- topic entropy (diversity of topics a user engages in) ---
    topic_ct = pd.crosstab(comments["user_id"], comments["topic"]).astype(float)
    topic_p = topic_ct.div(topic_ct.sum(axis=1).replace(0, 1), axis=0)
    topic_entropy = -(topic_p * np.log(topic_p.replace(0, 1))).sum(axis=1).rename("topic_entropy")

    # --- temporal burstiness: std/mean of daily activity ---
    bucket = int(cfg["features"].get("time_bucket_seconds", 86400))
    tmp = comments[["user_id", "timestamp"]].copy()
    tmp["day_bucket"] = (tmp["timestamp"] // bucket).astype(int)
    daily = tmp.groupby(["user_id", "day_bucket"]).size().rename("daily_cnt").reset_index()
    burst = daily.groupby("user_id")["daily_cnt"].agg(["mean", "std"]).fillna(0)
    burstiness = (_safe_div(burst["std"].values, burst["mean"].values)).astype(float)
    burstiness = pd.Series(burstiness, index=burst.index, name="burstiness")

    # --- graph metrics (influence proxies) ---
    if G_u.number_of_edges() > 0:
        pr = nx.pagerank(G_u, weight="weight")
        in_w = dict(G_u.in_degree(weight="weight"))
        out_w = dict(G_u.out_degree(weight="weight"))
    else:
        pr, in_w, out_w = {}, {}, {}

    users = sorted(comments["user_id"].unique().tolist())
    df = pd.DataFrame({"user_id": users})

    df = df.merge(comments_made.reset_index(), on="user_id", how="left")
    df = df.merge(likes_sum.reset_index(), on="user_id", how="left")
    df = df.merge(likes_avg.reset_index(), on="user_id", how="left")
    df = df.merge(harmful_ratio.reset_index(), on="user_id", how="left")
    df = df.merge(topic_entropy.reset_index(), on="user_id", how="left")
    df = df.merge(burstiness.reset_index(), on="user_id", how="left")
    df = df.fillna(0)

    df["pagerank"] = df["user_id"].map(lambda u: pr.get(f"user:{u}", 0.0))
    df["in_weight"] = df["user_id"].map(lambda u: float(in_w.get(f"user:{u}", 0.0)))
    df["out_weight"] = df["user_id"].map(lambda u: float(out_w.get(f"user:{u}", 0.0)))

    # label ratios
    df = df.merge(disinfo_ratio.reset_index(), on="user_id", how="left").fillna(0)
    df = df.merge(hate_ratio.reset_index(), on="user_id", how="left").fillna(0)

    # community id (integrated with modelling)
    df["community_id"] = df["user_id"].map(lambda u: cmap.get(f"user:{u}", -1))

    log.info(f"Features built: users={len(df):,}, cols={df.shape[1]}")
    return df