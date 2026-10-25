"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Dial from "./dial";
import { getAxis, randomAxis } from "./axes";
import { EmotionPair, WheelReveal } from "./emotion-wheel";
import RoundSetup from "./round-setup";
import ScenarioPrompt from "./scenario-prompt";
import { getScenario, randomScenario } from "./scenarios";
import { api, download } from "./api";
import type { Dataset, PairResult, PairState, Review, SoloResult, SoloState } from "./types";
import styles from "./game.module.css";

type Mode = "solo" | "pair" | "data";
const storageKey = "common-ground-v1";
const newSolo = (deck: string[] = []): SoloState => ({ axisId: randomAxis(), setup: true, deck, index: 0, guess: 50, touched: false, confidence: "sure", results: [], started: Date.now(), pending: null });
const newPair = (): PairState => ({ axisId: "satisfaction", phase: "intro", target: 50, text: "", guess: 50, touched: false, round: 1, results: [], started: Date.now(), pending: null });
const shuffled = <T,>(items: T[]) => {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
};
const elapsed = (started: number) => Math.min(3600000, Math.max(0, Date.now() - started));
const outcome = (distance: number) => distance <= 3 ? "On the same wavelength!" : distance <= 10 ? "That’s pretty close." : distance <= 20 ? "A little room for interpretation." : "A different read. That’s useful, too.";

