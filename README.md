# Taggle

A platform for gamifying data labeling. FastAPI backend, Next.js frontend, and a folder per game.

The home page is a game picker with Fruit Shift and Common Ground, a Wavelength-inspired sentiment game.

Fruit image research, a 48-photo review gallery, and segmentation feasibility notes are in [the dataset review](research/fruit-ninja/dataset-review/README.md). Gameplay uses **slash rotten / let healthy pass**.

## Structure

```text
backend/
  app/
    main.py                       # FastAPI app and health check
    games/
      fruit_ninja/router.py       # Fruit Ninja endpoints
      wavelength/                 # Review catalog, sentiment labels, synthetic pairs
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
    wavelength/game.tsx           # Common Ground solo and pass-and-play UI
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
- Fruit Shift endpoint: http://127.0.0.1:8000/api/games/fruit-ninja

The picker renders on its own; Fruit Shift needs the backend for images and saving. Requests to `/api/*` on the frontend are forwarded to FastAPI, so browser-side game components can use `fetch("/api/games/fruit-ninja")` without CORS configuration. To change the backend address, copy `frontend/.env.example` to `frontend/.env.local`, edit `BACKEND_URL`, and restart Next.js. Production rewrites use the value set at build time.

## Common Ground

Open **http://localhost:3000/games/wavelength**, or choose Common Ground on the home page. Both frontend and backend must be running.

- **Solo:** watch the emotion shuffle select a pair, read a fictional customer review, and guess its percentage toward that feeling. Lock your guess before the wheel spins to reveal the demo reference. Play sets of up to five unseen reviews.
- **Pass & play:** two people share one device. Emotion cards shuffle to select a pair, then a segmented wheel spins to Player 1’s secret percentage. Write a review to match, hide the target, and let Player 2 guess. Reveal, discuss the difference, then swap roles for five rounds.
- **The data you make:** inspect saved judgments and invented review pairs, then export JSON or CSV. Raw ratings, confidence, timing, provenance, and reference versions are retained. Synthetic writer intent and reader interpretation remain separate fields.

The 24 demo reviews and reference positions are authored examples, not real customer data or crowd consensus. Closeness points are game feedback, not annotation quality. Previously submitted reviews are excluded from this browser's new solo sets; the API flags repeat ratings under the same browser ID as feedback-conditioned. The handoff is a casual same-device interaction, not a secure multiplayer room.

Each round randomly chooses **Not angry ↔ Angry**, **Sad ↔ Happy**, **Bored ↔ Excited**, or **Disappointed ↔ Satisfied**. Percentages describe a position toward the right-hand feeling, not a probability. Every saved record and export includes the chosen emotion axis. Each review has a separately authored demo reference for each axis; anger is not inferred by inverting satisfaction. Existing saved data migrates to satisfaction, and pending submissions remain retry-safe. Reduced-motion mode skips the spins while showing the same selection and result.

Two-player rounds also pick an everyday scenario, such as stopping for gas, shopping, or ordering delivery. The neutral prompt guides the writer without suggesting a positive or negative experience. Both players see the same scenario, it survives reloads, and its title is saved in the synthetic review’s `category` field. Consecutive rounds use different scenarios.

Labels persist in `backend/wavelength.db`; set `WAVELENGTH_DB_PATH` to choose another path. Browser storage keeps an anonymous ID, current progress, and pending submissions for retry after reload. A failed save keeps its original submission ID and payload, so retries do not duplicate labels. This local prototype has no authentication; dataset inspection and exports cover all saved contributions on the server.

Design research, sources, collection limitations, and a proposed validation experiment are in [research/wavelength/README.md](research/wavelength/README.md).

Backend checks (including both games):

```sh
cd backend
.venv/bin/python -m unittest discover -s tests -v
```

Browser playtest instructions are in the [research notes](research/wavelength/README.md#browser-playtest).

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
npm test
npm run build
```

## Fruit Shift data

Open [Fruit Shift](http://localhost:3000/games/fruit-ninja). All 183 sprites are stored under `backend/assets/fruit_ninja/`. Player profiles, judgments, reviews and deck progress persist in Git-ignored `backend/data.db`. Names identify shared local profiles; there is no authentication.

Install backend test dependencies and run the isolated game tests from the repo root:

```sh
backend/.venv/bin/pip install -r backend/requirements-dev.txt
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -p 'test_fruit_shift.py' -v
```

The frontend test command uses native TypeScript stripping and requires Node 22.18+.
