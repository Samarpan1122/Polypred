"""Benchmark model architectures — exact replicas from Specific_Models_Final notebooks.

These classes must match the architectures used in notebooks so that saved
state_dict weights can be loaded correctly.
"""

import torch
import torch.nn as nn

try:
    from torch_geometric.nn import GATConv, global_mean_pool, GlobalAttention, GCNConv, VGAE
    from torch_geometric.data import Data
    HAS_PYG = True
except ImportError:
    HAS_PYG = False

# Must match the feature engineering pipeline (feature_engineering.py)
NODE_DIM = 58   # atom feature vector dimensionality
GLOBAL_DIM = 7  # molecular-level feature dimensionality


# ──────────────────────────────────────────────────────────────────────
#  SMILES tokenizer for LSTM-based models
# ──────────────────────────────────────────────────────────────────────
# Fixed vocabulary built from sorted unique chars in common SMILES.
# Must match the vocabulary used during training (sorted chars, 1-indexed, 0=pad).
SMILES_CHARS = sorted(list(
    "#()+-.1234=BCFHIKNOPS[]aeilnr"
))
SMILES_VOCAB = {c: i + 1 for i, c in enumerate(SMILES_CHARS)}
SMILES_VOCAB_SIZE = len(SMILES_VOCAB) + 1  # +1 for padding index 0
SMILES_MAX_LEN = 150


def encode_smiles(smiles: str, max_len: int = SMILES_MAX_LEN) -> torch.Tensor:
    """Convert a SMILES string to integer token tensor."""
    s = str(smiles)[:max_len]
    ids = [SMILES_VOCAB.get(c, 0) for c in s]
    ids = ids + [0] * (max_len - len(ids))
    return torch.tensor(ids, dtype=torch.long)


def graph_dict_to_single_pyg(graph: dict, device: str = "cpu") -> "Data":
    """Convert a single monomer graph dict → PyG Data object."""
    if not HAS_PYG:
        raise ImportError("torch_geometric is required for benchmark graph models")

    data = Data(
        x=torch.tensor(graph["node_features"], dtype=torch.float).to(device),
        edge_index=torch.tensor(graph["edge_index"], dtype=torch.long).to(device),
        edge_attr=torch.tensor(graph["edge_attr"], dtype=torch.float).to(device),
    )
    data.global_features = torch.tensor(
        graph["global_features"], dtype=torch.float
    ).to(device)
    return data


# ──────────────────────────────────────────────────────────────────────
#  1. Siamese+LSTM main model (SiameseGATArm + PolyPredict)
# ──────────────────────────────────────────────────────────────────────
class SiameseGATArm(nn.Module):
    """Deep 4-layer GAT encoder per monomer (from Siamese_plus_LSTM notebook)."""

    def __init__(self, in_ch=NODE_DIM, h=64, out=128, global_dim=GLOBAL_DIM):
        super().__init__()
        self.gat1 = GATConv(in_ch, h, heads=4, dropout=0.1)
        self.bn1 = nn.BatchNorm1d(h * 4)
        self.gat2 = GATConv(h * 4, h, heads=4, dropout=0.1)
        self.bn2 = nn.BatchNorm1d(h * 4)
        self.gat3 = GATConv(h * 4, h, heads=4, dropout=0.1)
        self.bn3 = nn.BatchNorm1d(h * 4)
        self.gat4 = GATConv(h * 4, out, heads=1, dropout=0.1)
        self.bn4 = nn.BatchNorm1d(out)

        self.pool = GlobalAttention(gate_nn=nn.Sequential(
            nn.Linear(out, 32), nn.ReLU(), nn.Linear(32, 1)
        ))

        self.global_dim = global_dim
        if global_dim > 0:
            self.global_proj = nn.Sequential(
                nn.Linear(global_dim, 32), nn.ReLU(), nn.Dropout(0.1)
            )
            self.out_dim = out + 32
        else:
            self.out_dim = out

    def forward(self, data):
        x, ei, batch = data.x, data.edge_index, data.batch
        if batch is None:
            batch = x.new_zeros(x.size(0), dtype=torch.long)

        x1 = torch.relu(self.bn1(self.gat1(x, ei)))
        x2 = torch.relu(self.bn2(self.gat2(x1, ei)))
        x3 = torch.relu(self.bn3(self.gat3(x1 + x2, ei)))  # Residual
        x4 = torch.relu(self.bn4(self.gat4(x3, ei)))

        emb = self.pool(x4, batch)

        if self.global_dim > 0 and hasattr(data, 'global_features'):
            gf = data.global_features.float()
            n_graphs = batch.max().item() + 1
            if gf.dim() == 1:
                gf = gf.view(n_graphs, -1)
            elif gf.shape[0] != n_graphs:
                gf = gf.view(n_graphs, -1)
            gf = self.global_proj(gf)
            emb = torch.cat([emb, gf], dim=-1)

        return emb


