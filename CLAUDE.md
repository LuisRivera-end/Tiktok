# Veta

Prototipo escolar de feed corto: recomendación multiobjetivo, subasta de anuncios, telemetría. No se publica a internet.

## Commands

- Dev (todo Docker): `docker compose up --build` → http://127.0.0.1:8080
- Dev (web local): `pnpm dev:web` (Vite 5173, proxy `/api` → :8000)
- API local: `apps/api/.venv/Scripts/uvicorn app.main:app --reload --port 8000` (cwd `apps/api`, `SEED_ON_START=true`)
- Build web: `pnpm build:web`
- Typecheck web: `pnpm --filter veta-web exec tsc -b`
- Test API: `apps/api/.venv/Scripts/pytest` (cwd `apps/api`)
- Test web: `pnpm test:web`
- E2E: `pnpm test:e2e` (Playwright desktop / tablet / mobile)

There is no project-wide lint script. Web `lint:web` is a stub.

## Stack

- Frontend: Vite + React 19 + TypeScript + Tailwind CSS v4 + GSAP, pnpm workspace `apps/web`
- Backend: FastAPI + SQLAlchemy async + PostgreSQL (users, videos, campaigns) + MongoDB (events, online profiles)
- Ranking lives in `apps/api/app/recsys/`; ads in `apps/api/app/ads/`. Serving must not wait on BI or Orange.
- Orange Data Mining uses `GET /lab/orange/interactions.csv` — see `orange/README.md`
- Demo logins: `viewer@veta.local` / `veta1234` (also `creator@`, `advertiser@`, `admin@`)

## Notes

- Dual database: do not put heartbeat writes in Postgres or campaign budget in Mongo.
- Do not hardcode thesis metrics (58.7 min, AUC 0.912). Measure from events.
- Docker Compose does not publish Postgres/Mongo on the host (avoids clashing with local Mongo on 27017).
- ECC project skills: `.claude/skills/ecc/` (python, fastapi, postgres, react, docker, e2e, a11y).
