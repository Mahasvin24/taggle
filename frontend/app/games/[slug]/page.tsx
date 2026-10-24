import Link from "next/link";
import { notFound } from "next/navigation";
import { games } from "@/games/registry";

export function generateStaticParams() {
  return games.map((game) => ({ slug: game.slug }));
}

export default async function GamePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const game = games.find((game) => game.slug === slug);

  if (!game) notFound();

  const Game = game.component;

  return (
    <div className="game-page">
      <Link href="/" className="back-link">← All games</Link>
      <Game />
    </div>
  );
}
