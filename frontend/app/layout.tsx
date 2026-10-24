import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Taggle | Pick a game",
  description: "Play small games. Help label real-world data.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link href="/" className="brand" aria-label="Taggle home">
            <span className="brand-mark" aria-hidden="true">t</span>
            taggle
          </Link>
          <span className="header-note">A little play. A little progress.</span>
        </header>
        <main>{children}</main>
        <footer>Small games. Useful labels.</footer>
      </body>
    </html>
  );
}
