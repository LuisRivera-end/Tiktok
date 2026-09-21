from __future__ import annotations

from pathlib import Path


def media_filename(path: str | None) -> str | None:
    if not path:
        return None
    name = Path(path.replace("\\", "/")).name
    return name or None


def media_url(path: str | None) -> str | None:
    name = media_filename(path)
    if not name:
        return None
    return f"/media/{name}"
