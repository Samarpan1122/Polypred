"""Feature engineering pipeline - extracted from sabya1/GNN notebooks.

Converts SMILES strings into:
  1. Morgan fingerprints (2048-bit ECFP4)
  2. Molecular graph objects (58 node + 13 edge + 7 global features)
  3. Flat feature vectors for traditional ML (248-dim)
  4. RDKit descriptors (210)
  5. 3D autocorrelation features (80-dim)
"""

import numpy as np
import torch
from torch_geometric.data import Data
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors

from app.config import settings

# ──────────────────────────────────────────────────────────────────────
#  Element / property lookup tables (from notebooks)
# ──────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────
#  Element / property lookup tables (Verbatim from User Snippet)
# ──────────────────────────────────────────────────────────────────────

atomSymbols = [
    'B', 'C', 'N', 'O', 'F', 'Si', 'P', 'S', 'Cl', 'Br', 'I',  
    'Fe', 'Ni', 'Zn', 'Sn', 'Na', 'K'   
]

atomDegree = [1, 2, 3, 4, 5]

atomHybridization = [
    Chem.rdchem.HybridizationType.UNSPECIFIED,
    Chem.rdchem.HybridizationType.S,
    Chem.rdchem.HybridizationType.SP,
    Chem.rdchem.HybridizationType.SP2,
    Chem.rdchem.HybridizationType.SP3,
    Chem.rdchem.HybridizationType.SP3D,
    Chem.rdchem.HybridizationType.SP3D2,
    Chem.rdchem.HybridizationType.OTHER
]

hydrogenConnectedNumber = [0, 1, 2, 3, 4]

bondType = [
    Chem.rdchem.BondType.SINGLE,
    Chem.rdchem.BondType.DOUBLE,
    Chem.rdchem.BondType.TRIPLE,
    Chem.rdchem.BondType.AROMATIC
]

stereoType = [
    Chem.rdchem.BondStereo.STEREONONE,
    Chem.rdchem.BondStereo.STEREOANY,
    Chem.rdchem.BondStereo.STEREOZ,
    Chem.rdchem.BondStereo.STEREOE
]

electronegativities = {
    'C': 2.55, 'N': 3.04, 'O': 3.44, 'F': 3.98, 
    'Si': 1.90, 'P': 2.19, 'S': 2.58, 'Cl': 3.16, 
    'Br': 2.96, 'I': 2.66, 'H': 2.20, 'B': 2.04,
    'Fe': 1.83, 'Ni': 1.91, 'Zn': 1.65, 'Sn': 1.96, 'Na': 0.93, 'K': 0.82
}


def _one_hot(val, choices):
    return [1.0 if val == choice else 0.0 for choice in choices]


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
#  2. Molecular Graph Features (Matches User IPYNB Exactly)
# ──────────────────────────────────────────────────────────────────────

def smileToMole(smile: str) -> Chem.Mol | None:
    """Convert SMILES string to RDKit molecule with explicit hydrogens and 3D coordinates."""
    if not isinstance(smile, str):
        return None
    try:
        molecule = Chem.MolFromSmiles(smile)
        if molecule is None:
            return None
        molecule = Chem.AddHs(molecule)
        try:
            status = AllChem.EmbedMolecule(molecule, randomSeed=42)
            if status == -1:
                status = AllChem.EmbedMolecule(molecule, randomSeed=42, useRandomCoords=True)
            if status != -1:
                AllChem.MMFFOptimizeMolecule(molecule)
        except Exception:
            pass
        return molecule
    except Exception:
        return None

def oneHotEncode(value, categories):
    return [1.0 if value == category else 0.0 for category in categories]

def calculateElectronicFeatures(atom: Chem.Atom) -> list:
    atom_en = electronegativities.get(atom.GetSymbol(), 2.20)
    neighbors = atom.GetNeighbors()
    neighbor_en = [electronegativities.get(n.GetSymbol(), 2.20) for n in neighbors]
    avg_neighbor_en = sum(neighbor_en) / len(neighbor_en) if neighbor_en else 0
    ewg_count = sum(1 for n in neighbors if n.GetSymbol() in ['F', 'Cl', 'Br', 'I', 'O', 'N'])
    return [atom_en, avg_neighbor_en, atom_en - avg_neighbor_en, float(ewg_count)]

