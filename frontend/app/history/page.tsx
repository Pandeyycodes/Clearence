"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CaseRecord, listCases } from "@/lib/api";

export default function History() {
  const [cases, setCases] = useState<CaseRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCases(100).then(setCases).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error-note">{error}</div>;
  if (!cases) return <p className="mono small">Retrieving history…</p>;
  if (!cases.length) return (
    <div className="card">
      <h2>Case history</h2>
      <p>No cases yet. Screen a resume from the intake screen and it will be
        logged here.</p>
    </div>
  );

  return (
    <main>
      <div className="card" style={{ overflowX: "auto" }}>
        <h2>Case history · every screening on record</h2>
        <table className="cases">
          <thead>
            <tr><th>When</th><th>File</th><th>Category</th>
              <th>JD match</th><th>Status</th><th>Batch</th><th></th></tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.id}>
                <td className="mono small">
                  {c.created_at ? new Date(c.created_at).toLocaleString() : "—"}
                </td>
                <td className="mono">{c.filename}</td>
                <td>{c.category ?? "—"}</td>
                <td className="num">
                  {c.match_pct !== null ? `${c.match_pct.toFixed(1)}%` : "—"}
                </td>
                <td><span className={`status ${c.status}`}>
                  {c.status.replace("_", " ")}</span></td>
                <td className="mono small">
                  {c.batch_id
                    ? <Link href={`/batch/${c.batch_id}`}>{c.batch_id.slice(0, 8)}</Link>
                    : "—"}
                </td>
                <td><Link href={`/case/${c.id}`}>open</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
