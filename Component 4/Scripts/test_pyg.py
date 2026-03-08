import torch
from torch_geometric.nn import SAGEConv

print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())

# quick layer init to verify pyg import works
conv = SAGEConv(in_channels=8, out_channels=16)
x = torch.randn(10, 8)
edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)
out = conv(x, edge_index)
print("pyg ok, output shape:", out.shape)