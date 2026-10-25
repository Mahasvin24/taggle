"use client";
/* Photographic sprites intentionally use native img: opaque same-origin URLs,
   alpha masks and decoded Canvas images are shared by the game and review. */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useRef, useState } from "react";
import Arena, { type Hud } from "./arena";
import { api, base, flush, pending, queue } from "./api";
import type {
  Asset,
  Dataset,
  Judgment,
  Label,
  Profile,
  Result,
  Round,
} from "./types";
import styles from "./game.module.css";

type Screen = "welcome" | "demo" | "play" | "results" | "review" | "dataset";
const emptyHud = { elapsed: 0, fresh: 0, rotten: 0, resolved: 0 };
const healthy = (label: Label) => (label === "fresh" ? "Healthy" : "Rotten");
export default function FruitNinja() {
  const [screen, setScreen] = useState<Screen>("welcome");
  const [profile, setProfile] = useState<Profile | null>(null),
    [name, setName] = useState("");
  const [previews, setPreviews] = useState<Asset[]>([]),
    [round, setRound] = useState<Round | null>(null),
    [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(true),
    [error, setError] = useState(""),
    [paused, setPaused] = useState(false),
    [muted, setMuted] = useState(false),
    [reduced, setReduced] = useState(false);
  const [waitingForSave, setWaitingForSave] = useState(false);
  const demoEvents = useRef<Record<string, Judgment>>({});
  const [hud, setHud] = useState<Hud>(emptyHud),
    [sectionScore, setSectionScore] = useState<{
      section: number;
      points: number;
      total: number;
    } | null>(null);
  const [demoIndex, setDemoIndex] = useState(0),
    [feedback, setFeedback] = useState("");
  const [scoreFeedback, setScoreFeedback] = useState("");
  const scoreTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wavePoints = useRef(new Map<number, number>());
  const [reviewRound, setReviewRound] = useState<Round | null>(null),
    [reviewSection, setReviewSection] = useState(0),
    [choices, setChoices] = useState<Record<string, Label>>({}),
    [savedSections, setSavedSections] = useState<number[]>([]);
  const [dataset, setDataset] = useState<Dataset | null>(null),
    [filter, setFilter] = useState("all");
  const latestHud = useRef(emptyHud),
    ended = useRef(false),
    sectionJobs = useRef(new Set<number>()),
    awarded = useRef(new Set<number>()),
    seen = useRef(new Set<string>()),
    finishing = useRef(false);
  const feedbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reviewIds = useRef<Record<number, string>>({});
  const root = useRef<HTMLElement>(null);
  const playHeading = useRef<HTMLDivElement>(null);
  useEffect(() => {
    (screen === "play" ? playHeading.current : root.current)?.scrollIntoView({
      block: "start",
      behavior: "instant",
    });
  }, [screen]);
  useEffect(() => {
    if (screen !== "play") return;
    const key = (event: KeyboardEvent) => {
      if (event.key !== "Escape" && event.key.toLowerCase() !== "p") return;
      event.preventDefault();
      if (!busy && !error && !ended.current) setPaused((value) => !value);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [screen, busy, error]);
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const info = await api<{ previews: Asset[] }>("");
        if (!live) return;
        setPreviews(info.previews);
        setReduced(
          window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
            localStorage.getItem("fruit-shift-reduced") === "true",
        );
        setMuted(localStorage.getItem("fruit-shift-muted") === "true");
        await flush();
        const stored = localStorage.getItem("fruit-shift-player");
        if (stored) {
          const p = await api<Profile>("/players/" + stored);
          if (live) {
            setProfile(p);
            setName(p.name);
          }
        }
        const interrupted = localStorage.getItem("fruit-shift-active");
        if (interrupted) {
          const r = await api<Result>("/rounds/" + interrupted + "/result");
          if (r.status === "completed" && r.kind === "game") {
            if (live) {
              setResult(r);
              setScreen("results");
            }
          } else await api("/rounds/" + interrupted + "/abandon", {});
          localStorage.removeItem("fruit-shift-active");
        }
      } catch (e) {
        if (live)
          setError(
            e instanceof Error
              ? e.message
              : "Could not connect. Start the backend and retry.",
          );
      } finally {
        if (live) setBusy(false);
      }
    })();
    return () => {
      live = false;
      if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
      if (scoreTimer.current) clearTimeout(scoreTimer.current);
    };
  }, []);
  async function task(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Something could not be saved. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    if (profile) setProfile(await api<Profile>("/players/" + profile.id));
  }
  async function identify() {
    await flush();
    const p = await api<Profile>("/players", { name });
    setProfile(p);
    setResult(null);
    setReviewRound(null);
    setName(p.name);
    localStorage.setItem("fruit-shift-player", p.id);
    if (p.calibration_required) await demonstrations(p.id);
    else await prepare("game", p.id);
  }
  function clockOut() {
    localStorage.removeItem("fruit-shift-player");
    setProfile(null);
    setName("");
    setResult(null);
    setReviewRound(null);
    setScreen("welcome");
  }
  async function prepare(kind: "game" | "calibration", playerId = profile?.id) {
    if (!playerId) return;
    await flush();
    const r = await api<Round>("/rounds", { player_id: playerId, kind });
    localStorage.setItem("fruit-shift-active", r.id);
    setWaitingForSave(false);
    wavePoints.current.clear();
    setScoreFeedback("");
    if (scoreTimer.current) clearTimeout(scoreTimer.current);
    setRound(r);
    setHud(emptyHud);
    latestHud.current = emptyHud;
    setSectionScore(null);
    setFeedback("");
    setPaused(false);
    setError("");
    seen.current.clear();
    sectionJobs.current.clear();
    awarded.current.clear();
    ended.current = false;
    finishing.current = false;
    setScreen("play");
  }
  async function demonstrations(playerId = profile?.id) {
    if (!playerId) return;
    const r = await api<Round>("/rounds", {
      player_id: playerId,
      kind: "demonstration",
    });
    await api("/rounds/" + r.id + "/start", {});
    setRound(r);
    setDemoIndex(0);
    demoEvents.current = {};
    setScreen("demo");
  }
  async function acknowledgeDemo() {
    if (!round) return;
    for (const p of round.presentations) {
      const event = (demoEvents.current[p.id] ??= {
        event_id: crypto.randomUUID(),
        presentation_id: p.id,
        action: "acknowledge",
        client_timestamp: new Date().toISOString(),
        elapsed_ms: 0,
        exposure_ms: 0,
      });
      queue(event.event_id, "/rounds/" + round.id + "/events", event);
    }
    await flush();
    await api("/rounds/" + round.id + "/complete", { elapsed_ms: 0 });
    await prepare(profile?.calibration_required ? "calibration" : "game");
  }

  function saveFailure(e: unknown) {
    setError(
      e instanceof Error ? e.message : "Save failed. Retry to continue.",
    );
    setPaused(true);
  }
  function judgment(event: Judgment) {
    if (!round) return;
    seen.current.add(event.presentation_id);
    try {
      queue(event.event_id, "/rounds/" + round.id + "/events", event);
    } catch (e) {
      saveFailure(e);
      return;
    }
    void flush()
      .then(async () => {
        if (round.kind === "calibration") {
          const f = await api<{ correct: boolean; expected_label: Label }>(
            "/rounds/" + round.id + "/events",
            event,
          );
          setFeedback(
            f.correct
              ? "Good call."
              : `Reference: ${healthy(f.expected_label)}. Look for widespread decay, not natural color variation.`,
          );
          if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
          feedbackTimer.current = setTimeout(() => setFeedback(""), 2000);
        }
      })
      .catch(saveFailure);
  }
  async function award(section: number) {
    if (!round || awarded.current.has(section)) return;
    await flush();
    const score = await api<{ section: number; points: number; total: number }>(
      "/rounds/" + round.id + "/sections/" + section,
      { elapsed_ms: Math.round(latestHud.current.elapsed) },
    );
    awarded.current.add(section);
    wavePoints.current.set(section, score.points);
    // A combo rewards both correct passes and cuts. Never reveal individual controls.
    let combo = 0;
    for (let i = section; i >= 0 && wavePoints.current.get(i) === 440; i--) combo++;
    setScoreFeedback(combo > 1
      ? `Perfect combo ×${combo}! +${score.points}`
      : combo === 1 ? `Perfect wave! +${score.points}` : `+${score.points} points`);
    if (scoreTimer.current) clearTimeout(scoreTimer.current);
    scoreTimer.current = setTimeout(() => setScoreFeedback(""), 2200);
    setSectionScore((previous) =>
      !previous || score.section >= previous.section ? score : previous,
    );
  }
  function tick(next: Hud) {
    latestHud.current = next;
    setHud(next);
    if (round?.kind === "game")
      for (let section = 0; section < 4; section++) {
        const group = round.presentations.filter((p) => p.section === section);
        const end = Math.max(...group.map((p) => p.spawn_ms + p.flight_ms));
        if (
          next.elapsed >= end &&
          group.every((p) => seen.current.has(p.id)) &&
          !sectionJobs.current.has(section)
        ) {
          sectionJobs.current.add(section);
          void award(section).catch((e) => {
            sectionJobs.current.delete(section);
            saveFailure(e);
          });
        }
      }
  }
  async function complete() {
    if (!round || finishing.current) return;
    finishing.current = true;
    setBusy(true);
    try {
      await flush();
      if (round.kind === "game")
        for (let section = 0; section < 4; section++) await award(section);
      const r = await api<Result>("/rounds/" + round.id + "/complete", {
        elapsed_ms: round.duration_ms,
      });
      setWaitingForSave(false);
      setResult(r);
      setScreen("results");
      setPaused(false);
      setError("");
      localStorage.removeItem("fruit-shift-active");
      await refresh();
    } catch (e) {
      saveFailure(e);
    } finally {
      finishing.current = false;
      setBusy(false);
    }
  }
  async function retry() {
    await flush();
    if (ended.current) await complete();
    else {
      if (round?.kind === "game")
        for (let section = 0; section < 4; section++) {
          const group = round.presentations.filter(
            (p) => p.section === section,
          );
          if (
            latestHud.current.elapsed >=
              Math.max(...group.map((p) => p.spawn_ms + p.flight_ms)) &&
            group.every((p) => seen.current.has(p.id))
          )
            await award(section);
        }
      setError("");
      setPaused(false);
    }
  }
  async function review() {
    if (!result) return;
    const r = await api<Round>("/rounds/" + result.id + "/review");
    setReviewRound(r);
    setChoices(
      Object.fromEntries(r.presentations.map((p) => [p.id, p.label!])),
    );
    setSavedSections(r.submitted_sections || []);
    setReviewSection(0);
    reviewIds.current = {};
    setScreen("review");
  }
  async function submitReview() {
    if (!reviewRound) return;
    const section = reviewSection;
    const judgments = Object.fromEntries(
      reviewRound.presentations
        .filter((p) => p.section === section)
        .map((p) => [p.id, choices[p.id]]),
    );
    const submission_id = (reviewIds.current[section] ??= crypto.randomUUID());
    // Persist the exact submission body so retries survive a page reload.
    if (!pending().some((p) => p.id === submission_id))
      queue(submission_id, `/rounds/${reviewRound.id}/review/${section}`, {
        submission_id,
        client_timestamp: new Date().toISOString(),
        judgments,
      });
    await flush();
    setSavedSections([...savedSections, section]);
    const saved = await api<Round>("/rounds/" + reviewRound.id + "/review");
    setChoices(
      Object.fromEntries(saved.presentations.map((p) => [p.id, p.label!])),
    );
    setResult(await api<Result>("/rounds/" + reviewRound.id + "/result"));
    if (section < 3) setReviewSection(section + 1);
    else setScreen("results");
  }
  async function openDataset() {
    setDataset(await api<Dataset>("/dataset"));
    setScreen("dataset");
  }
  const isTraining = round?.kind === "calibration";
  const demo = round?.presentations[demoIndex];
  const reviewGroup =
    reviewRound?.presentations.filter((p) => p.section === reviewSection) || [];
  const sectionSaved = savedSections.includes(reviewSection);
  const resultsCounts = result?.counts;
  return (
    <section
      ref={root}
      className={styles.shift}
      aria-label="Fruit Shift game"
      data-playing={screen === "play"}
    >
      {screen !== "play" && <header className={styles.topbar}>
        <button
          className={styles.wordmark}
          onClick={() => setScreen("welcome")}
          aria-label="Fruit Shift home"
        >
          Fruit Shift<span className={styles.wordmarkSlash}>╱</span>
        </button>
        <div className={styles.nav}>
          {profile && (
            <span className={styles.player}>
              <span className={styles.playerDot} />
              <span title={profile.name}>{profile.name}</span>
            </span>
          )}
        </div>
      </header>}
      {error && screen !== "play" && (
        <div className={styles.error} role="alert">
          {error}{" "}
          <button
            onClick={() =>
              task(async () => {
                await flush();
                await refresh();
              })
            }
          >
            Retry connection
          </button>
        </div>
      )}
      {screen === "welcome" && (
        <>
          <div className={styles.hero}>
            <div className={styles.heroCopy}>
              <h1>Make the cut.</h1>
              <p>One minute. Sharp instincts.<br />Slice the rotten. Let the healthy fly.</p>
              <div className={styles.rules}>
                <span><b>╱</b> Swipe to slice</span>
                <span><svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m4 10 4 4 8-9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg> Leave the good stuff</span>
              </div>
              {!profile ? (
                <form className={styles.nameForm} onSubmit={(e) => {
                  e.preventDefault();
                  void task(identify);
                }}>
                  <label htmlFor="player-name">Pick a player name</label>
                  <div>
                    <input id="player-name" autoComplete="nickname" maxLength={40}
                      value={name} onChange={(e) => setName(e.target.value)}
                      placeholder="Your name" required />
                    <button disabled={busy || !name.trim()} className={styles.primary}>
                      {busy ? "Loading…" : "Let’s play"}
                    </button>
                  </div>
                </form>
              ) : (
                <div className={styles.startPanel}>
                  <button className={styles.primary} disabled={busy}
                    onClick={() => task(() => profile.calibration_required ? demonstrations() : prepare("game"))}>
                    {busy ? "Loading…" : profile.calibration_required ? "How to play" : "Play · 60 seconds"}
                  </button>
                  {!profile.calibration_required && <button className={styles.linkButton}
                    disabled={busy} onClick={() => task(demonstrations)}>Fruit guide</button>}
                  <button className={styles.linkButton} onClick={clockOut}>Change player</button>
                  {profile.calibration_required && <p>A quick fruit guide, then a practice round.</p>}
                </div>
              )}
            </div>
            <div className={styles.heroArt} aria-hidden="true">
              {previews.slice(0, 3).map((a, i) => (
                <img key={a.asset_id} src={a.url} alt="" className={styles["heroFruit" + i]} />
              ))}
              <svg className={styles.heroBlade} viewBox="0 0 400 300" fill="none">
                <path d="M35 255 Q130 220 200 150 T370 45" stroke="#fff" strokeWidth="8" strokeLinecap="round" />
                <path d="M35 255 Q130 220 200 150 T370 45" stroke="#337e81" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </div>
          </div>
          {profile && profile.history.some((r) => r.kind === "game") && (
            <details className={styles.history}>
              <summary>Previous games</summary>
              {profile.history.filter((r) => r.kind === "game").map((r) => (
                <button key={r.id} onClick={() => task(async () => {
                  setResult(await api<Result>("/rounds/" + r.id + "/result"));
                  setScreen("results");
                })}>
                  <strong>{r.score.toLocaleString()} points</strong>
                  <span>{r.first_pass_correct}/{r.first_pass_total} correct</span>
                </button>
              ))}
            </details>
          )}
        </>
      )}
      {screen === "demo" && demo && round && (
        <div className={styles.guide}>
          <div className={styles.guideHeading}>
            <div><h1>Know your berries.</h1>
              <p>Five keepers. Five to slice. Some are trickier than they look.</p></div>
            <button className={styles.linkButton} onClick={() => setScreen("welcome")}>Back</button>
          </div>
          <div className={styles.guideScene}>
            {(["fresh", "rotten"] as Label[]).map((label) => (
              <div key={label} className={styles.guideRow}>
                <div className={styles.guideLabel}>
                  <h2>{healthy(label)}</h2>
                  <span>{label === "fresh" ? "Let them fly" : "Slice these"}</span>
                </div>
                <div className={styles.berryLine}>
                  {round.presentations.filter((p) => p.label === label).map((p) => (
                    <button key={p.id} className={styles.guideBerry}
                      aria-label={`${healthy(label)} example ${p.ordinal % 5 + 1}`}
                      aria-pressed={demo.id === p.id}
                      onClick={() => setDemoIndex(round.presentations.indexOf(p))}>
                      <img src={p.url} alt={`${healthy(label)} strawberry`} />
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className={styles.guideDetail} aria-live="polite">
            <img src={demo.url} alt={`Selected ${healthy(demo.label!).toLowerCase()} strawberry`} />
            <p><b>{healthy(demo.label!)}:</b> {demo.explanation}</p>
          </div>
          <div className={styles.guideBottom}>
            <p>Look for mold, sunken patches, and collapsed flesh.<br />Dark red or pale skin alone can be healthy. Tap a berry for a closer clue.</p>
            <button className={styles.primary} disabled={busy} onClick={() => task(acknowledgeDemo)}>
              {busy ? "Getting ready…" : profile?.calibration_required ? "Try a practice round" : "Play · 60 seconds"}
            </button>
          </div>
        </div>
      )}
      {screen === "play" && round && (
        <>
          <div ref={playHeading} className={styles.arenaWrap}>
            <div className={styles.hud}>
              <div className={styles.scoreBox}>
                <span>{isTraining ? "Practice" : "Score"}</span>
                <strong>{isTraining ? `${hud.resolved} / 10` : (sectionScore?.total || 0).toLocaleString()}</strong>
              </div>
              <span className={styles.playRule}>Slice rotten · Let healthy fly</span>
              <div className={styles.timer} data-urgent={round.duration_ms - hud.elapsed <= 10000}>
                <strong>{Math.ceil((round.duration_ms - hud.elapsed) / 1000)}</strong><span>sec</span>
              </div>
              <button className={styles.pauseButton} onClick={() => setPaused(true)} aria-label="Pause game">Ⅱ</button>
            </div>
            <Arena
              round={round}
              paused={paused}
              muted={muted}
              reduced={reduced}
              onReady={() => api<void>("/rounds/" + round.id + "/start", {})}
              onJudgment={judgment}
              onTick={tick}
              onEnd={() => {
                ended.current = true;
                setWaitingForSave(true);
                void complete();
              }}
              onPause={() => setPaused(true)}
            />
            {paused && (
              <div className={styles.pauseOverlay}>
                <span className={styles.pauseGlyph}>Ⅱ</span>
                <h2>{error ? "Save interrupted" : "Take a breather."}</h2>
                <p>
                  {error
                    ? `${error} Your pending calls are saved on this browser. Retry before continuing.`
                    : "Ready when you are. Your fruit and timer are paused."}
                </p>
                <button
                  className={styles.primary}
                  disabled={busy}
                  onClick={() => task(retry)}
                >
                  {busy
                    ? "Saving…"
                    : error
                      ? "Retry save & continue"
                      : "Keep playing"}
                </button>
                <div className={styles.controls}>
                  <button onClick={() => {
                    setMuted(!muted);
                    localStorage.setItem("fruit-shift-muted", String(!muted));
                  }} aria-pressed={muted}>{muted ? "Sound off" : "Sound on"}</button>
                  <button onClick={() => {
                    setReduced(!reduced);
                    localStorage.setItem("fruit-shift-reduced", String(!reduced));
                  }} aria-pressed={reduced}>{reduced ? "Effects low" : "Effects full"}</button>
                </div>
                <button
                  className={styles.lightButton}
                  disabled={busy}
                  onClick={() =>
                    task(async () => {
                      await flush();
                      await api("/rounds/" + round.id + "/abandon", {});
                      localStorage.removeItem("fruit-shift-active");
                      setPaused(false);
                      setScreen("welcome");
                    })
                  }
                >
                  Leave game
                </button>
              </div>
            )}
            {waitingForSave && !paused && (
              <div className={styles.arenaMessage}>
                <span className={styles.loader} />
                <p>Saving your shift…</p>
              </div>
            )}
            {scoreFeedback && !paused && !waitingForSave && (
              <div key={scoreFeedback} className={styles.scoreFeedback} role="status">{scoreFeedback}</div>
            )}
            {isTraining && feedback && !paused && (
              <div className={styles.feedback} role="status">
                {feedback}
              </div>
            )}
          </div>
          <div className={styles.arenaFooter}>
            <span>{isTraining ? "Get 8 of 10 right to unlock the game." : "Accurate cuts + healthy passes build perfect combos."}</span>
          </div>
        </>
      )}
      {screen === "results" && result && (
        <div className={styles.results}>
          <div className={styles.resultIntro}>
            <span className={styles.stationTag}>
              {result.kind === "calibration"
                ? "Practice complete"
                : "Time’s up!"}
            </span>
            <h1>
              {result.passed
                ? result.kind === "calibration"
                  ? "You’ve got the eye."
                  : "That’s a wrap!"
                : result.kind === "calibration"
                  ? "Let’s sharpen your eye."
                  : "Another round?"}
            </h1>
            <p>
              {result.exclusion_reason === "reference_version_changed"
                ? "The reference standard changed during this shift. Complete training with the updated examples."
                : result.kind === "calibration"
                ? result.passed
                  ? "Ready for the real thing? You’ve unlocked the one-minute game."
                  : "Get 8 of 10 reference fruit right. Review the examples and try again."
                : result.eligible
                  ? "Good eye. Your calls are saved. Jump back in or take a look at your fruit."
                  : "A few tricky ones got through. Try the fruit guide to sharpen your instincts."}
            </p>
          </div>
          <div className={styles.resultBoard} data-practice={result.kind === "calibration"}>
            <div className={styles.accuracy}>
              <span>Accuracy</span>
              <strong>
                {Math.round((result.correct / result.total) * 100)}
                <small>%</small>
              </strong>
              <p>
                {result.correct} / {result.total} correct{" "}
                <span
                  className={result.passed ? styles.passTag : styles.failTag}
                >
                  {result.passed ? (result.kind === "calibration" ? "Passed" : "Nice!") : "Try again"}
                </span>
              </p>
              <small>Scored on your first calls.</small>
            </div>
            {result.kind === "game" && <div className={styles.resultNumbers}>
              <div>
                <strong>{result.score.toLocaleString()}</strong>
                <span>
                  Points{" "}
                  {result.review_bonus > 0 &&
                    `/ ${result.review_bonus} review bonus`}
                </span>
              </div>
              <div className={styles.resultCalls}>
                <span>
                  <b>{resultsCounts?.fresh || 0}</b> Healthy calls
                </span>
                <span>
                  <b>{resultsCounts?.rotten || 0}</b> Rotten calls
                </span>
              </div>
            </div>}
          </div>
          <div className={styles.resultActions}>
            {result.kind === "game" && (
              <button
                className={styles.secondary}
                disabled={busy}
                onClick={() => task(review)}
              >
                {result.review_bonus === 40
                  ? "View your sorting"
                  : "Review your fruit"}{" "}
                <span>
                  {result.review_bonus === 40
                    ? "Confirmed"
                    : `Up to +${40 - result.review_bonus}`}
                </span>
              </button>
            )}
            <button
              className={styles.primary}
              disabled={busy}
              onClick={() =>
                task(async () => {
                  if (profile?.calibration_required) await demonstrations();
                  else await prepare("game");
                })
              }
            >
              {profile?.calibration_required
                ? "Back to training"
                : result.kind === "calibration"
                  ? "Play · 60 seconds"
                  : "Play again"}
            </button>
            <button
              className={styles.linkButton}
              onClick={clockOut}
            >
              Change player
            </button>
          </div>
        </div>
      )}
      {screen === "review" && reviewRound && (
        <div className={styles.review}>
          <div className={styles.reviewHeading}>
            <div>
              <span className={styles.stationTag}>
                Final sorting / optional
              </span>
              <h1>A second look.</h1>
              <p>
                Move fruit between your groups. Confirm each section for +10
                points, even if nothing changes.
              </p>
            </div>
            <button
              className={styles.secondary}
              onClick={() =>
                task(async () => {
                  setResult(
                    await api<Result>("/rounds/" + reviewRound.id + "/result"),
                  );
                  setScreen("results");
                })
              }
            >
              Finish sorting
            </button>
          </div>
          <div className={styles.sectionTabs} aria-label="Review sections">
            {[0, 1, 2, 3].map((i) => (
              <button
                key={i}
                aria-pressed={reviewSection === i}
                onClick={() => setReviewSection(i)}
              >
                Section {i + 1} {savedSections.includes(i) && "Saved"}
              </button>
            ))}
          </div>
          <div className={styles.sortBins}>
            {(["fresh", "rotten"] as Label[]).map((label) => (
              <div
                key={label}
                className={
                  label === "fresh" ? styles.healthyBin : styles.rottenBin
                }
                onDragOver={(e) => {
                  if (!sectionSaved && !busy) e.preventDefault();
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const id = e.dataTransfer.getData("text/plain");
                  if (
                    !sectionSaved &&
                    !busy &&
                    reviewGroup.some((p) => p.id === id)
                  )
                    setChoices({ ...choices, [id]: label });
                }}
              >
                <h2>
                  {healthy(label)}
                  <span>
                    {reviewGroup.filter((p) => choices[p.id] === label).length}
                  </span>
                </h2>
                <p>
                  {label === "fresh"
                    ? "Keep in the crate"
                    : "Remove from the line"}
                </p>
                <div className={styles.sortGrid}>
                  {reviewGroup
                    .filter((p) => choices[p.id] === label)
                    .map((p) => (
                      <div
                        className={styles.sortFruit}
                        key={p.id}
                        draggable={!sectionSaved && !busy}
                        onDragStart={(e) =>
                          e.dataTransfer.setData("text/plain", p.id)
                        }
                      >
                        <img
                          src={p.url}
                          alt={`Your ${healthy(label).toLowerCase()} call ${p.ordinal + 1}`}
                          draggable={false}
                        />
                        <button
                          disabled={sectionSaved || busy}
                          aria-label={`Mark fruit ${p.ordinal + 1} as ${label === "fresh" ? "rotten" : "healthy"}`}
                          onClick={() =>
                            setChoices({
                              ...choices,
                              [p.id]: label === "fresh" ? "rotten" : "fresh",
                            })
                          }
                        >
                          Move to {label === "fresh" ? "rotten" : "healthy"}{" "}
                          <span>↔</span>
                        </button>
                      </div>
                    ))}
                </div>
              </div>
            ))}
          </div>
          <div className={styles.reviewBottom}>
            <p>
              Each appearance still counts as one vote. First-pass accuracy
              stays fixed.
            </p>
            <button
              className={styles.primary}
              disabled={busy || sectionSaved}
              onClick={() => task(submitReview)}
            >
              {sectionSaved
                ? "Section confirmed"
                : busy
                  ? "Saving…"
                  : "Confirm section · +10 points"}
            </button>
          </div>
        </div>
      )}
      {screen === "dataset" && dataset && (
        <div className={styles.dataset}>
          <div className={styles.datasetHeading}>
            <div>
              <span className={styles.stationTag}>
                The work behind the play
              </span>
              <h1>A growing fruit dataset.</h1>
              <p>
                {dataset.total_votes} eligible votes across 92 target cutouts.
                Every qualifying appearance contributes one vote.
              </p>
            </div>
            <button
              className={styles.secondary}
              onClick={() => setScreen(result ? "results" : "welcome")}
            >
              Back to {result ? "results" : "game"}
            </button>
          </div>
          <div className={styles.datasetTools}>
            <div className={styles.sectionTabs}>
              {[
                ["all", "All 92"],
                ["labeled", "With votes"],
                ["unlabeled", "Awaiting votes"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className={styles.exports}>
              <a href={base + "/exports/json"} download>
                JSON ↧
              </a>
              <a href={base + "/exports/csv"} download>
                CSV ↧
              </a>
              <a href={base + "/exports/json?audit=true"} download>
                Audit JSON ↧
              </a>
              <a href={base + "/exports/csv?audit=true"} download>
                Audit CSV ↧
              </a>
            </div>
          </div>
          <div className={styles.datasetGrid}>
            {dataset.assets
              .filter(
                (a) =>
                  filter === "all" ||
                  (filter === "labeled"
                    ? a.contributions > 0
                    : a.contributions === 0),
              )
              .map((a, i) => (
                <article key={a.asset_id}>
                  <div>
                    <img src={a.url} alt={`Target fruit ${i + 1}`} />
                  </div>
                  <p>
                    <span className={styles.mintDark}>{a.fresh} Healthy</span>
                    <span className={styles.peachDark}>{a.rotten} Rotten</span>
                  </p>
                  <small>
                    {a.contributions} contribution
                    {a.contributions === 1 ? "" : "s"}
                  </small>
                </article>
              ))}
          </div>
          <p className={styles.attribution}>
            {dataset.attribution}{" "}
            <a
              href="https://doi.org/10.17632/bdd69gyhv8.1"
              target="_blank"
              rel="noreferrer"
            >
              Source dataset
            </a>
            . Target source labels are provenance, not player votes. Licensed
            under{" "}
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noreferrer"
            >
              CC BY 4.0
            </a>
            .
          </p>
        </div>
      )}
      {screen !== "play" && screen !== "demo" && <div className={styles.bottomBar}>
        <span>Real fruit. Sharp instincts.</span>
        <button className={styles.linkButton} disabled={busy} onClick={() => task(openDataset)}>View dataset</button>
      </div>}
    </section>
  );
}
