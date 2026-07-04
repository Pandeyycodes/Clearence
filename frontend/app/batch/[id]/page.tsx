"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { BatchRecord, getBatch } from "@/lib/api";
import { BiasDisclosure, SkillChips } from "@/components/case";
import Link from "next/link";

type SortKey = "match_pct" | "category" | "filename";

export default function BatchView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [batch, setBatch] = useState<BatchRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"table" | "grid">("table");
  const [sortKey, setSortKey] = useState<SortKey>("match_pct");
  const [asc, setAsc] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    getBatch(id).then(setBatch).catch((e) => setError(e.message));
  }, [id]);

  const cases = useMemo(() => {
    if (!batch) return [];
    return [...batch.cases].sort((a, b) => {
      const av = a[sortKey] ?? "", bv = b[sortKey] ?? "";
      const cmp = typeof av === "number" && typeof bv === "number"
        ? av - bv : String(av).localeCompare(String(bv));
      return asc ? cmp : -cmp;
    });
  }, [batch, sortKey, asc]);

  const toggle = (cid: string) =>
    setSelected((s) => s.includes(cid)
      ? s.filter((x) => x !== cid)
      : s.length < 4 ? [...s, cid] : s);

  const exportCsv = () => {
    if (!batch) return;
    const rows = [["filename", "category", "match_pct", "status",
      "matched_skills", "missing_skills"]];
    batch.cases.forEach((c) => rows.push([
      c.filename, c.category ?? "", String(c.match_pct ?? ""), c.status,
      c.matched_skills.join("; "), c.missing_skills.join("; ")]));
    const csv = rows.map((r) =>
      r.map((v) => `"${v.replace(/"/g, '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url; a.download = `clearance-batch-${id}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const header = (label: string, key: SortKey) => (
    <th onClick={() => key === sortKey ? setAsc(!asc)
        : (setSortKey(key), setAsc(false))}>
      {label}{sortKey === key ? (asc ? " ↑" : " ↓") : ""}
    </th>
  );

  if (error) return <div className="error-note">{error}</div>;
  if (!batch) return <p className="mono small">Retrieving batch…</p>;

  return (
    <main>
      <div className="card">
        <h2>Batch {id.slice(0, 8)} · {batch.cases.length} resumes</h2>
        <span className="label">Scored against</span>
        <p className="small" style={{ whiteSpace: "pre-wrap" }}>
          {batch.jd_text || "(no JD provided)"}
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button className="btn secondary"
            onClick={() => setView(view === "table" ? "grid" : "table")}>
            {view === "table" ? "Grid view" : "Table view"}
          </button>
          <button className="btn secondary" onClick={exportCsv}>
            Export CSV
          </button>
          {selected.length >= 2 && (
            <button className="btn"
              onClick={() => router.push(`/compare?ids=${selected.join(",")}`)}>
              Compare selected ({selected.length})
            </button>
          )}
        </div>
      </div>

      {view === "table" ? (
        <div className="card" style={{ overflowX: "auto" }}>
          <table className="cases">
            <thead>
              <tr>
                <th>Compare</th>
                {header("File", "filename")}
                {header("Category", "category")}
                {header("JD match", "match_pct")}
                <th>Status</th>
                <th>Case</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td>
                    <input type="checkbox"
                      aria-label={`Select ${c.filename} for comparison`}
                      checked={selected.includes(c.id)}
                      disabled={c.status !== "scored"}
                      onChange={() => toggle(c.id)} />
                  </td>
                  <td className="mono">{c.filename}</td>
                  <td>{c.category ?? "—"}</td>
                  <td className="num">
                    {c.match_pct !== null ? `${c.match_pct.toFixed(1)}%` : "—"}
                  </td>
                  <td><span className={`status ${c.status}`}>
                    {c.status.replace("_", " ")}</span></td>
                  <td><Link href={`/case/${c.id}`}>open</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid">
          {cases.map((c) => (
            <div className="card" key={c.id}>
              <label style={{ float: "right" }}>
                <input type="checkbox"
                  aria-label={`Select ${c.filename} for comparison`}
                  checked={selected.includes(c.id)}
                  disabled={c.status !== "scored"}
                  onChange={() => toggle(c.id)} />
              </label>
              <h3>{c.filename}</h3>
              <p className="mono" style={{ margin: "0 0 6px" }}>
                {c.category ?? "—"} ·{" "}
                {c.match_pct !== null ? `${c.match_pct.toFixed(1)}%` : "no JD score"}
              </p>
              <span className={`status ${c.status}`}>
                {c.status.replace("_", " ")}</span>
              {c.status === "scored" && (
                <>
                  <hr className="hairline" />
                  <SkillChips skills={c.matched_skills} kind="matched" />
                </>
              )}
              <p style={{ marginBottom: 0 }}>
                <Link href={`/case/${c.id}`}>open case</Link>
              </p>
            </div>
          ))}
        </div>
      )}

      <BiasDisclosure />
    </main>
  );
}
