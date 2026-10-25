import type { Scenario } from "./scenarios";
import styles from "./game.module.css";

export default function ScenarioPrompt({ scenario }: { scenario?: Scenario }) {
  if (!scenario) return null;
  return <div className={styles.scenarioPrompt} aria-label="This round’s scenario">
    <span>The scene</span>
    <h3>{scenario.title}</h3>
    <p>{scenario.prompt}</p>
  </div>;
}
