"""Feature engineering pipeline — extracted from sabya1/GNN notebooks.

Converts SMILES strings into:
  1. Morgan fingerprints (2048-bit ECFP4)
  2. Molecular graph objects (58 node + 13 edge + 7 global features)
  3. Flat feature vectors for traditional ML (248-dim)
  4. RDKit descriptors (210)
  5. 3D autocorrelation features (80-dim)
"""

import numpy as np
import torch
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors

from app.config import settings

# ──────────────────────────────────────────────────────────────────────
#  Element / property lookup tables (from notebooks)
# ──────────────────────────────────────────────────────────────────────
ELEMENTS = ["B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Br",
            "I", "Fe", "Ni", "Zn", "Sn", "Na", "K"]
HYBRIDIZATIONS = [
    Chem.rdchem.HybridizationType.UNSPECIFIED,
    Chem.rdchem.HybridizationType.S,
    Chem.rdchem.HybridizationType.SP,
    Chem.rdchem.HybridizationType.SP2,
    Chem.rdchem.HybridizationType.SP3,
    Chem.rdchem.HybridizationType.SP3D,
    Chem.rdchem.HybridizationType.SP3D2,
    Chem.rdchem.HybridizationType.OTHER,
]
STEREO_TYPES = [
    Chem.rdchem.BondStereo.STEREONONE,
    Chem.rdchem.BondStereo.STEREOANY,
    Chem.rdchem.BondStereo.STEREOZ,
    Chem.rdchem.BondStereo.STEREOE,
]

# Pauling electronegativity
ELECTRONEGATIVITY = {
    "H": 2.20, "B": 2.04, "C": 2.55, "N": 3.04, "O": 3.44, "F": 3.98,
    "Si": 1.90, "P": 2.19, "S": 2.58, "Cl": 3.16, "Br": 2.96, "I": 2.66,
    "Fe": 1.83, "Ni": 1.91, "Zn": 1.65, "Sn": 1.96, "Na": 0.93, "K": 0.82,
}


def _one_hot(val, choices):
    vec = [0.0] * len(choices)
    try:
        vec[choices.index(val)] = 1.0
    except ValueError:
        pass
    return vec


