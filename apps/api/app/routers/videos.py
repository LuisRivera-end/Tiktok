from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import CurrentUser, DbDep
from app.hashtags import parse_hashtags
from app.media_util import media_url
from app.models import Comment, InboxItem, Video
from app.recsys.vector import CATEGORIES, video_embedding
from app.schemas import CommentIn, CommentOut, VideoOut

router = APIRouter(prefix="/videos", tags=["videos"])


def serialize(video: Video, *, comment_count: int = 0, share_count: int = 0) -> VideoOut:
    creator_name = video.creator.display_name if video.creator else ""
    return VideoOut(
        id=video.id,
        creator_id=video.creator_id,
        creator_name=creator_name,
        title=video.title,
        description=video.description,
        tags=list(video.tags or []),
        audio_id=video.audio_id,
        category=video.category,
        duration_ms=video.duration_ms,
        media_path=video.media_path,
        poster_seed=video.poster_seed,
        status=video.status,
        play_count=video.play_count,
        age_restricted=video.age_restricted,
        width=int(getattr(video, "width", None) or 1080),
        height=int(getattr(video, "height", None) or 1920),
        media_url=media_url(video.media_path),
        comment_count=comment_count,
        share_count=share_count,
    )


@router.get("/{video_id}", response_model=VideoOut)
async def get_video(video_id: str, db: DbDep) -> VideoOut:
    result = await db.execute(select(Video).options(selectinload(Video.creator)).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    comments = await db.scalar(select(func.count()).select_from(Comment).where(Comment.video_id == video.id))
    shares = await db.scalar(select(func.count()).select_from(InboxItem).where(InboxItem.video_id == video.id))
    return serialize(video, comment_count=int(comments or 0), share_count=int(shares or 0))


@router.get("/{video_id}/comments", response_model=list[CommentOut])
async def list_comments(video_id: str, db: DbDep) -> list[CommentOut]:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    from app.models import User

    rows = await db.execute(
        select(Comment, User)
        .join(User, User.id == Comment.user_id)
        .where(Comment.video_id == video_id)
        .order_by(Comment.created_at.asc())
    )
    out: list[CommentOut] = []
    for comment, user in rows.all():
        out.append(
            CommentOut(
                id=comment.id,
                user_id=comment.user_id,
                author_name=user.display_name,
                body=comment.body,
                created_at=comment.created_at.isoformat(),
            )
        )
    return out


@router.post("/{video_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_comment(video_id: str, payload: CommentIn, db: DbDep, current: CurrentUser) -> CommentOut:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="El comentario está vacío")
    comment = Comment(user_id=current.id, video_id=video_id, body=body)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return CommentOut(
        id=comment.id,
        user_id=current.id,
        author_name=current.display_name,
        body=comment.body,
        created_at=comment.created_at.isoformat(),
    )


@router.post("", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
async def upload_video(
    db: DbDep,
    current: CurrentUser,
    title: str = Form(),
    category: str = Form(),
    description: str = Form(""),
    hashtags: str = Form(""),
    audio_id: str = Form("audio-lab"),
    duration_ms: int = Form(14000),
    width: int = Form(1080),
    height: int = Form(1920),
    file: UploadFile | None = File(default=None),
) -> VideoOut:
    if current.role not in {"creator", "advertiser", "admin"}:
        raise HTTPException(status_code=403, detail="Solo un creador o anunciante puede publicar")
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Categoría desconocida")

    media_path = None
    if file is not None and file.filename:
        folder = Path(settings.media_dir)
        folder.mkdir(parents=True, exist_ok=True)
        suffix = Path(file.filename).suffix.lower() or ".mp4"
        if suffix not in {".mp4", ".webm"}:
            suffix = ".mp4"
        stored_name = f"{current.id}-{uuid4().hex}{suffix}"
        stored = folder / stored_name
        stored.write_bytes(await file.read())
        media_path = stored_name

    tags = parse_hashtags(hashtags)
    if category not in tags:
        tags = [category, *tags][:8]

    video = Video(
        creator_id=current.id,
        title=title,
        description=description,
        tags=tags,
        audio_id=audio_id,
        category=category,
        duration_ms=duration_ms or 14000,
        width=width or 1080,
        height=height or 1920,
        media_path=media_path,
        poster_seed=title[:24],
        status="active",
        play_count=0,
        content_hash=f"upload-{current.id}-{title}",
        embedding=[],
    )
    db.add(video)
    await db.flush()
    video.embedding = video_embedding(video.id, video.category, video.audio_id)
    await db.commit()
    await db.refresh(video)
    video.creator = current
    return serialize(video)
