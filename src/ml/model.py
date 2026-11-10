"""BiLSTM with temporal attention for BUY/SELL/HOLD classification."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    def __init__(self, gamma: float, weight: torch.Tensor | None = None) -> None:
        super().__init__()
        self.gamma = gamma
        self.weight = weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        log_prob = F.log_softmax(logits, dim=-1)
        prob = log_prob.exp()
        targets_oh = F.one_hot(targets, num_classes=logits.size(-1)).float()
        pt = (prob * targets_oh).sum(dim=-1)
        log_pt = (log_prob * targets_oh).sum(dim=-1)
        focal = -((1 - pt) ** self.gamma) * log_pt
        if self.weight is not None:
            w = self.weight[targets]
            focal = focal * w
        return focal.mean()


class TemporalAttentionClassifier(nn.Module):
    def __init__(
        self,
        num_features: int,
        num_symbols: int,
        symbol_embed_dim: int,
        hidden_size: int,
        num_layers: int,
        num_classes: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.symbol_embedding = nn.Embedding(num_symbols, symbol_embed_dim)
        lstm_input = num_features + symbol_embed_dim

        self.lstm = nn.LSTM(
            input_size=lstm_input,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.attention = nn.Linear(hidden_size * 2, 1)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_size * 2, num_classes)

    def forward(
        self, x: torch.Tensor, symbol_ids: torch.Tensor
    ) -> torch.Tensor:
        batch, seq_len, _ = x.shape
        sym = self.symbol_embedding(symbol_ids)
        sym = sym.unsqueeze(1).expand(-1, seq_len, -1)
        merged = torch.cat([x, sym], dim=-1)

        lstm_out, _ = self.lstm(merged)
        scores = self.attention(lstm_out).squeeze(-1)
        weights = torch.softmax(scores, dim=-1)
        context = torch.bmm(weights.unsqueeze(1), lstm_out).squeeze(1)

        context = self.dropout(context)
        return self.classifier(context)
