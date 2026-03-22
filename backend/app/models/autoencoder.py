"""Standard & Denoising Autoencoder — from siamese / siamese_somu_1 notebooks.

Architecture: 2048 → 512 → 256 → 128 → 64 (latent)
Activations : Tanh (hidden), Sigmoid (output)
Loss        : BCE (binary fingerprints)
"""

import torch
import torch.nn as nn
import numpy as np


class MolecularAutoencoder(nn.Module):
    """Standard Autoencoder for Morgan fingerprint compression."""

    def __init__(self, input_dim: int = 2048, latent_dim: int = 64):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.Tanh(),
            nn.Linear(512, 256),
            nn.Tanh(),
            nn.Linear(256, 128),
            nn.Tanh(),
            nn.Linear(128, latent_dim),
            nn.Tanh(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.Tanh(),
            nn.Linear(128, 256),
            nn.Tanh(),
            nn.Linear(256, 512),
            nn.Tanh(),
            nn.Linear(512, input_dim),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encoder(x)
        return self.decoder(z)

    def get_latent(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return self.encoder(x)


class DenoisingAutoencoder(MolecularAutoencoder):
    """Adds Gaussian noise during forward pass (training only)."""

    def __init__(self, input_dim: int = 2048, latent_dim: int = 64, noise_std: float = 0.1):
        super().__init__(input_dim, latent_dim)
        self.noise_std = noise_std

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.training:
            x = x + torch.randn_like(x) * self.noise_std
            x = torch.clamp(x, 0.0, 1.0)
        z = self.encoder(x)
        return self.decoder(z)
