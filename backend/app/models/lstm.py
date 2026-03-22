"""Bidirectional LSTM Regressor — from sabya1 notebooks.

Two variants:
  • Large : 4 layers × 512 hidden, FC 1024→256→128→64→2 (batch_size=8)
  • Optimized: 2 layers × 128 hidden, FC 256→64→32→2  (batch_size=32)
"""

import torch
import torch.nn as nn


class LSTMRegressor(nn.Module):
    """Bidirectional LSTM that treats a 248-dim flat feature vector as a sequence.

    The input is reshaped into (batch, seq_len, input_size) by chunking the
    flat feature vector.
    """

    def __init__(
        self,
        input_dim: int = 248,
        hidden_size: int = 512,
        num_layers: int = 4,
        fc_sizes: tuple = (1024, 256, 128, 64),
        output_dim: int = 2,
        dropout: float = 0.3,
        seq_len: int = 8,
    ):
        super().__init__()
        self.seq_len = seq_len
        self.input_size = input_dim // seq_len  # e.g. 248 / 8 = 31
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=self.input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # FC head
        layers: list[nn.Module] = []
        prev = hidden_size * 2  # bidirectional
        for fc_dim in fc_sizes:
            layers += [nn.Linear(prev, fc_dim), nn.ReLU(), nn.Dropout(dropout)]
            prev = fc_dim
        layers.append(nn.Linear(prev, output_dim))
        self.fc = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, input_dim)  → reshape to (batch, seq_len, input_size)
        batch = x.size(0)
        # pad if needed
        remainder = x.size(1) % self.seq_len
        if remainder:
            pad = torch.zeros(batch, self.seq_len - remainder, device=x.device)
            x = torch.cat([x, pad], dim=1)
        x = x.view(batch, self.seq_len, -1)
        lstm_out, _ = self.lstm(x)
        # take last time-step
        out = lstm_out[:, -1, :]
        return self.fc(out)


# Pre-configured variants ─────────────────────────────────────────────

def build_lstm_large(input_dim: int = 248) -> LSTMRegressor:
    return LSTMRegressor(
        input_dim=input_dim,
        hidden_size=512,
        num_layers=4,
        fc_sizes=(1024, 256, 128, 64),
        output_dim=2,
        dropout=0.3,
        seq_len=8,
    )


def build_lstm_optimized(input_dim: int = 248) -> LSTMRegressor:
    return LSTMRegressor(
        input_dim=input_dim,
        hidden_size=128,
        num_layers=2,
        fc_sizes=(256, 64, 32),
        output_dim=2,
        dropout=0.2,
        seq_len=8,
    )