def calculateStericFeatures(atom: Chem.Atom) -> list:
    neighbors = atom.GetNeighbors()
    return [
        float(len([n for n in neighbors if n.GetSymbol() != 'H'])),
        float(sum(1 for n in neighbors if n.GetDegree() > 2)),
        float(sum(1 for n in neighbors if n.GetIsAromatic())),
        float(atom.IsInRing())
    ]

def find_vinyl_groups(mol):
    if mol is None: return []
    vinyl_groups = []
    for bond in mol.GetBonds():
        if (bond.GetBondType() == Chem.rdchem.BondType.DOUBLE and 
            mol.GetAtomWithIdx(bond.GetBeginAtomIdx()).GetSymbol() == 'C' and
            mol.GetAtomWithIdx(bond.GetEndAtomIdx()).GetSymbol() == 'C'):
            vinyl_groups.append((bond, bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()))
    return vinyl_groups

def identify_alpha_substituents(mol, carbon_idx, other_carbon_idx):
    substituents = []
    atom = mol.GetAtomWithIdx(carbon_idx)
    for neighbor in atom.GetNeighbors():
        if neighbor.GetIdx() == other_carbon_idx or neighbor.GetSymbol() == 'H':
            continue
        symbol = neighbor.GetSymbol()
        if symbol != 'C':
            if symbol in ['Cl', 'Br', 'F', 'I']:
                halogen_descriptions = {'Cl': "Chloro", 'Br': "Bromo", 'F': "Fluoro", 'I': "Iodo"}
                substituents.append({'type': f"{halogen_descriptions[symbol]}", 'reactivity_score': 5})
            elif symbol == 'O':
                has_h = any(n2.GetSymbol() == 'H' for n2 in neighbor.GetNeighbors() if n2.GetIdx() != carbon_idx)
                substituents.append({'type': "Hydroxy" if has_h else "Alkoxy/Ether", 'reactivity_score': 3 if has_h else 2})
            elif symbol == 'N':
                bond = mol.GetBondBetweenAtoms(carbon_idx, neighbor.GetIdx())
                if bond and bond.GetBondType() == Chem.rdchem.BondType.TRIPLE:
                    substituents.append({'type': "Cyano", 'reactivity_score': 7})
                else:
                    substituents.append({'type': "Amino", 'reactivity_score': 3})
            else:
                substituents.append({'type': f"{symbol}-group", 'reactivity_score': 1})
        else:
            if neighbor.GetIsAromatic():
                substituents.append({'type': "Phenyl/Aromatic", 'reactivity_score': 10})
                continue
            has_carbonyl = False
            for n2 in neighbor.GetNeighbors():
                if n2.GetIdx() != carbon_idx and n2.GetSymbol() == 'O':
                    bond = mol.GetBondBetweenAtoms(neighbor.GetIdx(), n2.GetIdx())
                    if bond and bond.GetBondType() == Chem.rdchem.BondType.DOUBLE:
                        has_carbonyl = True
                        found_special = False
                        for n3 in neighbor.GetNeighbors():
                            if n3.GetIdx() != carbon_idx and n3.GetIdx() != n2.GetIdx():
                                if n3.GetSymbol() == 'O':
                                    substituents.append({'type': "Ester/Carboxyl", 'reactivity_score': 6})
                                    found_special = True; break
                                elif n3.GetSymbol() == 'N':
                                    substituents.append({'type': "Amide", 'reactivity_score': 6})
                                    found_special = True; break
                        if not found_special:
                            substituents.append({'type': "Carbonyl", 'reactivity_score': 8})
                        break
            if has_carbonyl: continue
            # Cyano check on Carbon
            has_cyano_on_c = False
            for n2 in neighbor.GetNeighbors():
                if n2.GetIdx() != carbon_idx and n2.GetSymbol() == 'N':
                    bond = mol.GetBondBetweenAtoms(neighbor.GetIdx(), n2.GetIdx())
                    if bond and bond.GetBondType() == Chem.rdchem.BondType.TRIPLE:
                        substituents.append({'type': "Cyano", 'reactivity_score': 7})
                        has_cyano_on_c = True; break
            if has_cyano_on_c: continue
            # Alkenyl
            has_alkenyl = any(mol.GetBondBetweenAtoms(neighbor.GetIdx(), n2.GetIdx()).GetBondType() == Chem.rdchem.BondType.DOUBLE 
                            for n2 in neighbor.GetNeighbors() if n2.GetIdx() != carbon_idx and n2.GetSymbol() == 'C')
            if has_alkenyl:
                substituents.append({'type': "Alkenyl", 'reactivity_score': 9})
            else:
                substituents.append({'type': "Alkyl", 'reactivity_score': 4})
    
    return {'has_alpha_substitution': len(substituents) > 0, 'substituents': substituents}

