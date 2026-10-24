# Taggle

A platform for gamifying data labeling. FastAPI backend, Next.js frontend, and a folder per game.

The initial home page is a game picker. Fruit Ninja has a starter page and API router; gameplay, fruit images, and label storage will come next.

## Structure

```text
backend/
  app/
    main.py                       # FastAPI app and health check
    games/
      fruit_ninja/router.py       # Fruit Ninja endpoints
  requirements.txt
frontend/
  app/
    page.tsx                      # Game picker
    games/[slug]/page.tsx          # Looks up a game in the registry
    layout.tsx
    globals.css
  games/
    registry.ts                   # Game metadata and entry components
    fruit-ninja/game.tsx          # Fruit Ninja UI
  next.config.ts                  # Forwards /api/* to FastAPI
```

## Run locally

Requires Node.js 20.9+ and Python 3.10+.

Backend, from the repo root:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Frontend, in a second terminal from the repo root:

```sh
cd frontend
npm ci
npm run dev
```

- Frontend: http://localhost:3000
- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/health
- Fruit Ninja starter endpoint: http://127.0.0.1:8000/api/games/fruit-ninja

The frontend works on its own. Requests to `/api/*` on the frontend are forwarded to FastAPI, so browser-side game components can use `fetch("/api/games/fruit-ninja")` without CORS configuration. To change the backend address, copy `frontend/.env.example` to `frontend/.env.local`, edit `BACKEND_URL`, and restart Next.js. Production rewrites use the value set at build time.

## Add a game

1. Create `frontend/games/<slug>/game.tsx` and add its component and metadata to `frontend/games/registry.ts`. It gets a home page card and `/games/<slug>` route automatically.
2. Create `backend/app/games/<game_name>/router.py` (and `__init__.py`) with an `APIRouter` prefixed `/api/games/<slug>`.
3. Include that router in `backend/app/main.py`.

Keep game-specific components, assets, and API logic inside each game's folder. Add shared folders only when multiple games need them.

## Frontend checks

```sh
cd frontend
npm run lint
npm run typecheck
npm run build
```
