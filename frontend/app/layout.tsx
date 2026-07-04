import "./globals.css";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Clearance — resume screening with an audit trail",
  description:
    "Every resume is security-scanned, PII-redacted, scored, and logged.",
};

export default function RootLayout({ children }:
    { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=Public+Sans:wght@400;600&display=swap"
        />
      </head>
      <body>
        <div className="container">
          <header className="masthead">
            <h1>Clearance</h1>
            <nav>
              <Link href="/">Intake</Link>
              <Link href="/history">Case history</Link>
            </nav>
            <span className="tag">nothing is scored before it is scanned
              and redacted</span>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