def identifyVinylFeatures(atom: Chem.Atom, mol: Chem.Mol) -> list:
    isVinyl, hasAlphaSubst, hasEWG = 0.0, 0.0, 0.0
    v_groups = find_vinyl_groups(mol)
    for _, b_idx, e_idx in v_groups:
        if atom.GetIdx() in [b_idx, e_idx]:
            isVinyl = 1.0
            other = e_idx if atom.GetIdx() == b_idx else b_idx
            sub_info = identify_alpha_substituents(mol, atom.GetIdx(), other)
            hasAlphaSubst = 1.0 if sub_info['has_alpha_substitution'] else 0.0
            hasEWG = 1.0 if any(s['reactivity_score'] >= 5 for s in sub_info['substituents']) else 0.0
            break
    return [isVinyl, hasAlphaSubst, hasEWG]

def calculateResonanceFeatures(atom: Chem.Atom) -> list:
    return [
        float(atom.GetIsAromatic()),
        float(any(n.GetIsAromatic() for n in atom.GetNeighbors())),
        float(atom.GetHybridization() == Chem.rdchem.HybridizationType.SP2),
        float(len([b for b in atom.GetBonds() if b.GetBondType() == Chem.rdchem.BondType.DOUBLE]))
    ]

def calculateRingFeatures(atom: Chem.Atom, mol: Chem.Mol) -> list:
    ri = mol.GetRingInfo()
    atom_rings = ri.AtomRings()
    rings = [r for r in atom_rings if atom.GetIdx() in r]
    return [
        float(len(rings)),
        float(min([len(r) for r in rings] or [0])),
        float(any(len(r) == 6 for r in rings)),
        float(atom.GetIsAromatic() and len(rings) > 0)
    ]

def is_in_restricted_conformation(atom: Chem.Atom, mol: Chem.Mol) -> float:
    return float(atom.IsInRing() or len(atom.GetNeighbors()) > 3)

def _atom_features(atom, mol) -> list[float]:
    features = (
        oneHotEncode(atom.GetSymbol(), atomSymbols) +
        oneHotEncode(atom.GetDegree(), atomDegree) +
        [float(atom.GetFormalCharge())] +
        [float(atom.GetNumRadicalElectrons())] +
        oneHotEncode(atom.GetHybridization(), atomHybridization) +
        [1.0 if atom.GetIsAromatic() else 0.0] +
        oneHotEncode(atom.GetTotalNumHs(), hydrogenConnectedNumber)
    )
    features += calculateElectronicFeatures(atom)
    features += calculateStericFeatures(atom)
    features += identifyVinylFeatures(atom, mol)
    features += calculateResonanceFeatures(atom)
    features += calculateRingFeatures(atom, mol)
    features.append(is_in_restricted_conformation(atom, mol))
    return features

def _bond_features(bond, mol) -> list[float]:
    bt = bond.GetBondType()
    features = (
        oneHotEncode(bt, bondType) +
        [float(bond.GetIsConjugated())] +
        [float(bond.IsInRing())] +
        oneHotEncode(bond.GetStereo(), stereoType) +
        [float(bond.IsInRingSize(s)) for s in [3, 4, 5, 6, 7]] +
        [float(bt == Chem.rdchem.BondType.DOUBLE and all(a.GetSymbol() == 'C' for a in [bond.GetBeginAtom(), bond.GetEndAtom()]))]
    )
    return features