class SiameseLSTMPolyPredict(nn.Module):
    """Siamese GAT → BiLSTM → Explicit Difference Fusion → Regression Head."""

    def __init__(self):
        super().__init__()
        self.arm = SiameseGATArm(h=64, out=128)
        arm_out = self.arm.out_dim  # 160

        self.lstm = nn.LSTM(arm_out, 128, num_layers=2,
                            batch_first=True, bidirectional=True, dropout=0.2)

        combined_dim = (128 * 2) + arm_out  # 416

        self.head = nn.Sequential(
            nn.Linear(combined_dim, 256), nn.GELU(), nn.Dropout(0.2),
            nn.Linear(256, 128), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 2)
        )

    def forward(self, dA, dB):
        eA = self.arm(dA)
        eB = self.arm(dB)

        seq = torch.stack([eA, eB], dim=1)
        _, (hn, _) = self.lstm(seq)
        h_lstm = torch.cat([hn[-2], hn[-1]], dim=1)

        diff = torch.abs(eA - eB)

        h = torch.cat([h_lstm, diff], dim=1)
        return self.head(h)


# ──────────────────────────────────────────────────────────────────────
#  2 & 3. Siamese_Regression / Siamese+Bayesian (GNNArm + SiameseRegressor)
# ──────────────────────────────────────────────────────────────────────
class GNNArm(nn.Module):
    """Single arm of the Siamese network — shared weights (2-layer GAT)."""

    def __init__(self, in_ch=NODE_DIM, h=64, out=128):
        super().__init__()
        self.c1 = GATConv(in_ch, h, heads=4, dropout=0.2)
        self.c2 = GATConv(h * 4, out, heads=1, dropout=0.1)
        self.bn = nn.BatchNorm1d(out)

    def forward(self, data):
        x, ei, batch = data.x, data.edge_index, data.batch
        if batch is None:
            batch = x.new_zeros(x.size(0), dtype=torch.long)
        x = torch.relu(self.c1(x, ei))
        x = torch.relu(self.c2(x, ei))
        return self.bn(global_mean_pool(x, batch))


class SiameseRegressorGraph(nn.Module):
    """Siamese: pass both monomers through the SAME arm, then predict."""

    def __init__(self):
        super().__init__()
        self.arm = GNNArm()
        self.head = nn.Sequential(
            nn.Linear(128 * 2, 128), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 2)
        )

    def forward(self, dA, dB):
        eA = self.arm(dA)
        eB = self.arm(dB)
        return self.head(torch.cat([eA, eB], dim=1))


# ──────────────────────────────────────────────────────────────────────
#  4 & 6. BiLSTM over SMILES tokens (LSTM+Bayesian / Long_Short_Term_Memory)
# ──────────────────────────────────────────────────────────────────────
class BiLSTMRegressorSMILES(nn.Module):
    """Embedding → BiLSTM → shared encoder for both monomers → MLP head."""

    def __init__(self, vocab_size=SMILES_VOCAB_SIZE, emb_dim=64, hidden=128,
                 nlayers=2, dropout=0.3):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, emb_dim, padding_idx=0)
        self.drop = nn.Dropout(dropout)
        self.lstm = nn.LSTM(emb_dim, hidden, num_layers=nlayers,
                            batch_first=True, bidirectional=True, dropout=dropout)
        self.head = nn.Sequential(
            nn.Linear(hidden * 2 * 2, 128), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 2)
        )

    def encode(self, tokens):
        e = self.drop(self.emb(tokens))
        _, (hn, _) = self.lstm(e)
        return torch.cat([hn[-2], hn[-1]], dim=1)

    def forward(self, sA, sB):
        hA = self.encode(sA)
        hB = self.encode(sB)
        return self.head(torch.cat([hA, hB], dim=1))


