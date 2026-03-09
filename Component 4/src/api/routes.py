from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter()

def _artifact_dir(repo_root: Path) -> Path:
    return repo_root / "data" / "artifacts"

def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing artifact: {path.name}. Run pipeline first.")
    df = pd.read_csv(path)
    return df.to_dict(orient="records")

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/stats")
def stats():
    # graph_stats.json
    # (always produced by your pipeline export step)
    from src.api.main import REPO_ROOT  # safe here (single-process dev)
    p = _artifact_dir(REPO_ROOT) / "graph_stats.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Missing graph_stats.json. Run pipeline first.")
    return json.loads(p.read_text(encoding="utf-8"))

@router.get("/risk/top")
def risk_top(k: int = 20):
    from src.api.main import REPO_ROOT
    rows = _read_csv(_artifact_dir(REPO_ROOT) / "user_risk_scores.csv")
    return {"k": k, "rows": rows[:k]}

@router.get("/queue/top")
def queue_top(k: int = 20):
    from src.api.main import REPO_ROOT
    rows = _read_csv(_artifact_dir(REPO_ROOT) / "moderation_queue.csv")
    return {"k": k, "rows": rows[:k]}

@router.get("/communities/top")
def communities_top(k: int = 20):
    from src.api.main import REPO_ROOT
    rows = _read_csv(_artifact_dir(REPO_ROOT) / "community_summary.csv")
    return {"k": k, "rows": rows[:k]}

@router.get("/graph/sample")
def graph_sample(k: int = 25, neighbor_limit: int = 2):
    from src.api.main import REPO_ROOT

    risk_path = _artifact_dir(REPO_ROOT) / "user_risk_scores.csv"
    edge_path = _artifact_dir(REPO_ROOT) / "graph_edges.csv"

    if not risk_path.exists():
        raise HTTPException(status_code=404, detail="Missing user_risk_scores.csv. Run pipeline first.")
    if not edge_path.exists():
        raise HTTPException(status_code=404, detail="Missing graph_edges.csv. Run pipeline first.")

    risk_df = pd.read_csv(risk_path)
    edge_df = pd.read_csv(edge_path)

    # real users only
    risk_df = risk_df[~risk_df["user_id"].astype(str).str.startswith("synth_")].copy()
    edge_df = edge_df[
        ~edge_df["source"].astype(str).str.startswith("synth_") &
        ~edge_df["target"].astype(str).str.startswith("synth_")
    ].copy()

    risk_df["user_id"] = risk_df["user_id"].astype(str)
    edge_df["source"] = edge_df["source"].astype(str)
    edge_df["target"] = edge_df["target"].astype(str)

    # 1) seed nodes = top-k by risk
    top_users = risk_df.sort_values("risk_score", ascending=False).head(k).copy()
    seed_ids = set(top_users["user_id"].tolist())

    # 2) include strongest neighbors of seeds
    neighbor_rows = []
    for uid in seed_ids:
        edges_for_uid = edge_df[(edge_df["source"] == uid) | (edge_df["target"] == uid)].copy()
        edges_for_uid = edges_for_uid.sort_values("weight", ascending=False).head(neighbor_limit)
        neighbor_rows.append(edges_for_uid)

    if neighbor_rows:
        expanded_edges = pd.concat(neighbor_rows, ignore_index=True).drop_duplicates()
    else:
        expanded_edges = edge_df.head(0).copy()

    expanded_node_ids = set(seed_ids)
    expanded_node_ids.update(expanded_edges["source"].tolist())
    expanded_node_ids.update(expanded_edges["target"].tolist())

    node_df = risk_df[risk_df["user_id"].isin(expanded_node_ids)].copy()

    # keep only edges inside expanded node set
    sub_edges = edge_df[
        edge_df["source"].isin(expanded_node_ids) &
        edge_df["target"].isin(expanded_node_ids)
    ].copy()

    # strongest subset for UI clarity
    sub_edges = sub_edges.sort_values("weight", ascending=False).head(250)

    nodes = []
    for _, row in node_df.iterrows():
        nodes.append({
            "id": str(row["user_id"]),
            "community": int(row.get("community_id", -1)),
            "risk_score": float(row.get("risk_score", 0)),
            "risk_level": str(row.get("risk_level", "LOW")),
            "influence_score": float(row.get("influence_score", 0)),
            "exposure_score": float(row.get("exposure_score", 0)),
            "gnn_risk_score": float(row.get("gnn_risk_score", 0)) if "gnn_risk_score" in row else 0.0,
        })

    links = []
    for _, row in sub_edges.iterrows():
        links.append({
            "source": str(row["source"]),
            "target": str(row["target"]),
            "weight": float(row.get("weight", 1.0)),
            "etype": str(row.get("etype", "unknown")),
        })

    return {"nodes": nodes, "links": links}

    return {"nodes": nodes, "links": links}