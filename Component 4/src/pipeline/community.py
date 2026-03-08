from __future__ import annotations
import networkx as nx
from src.common.logging import get_logger

log = get_logger(__name__)

def detect_communities(graphs: dict) -> dict:
    G_u: nx.DiGraph = graphs["user_graph"]
    if G_u.number_of_nodes() == 0:
        return {"community_map": {}, "method": "none"}

    G = G_u.to_undirected()

    # Try Louvain if installed; otherwise fallback to greedy modularity
    try:
        import community as community_louvain  # python-louvain package
        part = community_louvain.best_partition(G, weight="weight")
        method = "louvain"
    except Exception:
        from networkx.algorithms.community import greedy_modularity_communities
        comms = list(greedy_modularity_communities(G))
        part = {}
        for i, c in enumerate(comms):
            for node in c:
                part[node] = i
        method = "greedy_modularity"

    log.info(f"Community detection complete: method={method}, communities={len(set(part.values())):,}")
    return {"community_map": part, "method": method}