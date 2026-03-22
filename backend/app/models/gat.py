"""Graph Attention Network — from GNNReactivityRatioPrediction notebook.

Two variants: MIMO (→ 2) and MISO (→ 1).

Uses GATConv from torch_geometric with multi-head attention, edge features,
residual connections, and global mean + max pooling.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from torch_geometric.nn import GATConv, global_mean_pool, global_max_pool
    from torch_geometric.data import Data, Batch
    HAS_PYG = True
except ImportError:
    HAS_PYG = False


class GATBlock(nn.Module):
    """Single GAT block with residual + LayerNorm."""

    def __init__(self, in_channels: int, out_channels: int, heads: int = 4,
                 edge_dim: int = 13, dropout: float = 0.2):
        super().__init__()
        self.conv = GATConv(in_channels, out_channels, heads=heads,
                            edge_dim=edge_dim, dropout=dropout, concat=True)
        self.norm = nn.LayerNorm(out_channels * heads)
        self.proj = nn.Linear(in_channels, out_channels * heads) if in_channels != out_channels * heads else nn.Identity()
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, edge_index, edge_attr):
        residual = self.proj(x)
        x = self.conv(x, edge_index, edge_attr=edge_attr)
        x = self.norm(x + residual)
        x = F.relu(x)
        x = self.dropout(x)
        return x


class ReactivityGAT(nn.Module):
    """Multi-layer GAT for monomer-pair reactivity ratio prediction.

    The pair is fed as a single graph with both monomers' atoms.
    """

    def __init__(
        self,
        node_dim: int = 58,
        edge_dim: int = 13,
        global_dim: int = 7,
        hidden_dim: int = 64,
        heads: int = 4,
        num_gat_layers: int = 3,
        output_dim: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.node_proj = nn.Linear(node_dim, hidden_dim)
        self.gat_layers = nn.ModuleList()
        for _ in range(num_gat_layers):
            self.gat_layers.append(GATBlock(hidden_dim * heads if _ > 0 else hidden_dim,
                                            hidden_dim, heads=heads,
                                            edge_dim=edge_dim, dropout=dropout))

        pool_dim = hidden_dim * heads * 2  # mean + max
        combined_dim = pool_dim + global_dim * 2  # global features for each monomer

        self.fc = nn.Sequential(
            nn.Linear(combined_dim, 256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim),
        )

    def forward(self, data):
        x, edge_index, edge_attr = data.x, data.edge_index, data.edge_attr
        batch = data.batch if hasattr(data, "batch") else torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        x = self.node_proj(x)
        for layer in self.gat_layers:
            x = layer(x, edge_index, edge_attr)

        # Global pooling
        mean_pool = global_mean_pool(x, batch)
        max_pool = global_max_pool(x, batch)
        graph_repr = torch.cat([mean_pool, max_pool], dim=-1)

        # Append global features if present
        if hasattr(data, "global_features"):
            graph_repr = torch.cat([graph_repr, data.global_features], dim=-1)

        return self.fc(graph_repr)


class ReactivityGATMISO(ReactivityGAT):
    """Single-output variant."""

    def __init__(self, **kwargs):
        kwargs["output_dim"] = 1
        super().__init__(**kwargs)


# ──────────────────────────────────────────────────────────────────────
#  Utility: dict → PyG Data object
# ──────────────────────────────────────────────────────────────────────
def graph_dict_to_pyg(graph_a: dict, graph_b: dict, device: str = "cpu") -> "Data":
    """Combine two monomer graphs into a single pair Data object."""
    if not HAS_PYG:
        raise ImportError("torch_geometric is required for GAT models")

    n_a = graph_a["node_features"].shape[0]

    # Shift B's edge indices
    ei_a = torch.tensor(graph_a["edge_index"], dtype=torch.long)
    ei_b = torch.tensor(graph_b["edge_index"], dtype=torch.long) + n_a
    edge_index = torch.cat([ei_a, ei_b], dim=1)

    node_feats = torch.cat([
        torch.tensor(graph_a["node_features"]),
        torch.tensor(graph_b["node_features"]),
    ], dim=0)

    edge_attr = torch.cat([
        torch.tensor(graph_a["edge_attr"]),
        torch.tensor(graph_b["edge_attr"]),
    ], dim=0)

    global_feats = torch.cat([
        torch.tensor(graph_a["global_features"]),
        torch.tensor(graph_b["global_features"]),
    ]).unsqueeze(0)

    data = Data(
        x=node_feats.to(device),
        edge_index=edge_index.to(device),
        edge_attr=edge_attr.to(device),
    )
    data.global_features = global_feats.to(device)
    return data
