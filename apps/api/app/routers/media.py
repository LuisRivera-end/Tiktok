import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(tags=["media"])
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


@router.get("/media/{filename}")
async def get_media(filename: str) -> FileResponse:
    if not SAFE_NAME.fullmatch(filename) or ".." in filename:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    folder = Path(settings.media_dir).resolve()
    target = (folder / filename).resolve()
    if not str(target).startswith(str(folder)) or not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(target)
