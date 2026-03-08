import sys
from pathlib import Path

# Add parent directory to path so src module can be imported
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.common.utils import load_yaml
from src.pipeline.load_data import load_inputs
from src.pipeline.preprocess import preprocess
from src.pipeline.graph_build import build_graphs
from src.pipeline.community import detect_communities
from src.pipeline.features import build_features
from src.pipeline.scoring import compute_risk_scores
from src.pipeline.active_learning import build_moderation_queue
from src.pipeline.export import export_artifacts
from src.gnn.dataset import build_pyg_dataset
from src.gnn.train import train_graphsage, gnn_risk_scores
from src.synthetic.synthetic_data import load_synthetic_dataset


def main():

    cfg = load_yaml(REPO_ROOT / "config/pipeline.yaml")

    mode = cfg["data_mode"]["source"].strip().lower()

    if mode == "synthetic":
        data = preprocess(load_synthetic_dataset(REPO_ROOT, cfg))
    else:
        data = preprocess(load_inputs(REPO_ROOT))

    graphs = build_graphs(data, cfg)

    comm = detect_communities(graphs)

    feats = build_features(data, graphs, comm, cfg)

    pyg_data = build_pyg_dataset(graphs, feats)

    print("GNN dataset:")
    print(" nodes:", pyg_data.num_nodes)
    print(" edges:", pyg_data.num_edges)

    model, gnn_metrics = train_graphsage(pyg_data, epochs=50)
    feats["gnn_risk_score"] = gnn_risk_scores(model, pyg_data)

    print("GNN metrics (internal):", gnn_metrics)
    print(feats[["user_id", "gnn_risk_score"]].head(5))

    scored = compute_risk_scores(feats, cfg)

    print("Risk score type:", scored["risk_score_type"].iloc[0])
    print(scored.sort_values("risk_score", ascending=False)[["user_id","risk_level","risk_score","risk_score_base","gnn_risk_score"]].head(10))

    queue = build_moderation_queue(scored, cfg)

    print("\nModerator Queue (Top 10)\n")
    print(queue[["user_id","priority_score","uncertainty","influence_score","gnn_risk_score","risk_score"]].head(10))

    export_artifacts(REPO_ROOT, data, graphs, scored, queue, comm)

    real_scored = scored[~scored["user_id"].astype(str).str.startswith("synth_")].copy()
    real_queue = queue[~queue["user_id"].astype(str).str.startswith("synth_")].copy()

    print("\nTop High Risk Users\n")
    print(
        real_scored.sort_values("risk_score", ascending=False)[
            ["user_id", "risk_level", "risk_score", "risk_score_base", "gnn_risk_score"]
        ].head(10)
    )

    print("\nModerator Queue (Top 10)\n")
    print(
        real_queue[
            ["user_id", "priority_score", "uncertainty", "influence_score", "gnn_risk_score", "risk_score"]
        ].head(10)
    )


if __name__ == "__main__":
    main()