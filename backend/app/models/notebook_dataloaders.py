import torch
import numpy as np
import pandas as pd
from torch_geometric.loader import DataLoader
from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from torch.utils.data import DataLoader as TorchDataLoader, Dataset

# ── DATA: PyG graph objects → DataLoaders (Autoencoders & Siamese+LSTM) ──────
class PairDataset(Dataset):
    def __init__(self, df, idx): 
        self.df = df
        self.idx = idx
    def __len__(self): return len(self.idx)
    def __getitem__(self, i):
        r = self.df.iloc[self.idx[i]]
        return r['Graph_A'], r['Graph_B'], torch.tensor([r['log_r1'], r['log_r2']], dtype=torch.float)

# ── DATA: molecular graphs → fixed-length NumPy vectors (ML Models) ──────────
def flatten_graph(g):
    if g is None: return np.zeros(65)
    node_mean = g.x.numpy().mean(axis=0)          # mean-pool atom features → 58-d
    if hasattr(g, 'global_features'):
        glob = g.global_features.numpy()          # 7 global molecular features
    else:
        glob = np.zeros(7)
    return np.concatenate([node_mean, glob])       # → 65-d vector per monomer

# ── DATA: SMILES strings → integer token sequences for LSTM ──────────────────
# NOTE: Requires vocab. You can pass dynamically computed vocab or use the globally defined one.
def encode_smiles_lstm(s, vocab, maxlen=150):
    s = str(s)[:maxlen]
    ids = [vocab.get(c, 0) for c in s]
    return ids + [0]*(maxlen - len(ids))        # zero-padding

def collate(rows, vocab, max_len=150):
    sA  = torch.tensor([encode_smiles_lstm(r['SMILES_A'], vocab, max_len) for _,r in rows], dtype=torch.long)
    sB  = torch.tensor([encode_smiles_lstm(r['SMILES_B'], vocab, max_len) for _,r in rows], dtype=torch.long)
    tgt = torch.tensor([[r['log_r1'], r['log_r2']] for _,r in rows],   dtype=torch.float)
    return sA, sB, tgt

class PolyDataset(Dataset):
    def __init__(self, df, vocab, max_len=150): 
        self.df = df.reset_index(drop=True)
        self.vocab = vocab
        self.max_len = max_len
        
    def __len__(self): return len(self.df)
    def __getitem__(self, i):
        r = self.df.iloc[i]
        return (torch.tensor(encode_smiles_lstm(r['SMILES_A'], self.vocab, self.max_len), dtype=torch.long),
                torch.tensor(encode_smiles_lstm(r['SMILES_B'], self.vocab, self.max_len), dtype=torch.long),
                torch.tensor([r['log_r1'], r['log_r2']],  dtype=torch.float))
