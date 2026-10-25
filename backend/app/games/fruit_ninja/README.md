# Fruit Shift

A local, name-based fruit-labeling arcade at `/games/fruit-ninja`. Slice rotten fruit; a fully completed unsliced flight means `fresh` (shown as **Healthy**).

## Fixed product decisions

- Use exactly the 183 kept research cutouts. The 53 excluded partials never enter the game catalog.
- Freeze 91 prototype reference controls (52 fresh / 39 rotten) and 92 independent labeling targets in `assets/fruit_ninja/catalog.json`, version `fruit-shift-controls-v1`. `catalog.py` contains the approved roster. Historical source labels are provenance; targets start with zero player votes.
- Show one interactive scene with five healthy and five rotten strawberries, then ten balanced single-fruit calibration trials. The guide mixes obvious and subtler examples, and tapping a berry enlarges it with a short clue. All ten are existing frozen controls; targets are never exposed as examples. Pass at 8/10. Require calibration for new profiles, a changed reference version, and after a failed gameplay check.
- Each 60-second round has 16 controls (8/8) and 16 targets. Each section of eight contains 2 fresh controls, 2 rotten controls and 4 targets, shuffled together. No reference identity, correctness or label appears in mixed-play payloads.
- Pass the immutable first-pass check at 13/16 controls. Targets from failed or abandoned rounds are excluded; their events remain in history. Review never rescues accuracy or eligibility.
- Score 100 per correct control and 10 per target judgment. Reveal only aggregate scores after all eight presentations in a section have resolved and saved. Maximum gameplay score: 1,760.
- Optional sorting confirms four sections of eight, with drag and explicit move buttons. Each confirmed section appends eight review events and grants 10 points, including unchanged confirmations. A confirmed section locks; retries are idempotent. Maximum combined score: 1,800.
- Every qualifying target **appearance** contributes one effective vote, including repeats by the same player. Its submitted review replaces its original contribution without deleting the original event.
- Profiles use Unicode NFKC, collapsed whitespace and casefold matching. There is no authentication: equal names intentionally share a profile on this local backend.

## Asset and visual decisions

`prepare_assets.py` verifies original cutout hashes and copies PNGs into backend-owned `originals/`. `gameplay/` contains transparent WebP variants, at most 384 pixels on the long side. Asset UUIDs and delivery URLs do not contain condition-bearing source filenames. The private catalog preserves original IDs, source-photo hashes, crop boxes, source labels, reference membership, and reference provenance. Changing membership under an existing reference version is rejected by the importer; bump `REFERENCE_VERSION` for a changed standard.

The prototype uses a flat light blue playfield `#d9e8ed`, ink `#203e49`, ice `#edf4f5`, yellow `#f5d367`, mint `#b4ddbd` and peach `#f1b9a7`. Barlow and Barlow Condensed are self-hosted, with the OFL in `frontend/public/fonts/OFL.txt`. Keep the photo colors intact so dark damage, pale skin and mold remain readable. No conveyor, background grid or inspection labels compete with the fruit. The active HUD shows score/practice count, time and pause; sound/effects settings live in pause. Dataset access and optional review stay outside active play. This remains a prototype: prioritize the play loop and legibility over a final polish pass.

