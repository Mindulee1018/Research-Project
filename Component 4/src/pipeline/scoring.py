from __future__ import annotations
import numpy as np
import pandas as pd
from src.common.logging import get_logger

log = get_logger(__name__)

def normalize(x: np.ndarray) -> np.ndarray:
    x = x.astype(float)
    mn, mx = np.min(x), np.max(x)
    if mx == mn:
        return np.zeros_like(x)
    return (x - mn) / (mx - mn)

def compute_risk_scores(features: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = features.copy()

    # ---- Influence score (graph importance) ----
    influence = (
        0.5 * normalize(df["pagerank"].values)
        + 0.3 * normalize(df["in_weight"].values)
        + 0.2 * normalize(df["likes_sum"].values)
    )

    # ---- Exposure score (disinformation behaviour) ----
    exposure = (
        0.6 * normalize(df["disinfo_ratio"].values)
        + 0.4 * normalize(df["hate_ratio"].values)
    )

    # ---- Activity score ----
    activity = (
        0.7 * normalize(df["comments_made"].values)
        + 0.3 * normalize(df["burstiness"].values)
    )

    df["influence_score"] = influence
    df["exposure_score"] = exposure
    df["activity_score"] = activity

    w = cfg["risk_scoring"]["weights"]

    # baseline risk score (no GNN)
    df["risk_score_base"] = (
        w["influence"] * df["influence_score"]
        + w["exposure"] * df["exposure_score"]
        + w["activity"] * df["activity_score"]
    )

    # ---- If GNN score exists, blend it in ----
    if "gnn_risk_score" in df.columns:
        gnn_norm = normalize(df["gnn_risk_score"].values)
        df["gnn_risk_norm"] = gnn_norm

        # panel-friendly: keep this as "hybrid score"
        # (no claiming exact optimal weights)
        df["risk_score"] = 0.75 * df["risk_score_base"] + 0.25 * df["gnn_risk_norm"]
        df["risk_score_type"] = "hybrid(base+gnn)"
    else:
        df["risk_score"] = df["risk_score_base"]
        df["risk_score_type"] = "baseline(graph+behavior)"

    # ---- Risk categories ----
    high = cfg["risk_scoring"]["risk_buckets"]["high"]
    med = cfg["risk_scoring"]["risk_buckets"]["medium"]

    df["risk_level"] = np.select(
        [df["risk_score"] >= high, df["risk_score"] >= med],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )

    log.info(f"Risk scoring completed ({df['risk_score_type'].iloc[0]})")
    return df