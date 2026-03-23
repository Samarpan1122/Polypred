import sys
import os
import numpy as np

# Add backend to path
sys.path.append(os.path.abspath("backend"))

from app.models.schemas import FeaturizationMethod
from app.services.feature_service import featurize_dataset, _compute_features

# Just test _compute_features directly
smiles_a = "CC(=O)O"  # Acetic acid
smiles_b = "CCO"      # Ethanol

full = _compute_features(smiles_a, smiles_b, FeaturizationMethod.ALL)
print(f"Full 130-dim vector length: {len(full) if full is not None else 'None'}")

steric = _compute_features(smiles_a, smiles_b, FeaturizationMethod.STERIC_INDEX)
print(f"Steric Index vector length: {len(steric) if steric is not None else 'None'}")

electronic = _compute_features(smiles_a, smiles_b, FeaturizationMethod.ELECTRONIC_PROPERTIES)
print(f"Electronic vector length: {len(electronic) if electronic is not None else 'None'}")
