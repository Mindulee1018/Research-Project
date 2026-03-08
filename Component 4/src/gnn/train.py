from __future__ import annotations
import numpy as np
import torch
import torch.nn.functional as F
from torch_geometric.data import Data

from src.common.logging import get_logger
from src.gnn.model import GraphSAGE

log = get_logger(__name__)

def train_graphsage(
    data: Data,
    epochs: int = 50,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    hidden_channels: int = 64,
    seed: int = 42
) -> tuple[GraphSAGE, dict]:

    torch.manual_seed(seed)
    np.random.seed(seed)

    device = torch.device("cpu")
    data = data.to(device)

    # --- split nodes ---
     # --- split only trainable nodes ---
    n = data.num_nodes
    trainable = data.trainable_mask.cpu().numpy()
    trainable_idx = np.where(trainable)[0]

    idx = np.random.permutation(trainable_idx)
    train_end = int(0.7 * len(idx))
    val_end = int(0.85 * len(idx))

    train_idx = torch.tensor(idx[:train_end], dtype=torch.long, device=device)
    val_idx = torch.tensor(idx[train_end:val_end], dtype=torch.long, device=device)
    test_idx = torch.tensor(idx[val_end:], dtype=torch.long, device=device)

    model = GraphSAGE(in_channels=data.num_node_features, hidden_channels=hidden_channels).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    best_val_loss = float("inf")
    best_state = None

    for epoch in range(1, epochs + 1):
        model.train()
        opt.zero_grad()

        out = model(data.x, data.edge_index)
        loss = F.cross_entropy(out[train_idx], data.y[train_idx])
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            out = model(data.x, data.edge_index)
            val_loss = F.cross_entropy(out[val_idx], data.y[val_idx]).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch % 10 == 0:
            log.info(f"GNN epoch {epoch:03d} | train_loss={loss.item():.4f} | val_loss={val_loss:.4f}")

    if best_state is not None:
        model.load_state_dict(best_state)

    # quick diagnostic (not for panel reporting if you prefer)
    model.eval()
    with torch.no_grad():
        logits = model(data.x, data.edge_index)
        pred = logits.argmax(dim=1)
        test_acc = (pred[test_idx] == data.y[test_idx]).float().mean().item()

    metrics = {"best_val_loss": best_val_loss, "test_acc_proxy": test_acc}
    log.info(f"GNN training done | best_val_loss={best_val_loss:.4f} | test_acc(proxy)={test_acc:.3f}")

    return model, metrics


def gnn_risk_scores(model: GraphSAGE, data: Data) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        logits = model(data.x, data.edge_index)
        probs = torch.softmax(logits, dim=1)[:, 1]  # probability of high-risk class
    return probs.cpu().numpy()