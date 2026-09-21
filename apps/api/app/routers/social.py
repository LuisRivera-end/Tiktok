from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from app.deps import CurrentUser, DbDep
from app.media_util import media_url
from app.models import Follow, InboxItem, User, Video
from app.schemas import FollowIn, InboxIn, InboxOut, ShareTargetOut

router = APIRouter(tags=["social"])


@router.post("/follows", status_code=status.HTTP_201_CREATED)
async def follow_user(payload: FollowIn, db: DbDep, current: CurrentUser) -> dict:
    if payload.followee_id == current.id:
        raise HTTPException(status_code=400, detail="No puedes seguirte a ti mismo")
    target = await db.get(User, payload.followee_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    existing = await db.scalar(
        select(Follow.id).where(Follow.follower_id == current.id, Follow.followee_id == payload.followee_id)
    )
    if existing:
        return {"ok": True, "followee_id": payload.followee_id, "created": False}
    db.add(Follow(follower_id=current.id, followee_id=payload.followee_id))
    await db.commit()
    return {"ok": True, "followee_id": payload.followee_id, "created": True}


@router.delete("/follows/{followee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(followee_id: str, db: DbDep, current: CurrentUser) -> None:
    row = await db.scalar(
        select(Follow).where(Follow.follower_id == current.id, Follow.followee_id == followee_id)
    )
    if row is None:
        return None
    await db.delete(row)
    await db.commit()
    return None


@router.get("/inbox", response_model=list[InboxOut])
async def list_inbox(db: DbDep, current: CurrentUser) -> list[InboxOut]:
    rows = await db.execute(
        select(InboxItem, User, Video)
        .join(User, User.id == InboxItem.from_user_id)
        .join(Video, Video.id == InboxItem.video_id)
        .where(InboxItem.to_user_id == current.id)
        .order_by(InboxItem.created_at.desc())
    )
    out: list[InboxOut] = []
    for item, sender, video in rows.all():
        out.append(
            InboxOut(
                id=item.id,
                from_user_id=sender.id,
                from_name=sender.display_name,
                video_id=video.id,
                video_title=video.title,
                created_at=item.created_at.isoformat(),
            )
        )
    return out


@router.post("/inbox", response_model=InboxOut, status_code=status.HTTP_201_CREATED)
async def send_inbox(payload: InboxIn, db: DbDep, current: CurrentUser) -> InboxOut:
    if payload.to_user_id == current.id:
        raise HTTPException(status_code=400, detail="No te envíes un recado a ti mismo")
    target = await db.get(User, payload.to_user_id)
    video = await db.get(Video, payload.video_id)
    if target is None or video is None:
        raise HTTPException(status_code=404, detail="Usuario o clip no encontrado")
    item = InboxItem(from_user_id=current.id, to_user_id=payload.to_user_id, video_id=payload.video_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return InboxOut(
        id=item.id,
        from_user_id=current.id,
        from_name=current.display_name,
        video_id=video.id,
        video_title=video.title,
        created_at=item.created_at.isoformat(),
    )


@router.get("/users/share-targets", response_model=list[ShareTargetOut])
async def share_targets(db: DbDep, current: CurrentUser) -> list[ShareTargetOut]:
    rows = await db.execute(select(User).where(User.id != current.id).order_by(User.role.asc()).limit(8))
    people = [user for user in rows.scalars() if user.role in {"creator", "viewer", "advertiser"}][:6]
    return [ShareTargetOut(id=user.id, display_name=user.display_name, role=user.role) for user in people]


@router.get("/me/profile")
async def my_profile(db: DbDep, current: CurrentUser) -> dict:
    videos = list(
        (
            await db.execute(
                select(Video).where(Video.creator_id == current.id).order_by(Video.created_at.desc())
            )
        ).scalars()
    )
    follow_count = int(
        (await db.scalar(select(func.count()).select_from(Follow).where(Follow.follower_id == current.id))) or 0
    )
    followee_rows = await db.execute(
        select(User)
        .join(Follow, Follow.followee_id == User.id)
        .where(Follow.follower_id == current.id)
        .limit(8)
    )
    followees = [{"id": person.id, "display_name": person.display_name} for person in followee_rows.scalars()]
    return {
        "user": {
            "id": current.id,
            "email": current.email,
            "display_name": current.display_name,
            "role": current.role,
            "age": current.age,
        },
        "clip_count": len(videos),
        "follow_count": follow_count,
        "following": followees,
        "videos": [
            {
                "id": video.id,
                "title": video.title,
                "category": video.category,
                "poster_seed": video.poster_seed,
                "width": int(getattr(video, "width", None) or 1080),
                "height": int(getattr(video, "height", None) or 1920),
                "media_url": media_url(video.media_path),
            }
            for video in videos
        ],
    }
