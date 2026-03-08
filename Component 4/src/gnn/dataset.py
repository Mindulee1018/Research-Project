from __future__ import annotations
import torch
import numpy as np
import pandas as pd
import networkx as nx
from torch_geometric.data import Data

from src.common.logging import get_logger

log = get_logger(__name__)


FEATURE_COLS = [
    "pagerank",
    "in_weight",
    "out_weight",
    "likes_sum",
    "likes_avg",
    "comments_made",
    "disinfo_ratio",
    "hate_ratio",
    "topic_entropy",
    "burstiness",
]


def build_pyg_dataset(graphs: dict, features: pd.DataFrame) -> Data:

    G: nx.DiGraph = graphs["user_graph"]

    # map user_id → node index
    users = features["user_id"].tolist()
    node_map = {f"user:{u}": i for i, u in enumerate(users)}

    # --- node features ---
    X = features[FEATURE_COLS].fillna(0).values
    x = torch.tensor(X, dtype=torch.float)

    # --- edges ---
    edges = []
    for src, dst in G.edges():
        if src in node_map and dst in node_map:
            edges.append([node_map[src], node_map[dst]])

    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()

    # --- labels (proxy) ---
    # IMPORTANT: for development only. Real labels come from moderation/ground-truth later.
    y = (features["disinfo_ratio"] > 0.3).astype(int).values
    y = torch.tensor(y, dtype=torch.long)

    # --- mask: exclude synthetic accounts from training/validation/test splits ---
    # (keep them in graph for inference, but do not let them dominate learning)
    is_synth = features["user_id"].astype(str).str.startswith("user_synth_").values
    trainable_mask = torch.tensor(~is_synth, dtype=torch.bool)

    data = Data(x=x, edge_index=edge_index, y=y)
    data.trainable_mask = trainable_mask


    log.info(
        f"PyG dataset created: nodes={data.num_nodes}, edges={data.num_edges}"
    )

    return data