# ──────────────────────────────────────────────────────────────────────
#  5. LSTM+Siamese+Bayesian (PolyPredict variant)
# ──────────────────────────────────────────────────────────────────────
class LSTMSiamesePolyPredict(nn.Module):
    """Siamese GAT → BiLSTM → MLP head (from LSTM+Siamese+Bayesian notebook)."""

    def __init__(self, node_dim=NODE_DIM, gnn_out=128, lstm_h=64):
        super().__init__()
        self.gat1 = GATConv(node_dim, 64, heads=4, dropout=0.2)
        self.gat2 = GATConv(256, gnn_out, heads=1)
        self.bn = nn.BatchNorm1d(gnn_out)

        self.lstm = nn.LSTM(gnn_out, lstm_h, num_layers=2,
                            batch_first=True, bidirectional=True, dropout=0.2)
        self.head = nn.Sequential(
            nn.Linear(lstm_h * 2, 128), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 2)
        )

    def encode(self, data):
        x, ei, b = data.x, data.edge_index, data.batch
        if b is None:
            b = x.new_zeros(x.size(0), dtype=torch.long)
        x = torch.relu(self.gat1(x, ei))
        x = torch.relu(self.gat2(x, ei))
        return self.bn(global_mean_pool(x, b))

    def forward(self, dA, dB):
        eA = self.encode(dA)
        eB = self.encode(dB)
        seq = torch.stack([eA, eB], dim=1)
        _, (hn, _) = self.lstm(seq)
        h = torch.cat([hn[-2], hn[-1]], dim=1)
        return self.head(h)


# ──────────────────────────────────────────────────────────────────────
#  7. Graph VAE (Autoencoders notebook)
# ──────────────────────────────────────────────────────────────────────
LATENT_VAE = 32

class GCNEncoder(nn.Module):
    def __init__(self, in_ch=NODE_DIM, hidden=64, out=LATENT_VAE):
        super().__init__()
        self.conv1    = GCNConv(in_ch,   hidden*2)
        self.conv_mu  = GCNConv(hidden*2, out)
        self.conv_std = GCNConv(hidden*2, out)

    def forward(self, x, edge_index):
        h = torch.relu(self.conv1(x, edge_index))
        return self.conv_mu(h, edge_index), self.conv_std(h, edge_index)


class VAERegressor(nn.Module):
    """
    Encodes each molecule into latent Z via VGAE, pools z to graph-level,
    then passes concatenated Z_A || Z_B through an MLP regression head.
    Combined loss = reconstruction + KL + regression MSE.
    """
    def __init__(self):
        super().__init__()
        self.encoder = VGAE(GCNEncoder())
        self.reg     = nn.Sequential(
            nn.Linear(LATENT_VAE*2, 64), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(64, 32),       nn.ReLU(),
            nn.Linear(32, 2)
        )

    def encode_molecule(self, data):
        if data is None:
            # Fallback tensor creation on the same device as the model parameters
            device = next(self.parameters()).device
            return torch.zeros((1, LATENT_VAE), device=device)
        b = data.batch if data.batch is not None else data.x.new_zeros(data.x.size(0), dtype=torch.long)
        z = self.encoder.encode(data.x, data.edge_index)   # reparameterised sample
        return global_mean_pool(z, b)                       # (B, LATENT)

    def forward(self, dA, dB):
        zA = self.encode_molecule(dA)
        zB = self.encode_molecule(dB)
        return self.reg(torch.cat([zA, zB], dim=1))