def _global_features(mol) -> list[float]:
    v_groups = find_vinyl_groups(mol)
    has_v = 1.0 if len(v_groups) > 0 else 0.0
    return [
        float(rdMolDescriptors.CalcNumRotatableBonds(mol)),
        float(Chem.rdMolDescriptors.CalcNumRings(mol)),
        float(Chem.rdMolDescriptors.CalcNumAromaticRings(mol)),
        float(len(v_groups)),
        has_v,
        float(rdMolDescriptors.CalcFractionCSP3(mol)),
        float(len(Chem.GetSymmSSSR(mol)))
    ]

def moleToGraph(mole: Chem.Mol) -> Data | None:
    """Verbatim GNN graph construction from user IPYNB."""
    if mole is None:
        return None
    atomFeatures, reactionCenters = [], []
    for atom in mole.GetAtoms():
        basicFeatures = (
            oneHotEncode(atom.GetSymbol(), atomSymbols) +                
            oneHotEncode(atom.GetDegree(), atomDegree) +                 
            [float(atom.GetFormalCharge())] +                                   
            [float(atom.GetNumRadicalElectrons())] +                            
            oneHotEncode(atom.GetHybridization(), atomHybridization) +   
            [1.0 if atom.GetIsAromatic() else 0.0] +                         
            oneHotEncode(atom.GetTotalNumHs(), hydrogenConnectedNumber)  
        )
        electronicFeatures = calculateElectronicFeatures(atom)          
        stericFeatures = calculateStericFeatures(atom)                  
        vinylFeatures = identifyVinylFeatures(atom, mole)              
        resonanceFeatures = calculateResonanceFeatures(atom)           
        ringFeatures = calculateRingFeatures(atom, mole)               
        conformationalFeatures = [is_in_restricted_conformation(atom, mole)]
        
        features = (basicFeatures + electronicFeatures + stericFeatures + 
                   vinylFeatures + resonanceFeatures + ringFeatures + 
                   conformationalFeatures)
        atomFeatures.append(features)
        reactionCenters.append(vinylFeatures[0]) 
    
    x = torch.tensor(atomFeatures, dtype=torch.float)
    r_centers = torch.tensor(reactionCenters, dtype=torch.float).view(-1, 1)
    
    edgeIndices, edgeFeatures = [], []
    for bond in mole.GetBonds():
        i = bond.GetBeginAtomIdx()
        j = bond.GetEndAtomIdx()
        edgeIndices.extend([[i, j], [j, i]])
        bondFeatures = _bond_features(bond, mole)
        edgeFeatures.extend([bondFeatures, bondFeatures])
    
    edgeIndex = torch.tensor(edgeIndices, dtype=torch.long).t().contiguous()
    edgeAttr = torch.tensor(edgeFeatures, dtype=torch.float)
    globalFeatures = torch.tensor(_global_features(mole), dtype=torch.float)
    
    data = Data(x=x, edge_index=edgeIndex, edge_attr=edgeAttr, 
                global_features=globalFeatures, reaction_centers=r_centers)
    return data

def smiles_to_graph(smiles: str) -> dict[str, np.ndarray] | None:
    mol = smileToMole(smiles)
    if mol is None: return None
    node_feats = [_atom_features(atom, mol) for atom in mol.GetAtoms()]
    edge_index, edge_attr = [], []
    for bond in mol.GetBonds():
        i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        edge_index += [[i, j], [j, i]]
        bf = _bond_features(bond, mol)
        edge_attr += [bf, bf]

    return {
        "node_features": np.array(node_feats, dtype=np.float32),
        "edge_index": np.array(edge_index, dtype=np.int64).T if edge_index else np.zeros((2, 0), dtype=np.int64),
        "edge_attr": np.array(edge_attr, dtype=np.float32) if edge_attr else np.zeros((0, 16), dtype=np.float32),
        "global_features": np.array(_global_features(mol), dtype=np.float32),
    }

def graph_to_flat_features(graph: dict[str, np.ndarray]) -> np.ndarray:
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


