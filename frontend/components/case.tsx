"use client";

import { useEffect, useState } from "react";
import { CaseRecord, Term, getBiasReport } from "@/lib/api";

/* Render redacted text, converting solid-block runs into redaction bars. */
export function RedactedText({ text }: { text: string }) {
  const parts = text.split(/(\u2588+)/g);
  return (
    <div className="redacted-text">
      {parts.map((p, i) =>
        p.startsWith("\u2588")
          ? <span key={i} className="bar">{"\u00A0".repeat(8)}</span>
          : <span key={i}>{p}</span>
      )}
    </div>
  );
}

export function SkillChips({ skills, kind, highlight = [] }:
    { skills: string[]; kind: "matched" | "missing"; highlight?: string[] }) {
  if (!skills.length) return <span className="small">none</span>;
  return (
    <div className="chips">
      {skills.map((s) => (
        <span key={s}
          className={`chip ${kind}${highlight.includes(s) ? " diff" : ""}`}>
          {s}
        </span>
      ))}
    </div>
  );
}

export function TopTerms({ terms }: { terms: Term[] }) {
  if (!terms.length) return <span className="small">no terms recorded</span>;
  const max = Math.max(...terms.map((t) => t.weight), 1e-9);
  return (
    <ul className="terms">
      {terms.map((t) => (
        <li key={t.term}>
          <span>{t.term}</span>
          <span className="track">
            <span className="fill"
              style={{ width: `${(t.weight / max) * 100}%`, display: "block" }} />
          </span>
          <span>{t.weight.toFixed(3)}</span>
        </li>
      ))}
    </ul>
  );
}

export function Stamp({ pct }: { pct: number | null }) {
  if (pct === null) return null;
  return (
    <div className={`stamp${pct < 40 ? " flag" : ""}`} role="status"
      aria-label={`Match ${pct} percent`}>
      <div className="pct">{pct.toFixed(0)}%</div>
      <div className="cap">JD match</div>
    </div>
  );
}

/* Full case card. `signature` turns on the one-time redaction sweep +
   stamp animation — used on the single-case result only, never in
   batch/compare views. */
export function CaseCard({ c, signature = false }:
    { c: CaseRecord; signature?: boolean }) {
  const [sweep, setSweep] = useState(signature);
  useEffect(() => {
    if (!signature) return;
    const t = setTimeout(() => setSweep(false), 900);
    return () => clearTimeout(t);
  }, [signature]);

  if (c.status !== "scored") {
    return (
      <div className="card">
        <h3>{c.filename}</h3>
        <span className={`status ${c.status}`}>{c.status.replace("_", " ")}</span>
        <p>{c.reject_reason}</p>
        <p className="small">
          {c.status === "rejected_unsafe"
            ? "The file was rejected before parsing. Remove the active content and upload again."
            : "Fix the file and upload again."}
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <Stamp pct={c.match_pct} />
      <h3>{c.filename}</h3>
      <p className="mono" style={{ fontSize: 16, margin: "2px 0 10px" }}>
        {c.category}
      </p>
      <span className="status scored">scored</span>{" "}
      <span className="chip">PII redacted{c.fields_redacted.length
        ? `: ${c.fields_redacted.join(", ")}` : ""}</span>

      <hr className="hairline" />
      <span className="label">Skills matched to the JD</span>
      <SkillChips skills={c.matched_skills} kind="matched" />
      <span className="label" style={{ marginTop: 12 }}>Missing from the resume</span>
      <SkillChips skills={c.missing_skills} kind="missing" />

      <hr className="hairline" />
      <span className="label">Why the model chose {c.category}</span>
      <TopTerms terms={c.top_terms} />

      {c.redacted_preview && (
        <>
          <hr className="hairline" />
          <span className="label">Redacted resume text (stored record)</span>
          <div className={`redaction-pane${sweep ? " sweep" : ""}`}>
            <RedactedText text={c.redacted_preview} />
          </div>
        </>
      )}
      <p className="small" style={{ marginTop: 10 }}>
        case {c.id} · match method: {c.match_method}
      </p>
    </div>
  );
}

/* Bias disclosure — permanently visible on batch views, never dismissible. */
export function BiasDisclosure() {
  const [report, setReport] = useState<any>(null);
  useEffect(() => { getBiasReport().then(setReport).catch(() => null); }, []);
  return (
    <div className="disclosure">
      <span className="label">Bias audit disclosure</span>
      {report?.available ? (
        <>
          <p style={{ margin: "4px 0" }}>
            Last name-swap audit ({new Date(report.run_at).toLocaleDateString()}):{" "}
            {report.summary.n_comparisons} comparisons across{" "}
            {report.summary.n_name_pairs} masculine/feminine name pairs.
            Prediction flips caused by the name alone:{" "}
            <strong className="mono">
              {report.summary.prediction_flips} ({(report.summary.flip_rate * 100).toFixed(2)}%)
            </strong>.
          </p>
          <p className="small" style={{ margin: 0 }}>{report.notes}</p>
        </>
      ) : (
        <p className="small" style={{ margin: 0 }}>
          No audit on record. Run <span className="mono">python -m models.bias_audit</span>{" "}
          in the backend to generate one. Scores should not be used for
          decisions until an audit exists.
        </p>
      )}
    </div>
  );
}
