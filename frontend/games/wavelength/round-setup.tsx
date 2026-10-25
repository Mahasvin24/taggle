import { useEffect, useRef, useState } from "react";
import { axes, type EmotionAxis } from "./axes";
import EmotionWheel from "./emotion-wheel";
import ScenarioPrompt from "./scenario-prompt";
import type { Scenario } from "./scenarios";
import styles from "./game.module.css";

export default function RoundSetup({ axis, target, scenario, onReady }: { axis: EmotionAxis; target?: number; scenario?: Scenario; onReady: () => void }) {
  const [stage, setStage] = useState<"shuffle" | "wheel" | "ready">("shuffle");
  const reel = useRef<HTMLDivElement>(null);
  const landingIndex = axes.length * 5 + axes.findIndex(a => a.id === axis.id);

  useEffect(() => {
    if (!reel.current) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const animation = reel.current.animate([
      { transform: "translateY(0px)" },
      { transform: `translateY(${-landingIndex * 96}px)` },
    ], { duration: reduced ? 0 : 1900, easing: "cubic-bezier(.12,.7,.12,1)", fill: "forwards" });
    let active = true;
    animation.finished.then(() => { if (active) setStage(target === undefined ? "ready" : "wheel"); }).catch(() => {});
    return () => { active = false; animation.cancel(); };
  }, [landingIndex, target]);

  return <div className={styles.roundSetup} data-stage={stage}>
    <div className={styles.setupSteps}><span className={stage === "shuffle" ? styles.activeStep : ""}>1. Pick a feeling</span>{target !== undefined && <><i /> <span className={stage === "wheel" ? styles.activeStep : ""}>2. Spin a percentage</span></>}</div>
    <h2>{stage === "shuffle" ? "What’s the feeling?" : target !== undefined ? stage === "wheel" ? "Let the wheel decide." : "There’s your feeling." : "That’s this round’s feeling."}</h2>
    <p>{stage === "shuffle" ? "A fresh pair of emotions for this round…" : target !== undefined ? "Player 1, keep this percentage to yourself." : "Read the review with just these feelings in mind."}</p>
    <ScenarioPrompt scenario={scenario} />
    <div className={`${styles.emotionSlot} ${stage !== "shuffle" ? styles.slotSelected : ""}`} aria-hidden="true"><div ref={reel}>{Array.from({ length: 7 }, (_, loop) => axes.map(a => <div className={styles.slotRow} key={`${loop}-${a.id}`}><span>{a.leftEmoji}</span><b>{a.left}</b><i>↔</i><b>{a.right}</b><span>{a.rightEmoji}</span></div>))}</div></div>
    <div className={styles.srOnly} role="status">{stage === "shuffle" ? "Choosing the emotion pair" : `Selected ${axis.left} to ${axis.right}`}</div>
    {target !== undefined && stage !== "shuffle" ? <EmotionWheel value={target} axis={axis} spinning={stage === "wheel"} onLanded={() => setStage("ready")} label={`toward ${axis.right.toLowerCase()}`} /> : <div className={styles.setupTeaser} aria-hidden="true"><span>✦</span><span>✧</span><span>✦</span></div>}
    {stage === "ready" ? <div className={styles.setupReady}><span className={styles.selectedNote}>Feeling selected. {target !== undefined ? "Percentage locked in." : "Trust your first impression."}</span><button className={styles.primary} onClick={onReady}>{target !== undefined ? "Write your review" : "Read the review"}<span aria-hidden="true">→</span></button></div> : <p className={styles.spinCaption}>{stage === "shuffle" ? "Shuffling feelings…" : "Spinning your secret target…"}</p>}
  </div>;
}