_BASE_65_NAMES = [
    "Is_B", "Is_C", "Is_N", "Is_O", "Is_F", "Is_Si", "Is_P", "Is_S", "Is_Cl", "Is_Br", "Is_I", "Is_Fe", "Is_Ni", "Is_Zn", "Is_Sn", "Is_Na", "Is_K", "Is_Other_Element",
    "Degree_1", "Degree_2", "Degree_3", "Degree_4", "Degree_5", "Degree_Other",
    "FormalCharge", "NumRadicalElectrons",
    "Hyb_UNSPECIFIED", "Hyb_S", "Hyb_SP", "Hyb_SP2", "Hyb_SP3", "Hyb_SP3D", "Hyb_SP3D2", "Hyb_Other",
    "IsAromatic",
    "TotalNumHs_0", "TotalNumHs_1", "TotalNumHs_2", "TotalNumHs_3", "TotalNumHs_4", "TotalNumHs_Other",
    "Electronegativity", "AvgNeighborEN", "ENDifference", "EWGCount",
    "VdwRadius",
    "IsVinyl", "HasAlphaSubst", "HasEWG",
    "IsAtomAromatic", "HasAromaticNeighbor",
    "IsSP2",
    "NumDoubleBonds",
    "NumRingsContainingAtom", "MinRingSize", "IsIn6Ring", "IsAromaticAndInRing", "IsInRestrictedConform",
    "NumRotatableBonds", "NumRings", "NumAromaticRings",
    "SumReactionCenters", "AnyReactionCenters", "FractionCSP3", "NumSymmSSSR"
]

_BIG8_FEATURE_MAP = {
    "steric_index": [
        "Degree", "NonHNeighbors", "DenseNeighbors", "InRing", 
        "RingCount", "MinRingSize", "In6Ring", "RestrictedConform", 
        "Is_Si", "Is_P", "Is_S", "Is_Fe", "Is_Ni", "Is_Zn", "Is_Sn", "Is_C", "Is_B",
        "NumRotatableBonds", "NumRings", "AnyReactionCenters", "SumReactionCenters",
        "FractionCSP3", "NumSymmSSSR", "VdwRadius", "NumRingsContainingAtom"
    ],
    "electronic_properties": [
        "FormalCharge", "NumRadicalElectrons", "TotalNumHs", "Electronegativity", "AvgNeighborEN", "ENDifference", "EWGCount", "HasEWG",
        "Is_N", "Is_O", "Is_F", "Is_Cl", "Is_Br", "Is_I", "Is_Na", "Is_K", "Is_Other_Element"
    ],
    "resonance_stabilization": [
        "IsAromatic", "IsAtomAromatic", "HasAromaticNeighbor", "IsAromaticAndInRing", "NumAromaticRings", "IsSP2", "NumDoubleBonds"
    ],
    "vinyl_substitution": [
        "IsVinyl", "HasAlphaSubst", "HasEWG", "NumDoubleBonds"
    ],
    "hybridization_index": [
        "Hyb", "IsSP2"
    ],
    "polarity": [
        "Electronegativity", "AvgNeighborEN", "ENDifference", "Is_N", "Is_O", "Is_F", "Is_Cl", "Is_Br", "Is_I", "Is_Na", "Is_K"
    ],
    "aromaticity": [
        "IsAromatic", "IsAtomAromatic", "HasAromaticNeighbor", "IsAromaticAndInRing", "NumAromaticRings"
    ],
    "h_bonding_capacity": [
        "Is_N", "Is_O", "Is_F", "TotalNumHs"
    ]
}

def pair_flat_features_ensemble_masked(smiles_a: str, smiles_b: str, method: str) -> np.ndarray | None:
    """130-dim vector subsetted using the requested Big 8 featurization mask."""
    flat_vector = pair_flat_features_ensemble(smiles_a, smiles_b)
    if flat_vector is None:
        return None
    
    if method == "all":
        return flat_vector
        
    keywords = _BIG8_FEATURE_MAP.get(method, [])
    if not keywords:
        return flat_vector
        
    mask = []
    # Both Monomer A and B have the same 65 features
    for _ in range(2):
        for name in _BASE_65_NAMES:
            matched = any(kw in name for kw in keywords)
            mask.append(matched)
            
    return flat_vector[mask]


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
    """CalcAUTOCORR3D - 80-dim 3D spatial autocorrelation descriptors."""
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
