from __future__ import annotations
import networkx as nx
import numpy as np
import pandas as pd

from src.common.logging import get_logger
from src.synthetic.follow_graph import generate_synthetic_follow_graph
log = get_logger(__name__)

def build_graphs(data: dict, cfg: dict) -> dict:
    posts: pd.DataFrame = data["posts"]
    comments: pd.DataFrame = data["comments"]

    # --- Graph A: bipartite user-post ---
    G_bi = nx.Graph()
    for _, p in posts.iterrows():
        G_bi.add_node(f"post:{p['post_id']}", ntype="post", post_label=p.get("post_label", "Unknown"))

    for _, c in comments.iterrows():
        u = f"user:{c['user_id']}"
        p = f"post:{c['post_id']}"
        G_bi.add_node(u, ntype="user")

        w = float(c.get("likes", 0)) + 1.0
        if G_bi.has_edge(u, p):
            G_bi[u][p]["weight"] += w
            G_bi[u][p]["count"] += 1
        else:
            G_bi.add_edge(u, p, etype="commented", weight=w, count=1)

    # --- Graph B: user-user derived graph ---
    G_u = nx.DiGraph()
    users = comments["user_id"].unique().tolist()
    for uid in users:
        G_u.add_node(f"user:{uid}", ntype="user")

    # 1) Co-engagement edges (users on same post)
    if cfg["graph"]["co_engagement"]["enabled"]:
        min_shared = int(cfg["graph"]["co_engagement"].get("min_shared_posts", 2))
        grouped = comments.groupby("post_id")["user_id"].apply(lambda x: list(dict.fromkeys(x.tolist())))
        shared = {}

        for _, ulist in grouped.items():
            for i in range(len(ulist)):
                for j in range(i + 1, len(ulist)):
                    a, b = ulist[i], ulist[j]
                    key = (a, b) if a < b else (b, a)
                    shared[key] = shared.get(key, 0) + 1

        for (a, b), cnt in shared.items():
            if cnt >= min_shared:
                # add both directions to keep user graph directed but symmetric here
                G_u.add_edge(f"user:{a}", f"user:{b}", etype="co_engage", weight=float(cnt))
                G_u.add_edge(f"user:{b}", f"user:{a}", etype="co_engage", weight=float(cnt))

    # 2) Temporal co-activity edges (same post within window)
    if cfg["graph"]["temporal_coactivity"]["enabled"]:
        window = int(cfg["graph"]["temporal_coactivity"].get("window_seconds", 3600))
        for _, dfp in comments.sort_values("timestamp").groupby("post_id"):
            rows = dfp[["user_id", "timestamp"]].values.tolist()
            for i in range(len(rows)):
                ui, ti = rows[i]
                j = i + 1
                while j < len(rows) and (rows[j][1] - ti) <= window:
                    uj, _ = rows[j]
                    if ui != uj:
                        src, dst = f"user:{ui}", f"user:{uj}"
                        if G_u.has_edge(src, dst):
                            G_u[src][dst]["weight"] += 0.25
                        else:
                            G_u.add_edge(src, dst, etype="temporal", weight=0.25)
                    j += 1

    # 3) Topic similarity edges (cosine similarity)
    if cfg["graph"]["topic_similarity"]["enabled"]:
        min_cos = float(cfg["graph"]["topic_similarity"].get("min_cosine", 0.25))
        user_topic = pd.crosstab(comments["user_id"], comments["topic"]).astype(float)
        mat = user_topic.values
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms
        ids = user_topic.index.tolist()
        n = len(ids)

        # sample pairs to keep it fast
        max_pairs = min(25000, n * (n - 1) // 2)
        rng = np.random.default_rng(int(cfg["general"]["random_seed"]))
        pairs = set()
        while len(pairs) < max_pairs and n > 1:
            i = int(rng.integers(0, n))
            j = int(rng.integers(0, n))
            if i == j:
                continue
            a, b = (i, j) if i < j else (j, i)
            pairs.add((a, b))

        for i, j in pairs:
            cos = float(np.dot(mat[i], mat[j]))
            if cos >= min_cos:
                a, b = ids[i], ids[j]
                G_u.add_edge(f"user:{a}", f"user:{b}", etype="topic", weight=cos)
                G_u.add_edge(f"user:{b}", f"user:{a}", etype="topic", weight=cos)

    log.info(
        f"Built graphs: bipartite nodes={G_bi.number_of_nodes():,} edges={G_bi.number_of_edges():,} | "
        f"user_graph nodes={G_u.number_of_nodes():,} edges={G_u.number_of_edges():,}"
    )
     # --- add synthetic follow edges for stress-test / robustness experiments ---
    s_cfg = cfg.get("synthetic_follow_graph", {})
    if s_cfg.get("enabled", False):
        G_follow = generate_synthetic_follow_graph(cfg)

        # Merge synthetic follow graph into user graph
        # NOTE: synthetic users are separate namespace (user:synth_*)
        for n, attrs in G_follow.nodes(data=True):
            if not G_u.has_node(n):
                G_u.add_node(n, **attrs)

        for u, v, attrs in G_follow.edges(data=True):
            if G_u.has_edge(u, v):
                # keep existing edge weight + small addition
                G_u[u][v]["weight"] = float(G_u[u][v].get("weight", 0.0)) + 0.1
                G_u[u][v]["synthetic_follow_added"] = True
            else:
                G_u.add_edge(u, v, **attrs)
                G_u[u][v]["etype"] = "follow_synth"
                G_u[u][v]["weight"] = float(G_u[u][v].get("weight", 1.0))
                G_u[u][v]["synthetic_follow_added"] = True

        log.info(
            f"Injected synthetic follow edges: +nodes={G_follow.number_of_nodes():,}, +edges={G_follow.number_of_edges():,}"
        )
    return {"bipartite": G_bi, "user_graph": G_u}