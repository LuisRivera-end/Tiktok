from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.mongo import close_mongo, ensure_indexes
from app.routers import auth, campaigns, events, feed, lab, media, social, videos
from app.seed import inject_corpus_if_needed, seed_if_empty, seed_social_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS width INTEGER DEFAULT 1080"))
        await conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS height INTEGER DEFAULT 1920"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS region VARCHAR(40) DEFAULT ''"))
        await conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS region VARCHAR(40) DEFAULT ''"))
    try:
        await ensure_indexes()
    except Exception:
        # Mongo puede faltar en pruebas unitarias locales.
        pass
    if settings.seed_on_start:
        async with SessionLocal() as session:
            await seed_if_empty(session)
            await seed_social_if_empty(session)
            await inject_corpus_if_needed(session)
    yield
    await engine.dispose()
    await close_mongo()


def create_app() -> FastAPI:
    application = FastAPI(title="Veta API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth.router)
    application.include_router(videos.router)
    application.include_router(events.router)
    application.include_router(feed.router)
    application.include_router(campaigns.router)
    application.include_router(lab.router)
    application.include_router(social.router)
    application.include_router(media.router)
    return application


app = create_app()


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "app": settings.app_name, "env": settings.app_env}
