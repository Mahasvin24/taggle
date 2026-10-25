import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { EmotionAxis } from "./axes";
import styles from "./game.module.css";

function point(value: number, radius: number) {
  const angle = Math.PI * (1 - value / 100);
  return [260 + Math.cos(angle) * radius, 238 - Math.sin(angle) * radius];
}
function arc(from: number, to: number, radius: number) {
  const a = point(from, radius), b = point(to, radius);
  return `M ${a[0]} ${a[1]} A ${radius} ${radius} 0 0 1 ${b[0]} ${b[1]}`;
}
const landingAngle = (value: number) => value * 1.8 - 90;

export function EmotionPair({ axis }: { axis: EmotionAxis }) {
  return <div className={styles.emotionPair} aria-label={`This round: ${axis.left} to ${axis.right}`}><span><b aria-hidden="true">{axis.leftEmoji}</b>{axis.left}</span><i aria-hidden="true">↔</i><span><b aria-hidden="true">{axis.rightEmoji}</b>{axis.right}</span></div>;
}

export default function EmotionWheel({ value, axis, spinning = false, onLanded, label = "Your percentage" }: {
  value: number; axis: EmotionAxis; spinning?: boolean; onLanded?: () => void; label?: string;
}) {
  const needle = useRef<SVGGElement>(null);
  const callback = useRef(onLanded);
  useEffect(() => { callback.current = onLanded; }, [onLanded]);
  useEffect(() => {
    if (!spinning || !needle.current) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const target = landingAngle(value);
    const animation = needle.current.animate([
      { transform: "rotate(-90deg)", offset: 0 },
      { transform: "rotate(90deg)", offset: .16 },
      { transform: "rotate(-90deg)", offset: .32 },
      { transform: "rotate(90deg)", offset: .48 },
      { transform: "rotate(-80deg)", offset: .64 },
      { transform: "rotate(65deg)", offset: .78 },
      { transform: `rotate(${Math.max(-90, target - 18)}deg)`, offset: .9 },
      { transform: `rotate(${target}deg)`, offset: 1 },
    ], { duration: reduced ? 0 : 3000, easing: "ease-in-out", fill: "forwards" });
    let active = true;
    animation.finished.then(() => { if (active) callback.current?.(); }).catch(() => {});
    return () => { active = false; animation.cancel(); };
  }, [spinning, value]);

  return <div className={styles.emotionWheel} data-spinning={spinning} style={{ "--emotion-color": axis.color } as CSSProperties}>
    <svg className={styles.semicircle} viewBox="0 0 520 275" aria-hidden="true">
      <path d={arc(0, 100, 213)} fill="none" stroke="#eae2f0" strokeWidth="54" />
      {Array.from({ length: 20 }, (_, i) => <path key={i} d={arc(i * 5 + .3, (i + 1) * 5 - .3, 209)} fill="none" stroke={!spinning && i === Math.min(19, Math.floor(value / 5)) ? "#efcf83" : i % 2 ? axis.color : "#d9cbe6"} strokeWidth="38" opacity={i % 2 ? .5 + i / 40 : 1} />)}
      <path d="M 30 239 H 490" stroke="#e4dbe9" strokeWidth="2" />
      <g ref={needle} className={styles.wheelNeedle} style={{ transform: `rotate(${landingAngle(value)}deg)` }}>
        <path d="M 260 238 V 61" stroke="#6c4b85" strokeWidth="6" strokeLinecap="round" />
        <path d="m260 35 10 28h-20Z" fill="#6c4b85" />
      </g>
      <circle cx="260" cy="238" r="26" fill="#eee5f6" stroke="#d6c6e2" />
      <circle cx="260" cy="238" r="16" fill="#77508f" />
      <circle cx="260" cy="238" r="5" fill="#fffefd" />
    </svg>
    <div className={styles.wheelHub} aria-live="polite"><span aria-hidden="true">{spinning ? "✦" : value < 40 ? axis.leftEmoji : value > 60 ? axis.rightEmoji : "🤔"}</span><strong>{spinning ? "?" : value}<small>{spinning ? "" : "%"}</small></strong><p>{spinning ? "Finding your feeling…" : label}</p></div>
  </div>;
}

export function WheelReveal({ value, axis, children }: { value: number; axis: EmotionAxis; children: ReactNode }) {
  const [landed, setLanded] = useState(false);
  return <div className={styles.wheelReveal}><EmotionPair axis={axis} /><EmotionWheel value={value} axis={axis} spinning={!landed} onLanded={() => setLanded(true)} label="The revealed percentage" />{landed ? children : <p className={styles.spinCaption} role="status">Finding the feeling… where will it land?</p>}</div>;
}