function Icon({ name, size = 20 }: { name: "wave" | "solo" | "pair" | "arrow" | "check" | "spark" | "data" | "eye" | "help" | "download"; size?: number }) {
  const paths: Record<typeof name, ReactNode> = {
    wave: <><path d="M2 12c3-12 5 12 8 0S15 0 18 12s3 0 4 0" /></>,
    solo: <><circle cx="12" cy="7" r="3.5" /><path d="M5 21v-3a7 7 0 0 1 14 0v3" /></>,
    pair: <><circle cx="9" cy="7" r="3" /><path d="M3 20v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 5v1" /></>,
    arrow: <><path d="M4 12h15m-6-6 6 6-6 6" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    spark: <><path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5Z" /></>,
    data: <><path d="M5 21V11m7 10V3m7 18V7" /></>,
    eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4m0 3h.01" /></>,
    download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

export default function CommonGround() {
  const [mode, setMode] = useState<Mode>("solo");
  const [reviews, setReviews] = useState<Review[]>([]);
  const [solo, setSolo] = useState<SoloState | null>(null);
  const [pair, setPair] = useState<PairState | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [seen, setSeen] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState("");
  const [help, setHelp] = useState(false);
  const [storageWarning, setStorageWarning] = useState(false);
  const submitting = useRef(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoadError("");
      try {
        const data = await api<{ reviews: Review[] }>("/reviews");
        if (!active) return;
        if (!data.reviews.length) throw new Error("No reviews are available yet. Add reviews to the server, then try again.");
        setReviews(data.reviews);
        let stored: { sessionId?: string; solo?: SoloState; pair?: PairState; seen?: string[] } = {};
        try {
          const parsed = JSON.parse(localStorage.getItem(storageKey) ?? "{}");
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) stored = parsed;
        } catch { setStorageWarning(true); }
        const validIds = new Set(data.reviews.map(r => r.id));
        const known = Array.isArray(stored.seen) ? stored.seen.filter(id => validIds.has(id)) : [];
        setSeen(known);
        setSessionId(typeof stored.sessionId === "string" && /^[0-9a-f-]{36}$/i.test(stored.sessionId) ? stored.sessionId : crypto.randomUUID());
        const saved = stored.solo;
        const validSolo = saved && Array.isArray(saved.deck) && saved.deck.every(id => validIds.has(id)) && Number.isInteger(saved.index) && saved.index >= 0 && saved.index <= saved.deck.length && Array.isArray(saved.results) && saved.results.length >= saved.index;
        const freshEmotionRound = validSolo && !saved.axisId && !saved.pending && !saved.results[saved.index];
        setSolo(validSolo ? {
          ...saved,
          axisId: freshEmotionRound ? randomAxis() : getAxis(saved.axisId).id,
          setup: saved.setup ?? freshEmotionRound,
          ...(freshEmotionRound ? { guess: 50, touched: false } : {}),
        } : newSolo(shuffled(data.reviews.filter(r => !known.includes(r.id))).slice(0, 5).map(r => r.id)));
        const savedPair = stored.pair;
        // Give an empty legacy round a scene, but don't assign a new context
        // to a review that was already written or is waiting to be saved.
        const restoredScenario = getScenario(savedPair?.scenarioId)
          ?? (savedPair && !savedPair.text && !savedPair.pending ? randomScenario() : undefined);
        // A refreshed handoff always returns to the privacy screen.
        setPair(savedPair && ["intro", "setup", "write", "handoff", "guess", "reveal"].includes(savedPair.phase) && Array.isArray(savedPair.results) ? { ...savedPair, scenarioId: restoredScenario?.id, axisId: getAxis(savedPair.axisId).id, phase: savedPair.phase === "guess" ? "handoff" : savedPair.phase } : newPair());
      } catch (e) { if (active) setLoadError(e instanceof Error ? e.message : "The game couldn’t load. Try again."); }
    }
    void load();
    return () => { active = false; };
  }, [reload]);

  useEffect(() => {
    if (!solo || !pair || !sessionId) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify({ sessionId, solo, pair, seen }));
    } catch {
      // Report a failure of the external storage write once, rather than
      // deriving another game state from render state.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStorageWarning(true);
    }
  }, [solo, pair, sessionId, seen]);

  useEffect(() => {
    if (help) dialog.current?.showModal();
    else dialog.current?.close();
  }, [help]);

  async function loadDataset() {
    setDataLoading(true); setDataError("");
    try { setDataset(await api<Dataset>("/dataset")); }
    catch (e) { setDataError(e instanceof Error ? e.message : "Couldn’t load the dataset."); }
    finally { setDataLoading(false); }
  }

  function selectMode(next: Mode) {
    if (submitting.current) return;
    setError(""); setMode(next);
    if (next === "data") void loadDataset();
  }

  async function submitSolo() {
    if (!solo || submitting.current || solo.results[solo.index]) return;
    const review = reviews.find(r => r.id === solo.deck[solo.index]);
    if (!review) return;
    submitting.current = true; setBusy(true); setError("");
    const pending = solo.pending ?? { submission_id: crypto.randomUUID(), session_id: sessionId, review_id: review.id, axis_id: solo.axisId, score: solo.guess, confidence: solo.confidence, elapsed_ms: elapsed(solo.started) };
    setSolo(s => s && { ...s, pending });
    try {
      const result = await api<SoloResult>("/annotations", pending);
      setSolo(s => s && { ...s, pending: null, results: [...s.results, result] });
      setSeen(s => [...new Set([...s, review.id])]);
      heading.current?.focus();
    } catch (e) { setError(e instanceof Error ? e.message : "Your guess couldn’t be saved. Try again."); }
    finally { submitting.current = false; setBusy(false); }
  }

  async function submitPair() {
    if (!pair || submitting.current || pair.phase !== "guess") return;
    submitting.current = true; setBusy(true); setError("");
    const pending = pair.pending ?? { submission_id: crypto.randomUUID(), session_id: sessionId, text: pair.text.trim(), category: getScenario(pair.scenarioId)?.title ?? "Player-written", axis_id: pair.axisId, target: pair.target, guess: pair.guess, elapsed_ms: elapsed(pair.started) };
    setPair(s => s && { ...s, pending });
    try {
      const result = await api<PairResult>("/clues", pending);
      setPair(s => s && { ...s, phase: "reveal", pending: null, results: [...s.results, result] });
      heading.current?.focus();
    } catch (e) { setError(e instanceof Error ? e.message : "Your round couldn’t be saved. Try again."); }
    finally { submitting.current = false; setBusy(false); }
  }

  function startPair() {
    setError("");
    setPair(s => s && { ...s, scenarioId: randomScenario(s.scenarioId).id, axisId: randomAxis(), phase: "setup", target: 10 + Math.floor(Math.random() * 81), text: "", guess: 50, touched: false, started: Date.now(), pending: null });
  }
  function nextSolo() {
    setError("");
    setSolo(s => s && { ...s, axisId: randomAxis(), setup: true, index: s.index + 1, guess: 50, touched: false, confidence: "sure", started: Date.now(), pending: null });
    heading.current?.focus();
  }
  function nextSet() {
    setSolo(newSolo(shuffled(reviews.filter(r => !seen.includes(r.id))).slice(0, 5).map(r => r.id)));
    heading.current?.focus();
  }

  const soloAxis = getAxis(solo?.axisId);
  const pairAxis = getAxis(pair?.axisId);
  const pairScenario = getScenario(pair?.scenarioId);
  const activeAxis = mode === "pair" ? pairAxis : soloAxis;
  const choosingFeeling = mode === "pair" ? pair?.phase === "setup" || pair?.phase === "intro" : solo?.setup;
  const review = reviews.find(r => r.id === solo?.deck[solo.index]);
  const soloResult = solo?.results[solo.index];
  const soloDone = !!solo && solo.index >= solo.deck.length;
  const pairResult = pair?.results.at(-1);
  const total = mode === "pair" ? pair?.results.reduce((sum, r) => sum + r.points, 0) ?? 0 : solo?.results.reduce((sum, r) => sum + r.points, 0) ?? 0;
  const ready = !!solo && !!pair;
  const round = mode === "pair" ? pair?.round ?? 1 : Math.min((solo?.index ?? 0) + 1, solo?.deck.length ?? 5);
  const rounds = mode === "pair" ? 5 : solo?.deck.length ?? 5;
  const remaining = reviews.filter(r => !seen.includes(r.id)).length;
  const pairDone = pair?.phase === "reveal" && pair.round === 5;
  const confidenceLocked = busy || !!solo?.pending || !!soloResult;

  return (
    <section className={styles.root} aria-label="Common Ground sentiment game">
      <div className={styles.gameHeader}>
        <div className={styles.gameIdentity}><span className={styles.gameMark}><Icon name="wave" size={28} /></span><div><span className={styles.gameName}>Common Ground</span><span className={styles.gameDescriptor}>A game of reading the room</span></div></div>
        <button className={styles.textButton} onClick={() => setHelp(true)}><Icon name="help" size={18} /> How to play</button>
      </div>

      <div className={styles.titleRow}><div><h1>Read between the lines.</h1><p>Spin a feeling. Read the room. Find your common ground.</p></div><span className={styles.pocBadge}><span /> Playable experiment</span></div>

      <div className={styles.toolbar}>
        <nav className={styles.modeSwitch} aria-label="Game mode">
          <button aria-pressed={mode === "solo"} disabled={busy} onClick={() => selectMode("solo")}><Icon name="solo" size={17} /> Solo</button>
          <button aria-pressed={mode === "pair"} disabled={busy} onClick={() => selectMode("pair")}><Icon name="pair" size={19} /> Pass & play<span className={styles.twoPlayers}>2 players</span></button>
        </nav>
        <button className={`${styles.textButton} ${mode === "data" ? styles.activeData : ""}`} aria-pressed={mode === "data"} disabled={busy} onClick={() => selectMode(mode === "data" ? "solo" : "data")}><Icon name="data" size={17} /> The data you make</button>
      </div>

      {loadError ? <div className={styles.loadState} role="alert"><Icon name="wave" size={40} /><h2>Let’s get the game connected.</h2><p>{loadError}</p><button className={styles.primary} onClick={() => setReload(r => r + 1)}>Try again</button></div> : !ready ? <div className={styles.loadState} role="status"><Icon name="wave" size={40} /><p>Finding our wavelength…</p></div> : mode === "data" ? <DataView dataset={dataset} reviews={reviews} loading={dataLoading} error={dataError} refresh={loadDataset} /> : <div className={styles.playLayout}>
        <div className={styles.board}>
          <div className={styles.roundBar}><span>{mode === "pair" ? "Shared wavelength" : "A fresh perspective"}</span><div className={styles.roundProgress} aria-label={rounds ? `Round ${round} of ${rounds}` : "Catalog complete"}>
            {Array.from({ length: rounds }, (_, i) => <i key={i} className={mode === "solo" && soloDone || i < round - 1 || (mode === "solo" ? soloResult : pair?.phase === "reveal") && i === round - 1 ? styles.completedDot : i === round - 1 ? styles.currentDot : ""} />)}<span>{rounds ? `${round} / ${rounds}` : "All read"}</span>
          </div></div>

          {mode === "solo" && solo && (soloDone ? <div className={styles.finish}>
            <span className={styles.finishIcon}><Icon name="spark" size={42} /></span><h2 ref={heading} tabIndex={-1}>{solo.results.length ? "A little more in tune." : "You’ve read the whole room."}</h2>
            <p>{solo.results.length ? `${solo.results.length} reviews, ${solo.results.length} perspectives added. Nice reading.` : "Every demo review has your take. Try writing a few with a friend."}</p>
            {solo.results.length > 0 && <><strong className={styles.finishScore}>{total}<small> / {solo.results.length * 100} points</small></strong><div className={styles.roundScores}>{solo.results.map((r, i) => <div key={r.annotation_id}><span>Round {i + 1}</span><strong>{r.points}</strong><small>{r.distance} apart</small></div>)}</div></>}
            <p className={styles.smallNote}>Points measure closeness to an authored reference. Every honest interpretation still belongs in the dataset.</p>
            {remaining > 0 ? <button className={styles.primary} onClick={nextSet}>Play another set <Icon name="arrow" size={18} /></button> : <button className={styles.primary} onClick={() => selectMode("pair")}>Try pass & play <Icon name="pair" size={18} /></button>}
            <button className={styles.textButton} onClick={() => selectMode("data")}>See the labels you’re helping create</button>
          </div> : review && <>{solo.setup ? <RoundSetup key={`solo-${solo.index}`} axis={soloAxis} onReady={() => setSolo(s => s && { ...s, setup: false, started: Date.now() })} /> : <>
            <div className={styles.promptHeading}><h2 ref={heading} tabIndex={-1}>{soloResult ? "Let’s see how you read the feeling." : soloAxis.prompt}</h2><p>{soloResult ? "Your take is saved. Here’s how the demo author read it." : "Just this feeling. How much of it do you hear?"}</p></div>
            <ReviewCard review={review} />
            {!soloResult && <Dial value={solo.guess} axis={soloAxis} disabled={confidenceLocked} onChange={value => setSolo(s => s && { ...s, guess: value, touched: true })} />}
            {soloResult ? <WheelReveal key={soloResult.annotation_id} value={soloResult.reference_score} axis={soloAxis}><div className={styles.reveal} aria-live="polite"><div className={styles.revealNumbers}><span>Your read <strong>{solo.guess}%</strong></span><span><i />Demo reference <strong>{soloResult.reference_score}%</strong></span><b>+{soloResult.points} pts</b></div><h3>{outcome(soloResult.distance)}</h3><p>{soloResult.reference_note}</p><span className={styles.saved}><Icon name="check" size={14} /> Your independent rating was saved before the reveal.</span><button className={styles.primary} onClick={nextSolo}>{solo.index === solo.deck.length - 1 ? "See your results" : "Next review"}<Icon name="arrow" size={18} /></button></div></WheelReveal> : <div className={styles.lockArea}>
              <fieldset className={styles.confidence} disabled={confidenceLocked}><legend>How clear is the sentiment?</legend><label><input type="radio" name="confidence" value="sure" checked={solo.confidence === "sure"} onChange={() => setSolo(s => s && { ...s, confidence: "sure" })} /> Pretty clear</label><label><input type="radio" name="confidence" value="unsure" checked={solo.confidence === "unsure"} onChange={() => setSolo(s => s && { ...s, confidence: "unsure" })} /> Open to interpretation</label></fieldset>
              <ErrorMessage error={error} />
              <button className={styles.primary} disabled={busy || !solo.touched} onClick={submitSolo}>{busy ? "Saving your read…" : solo.pending ? "Retry save" : "Lock in my guess"}{!busy && <Icon name={solo.pending ? "check" : "arrow"} size={18} />}</button>
              {!solo.touched && <button className={styles.neutralChoice} onClick={() => setSolo(s => s && { ...s, touched: true })}>Right in the middle? Keep 50.</button>}
            </div>}
          </>}</>)}

          {mode === "pair" && pair && (pair.phase === "intro" ? <div className={styles.pairIntro}><div className={styles.peopleArt}><span><Icon name="solo" size={48} /></span><Icon name="wave" size={42} /><span><Icon name="solo" size={48} /></span></div><h2 ref={heading} tabIndex={-1}>Can you read each other?</h2><p>An everyday scene. A secret feeling.<br />See how close a friend can get to your way of thinking.</p><ol className={styles.pairSteps}><li><strong>Spin a feeling.</strong><span>Get a scene, shuffle the emotions, and spin a secret percentage. Write a review to match.</span></li><li><strong>Pass the screen.</strong><span>The target disappears. Player 2 reads the review and guesses.</span></li><li><strong>Find common ground.</strong><span>Reveal the gap, collect points, then swap roles.</span></li></ol><button className={styles.primary} onClick={startPair}>Spin a feeling <Icon name="eye" size={19} /></button><p className={styles.smallNote}>2 people, 1 device. Five rounds together.</p></div> : pair.phase === "setup" ? <RoundSetup key={`pair-${pair.round}`} axis={pairAxis} target={pair.target} scenario={pairScenario} onReady={() => setPair(s => s && { ...s, phase: "write", started: Date.now() })} /> : pair.phase === "write" ? <>
            <div className={styles.promptHeading}><span className={styles.playerPill}>For Player 1’s eyes only</span><h2 ref={heading} tabIndex={-1}>Put this feeling into words.</h2><p>Use the scene below and write a review that matches your secret feeling.</p></div>
            <ScenarioPrompt scenario={pairScenario} />
            <Dial value={pair.target} axis={pairAxis} />
            <div className={styles.writeArea}><label htmlFor="review-clue">Your made-up review</label><textarea id="review-clue" value={pair.text} minLength={10} maxLength={500} onChange={e => setPair(s => s && { ...s, text: e.target.value })} placeholder={pairScenario ? `What would you say about ${pairScenario.title.toLowerCase()}?` : "Describe what happened and how the experience felt…"} rows={4} /><div className={styles.writeHint}><span>Describe the experience. Keep the number a secret.</span><span>{pair.text.length}/500</span></div><p className={styles.smallNote}>Use an invented experience without personal details.</p><button className={styles.primary} disabled={pair.text.trim().length < 10} onClick={() => setPair(s => s && { ...s, text: s.text.trim(), phase: "handoff" })}>Hide target & pass the screen <Icon name="pair" size={18} /></button></div>
          </> : pair.phase === "handoff" ? <div className={styles.handoff}><span className={styles.handoffIcon}><Icon name="pair" size={60} /></span><span className={styles.playerPill}>Target safely hidden</span><EmotionPair axis={pairAxis} /><h2 ref={heading} tabIndex={-1}>Over to you, Player 2.</h2><p>Take the screen. Read the review.<br />Guess how much of this feeling your friend meant.</p><button className={styles.primary} onClick={() => setPair(s => s && { ...s, phase: "guess" })}>I’m Player 2. Let me guess. <Icon name="arrow" size={18} /></button><span className={styles.smallNote}>Player 1: no hints, no peeking reactions.</span></div> : <>
            <div className={styles.promptHeading}><h2 ref={heading} tabIndex={-1}>{pair.phase === "reveal" && pairResult ? "Time for the big reveal." : "How much of this feeling did they mean?"}</h2><p>{pair.phase === "reveal" ? "The target is your friend’s intent. Your guess is your interpretation." : "Player 2, read the review and place your guess."}</p></div>
            <ScenarioPrompt scenario={pairScenario} />
            <ReviewCard review={{ id: "clue", text: pair.text, category: "Your friend’s review", source: "authored_demo" }} playerWritten />
            {pair.phase !== "reveal" && <Dial value={pair.guess} axis={pairAxis} disabled={busy || !!pair.pending} onChange={value => setPair(s => s && { ...s, guess: value, touched: true })} />}
            {pair.phase === "reveal" && pairResult ? <WheelReveal key={pairResult.pair_id} value={pair.target} axis={pairAxis}><div className={styles.reveal} aria-live="polite"><div className={styles.revealNumbers}><span>Your guess <strong>{pair.guess}%</strong></span><span><i />Secret target <strong>{pair.target}%</strong></span><b>+{pairResult.points} pts</b></div><h3>{outcome(pairResult.distance)}</h3><p>{pairResult.distance <= 10 ? "You speak the same sentiment. How did you pick up on it?" : "Which words pulled you in a different direction? That gap is part of the story."}</p><span className={styles.saved}><Icon name="check" size={14} /> Saved as a synthetic review with two separate signals.</span>{pairDone ? <div className={styles.pairFinish}><strong>{total} / 500 points together</strong><p>Five reviews created. Five interpretations captured.</p><button className={styles.primary} onClick={() => { setPair(newPair()); }}>Play another set <Icon name="pair" size={18} /></button></div> : <button className={styles.primary} onClick={() => { setPair(s => s && { ...s, round: s.round + 1, phase: "intro" }); }}>Swap roles & continue <Icon name="pair" size={18} /></button>}</div></WheelReveal> : <div className={styles.lockArea}><ErrorMessage error={error} /><button className={styles.primary} disabled={busy || !pair.touched} onClick={submitPair}>{busy ? "Saving your round…" : pair.pending ? "Retry save" : "Reveal the target"}<Icon name="eye" size={18} /></button>{!pair.touched && <button className={styles.neutralChoice} onClick={() => setPair(s => s && { ...s, touched: true })}>Right in the middle? Keep 50.</button>}</div>}
          </>)}
        </div>

        <aside className={styles.sidebar}>
          <div className={styles.scoreCard}><span className={styles.scoreIcon}><Icon name="spark" size={22} /></span><span>{mode === "pair" ? "Your shared score" : "Your score this set"}</span><strong>{total}<small> pts</small></strong><div className={styles.scoreTrack}><span style={{ width: `${Math.min(100, total / (rounds || 5))}%` }} /></div><span className={styles.scoreCaption}>A closer read. A bigger score.</span></div>
          <div className={styles.howCard}><h3>{mode === "pair" ? "Same review. Two minds." : "Trust your first read."}</h3><p>{mode === "pair" ? "The fun is finding out what “pretty good” means to someone else." : "Look beyond positive and negative. A “but,” a little sarcasm, or a backhanded compliment can change everything."}</p>{choosingFeeling ? <p className={styles.emotionTip}>Let the shuffle pick your feelings. Then follow the wheel to your percentage.</p> : <><EmotionPair axis={activeAxis} /><p className={styles.emotionTip}>One pair per round. A bigger percentage leans more toward {activeAxis.right.toLowerCase()}.</p></>}<details><summary>How do points work?</summary><p>Within 3 of the {mode === "pair" ? "secret target" : "demo reference"} earns 100 points. Otherwise, start at 100 and subtract 3 per point of distance, down to zero.</p><p>Points are for play. They don’t measure whether an annotation is valid.</p></details></div>
          <div className={styles.purposeCard}><span className={styles.purposeIcon}><Icon name="data" size={20} /></span><h3>A little play.<br />A useful perspective.</h3><p>{mode === "pair" ? "Your invented review, intended sentiment, and your friend’s interpretation become a synthetic example." : "Each guess adds a sentiment label. Different reads help us see where language gets complicated."}</p><button className={styles.inlineButton} onClick={() => selectMode("data")}>See what gets saved <Icon name="arrow" size={15} /></button></div>
        </aside>
      </div>}

      <div className={styles.gameFoot}><span><Icon name="check" size={14} /> Playing saves anonymous guesses to this prototype’s database.</span><span>Inspired by Wavelength. Made for a little more understanding.</span></div>
      {storageWarning && <p className={styles.smallNote}>Browser storage is unavailable. Your saved labels remain on the server; game progress may reset when you reload.</p>}
      <dialog ref={dialog} aria-labelledby="ground-instructions" onCancel={() => setHelp(false)} onClose={() => setHelp(false)} className={styles.helpDialog}>
        <button className={styles.closeDialog} aria-label="Close instructions" onClick={() => setHelp(false)}>×</button><span className={styles.gameMark}><Icon name="wave" size={28} /></span><h2 id="ground-instructions">Find the feeling.</h2><p>Common Ground is inspired by Wavelength: turn a feeling into a position on a spectrum.</p><h3>Playing solo</h3><p>Watch the emotion shuffle choose a pair, such as Sad and Happy. Read the review, choose a percentage toward the second feeling, and lock your guess. Then the wheel spins to reveal the demo reference. We save your rating before the reveal.</p><h3>Playing together</h3><p>The emotion shuffle picks a pair. Then the wheel spins and lands on Player 1’s secret percentage. Each round also gives you an everyday scene, like stopping for gas or shopping. Player 1 writes a fictional review of that scene to match the feeling and percentage. Hide the target and pass the device. Player 2 guesses. Reveal, discuss, and swap roles for five rounds.</p><h3>Your perspective counts</h3><p>Sentiment is subjective. References are demo authors’ estimates, and points measure closeness to them. These are original fictional reviews, not customer data or a crowd consensus.</p><p>Ratings, confidence, timing, and an anonymous browser ID are stored in a local SQLite database. Invented reviews and their targets are kept separately. Don’t include personal information.</p><button className={styles.primary} onClick={() => setHelp(false)}>Got it. Let’s play.</button>
      </dialog>
    </section>
  );
}

