from __future__ import annotations
import numpy as np
import pandas as pd
from src.common.logging import get_logger

log = get_logger(__name__)

def gnn_uncertainty(p: np.ndarray) -> np.ndarray:
    """
    Uncertainty is highest at p=0.5 and lowest near 0 or 1.
    Returns values in [0, 1].
    """
    p = np.clip(p.astype(float), 0.0, 1.0)
    return 1.0 - (np.abs(p - 0.5) * 2.0)

def build_moderation_queue(scored: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = scored.copy()

    mix = cfg["active_learning"]["priority_mix"]
    w_u = float(mix["uncertainty"])
    w_i = float(mix["influence"])

    if "gnn_risk_score" in df.columns:
        u = gnn_uncertainty(df["gnn_risk_score"].values)
        df["uncertainty"] = u
        df["priority_reason"] = "gnn_ambiguity_x_influence"
    else:
        # fallback: if GNN isn't available, uncertainty can't be computed reliably
        df["uncertainty"] = 0.0
        df["priority_reason"] = "influence_only(no_gnn)"

    df["priority_score"] = w_u * df["uncertainty"] + w_i * df["influence_score"]

    queue = df.sort_values("priority_score", ascending=False).copy()

    log.info("Moderation queue generated (GNN uncertainty + influence)")
    return queue