# ──────────────────────────────────────────────────────────────────────
#  1. Morgan Fingerprints
# ──────────────────────────────────────────────────────────────────────
def smiles_to_morgan_fp(smiles: str, radius: int = 2, n_bits: int = 2048) -> np.ndarray | None:
    """Convert SMILES → Morgan fingerprint (binary numpy array)."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
    return np.array(fp, dtype=np.float32)


def pair_fingerprints(smiles_a: str, smiles_b: str):
    """Return concatenated pair FP or None if either SMILES is invalid."""
    fp_a = smiles_to_morgan_fp(smiles_a)
    fp_b = smiles_to_morgan_fp(smiles_b)
    if fp_a is None or fp_b is None:
        return None, None, None
    return fp_a, fp_b, np.concatenate([fp_a, fp_b])


# ──────────────────────────────────────────────────────────────────────
#  2. Molecular Graph Features
# ──────────────────────────────────────────────────────────────────────
def _atom_features(atom, mol) -> list[float]:
    """58-dimensional atom feature vector."""
    symbol = atom.GetSymbol()
    features = []
    # One-hot element (17)
    features += _one_hot(symbol, ELEMENTS)
    # One-hot degree (5)
    features += _one_hot(atom.GetDegree(), [1, 2, 3, 4, 5])
    # Formal charge (1)
    features.append(float(atom.GetFormalCharge()))
    # Radical electrons (1)
    features.append(float(atom.GetNumRadicalElectrons()))
    # One-hot hybridization (8)
    features += _one_hot(atom.GetHybridization(), HYBRIDIZATIONS)
    # Aromaticity (1)
    features.append(float(atom.GetIsAromatic()))
    # Total Hs one-hot (5)
    features += _one_hot(atom.GetTotalNumHs(), [0, 1, 2, 3, 4])
    # Electronic features (4)
    en = ELECTRONEGATIVITY.get(symbol, 2.5)
    idx = atom.GetIdx()
    neighbors = atom.GetNeighbors()
    avg_neighbor_en = np.mean([ELECTRONEGATIVITY.get(n.GetSymbol(), 2.5) for n in neighbors]) if neighbors else en
    net_electronic = en - avg_neighbor_en
    ewg_count = sum(1 for n in neighbors if ELECTRONEGATIVITY.get(n.GetSymbol(), 2.5) > 2.8)
    features += [en, avg_neighbor_en, net_electronic, float(ewg_count)]
    # Steric features (4)
    non_h = sum(1 for n in neighbors if n.GetSymbol() != "H")
    bulky = sum(1 for n in neighbors if n.GetDegree() >= 3)
    aromatic_n = sum(1 for n in neighbors if n.GetIsAromatic())
    ring_info = mol.GetRingInfo()
    ring_part = float(ring_info.NumAtomRings(idx))
    features += [float(non_h), float(bulky), float(aromatic_n), ring_part]
    # Vinyl features (3)
    is_vinyl = 0.0
    has_alpha = 0.0
    has_ewg_on_vinyl = 0.0
    if symbol == "C":
        for bond in atom.GetBonds():
            if bond.GetBondTypeAsDouble() == 2.0:
                other = bond.GetOtherAtom(atom)
                if other.GetSymbol() == "C":
                    is_vinyl = 1.0
                    for n2 in other.GetNeighbors():
                        if n2.GetIdx() != idx:
                            has_alpha = 1.0
                            if ELECTRONEGATIVITY.get(n2.GetSymbol(), 2.5) > 2.8:
                                has_ewg_on_vinyl = 1.0
    features += [is_vinyl, has_alpha, has_ewg_on_vinyl]
    # Resonance features (4)
    is_aromatic = float(atom.GetIsAromatic())
    adj_aromatic = float(any(n.GetIsAromatic() for n in neighbors))
    is_sp2 = float(atom.GetHybridization() == Chem.rdchem.HybridizationType.SP2)
    double_bonds = sum(1 for b in atom.GetBonds() if b.GetBondTypeAsDouble() == 2.0)
    features += [is_aromatic, adj_aromatic, is_sp2, float(double_bonds)]
    # Ring features (4)
    num_rings = float(ring_info.NumAtomRings(idx))
    atom_rings = ring_info.AtomRingSizes(idx) if hasattr(ring_info, "AtomRingSizes") else []
    smallest = min(atom_rings) if atom_rings else 0.0
    in_6 = float(6 in atom_rings) if atom_rings else 0.0
    in_arom_ring = float(atom.GetIsAromatic() and num_rings > 0)
    features += [num_rings, float(smallest), in_6, in_arom_ring]
    # Conformational (1)
    restricted = float(ring_part > 0 or is_sp2 > 0)
    features.append(restricted)
    return features  # 58 total


def _bond_features(bond, mol) -> list[float]:
    """13-dimensional bond feature vector."""
    features = []
    # Bond type one-hot (4)
    bt = bond.GetBondType()
    features += [
        float(bt == Chem.rdchem.BondType.SINGLE),
        float(bt == Chem.rdchem.BondType.DOUBLE),
        float(bt == Chem.rdchem.BondType.TRIPLE),
        float(bt == Chem.rdchem.BondType.AROMATIC),
    ]
    # Conjugation (1)
    features.append(float(bond.GetIsConjugated()))
    # Ring (1)
    features.append(float(bond.IsInRing()))
    # Stereo one-hot (4)
    features += _one_hot(bond.GetStereo(), STEREO_TYPES)
    # Ring sizes (3 through 7) — 5 flags — but we pack to fit 13 total
    # Vinyl bond (1)
    is_vinyl = 0.0
    if bt == Chem.rdchem.BondType.DOUBLE:
        a1, a2 = bond.GetBeginAtom(), bond.GetEndAtom()
        if a1.GetSymbol() == "C" and a2.GetSymbol() == "C":
            is_vinyl = 1.0
    features.append(is_vinyl)
    return features  # 13 total


def _global_features(mol) -> list[float]:
    """7-dimensional molecular-level features."""
    ri = mol.GetRingInfo()
    n_rot = float(Descriptors.NumRotatableBonds(mol))
    n_ring = float(ri.NumRings())
    n_arom = float(Descriptors.NumAromaticRings(mol))
    # Vinyl group count
    vinyl_count = 0
    for bond in mol.GetBonds():
        if bond.GetBondType() == Chem.rdchem.BondType.DOUBLE:
            a1, a2 = bond.GetBeginAtom(), bond.GetEndAtom()
            if a1.GetSymbol() == "C" and a2.GetSymbol() == "C":
                vinyl_count += 1
    has_vinyl = float(vinyl_count > 0)
    frac_csp3 = float(Descriptors.FractionCSP3(mol))
    ring_complexity = float(ri.NumRings())
    return [n_rot, n_ring, n_arom, float(vinyl_count), has_vinyl, frac_csp3, ring_complexity]


def smiles_to_graph(smiles: str):
    """Convert SMILES → dict with node_features, edge_index, edge_attr, global_features."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    try:
        AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol)
    except Exception:
        pass
    mol = Chem.RemoveHs(mol)

    node_feats = [_atom_features(atom, mol) for atom in mol.GetAtoms()]
    edge_index = []
    edge_attr = []
    for bond in mol.GetBonds():
        i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        edge_index.append([i, j])
        edge_index.append([j, i])
        bf = _bond_features(bond, mol)
        edge_attr.append(bf)
        edge_attr.append(bf)

    glob = _global_features(mol)
    return {
        "node_features": np.array(node_feats, dtype=np.float32),
        "edge_index": np.array(edge_index, dtype=np.int64).T if edge_index else np.zeros((2, 0), dtype=np.int64),
        "edge_attr": np.array(edge_attr, dtype=np.float32) if edge_attr else np.zeros((0, 13), dtype=np.float32),
        "global_features": np.array(glob, dtype=np.float32),
    }


