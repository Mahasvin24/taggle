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
            <div className={`game-art ${game.slug === "wavelength" ? "spectrum-art" : ""}`} aria-hidden="true">
              {game.slug === "wavelength" ? <svg className="spectrum-preview" viewBox="0 0 260 150" fill="none"><path d="M30 125a100 100 0 0 1 200 0" stroke="#ded7e6" strokeWidth="32" /><path d="M30 125a100 100 0 0 1 100-100" stroke="#e9a89d" strokeWidth="25" /><path d="M130 25a100 100 0 0 1 100 100" stroke="#96bfa9" strokeWidth="25" /><path d="m130 125 47-79" stroke="#72538f" strokeWidth="4" strokeLinecap="round" /><circle cx="130" cy="125" r="15" fill="#816497" /><circle cx="130" cy="125" r="5" fill="#f2edf7" /></svg> : <span className="fruit-icon">{game.icon}</span>}
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
