from __future__ import annotations
from pathlib import Path
import pandas as pd
import json
from src.common.logging import get_logger

log = get_logger(__name__)

def export_artifacts(repo_root: Path, data: dict, graphs: dict, scored: pd.DataFrame, queue: pd.DataFrame, comm: dict):
    out = repo_root / "data/artifacts"
    out.mkdir(exist_ok=True)

    # ---- user risk scores (for dashboard + integration) ----
    keep_cols = [
        "user_id",
        "risk_level",
        "risk_score_type",
        "risk_score",
        "risk_score_base",
        "influence_score",
        "exposure_score",
        "activity_score",
        "pagerank",
        "in_weight",
        "out_weight",
        "comments_made",
        "likes_sum",
        "disinfo_ratio",
        "hate_ratio",
        "community_id",
    ]
    if "gnn_risk_score" in scored.columns:
        keep_cols.append("gnn_risk_score")
    if "gnn_risk_norm" in scored.columns:
        keep_cols.append("gnn_risk_norm")

    scored_out = scored.copy()
    scored_out = scored_out[[c for c in keep_cols if c in scored_out.columns]]

    # remove synthetic users from final exported ranking
    scored_out = scored_out[~scored_out["user_id"].astype(str).str.startswith("synth_")]

    scored_out.sort_values("risk_score", ascending=False).to_csv(
        out / "user_risk_scores.csv", index=False
    )

    # ---- moderation queue ----
    queue_cols = [
        "user_id",
        "priority_reason",
        "priority_score",
        "uncertainty",
        "influence_score",
        "risk_score",
        "risk_level",
    ]
    if "gnn_risk_score" in queue.columns:
        queue_cols.append("gnn_risk_score")

    queue_out = queue.copy()
    queue_out = queue_out[[c for c in queue_cols if c in queue_out.columns]]

    # remove synthetic users from final exported queue
    queue_out = queue_out[~queue_out["user_id"].astype(str).str.startswith("synth_")]

    queue_out.to_csv(out / "moderation_queue.csv", index=False)

    # ---- community summary ----
    cmap = comm.get("community_map", {})
    df = scored.copy()
    df["community_id"] = df["user_id"].map(lambda u: cmap.get(f"user:{u}", -1))

    # only real users for exported reporting
    df = df[~df["user_id"].astype(str).str.startswith("synth_")].copy()

    comm_summary = (
        df.groupby("community_id")
        .agg(
            users=("user_id", "count"),
            mean_risk=("risk_score", "mean"),
            mean_influence=("influence_score", "mean"),
            mean_exposure=("exposure_score", "mean"),
        )
        .reset_index()
        .sort_values("mean_risk", ascending=False)
    )

    comm_summary.to_csv(out / "community_summary.csv", index=False)

    # ---- stats ----
    stats = {
        "posts": int(len(data["posts"])),
        "comments": int(len(data["comments"])),
        "user_nodes": int(graphs["user_graph"].number_of_nodes()),
        "user_edges": int(graphs["user_graph"].number_of_edges()),
        "bipartite_nodes": int(graphs["bipartite"].number_of_nodes()),
        "bipartite_edges": int(graphs["bipartite"].number_of_edges()),
        "communities": int(comm_summary["community_id"].nunique()),
        "community_method": comm.get("method", "unknown"),
    }

    with open(out / "graph_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    
    user_graph = graphs["user_graph"]

    edge_rows = []
    for u, v, attrs in user_graph.edges(data=True):
        edge_rows.append({
            "source": u.replace("user:", ""),
            "target": v.replace("user:", ""),
            "weight": float(attrs.get("weight", 1.0)),
            "etype": attrs.get("etype", "unknown"),
        })

    edge_df = pd.DataFrame(edge_rows)

    # keep only strongest edges for visualization performance
    if not edge_df.empty:
        edge_df = edge_df.sort_values("weight", ascending=False).head(1500)

    edge_df.to_csv(out / "graph_edges.csv", index=False)

    log.info("Artifacts exported (with GNN + queue fields)")