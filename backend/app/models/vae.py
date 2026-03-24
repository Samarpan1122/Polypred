"""Variational Autoencoder - from VAE_siamese.ipynb.

Same encoder/decoder shell as MolecularAutoencoder but with
reparameterisation trick and KL-divergence loss.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class VariationalAutoencoder(nn.Module):

    def __init__(self, input_dim: int = 2048, latent_dim: int = 64):
        super().__init__()
        self.encoder_layers = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.Tanh(),
            nn.Linear(512, 256),
            nn.Tanh(),
            nn.Linear(256, 128),
            nn.Tanh(),
        )
        self.fc_mu = nn.Linear(128, latent_dim)
        self.fc_logvar = nn.Linear(128, latent_dim)

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

    @staticmethod
    def reparameterize(mu: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def encode(self, x: torch.Tensor):
        h = self.encoder_layers(x)
        return self.fc_mu(h), self.fc_logvar(h)

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        return self.decoder(z)

    def forward(self, x: torch.Tensor):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        return self.decode(z), mu, logvar

    def get_latent(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            mu, _ = self.encode(x)
            return mu  # use mean (no sampling) at inference

    @staticmethod
    def vae_loss(recon_x, x, mu, logvar):
        bce = F.binary_cross_entropy(recon_x, x, reduction="sum")
        kl = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
        return bce + kl
