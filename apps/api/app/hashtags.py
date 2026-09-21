from __future__ import annotations

import re

TOKEN = re.compile(r"^[a-z0-9-]{1,24}$")
SPLIT = re.compile(r"[\s,]+")


def parse_hashtags(raw: str, *, limit: int = 8) -> list[str]:
    parts = SPLIT.split((raw or "").strip().lower())
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        tag = part.lstrip("#")
        if not tag or tag in seen or not TOKEN.fullmatch(tag):
            continue
        seen.add(tag)
        out.append(tag)
        if len(out) >= limit:
            break
    return out