Sources: Nusrat Sultana, Musfika Jahan and Mohammad Shorif Uddin (2022), *Fresh and Rotten Fruits Dataset for Machine-Based Evaluation of Fruit Quality*, [Mendeley Data V1](https://doi.org/10.17632/bdd69gyhv8.1), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Cutouts add segmentation, cropping, alpha masks, resizing and WebP encoding. Original source photographs are unchanged. These are visually reviewed prototype references, not a new expert-certified standard.

## Timing and input

The animation loop lives outside React rendering. Twenty-one waves alternate two/one fruit at `800 + wave * 2800` milliseconds, with 3,200-millisecond flights. The last flight ends at 60,000 ms; at most three unsliced fruit are in flight. Lanes at 23% / 77%, alternating with 50%, separate trajectories. Speed and density stay constant.

All round images decode before the server starts the round. A three-second countdown precedes the active game clock. Pointer capture supports mouse/trackpad press-and-drag and touch swipes. Hover never calls hit testing. Swept segments are transformed into each rotated sprite's coordinates and sampled against its alpha mask. A resolved-ID set prevents duplicate cuts. Sprite halves are Canvas-clipped along the blade direction, then separate, rotate and fall; particles, a fading blade and synthesized short sounds acknowledge every cut identically. Mute and reduced-effects preferences persist locally. Fruit now use up to 184 pixels on the long side (98 minimum), with an arc that keeps even the rotated diagonal below the HUD on phones.

Two or more cuts in one continuous swipe, no more than 450 ms apart, trigger multi-slice callouts and rising sound pitch. These are cosmetic: they never assert correctness or grant points for indiscriminate cutting. A fully correct group of reference calls produces “Perfect wave”; consecutive perfect groups produce “Perfect combo ×N”. Both healthy passes and rotten cuts matter, and the feedback uses only the existing aggregate server score (440 for a perfect group), never an individual hidden label. Scoring and qualification thresholds are unchanged. Escape or P toggles pause unless saving needs attention.

Blur, hidden documents and a render gap over 500 ms pause the active clock and input. Resuming never advances a paused flight. Unsliced fruit labels are emitted only at the end of a complete active-play flight. Reloading abandons the unfinished round after pending uploads are flushed; it never completes unseen fruit as healthy.

## Persistence and retry rules

SQLite defaults to `backend/data.db`; `FRUIT_SHIFT_DB_PATH` selects another file. WAL and foreign keys are enabled. The database and its sidecars are Git-ignored. Back up with SQLite's backup API rather than copying only a live database file without its WAL.

- `assets`: immutable opaque identity and private source/reference metadata.
- `players`: normalized names, calibration state and persistent decks.
- `rounds`: kind, lifecycle, reference version, timestamps, frozen first-pass result and eligibility.
- `presentations`: server-owned assignments, timing, appearance ID and private reference snapshot.
- `label_events`: append-only original, demonstration and review actions, client/server timestamps and active-play exposure.
- `section_scores` / `review_submissions`: transactional, retry-safe section awards and confirmations.

A player's target deck covers all 92 before a cycle repeats. Controls rotate separately in fresh/rotten bags. A new round abandons any older active round for that player; unresolved targets return to the front of the deck. Completed appearances from an abandoned round remain recorded but excluded.

The browser writes pending operations to `localStorage` before sending. One serial outbox retries exact event/submission IDs and removes them only after acknowledgment. An 8-second API timeout or save failure pauses play. Completion requires all judgments saved; unsaved rounds cannot qualify. The server maps actions to labels, validates flight windows/completed exposure, owns score calculation, and rejects conflicting duplicate judgments. These checks provide consistency for a local prototype; this is not an authenticated anti-cheat service.

## API and exports

All routes are under `/api/games/fruit-ninja`; see `/docs` for request schemas.

| Resource | Behavior |
| --- | --- |
| `POST /players`, `GET /players/{id}` | Match/create profile; calibration state and recent shifts |
| `POST /rounds` | Prepare `demonstration`, `calibration` or `game` assignments |
| `POST /rounds/{id}/start` | Start only after image preparation |
| `POST /rounds/{id}/events` | Idempotent action ingestion; feedback only for calibration |
| `POST /rounds/{id}/sections/{section}` | Aggregate eight-presentation score |
| `POST /rounds/{id}/complete`, `/abandon` | Freeze eligibility or retain excluded history |
| `GET /rounds/{id}/result`, `/review` | Results and the player's effective assignments |
| `POST /rounds/{id}/review/{section}` | Append one retry-safe confirmation per section |
| `GET /assets/{opaque_id}` | Transparent gameplay WebP; `?original=true` serves original PNG |
| `GET /dataset` | 92 target thumbnails, tallies and eligible effective votes |
| `GET /exports/json`, `/exports/csv` | Eligible effective votes; `?audit=true` includes every raw event |

Public source-photo provenance uses stable opaque photo IDs, source-photo SHA-256, original cutout SHA-256 and source crop coordinates. This supports grouping/splitting correlated fruit and joining back to the private seed. Public exports omit condition-bearing source IDs, historical labels and reference answers. Audit rows retain original/review events, players, timestamps, first-pass round eligibility, effective-vote flags and exclusion reasons. Default exports never count demonstrations, calibration, controls, superseded originals or ineligible rounds.

## Run and verify

Assets are included. To regenerate them from the existing research outputs, from the repository root:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m app.games.fruit_ninja.prepare_assets
```

Start the existing FastAPI and Next.js apps as described in the root README. Python 3.10+ runs the backend; use Node 22.18+ for the native TypeScript test command.

```sh
backend/.venv/bin/pip install -r backend/requirements-dev.txt
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -p 'test_fruit_shift.py' -v
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
```

The tests cover asset membership/hash/transparency, thresholds, hidden control balance and payloads, incomplete/failed rounds, idempotency, unchanged/revised review sections, repeat votes, deck coverage and restart persistence. Client tests cover fast/rotated alpha-aware swipes, transparent misses, a stroke across multiple fruit, flight geometry and durable outbox retries.

Browser evidence and manual verification are recorded in `research/fruit-ninja/game-verification/README.md`.


## Label-quality research

The trained gradient-boosting pilot, frozen data snapshot, photo-held-out evaluation, visual audit and follow-up experiment design live in `research/fruit-ninja/label-quality/README.md` and `results/REPORT.md`. This research runs in an isolated virtual environment and reads SQLite without modifying gameplay labels. It is not part of the live game's qualification/scoring logic.
