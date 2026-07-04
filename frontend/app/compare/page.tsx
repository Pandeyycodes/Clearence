"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CaseRecord, compareCases } from "@/lib/api";
import { SkillChips, TopTerms } from "@/components/case";

function CompareInner() {
  const params = useSearchParams();
  const ids = (params.get("ids") ?? "").split(",").filter(Boolean);
  const [cases, setCases] = useState<CaseRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ids.length < 2) { setError("Select 2 to 4 cases from a batch to compare."); return; }
    compareCases(ids).then((d) => setCases(d.cases)).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  if (error) return <div className="error-note">{error}</div>;
  if (!cases) return <p className="mono small">Retrieving cases…</p>;

  const rows: [string, (c: CaseRecord) => React.ReactNode][] = [
    ["File", (c) => <span className="mono">{c.filename}</span>],
    ["Category", (c) => c.category ?? "—"],
    ["JD match", (c) => (
      <span className="mono" style={{ fontSize: 20 }}>
        {c.match_pct !== null ? `${c.match_pct.toFixed(1)}%` : "—"}
      </span>
    )],
    ["Matched skills (highlight = only this candidate)", (c) => (
      <SkillChips skills={c.matched_skills} kind="matched"
        highlight={c.unique_skills ?? []} />
    )],
    ["Missing skills", (c) => <SkillChips skills={c.missing_skills} kind="missing" />],
    ["Top model terms", (c) => <TopTerms terms={c.top_terms.slice(0, 6)} />],
  ];

  return (
    <main>
      <div className="card">
        <h2>Compare · {cases.length} candidates</h2>
        <p className="small">Highlighted chips mark skills only that candidate
          matched — the actual separation between them.</p>
      </div>
      {rows.map(([label, render]) => (
        <div key={label} style={{ marginTop: 14 }}>
          <span className="label">{label}</span>
          <div className={`compare-grid n${cases.length}`}>
            {cases.map((c) => (
              <div className="card compare-row" key={c.id}>{render(c)}</div>
            ))}
          </div>
        </div>
      ))}
    </main>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<p className="mono small">Loading…</p>}>
      <CompareInner />
    </Suspense>
  );
}
