from __future__ import annotations

import hashlib
import math

CATEGORIES = [
    "comedia",
    "ciencia",
    "musica",
    "cocina",
    "deporte",
    "arte",
    "idiomas",
    "tecnologia",
    "naturaleza",
    "historia",
    "baile",
    "manualidades",
    "salud",
    "cine",
    "emprendimiento",
]

EMBED_DIM = 128


def _unit(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def category_basis(category: str) -> list[float]:
    idx = CATEGORIES.index(category) if category in CATEGORIES else 0
    vec = [0.0] * EMBED_DIM
    block = EMBED_DIM // len(CATEGORIES)
    start = idx * block
    for i in range(start, min(start + block, EMBED_DIM)):
        vec[i] = 1.0
    return _unit(vec)


def seeded_noise(seed: str, dim: int = EMBED_DIM) -> list[float]:
    digest = hashlib.sha256(seed.encode()).digest()
    out: list[float] = []
    while len(out) < dim:
        digest = hashlib.sha256(digest).digest()
        for byte in digest:
            out.append((byte / 255.0) * 2 - 1)
            if len(out) == dim:
                break
    return out


def video_embedding(video_id: str, category: str, audio_id: str) -> list[float]:
    base = category_basis(category)
    noise = seeded_noise(f"{video_id}:{audio_id}")
    mixed = [0.82 * b + 0.18 * n for b, n in zip(base, noise, strict=True)]
    return _unit(mixed)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True))


def blend(current: list[float], target: list[float], lr: float) -> list[float]:
    if not current:
        return list(target)
    mixed = [(1 - lr) * c + lr * t for c, t in zip(current, target, strict=True)]
    return _unit(mixed)


def move_away(current: list[float], target: list[float], lr: float) -> list[float]:
    if not current:
        return _unit([-t for t in target])
    mixed = [c - (1.0 + lr) * t for c, t in zip(current, target, strict=True)]
    return _unit(mixed)
