from __future__ import annotations
import random
import networkx as nx
from src.common.logging import get_logger

log = get_logger(__name__)

def generate_synthetic_follow_graph(cfg: dict) -> nx.DiGraph:
    s = cfg["synthetic_follow_graph"]
    n = int(s["num_users"])
    seed = int(s.get("seed", 42))
    model = str(s.get("model", "ba")).lower()
    avg_degree = int(s.get("avg_degree", 12))

    random.seed(seed)

    # Generate an undirected structure then convert to directed follow edges
    if model == "ba":
        # Preferential attachment: choose m so average degree ~ 2m
        m = max(1, avg_degree // 2)
        G0 = nx.barabasi_albert_graph(n=n, m=m, seed=seed)
        gen_name = f"BA(n={n},m={m})"
    elif model == "ws":
        # Small-world: k must be even
        k = max(2, avg_degree if avg_degree % 2 == 0 else avg_degree + 1)
        p = 0.1
        G0 = nx.watts_strogatz_graph(n=n, k=k, p=p, seed=seed)
        gen_name = f"WS(n={n},k={k},p={p})"
    else:
        raise ValueError("synthetic_follow_graph.model must be 'ba' or 'ws'")

    G = nx.DiGraph()

    # Users as user:<id> to match your existing graph naming
    for i in range(n):
        G.add_node(f"user:synth_{i}", ntype="user", synthetic=True)

    # Convert undirected edges into directed "follow" edges in random direction(s)
    for u, v in G0.edges():
        uu = f"user:synth_{u}"
        vv = f"user:synth_{v}"
        # Either one direction or both; use one direction to mimic follower structure
        if random.random() < 0.5:
            G.add_edge(uu, vv, etype="follow", weight=1.0, synthetic=True)
        else:
            G.add_edge(vv, uu, etype="follow", weight=1.0, synthetic=True)

    log.info(f"Synthetic follow graph generated: {gen_name}, nodes={G.number_of_nodes()}, edges={G.number_of_edges()}")
    return G