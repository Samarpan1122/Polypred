"""Siamese-network predictors — from siamese / siamese2 / siamese_somu_1 notebooks.

Two main variants:
  • MIMO — single model outputs both (r₁, r₂)
  • MISO — two independent models each predicting one ratio
Both accept autoencoder latent vectors as input.

Also includes DirectFingerprintRegressor (baseline MLP) that operates on
raw concatenated Morgan FPs (4096-dim).
"""

import torch
import torch.nn as nn


# ──────────────────────────────────────────────────────────────────────
#  Siamese Pair Feature Builder
# ──────────────────────────────────────────────────────────────────────
def build_pair_features(z_a: torch.Tensor, z_b: torch.Tensor) -> torch.Tensor:
    """Concatenate [z_a, z_b, |z_a - z_b|, z_a ⊙ z_b] → 4 × latent_dim."""
    return torch.cat([z_a, z_b, torch.abs(z_a - z_b), z_a * z_b], dim=-1)


# ──────────────────────────────────────────────────────────────────────
#  MIMO regressors (output 2: r₁, r₂)
# ──────────────────────────────────────────────────────────────────────
class SiameseRegressorMIMO(nn.Module):
    """Takes pair features (256-dim by default) → predicts (r₁, r₂)."""

    def __init__(self, input_dim: int = 256, dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ──────────────────────────────────────────────────────────────────────
#  MISO regressor (output 1)
# ──────────────────────────────────────────────────────────────────────
class SiameseRegressorMISO(nn.Module):
    """Same architecture but single output."""

    def __init__(self, input_dim: int = 256, dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ──────────────────────────────────────────────────────────────────────
#  Direct Fingerprint Regressor (Baseline MLP from siamese2 notebooks)
# ──────────────────────────────────────────────────────────────────────
class DirectFingerprintRegressorMIMO(nn.Module):
    """4096 → 512 → 256 → 128 → 64 → 2 (no autoencoder)."""

    def __init__(self, input_dim: int = 4096, dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class DirectFingerprintRegressorMISO(nn.Module):
    """Same but single output."""

    def __init__(self, input_dim: int = 4096, dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ──────────────────────────────────────────────────────────────────────
#  Convenience wrappers that combine encoder + regressor
# ──────────────────────────────────────────────────────────────────────
class SiamesePipeline(nn.Module):
    """End-to-end: (fp_a, fp_b) → encoder → pair features → regressor."""

    def __init__(self, encoder: nn.Module, regressor: nn.Module):
        super().__init__()
        self.encoder = encoder
        self.regressor = regressor

    def forward(self, fp_a: torch.Tensor, fp_b: torch.Tensor) -> torch.Tensor:
        z_a = self.encoder(fp_a)
        z_b = self.encoder(fp_b)
        pair = build_pair_features(z_a, z_b)
        return self.regressor(pair)