function ReviewCard({ review, playerWritten = false }: { review: Review; playerWritten?: boolean }) {
  return <div className={styles.reviewCard}><div className={styles.reviewMeta}><span><span className={styles.reviewIcon}><Icon name="wave" size={14} /></span>{review.category}</span><small>{playerWritten ? "Made up for this round" : "Original demo review"}</small></div><blockquote>“{review.text}”</blockquote><div className={styles.reviewRule} /></div>;
}
function ErrorMessage({ error }: { error: string }) { return error ? <p role="alert" className={styles.error}>{error}</p> : null; }

function DataView({ dataset, reviews, loading, error, refresh }: { dataset: Dataset | null; reviews: Review[]; loading: boolean; error: string; refresh: () => Promise<void> }) {
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState(false);
  async function exportData(format: "json" | "csv") {
    setExporting(true); setExportError("");
    try { await download(format); } catch { setExportError("The download couldn’t be prepared. Check the server and try again."); } finally { setExporting(false); }
  }
  return <div className={styles.dataView}>
    <div className={styles.dataHeader}><div><h2>Play leaves a little knowledge behind.</h2><p>Every saved read, with its context intact. Totals cover this prototype’s database.</p></div><button className={styles.textButton} disabled={loading} onClick={() => void refresh()}>{loading ? "Refreshing…" : "Refresh"}</button></div>
    <ErrorMessage error={error || exportError} />
    {!dataset ? <div className={styles.loadState}>{loading ? "Loading saved perspectives…" : "Connect to the server, then refresh to see saved labels."}</div> : <>
      <div className={styles.dataStats}><div><strong>{dataset.summary.annotations}</strong><span>Review ratings</span></div><div><strong>{dataset.summary.unique_reviews}</strong><span>Reviews explored</span></div><div><strong>{dataset.summary.unsure_annotations}</strong><span>Ambiguous reads</span></div><div><strong>{dataset.summary.synthetic_pairs}</strong><span>Invented review pairs</span></div></div>
      <div className={styles.dataExplanation}><div><span className={styles.playerPill}>Solo</span><h3>Independent interpretation</h3><p>A 0–100 rating, confidence, time taken, review ID, and reference version. The rating is recorded before feedback. Repeat reads are flagged by the server.</p></div><div><span className={styles.playerPill}>Pass & play</span><h3>Synthetic examples</h3><p>The invented review, author’s intended target, and another person’s guess. Intent and interpretation stay separate; neither becomes a verified label.</p></div></div>
      <div className={styles.exportBar}><div><h3>Take the data with you.</h3><p>JSON preserves the full structure. CSV includes both types with provenance.</p></div><div><button className={styles.secondary} disabled={exporting} onClick={() => void exportData("json")}><Icon name="download" size={16} /> JSON</button><button className={styles.secondary} disabled={exporting} onClick={() => void exportData("csv")}><Icon name="download" size={16} /> CSV</button></div></div>
      <h3 className={styles.tableHeading}>Recent review ratings</h3>
      {dataset.annotations.length ? <div className={styles.tableScroll}><table><caption className={styles.srOnly}>The ten most recent sentiment annotations</caption><thead><tr><th>Review</th><th>Feeling</th><th>Percentage</th><th>Confidence</th></tr></thead><tbody>{dataset.annotations.slice(-10).reverse().map((a, i) => <tr key={String(a.submission_id ?? i)}><td>{reviews.find(r => r.id === a.review_id)?.text ?? a.review_id}</td><td>{getAxis(String(a.axis_id ?? "satisfaction")).right}</td><td><span className={styles.sentimentChip}>{a.score}<small>%</small></span></td><td>{a.confidence === "unsure" ? "Open to interpretation" : "Pretty clear"}</td></tr>)}</tbody></table></div> : <p className={styles.emptyData}>Your first read starts the collection. Play a solo round, then come back here.</p>}
      <h3 className={styles.tableHeading}>Recent invented review pairs</h3>
      {dataset.synthetic_pairs.length ? <div className={styles.tableScroll}><table><caption className={styles.srOnly}>The ten most recent synthetic review pairs, with intent and interpretation separated</caption><thead><tr><th>Invented review</th><th>Feeling</th><th>Writer’s target</th><th>Reader’s guess</th></tr></thead><tbody>{dataset.synthetic_pairs.slice(-10).reverse().map((p, i) => <tr key={String(p.pair_id ?? i)}><td>{p.text}</td><td>{getAxis(String(p.axis_id ?? "satisfaction")).right}</td><td><span className={styles.sentimentChip}>{p.intended_score}<small>%</small></span></td><td><span className={styles.sentimentChip}>{p.guessed_score}<small>%</small></span></td></tr>)}</tbody></table></div> : <p className={styles.emptyData}>Play with a friend to create an example with both a writer’s intent and a reader’s interpretation.</p>}
      <p className={styles.smallNote}>This is a local research prototype with authored examples. Scores are game feedback, not a measure of label quality. No claim of a validated training dataset.</p>
    </>}
  </div>;
}
