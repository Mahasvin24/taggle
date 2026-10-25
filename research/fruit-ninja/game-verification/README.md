# Fruit Shift verification

Verified locally on 2026-10-24. This folder contains browser screenshots; durable game rules and implementation decisions are in `backend/app/games/fruit_ninja/README.md`.

## Automated checks

- Six backend API/database tests cover all 183 kept asset IDs and byte hashes, the exact 91/92 partition, alpha variants, calibration and gameplay thresholds, balanced control assignments, reference-version invalidation, no private-label leakage, retry IDs, section scoring, excluded failed/abandoned rounds, immutable accuracy, effective review votes, repeated appearances, persistent deck coverage, SQLite restart persistence, and JSON/CSV contents.
- Four frontend tests cover swept alpha hits, transparent misses, rotation, a stroke crossing multiple fruit, flight endpoints/apex, half-plane geometry and outbox persistence/retries/concurrent flushes.
- Frontend lint, TypeScript checks and production build passed during Fruit Shift verification. The final repeat of the repository-wide typecheck encountered concurrent `frontend/games/wavelength/game.tsx` changes (missing axis/setup properties and changed Dial props); it reported no Fruit Shift type errors. Those unrelated edits were preserved.

## Browser playthrough

A clearly named local QA profile was created through the name form. All four demonstrations were inspected. Calibration was played through the Canvas using actual pointer drags, including failed attempts and a passing 8/10 attempt. The test driver initially missed some fruit because its stored canvas coordinates became stale after the browser scrolled a clicked control into view; correcting the driver to read the current bounding rectangle resolved the misses.

The complete gameplay round ran for 60 seconds of active play, used all 32 presentations, showed only grouped section scores, and finished with 16/16 first-pass control accuracy and 1,760 gameplay points. The reference schedule was read privately for deterministic QA; this is a functional check, not a measurement of a human labeler's ability. Target judgments in this QA run are test data, not a curated training dataset.

The backend was deliberately stopped midway through that round. A completed judgment stayed pending in browser storage; the game paused with “Saving needs attention.” After restarting FastAPI against the same SQLite file, retry recovered the pending event, preserved the timer/round state and completed without duplicate votes.

One target assignment was changed during final sorting, then all four review sections were confirmed (including unchanged sections). Results showed 1,800 total points, unchanged 16/16 first-pass accuracy, and 16 effective target votes. The changed appearance replaced its previous contribution: the dataset displayed 15 healthy / 1 rotten target votes rather than 17 total votes.

The returning profile and previous 1,800-point result survived backend restart and page reload. An additional paused round was reloaded while unfinished; it was abandoned without converting unseen fruit into healthy judgments. Responsive views were inspected at 390 × 844 and the surrounding small-width layout; normal laptop play was inspected at 1280 × 720. A physical touchscreen was not available; the same Pointer Events path handles mouse and touch.

## Export check boundary

API/database tests verify eligible JSON/CSV rows and raw audit exports. Clicking CSV in the browser reached the browser's download permission gate, which was declined. No downloaded browser file was acquired and no workaround was attempted. Actual browser download delivery remains unverified in this environment.

## Screenshots

- `slice.png`: two clipped sprite halves separating during gameplay, with another fruit still in flight and no per-fruit score/correctness indicators.
- `results.png`: 16/16 first-pass accuracy and 1,760 gameplay points before review.
- `mobile-dataset.png`: touch-sized dataset view with target tallies and export controls.
- `mobile-play.png`: touch-sized paused arena and controls.

The 106 local QA events and their unchanged rounds, scores, reviews, profile and deck are archived in Git-ignored `backend/fruit-shift-browser-qa.db`. The archive was verified and committed before removing only that test profile’s rows from `backend/data.db`; unrelated data is preserved. No QA votes remain in production; existing judgments from other players are preserved. Automated tests use temporary databases.


## Simpler arcade prototype pass (2026-10-24)

The manual now shows five healthy and five rotten strawberries together, with selectable larger previews and concise explanations. It uses only existing reference controls, mixing bright/dark healthy berries and obvious/subtle deterioration. The active game uses a flat light blue ground, larger unfiltered photographic sprites and only score/practice count, timer and pause. Sound and effects settings moved into pause. The welcome/results copy emphasizes playing again; dataset tools stay outside the playfield.

Multi-fruit swipes produce a callout, separated halves, a contrasting blade trail and rising sound pitch. Cuts must be within one continuous gesture and 450 ms of each other. These effects grant no extra points or correctness hints. Fully correct reference groups produce a perfect-wave callout; consecutive perfect groups produce accuracy combos, including healthy passes. Existing server points and qualification thresholds stay unchanged. Flight arcs reserve HUD space even for the rotated sprite diagonal on a phone.

Verification for this pass:

- Seven backend tests passed, including a new contract test for ten balanced strawberry demonstrations, exclusion from dataset votes, and disjoint calibration examples. Four frontend tests passed, including swept/rotated hits, multi-fruit strokes, durable outbox retries and HUD clearance at phone width. Lint, typecheck and production build passed.
- Isolated headless Chrome playthrough used real pointer input and a simulated animation clock: practice 10/10; a full game 16/16 reference accuracy, 32 saved calls, 1,760 points and 16 eligible target votes. Test targets were deliberately left healthy; this checks the game plumbing, not human labeling performance. Browser/API errors: none. Pause held the timer; resume, effects/mute preferences, replay and abandon worked.
- A single desktop gesture cut two fruit. A native Chromium touch emulation gesture also cut two fruit on a 390px-wide phone viewport. The first touch test aimed at stale positions while fruit were rising; following the current render positions near the apex corrected the test. No physical touchscreen or sound-listening assessment was performed.
- Desktop, tablet and phone screenshots were inspected. The installed Taste Skill browser inspector reported zero failures and four warnings on the welcome screen. The warnings concern the shared Taggle system font, a deliberate gap below the game wordmark, and game-title size versus its dashboard defaults; these were retained to keep this a scoped prototype change.

QA votes live only in `/tmp/fruit-ui-qa/game.db`, routed through a separate temporary backend on port 8001. No gameplay test votes were sent to the production backend. The running local backend on port 8000 was restarted with its original default database paths to load the new catalog.

New screenshots: `prototype-guide.png`, `prototype-guide-mobile.png`, `prototype-combo.png`, and `prototype-touch-combo.png`. Earlier screenshots above describe the previous packing-line visual.
