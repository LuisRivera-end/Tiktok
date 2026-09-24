import torch
from torch import nn


class MMoE(nn.Module):
    def __init__(self, inputs):
        super().__init__()
        self.experts = nn.ModuleList([nn.Sequential(nn.Linear(inputs, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU()) for _ in range(4)])
        self.gates = nn.ModuleList([nn.Linear(inputs, 4) for _ in range(4)])
        self.towers = nn.ModuleList([nn.Sequential(nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, 1)) for _ in range(4)])

    def forward(self, x):
        experts = torch.stack([expert(x) for expert in self.experts], dim=1)
        return torch.cat([tower((gate(x).softmax(-1).unsqueeze(-1) * experts).sum(1))
                          for gate, tower in zip(self.gates, self.towers)], dim=1)


def masked_loss(logits, targets, masks):
    losses = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    counts = masks.sum(0)
    return ((losses * masks).sum(0) / counts.clamp_min(1))[counts > 0].mean()
