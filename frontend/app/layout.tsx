import "./globals.css";
import type { Metadata } from "next";
import { Nav } from "@/components/nav";
import { AuthGate } from "@/components/authgate";

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
            <Nav />
            <span className="tag">nothing is scored before it is scanned
              and redacted</span>
          </header>
          <AuthGate>{children}</AuthGate>
        </div>
      </body>
    </html>
  );
}
