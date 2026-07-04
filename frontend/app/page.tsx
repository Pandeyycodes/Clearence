"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CaseRecord, screen, screenBatch } from "@/lib/api";
import { CaseCard } from "@/components/case";

const STEPS = ["Security scan", "PII redaction", "Category + JD score",
  "Case record written"];

export default function Intake() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [jd, setJd] = useState("");
  const [drag, setDrag] = useState(false);
  const [phase, setPhase] = useState<"idle" | "working" | "done">("idle");
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<CaseRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const accepted = Array.from(list).filter((f) =>
      /\.(pdf|docx|txt)$/i.test(f.name));
    setFiles((prev) => [...prev, ...accepted]);
    if (Array.from(list).length !== accepted.length)
      setError("Only .pdf, .docx and .txt files are accepted. Others were skipped.");
  };

  const submit = async () => {
    if (!files.length) { setError("Add at least one resume file."); return; }
    setError(null);
    setPhase("working");
    setStep(0);
    // The API is a single call; tick the checklist while it runs so the
    // intake order is visible, complete all steps when it resolves.
    const ticker = setInterval(
      () => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 550);
    try {
      if (files.length === 1) {
        const c = await screen(files[0], jd);
        clearInterval(ticker);
        setStep(STEPS.length);
        setResult(c);
        setPhase("done");
      } else {
        const b = await screenBatch(files, jd);
        clearInterval(ticker);
        router.push(`/batch/${b.batch_id}`);
      }
    } catch (e: any) {
      clearInterval(ticker);
      setPhase("idle");
      setError(e.message ?? "The request failed. Check that the backend is running on port 8000.");
    }
  };

  return (
    <main>
      {phase === "idle" && (
        <>
          <div className="card">
            <h2>Evidence intake</h2>
            <div
              className={`dropzone${drag ? " drag" : ""}`}
              role="button" tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false);
                addFiles(e.dataTransfer.files); }}
            >
              <div className="mono">Drop resumes here or press Enter to browse</div>
              <div className="hint">.pdf, .docx, .txt · one file scores a case,
                several files open a ranked batch</div>
              <input ref={inputRef} type="file" multiple hidden
                accept=".pdf,.docx,.txt"
                onChange={(e) => addFiles(e.target.files)} />
            </div>
            {files.length > 0 && (
              <ul className="filelist">
                {files.map((f, i) => (
                  <li key={i}>
                    <span>{f.name}</span>
                    <button className="btn secondary" style={{ padding: "1px 8px" }}
                      onClick={() => setFiles(files.filter((_, j) => j !== i))}>
                      remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h2>Job description</h2>
            <label className="label" htmlFor="jd">
              Paste the JD to score against (optional for a single file,
              required for a useful ranking)
            </label>
            <textarea id="jd" rows={7} value={jd}
              placeholder="e.g. Senior accountant. Requirements: accounting, general ledger, financial reporting, auditing, Excel..."
              onChange={(e) => setJd(e.target.value)} />
            <div style={{ marginTop: 14 }}>
              <button className="btn" onClick={submit}>
                {files.length > 1 ? `Screen ${files.length} resumes` : "Screen resume"}
              </button>
            </div>
          </div>
          {error && <div className="error-note">{error}</div>}
        </>
      )}

      {phase === "working" && (
        <div className="card" aria-live="polite">
          <h2>Processing</h2>
          <ul className="steps">
            {STEPS.map((s, i) => (
              <li key={s} className={i < step ? "done" : i === step ? "active" : ""}>
                <span className="box" aria-hidden />{s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {phase === "done" && result && (
        <>
          <CaseCard c={result} signature />
          <div style={{ marginTop: 16, display: "flex", gap: 10 }}>
            <button className="btn secondary" onClick={() => {
              setPhase("idle"); setFiles([]); setResult(null);
            }}>Screen another</button>
          </div>
        </>
      )}
    </main>
  );
}
