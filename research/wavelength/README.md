# Common Ground: sentiment as a social guessing game

Research and implementation rationale, 2026-10-24. This is an original proof of concept inspired by Wavelength's hidden-target mechanic, not an official Wavelength adaptation.

## What makes Wavelength useful here

One player privately sees a target on a spectrum between opposing concepts, then gives a conceptual clue. Other players interpret the clue and place a dial before the target is revealed. That loop creates anticipation and conversation around differences in interpretation. The publisher and distributor describe this mechanism in [CMYK's Wavelength overview](https://www.cmyk.games/products/wavelength) and [Asmodee's gameplay description](https://www.asmodeenordics.com/product/wavelength/).

For reviews, each round focuses on one familiar emotion pair: **Not angry ↔ Angry**, **Sad ↔ Happy**, **Bored ↔ Excited**, or **Disappointed ↔ Satisfied**. An animated emotion-card reel visibly selects the pair. In pass-and-play a segmented wheel then spins to the secret percentage; in solo the wheel reveals the authored reference only after the guess is saved. Large emoji cards and a prominent percentage replace the plotted dial. Percentages express position toward the right-hand feeling, not calibrated probabilities. The interesting cases are mixed experiences, restrained praise, sarcasm, and different expectations. Whether these mechanics improve engagement and useful annotation remains a hypothesis.

## Two loops, two kinds of data

| Mode | Play | What the record means |
| --- | --- | --- |
| Solo | Shuffle an emotion pair, read a review, choose a percentage and confidence, lock the answer, then spin to reveal the demo reference. | An independent human interpretation for the selected emotion dimension, captured before feedback. |
| Two players | Shuffle an emotion pair, spin a secret target, write a plausible review; hide the target, pass the device, let the reader guess, then spin to reveal. | A synthetic review with an intended emotion and a separate reader interpretation. |

The writer's target is **an instruction**, not a verified sentiment label. The reader's guess measures interpretation of deliberately generated text; it is not evidence about naturally occurring customer reviews. Keep these records separately identified in storage and exports. Same-device handoff is a social privacy convention, not a security boundary against inspecting the browser.

All included review examples and their reference positions are authored demonstrations. They are not scraped customer data, independent crowd consensus, or gold labels. Each review has a separately authored reference for each emotion axis. These are not mathematical conversions of an overall satisfaction label. Records and exports include `axis_id`, `axis_left`, and `axis_right`; existing records migrate to satisfaction. A solo record is independently supplied by the player, but its underlying text still has synthetic/demo provenance. Do not call its reference the "correct answer."

## Evidence that informs the design

- **Games with a purpose:** von Ahn and Dabbish explain how useful outputs can arise from play. Their evaluation combines useful work per human-hour with how long people choose to play. This suggests measuring retained participation and usable contributions, not just how quickly people move a slider. [Designing Games With a Purpose, 2008](https://www.cs.cmu.edu/~biglou/GWAP_CACM.pdf).
- **Sentiment-specific precedent:** Guesstiment is an asynchronous two-player game intended to collect document sentiment and sentiment-bearing words. It supports the feasibility of a shared interpretation loop, but does not validate this prototype's numerical scale or review-writing mechanic. [Musat, Ghasemi, and Faltings, 2012](https://aclanthology.org/W12-4001/).
- **Fine-grained annotation:** Sentimentator demonstrates gamified collection of multidimensional sentiment and emotion annotations. It is a precedent for making fine-grained judgments playable; it does not establish that gamification automatically improves annotation quality. [Öhman et al., 2018](https://aclanthology.org/W18-6205/).
- **Preserve disagreement:** Plank argues that human label variation can reflect valid alternative interpretations rather than annotation error. Save individual judgments and confidence instead of replacing them with a single aggregate. In a later sentiment annotation study, Barz et al. similarly report substantial disagreement in environmental communication; that domain differs from customer reviews. [Plank, 2022](https://aclanthology.org/2022.emnlp-main.731/), [Barz et al., 2025](https://aclanthology.org/2025.law-1.1/).

## Incentives and safeguards

Use short rounds, a tactile dial, a delayed reveal, and session progress to create a game loop. Avoid a speed bonus: thoughtful reading should remain viable. Let players express uncertainty and skip examples. Keep raw guesses even when they earn few points.

Distance-to-reference points make the demo legible, but reward learning the author's taste. They must not be used as an annotator-reliability metric. Do not show prior votes or references before submission. Avoid repeating examples after their reference has been revealed; a later vote is feedback-conditioned and should not be counted as a new independent first impression. Save reference versions, anonymous session identifiers, elapsed time, and idempotent submission identifiers so feedback, retries, and repeat sessions can be interpreted correctly.

For a real collection pilot, reserve accuracy points for clearly designated calibration items. Reward participation on unknown items; reveal a distribution only after independent responses exist. Retain disagreement rather than pressuring everyone toward a majority. These are proposed next-stage safeguards, not features claimed to exist in the demo.

## Validation experiment before scaling

Run a small preregistered pilot comparing a plain sentiment slider with the solo game. Give both groups the same instructions and randomized, licensed real review items; include mixed and sarcastic language. Obtain at least three independent judgments per item, keep a participant's item exposure history, and use a separate calibration set. A second pilot can compare synthetic two-player examples against held-out real reviews; do not mix the corpora while evaluating.

Measure completion rate, voluntary additional rounds, usable first-exposure judgments per participant-minute, confidence, and reported enjoyment. Evaluate test–retest consistency on a separately scheduled subset and disagreement distributions per item; neither agreement nor closeness to an author's reference alone establishes quality. With domain-expert review, investigate low-confidence and strongly divergent cases rather than deleting them automatically. Evaluate any downstream sentiment model on held-out real reviews, splitting synthetic examples by author/pair to reduce leakage.

The proof of concept succeeds if people understand both modes, enjoy another round, and produce correctly attributed, exportable records. It does not yet establish cheaper labeling, representative sentiment ground truth, reliable identity, or improved model performance.

## Browser playtest

`playtest.py` checks complete five-round solo and two-player sets, keyboard controls, hidden-target handoff, reload recovery, a rejected save, a committed save with a lost response, retry idempotency, non-repeating decks, JSON/CSV downloads, and mobile overflow. It generates screenshots for visual review. Use a **fresh disposable database**, because the script intentionally creates test contributions and requires an empty collection. It leaves the normal development database untouched by proxying game API requests to port 8001.

With the normal frontend running on port 3000, start an isolated API from the repo root in another terminal:

```sh
PLAYTEST_DIR=$(mktemp -d /tmp/common-ground-qa.XXXXXX)
cd backend
FRUIT_SHIFT_DB_PATH="$PLAYTEST_DIR/fruit.db" WAVELENGTH_DB_PATH="$PLAYTEST_DIR/sentiment.db" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Run the browser script from the repo root using a Python environment with `playwright` installed (`python -m pip install playwright`, then `python -m playwright install chromium`):

```sh
python research/wavelength/playtest.py
```

Optional environment variables: `BASE_URL`, `API_ORIGIN`, `PLAYTEST_OUTPUT` (default `/tmp/common-ground-playtest`), and `CHROME_PATH` to use an existing Chrome executable. Stop the isolated API after testing. Backend validation and persistence checks are in `backend/tests/test_wavelength.py`; use the root README's unittest command to run both games' tests.