def graph_to_flat_features(graph: dict) -> np.ndarray:
    """Mean + max pool of node features + vinyl count + global → 124 per monomer."""
    nf = graph["node_features"]
    if nf.shape[0] == 0:
        return np.zeros(124, dtype=np.float32)
    mean_pool = nf.mean(axis=0)  # 58
    max_pool = nf.max(axis=0)    # 58
    # vinyl count from global features
    vinyl_count = graph["global_features"][3:4]  # 1
    glob = graph["global_features"]  # 7
    return np.concatenate([mean_pool, max_pool, vinyl_count, glob])  # 124


def pair_flat_features(smiles_a: str, smiles_b: str) -> np.ndarray | None:
    """248-dim flat feature vector for a monomer pair (for DT, RF, LSTM, etc.)."""
    ga = smiles_to_graph(smiles_a)
    gb = smiles_to_graph(smiles_b)
    if ga is None or gb is None:
        return None
    flat_a = graph_to_flat_features(ga)
    flat_b = graph_to_flat_features(gb)
    return np.concatenate([flat_a, flat_b])


def pair_flat_features_ensemble(smiles_a: str, smiles_b: str) -> np.ndarray | None:
    """130-dim flat feature vector matching ensemble training pipeline.

    Per monomer: 58-dim mean-pooled node features + 7 global features = 65.
    Concatenated pair = 130 features.
    """
    ga = smiles_to_graph(smiles_a)
    gb = smiles_to_graph(smiles_b)
    if ga is None or gb is None:
        return None
    flat_a = np.concatenate([ga["node_features"].mean(axis=0), ga["global_features"]])
    flat_b = np.concatenate([gb["node_features"].mean(axis=0), gb["global_features"]])
    return np.concatenate([flat_a, flat_b])


# ──────────────────────────────────────────────────────────────────────
#  3. RDKit Descriptors (210)
# ──────────────────────────────────────────────────────────────────────
def compute_rdkit_descriptors(smiles: str) -> np.ndarray | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    desc_names = [name for name, _ in Descriptors._descList]
    vals = []
    for name in desc_names:
        try:
            vals.append(float(Descriptors.__dict__[name](mol)))
        except Exception:
            vals.append(0.0)
    return np.array(vals, dtype=np.float32)


# ──────────────────────────────────────────────────────────────────────
#  4. 3D Autocorrelation Features (from VAE_siamese notebook)
# ──────────────────────────────────────────────────────────────────────
def compute_3d_autocorr(smiles: str) -> np.ndarray | None:
    """CalcAUTOCORR3D — 80-dim 3D spatial autocorrelation descriptors."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    try:
        AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol)
    except Exception:
        return None
    try:
        autocorr = rdMolDescriptors.CalcAUTOCORR3D(mol)
        return np.array(autocorr, dtype=np.float32)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────
#  5. Molecular Descriptors for EDA
# ──────────────────────────────────────────────────────────────────────
EDA_DESCRIPTORS = [
    ("MolWt", Descriptors.MolWt),
    ("LogP", Descriptors.MolLogP),
    ("NumHDonors", Descriptors.NumHDonors),
    ("NumHAcceptors", Descriptors.NumHAcceptors),
    ("NumRotatableBonds", Descriptors.NumRotatableBonds),
    ("TPSA", Descriptors.TPSA),
    ("NumAromaticRings", Descriptors.NumAromaticRings),
    ("NumHeavyAtoms", Descriptors.HeavyAtomCount),
]


def compute_eda_descriptors(smiles: str) -> dict | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return {name: float(fn(mol)) for name, fn in EDA_DESCRIPTORS}
