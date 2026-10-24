import Link from "next/link";
import { games } from "@/games/registry";

export default function Home() {
  return (
    <div className="home">
      <section className="intro">
        <h1>Pick your next<br />little challenge.</h1>
        <p>Turn a few minutes of play into useful data.<br className="desktop-break" /> Choose a game to get started.</p>
      </section>

      <section className="game-grid" aria-label="Choose a game">
        {games.map((game) => (
          <Link className="game-card" href={`/games/${game.slug}`} key={game.slug}>
            <div className="game-art" aria-hidden="true">
              <span className="fruit-icon">{game.icon}</span>
              <span className="preview-label">{game.previewLabel}</span>
            </div>
            <div className="game-card-content">
              <span className="status">{game.status}</span>
              <h2>{game.title}</h2>
              <p>{game.description}</p>
              <span className="card-action">View game <span aria-hidden="true">↗</span></span>
            </div>
          </Link>
        ))}
        <div className="coming-soon">
          <span className="plus-mark" aria-hidden="true">+</span>
          <h2>More ways to play.</h2>
          <p>New labeling games are on the way.</p>
        </div>
      </section>
    </div>
  );
}
