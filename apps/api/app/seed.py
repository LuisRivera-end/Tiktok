from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdCampaign, AdCreative, Comment, Follow, User, Video
from app.recsys.vector import CATEGORIES, video_embedding
from app.security import hash_password

PASSWORD = "veta1234"

TITLES = {
    "comedia": ["El corte que nadie pidió", "Sí, otra vez el mismo chiste", "Micro sketch de laboratorio"],
    "ciencia": ["Por qué cae el feed", "Vectores en 40 segundos", "El sesgo que no ves"],
    "musica": ["Loop de cobre", "Beat de cantera", "Acordes para quedarse"],
    "cocina": ["Salsa en un take", "Pan de prueba A/B", "El fuego justo"],
    "deporte": ["El último sprint", "Táctica de 12 segundos", "El rebote que cuenta"],
    "arte": ["Tinta sobre escenario", "Un trazo, un scroll", "Color que no pide like"],
    "idiomas": ["Una palabra que se queda", "Traduce el ritmo", "Frase corta, recuerdo largo"],
    "tecnologia": ["Latencia que se siente", "El ranking en voz alta", "HNSW sin misterio"],
    "naturaleza": ["Veta de río", "Luz de las 18:00", "Piedra y musgo"],
    "historia": ["Un minuto, un siglo", "Archivo abierto", "Lo que el algoritmo olvida"],
    "baile": ["Cuenta ocho", "Piso de teatro", "Giro que no se salta"],
    "manualidades": ["Cobre y hilo", "Pieza pequeña", "El detalle que retiene"],
    "salud": ["Respira entre clips", "Pausa de 2 segundos", "Cuerpo vs scroll"],
    "cine": ["Plano corto", "Corte en negro", "El gancho honesto"],
    "emprendimiento": ["Presupuesto del día", "La puja justa", "No vendas el feed"],
}


async def seed_if_empty(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count()).select_from(User))
    if count:
        return

    viewer = User(email="viewer@veta.local", display_name="Lía Viewer", password_hash=hash_password(PASSWORD), role="viewer", age=21)
    creator = User(email="creator@veta.local", display_name="Mar Cantera", password_hash=hash_password(PASSWORD), role="creator", age=24)
    advertiser = User(email="advertiser@veta.local", display_name="Taller Norte", password_hash=hash_password(PASSWORD), role="advertiser", age=30)
    admin = User(email="admin@veta.local", display_name="Admin Lab", password_hash=hash_password(PASSWORD), role="admin", age=28)
    extras = [
        User(
            email=f"creator{i}@veta.local",
            display_name=f"Creador {i:02d}",
            password_hash=hash_password(PASSWORD),
            role="creator",
            age=20 + i,
        )
        for i in range(1, 9)
    ]
    db.add_all([viewer, creator, advertiser, admin, *extras])
    await db.flush()

    creators = [creator, *extras]
    videos: list[Video] = []
    for cat_index, category in enumerate(CATEGORIES):
        titles = TITLES[category]
        for copy_index in range(4):
            title = titles[copy_index % len(titles)]
            creator_row = creators[(cat_index + copy_index) % len(creators)]
            play_count = 12 if copy_index == 0 else 40 + cat_index * 7 + copy_index * 11
            if copy_index == 0:
                play_count = 18 + cat_index  # emergentes < 100
            video = Video(
                creator_id=creator_row.id,
                title=f"{title} · {copy_index + 1}",
                description="Clip sintético del laboratorio Veta.",
                tags=[category, "laboratorio", "corto", "veta"],
                audio_id=f"audio-{category}-{copy_index % 3}",
                category=category,
                duration_ms=12000 + (copy_index * 2500) + cat_index * 400,
                poster_seed=f"{category}-{copy_index}",
                status="active",
                play_count=play_count,
                content_hash=f"{category}-{copy_index}-{creator_row.id[:8]}",
                embedding=[],
            )
            videos.append(video)
    db.add_all(videos)
    await db.flush()
    for video in videos:
        video.embedding = video_embedding(video.id, video.category, video.audio_id)

    ad_video = next(v for v in videos if v.category == "emprendimiento")
    campaign = AdCampaign(
        advertiser_id=advertiser.id,
        name="Taller de retención",
        status="active",
        bid_cents=120,
        daily_budget_cents=8000,
        spent_today_cents=0,
        targeting_tags=["laboratorio"],
        targeting_categories=["tecnologia", "emprendimiento", "ciencia"],
    )
    empty_campaign = AdCampaign(
        advertiser_id=advertiser.id,
        name="Sin presupuesto",
        status="active",
        bid_cents=90,
        daily_budget_cents=0,
        spent_today_cents=0,
        targeting_categories=["comedia"],
    )
    db.add_all([campaign, empty_campaign])
    await db.flush()
    db.add(AdCreative(campaign_id=campaign.id, video_id=ad_video.id, landing_url="https://example.edu/veta"))
    await db.commit()
    await seed_social_if_empty(db)


async def seed_social_if_empty(db: AsyncSession) -> None:
    comment_count = await db.scalar(select(func.count()).select_from(Comment))
    follow_count = await db.scalar(select(func.count()).select_from(Follow))
    if comment_count and follow_count:
        return

    viewer = await db.scalar(select(User).where(User.email == "viewer@veta.local"))
    mar = await db.scalar(select(User).where(User.email == "creator@veta.local"))
    taller = await db.scalar(select(User).where(User.email == "advertiser@veta.local"))
    if viewer is None or mar is None:
        return

    if not follow_count:
        db.add(Follow(follower_id=viewer.id, followee_id=mar.id))

    if not comment_count:
        ciencia = list(
            (await db.execute(select(Video).where(Video.category == "ciencia").limit(2))).scalars()
        )
        musica = list(
            (await db.execute(select(Video).where(Video.category == "musica").limit(1))).scalars()
        )
        samples = ciencia + musica
        texts = [
            (viewer, "el sesgo se ve en el skip"),
            (mar, "vector vs popular, 40s"),
            (taller, "esto retiene más que el anuncio"),
        ]
        for index, video in enumerate(samples):
            author, body = texts[index % len(texts)]
            db.add(Comment(user_id=author.id, video_id=video.id, body=body))
            if index == 0 and mar is not None:
                db.add(Comment(user_id=mar.id, video_id=video.id, body="el hashtag laboratorio pesa"))

    await db.commit()
