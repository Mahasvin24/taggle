import { useId } from "react";
import { feeling, type EmotionAxis } from "./axes";
import EmotionWheel, { EmotionPair } from "./emotion-wheel";
import styles from "./game.module.css";

export default function Dial({ value, onChange, disabled = false, axis }: {
  value: number; onChange?: (value: number) => void; disabled?: boolean; axis: EmotionAxis;
}) {
  const inputId = useId();
  return <div className={styles.feelingControl}>
    <EmotionPair axis={axis} />
    <EmotionWheel value={value} axis={axis} label={feeling(value, axis)} />
    {onChange && <div className={styles.feelingSlider}>
      <label htmlFor={inputId}>Set your guess toward {axis.right.toLowerCase()}.</label>
      <input id={inputId} type="range" min="0" max="100" step="1" value={value} disabled={disabled} onChange={e => onChange(Number(e.target.value))} aria-label="Your sentiment guess" aria-valuetext={`${value} percent toward ${axis.right}`} />
      <div><span>{axis.leftEmoji} {axis.left}</span><span>{axis.right} {axis.rightEmoji}</span></div>
    </div>}
  </div>;
}
