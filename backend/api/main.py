"""Clearance API.

Every screening follows the same intake order and it is enforced here, not
in the UI: scan -> extract -> redact -> classify -> match -> skill gap ->
persist. The raw file bytes and unredacted text exist only inside the
request handler and are never written anywhere (no DB, no disk, no logs).

Run:  uvicorn api.main:app --reload --port 8000   (from backend/)
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import joblib
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from db.models import Batch, BiasAuditRun, Case, Explanation, RedactedResume, SkillMatch
from db.session import get_db, init_db
from matching.embeddings import METHOD as MATCH_METHOD, match_score
from matching.skill_gap import skill_gap
from models.explain import top_terms
from preprocessing.cleaning import clean_text
from preprocessing.pii import redact
from security.file_scan import scan

app = FastAPI(title="Clearance", version="1.0.0",
              description="Resume screening with a real audit trail.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-app.vercel.app"],
    allow_methods=["*"], allow_headers=["*"],
)

MODEL_PATH = BACKEND / "artifacts" / "model_archive.joblib"
_pipeline = None


@app.on_event("startup")
def startup():
    global _pipeline
    init_db()
    _pipeline = joblib.load(MODEL_PATH)


# ---------------------------------------------------------------- helpers
def _extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith(".docx"):
        import docx
        d = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs)
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {filename} "
                     "(accepted: .pdf, .docx, .txt)")


def _screen_one(db: Session, filename: str, data: bytes, jd_text: str,
                batch_id: str | None = None) -> Case:
    """Scan -> extract -> redact -> classify -> match -> persist ONE file."""
    # 1. Security scan — before any parsing.
    safe, reason = scan(filename, data)
    if not safe:
        case = Case(batch_id=batch_id, filename=filename,
                    status="rejected_unsafe", reject_reason=reason)
        db.add(case); db.commit(); db.refresh(case)
        return case

    try:
        # 2. Extract (in memory only).
        raw_text = _extract_text(filename, data)
        if len(raw_text.strip()) < 50:
            raise ValueError("Could not extract readable text "
                             "(possibly a scanned/image-only file).")

        # 3. Redact. From here on, only redacted text is used or stored.
        redacted_text, fields = redact(raw_text)
        del raw_text, data

        # 4. Classify + explain.
        cleaned = clean_text(redacted_text)
        category = _pipeline.predict([cleaned])[0]
        terms = top_terms(_pipeline, cleaned, category)

        # 5. JD match + skill gap (against redacted text).
        pct = match_score(redacted_text, jd_text) if jd_text.strip() else None
        matched, missing = skill_gap(redacted_text, jd_text)

        case = Case(batch_id=batch_id, filename=filename, category=category,
                    match_pct=pct, status="scored")
        db.add(case); db.flush()
        db.add(RedactedResume(case_id=case.id, redacted_text=redacted_text,
                              fields_redacted=fields))
        db.add(SkillMatch(case_id=case.id, matched_skills=matched,
                          missing_skills=missing))
        db.add(Explanation(case_id=case.id, top_terms=terms))
        db.commit(); db.refresh(case)
        return case
    except Exception as exc:  # noqa: BLE001 — audit trail needs the error
        db.rollback()
        case = Case(batch_id=batch_id, filename=filename, status="error",
                    reject_reason=str(exc)[:500])
        db.add(case); db.commit(); db.refresh(case)
        return case


def _case_json(case: Case) -> dict:
    return {
        "id": case.id, "batch_id": case.batch_id, "filename": case.filename,
        "category": case.category,
        "match_pct": float(case.match_pct) if case.match_pct is not None else None,
        "status": case.status, "reject_reason": case.reject_reason,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "fields_redacted": case.redacted.fields_redacted if case.redacted else [],
        "redacted_preview": (case.redacted.redacted_text[:1200]
                             if case.redacted else None),
        "matched_skills": case.skills.matched_skills if case.skills else [],
        "missing_skills": case.skills.missing_skills if case.skills else [],
        "top_terms": case.explanation.top_terms if case.explanation else [],
        "match_method": MATCH_METHOD,
    }


# ----------------------------------------------------------------- routes
@app.post("/screen")
async def screen(file: UploadFile = File(...), jd_text: str = Form(""),
                 db: Session = Depends(get_db)):
    data = await file.read()
    case = _screen_one(db, file.filename, data, jd_text)
    return _case_json(case)


@app.post("/batch")
async def batch(files: list[UploadFile] = File(...), jd_text: str = Form(...),
                db: Session = Depends(get_db)):
    b = Batch(jd_text=jd_text)
    db.add(b); db.commit(); db.refresh(b)
    cases = []
    for f in files:
        data = await f.read()
        cases.append(_screen_one(db, f.filename, data, jd_text, batch_id=b.id))
    ranked = sorted((_case_json(c) for c in cases),
                    key=lambda c: (c["match_pct"] is None,
                                   -(c["match_pct"] or 0)))
    return {"batch_id": b.id, "jd_text": jd_text, "cases": ranked}


@app.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found.")
    return _case_json(case)


@app.get("/cases")
def list_cases(limit: int = 50, db: Session = Depends(get_db)):
    rows = (db.query(Case).order_by(Case.created_at.desc())
            .limit(min(limit, 200)).all())
    return [_case_json(c) for c in rows]


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    b = db.get(Batch, batch_id)
    if b is None:
        raise HTTPException(404, "Batch not found.")
    cases = sorted((_case_json(c) for c in b.cases),
                   key=lambda c: (c["match_pct"] is None,
                                  -(c["match_pct"] or 0)))
    return {"batch_id": b.id, "jd_text": b.jd_text,
            "created_at": b.created_at.isoformat(), "cases": cases}


@app.get("/bias-report")
def bias_report(db: Session = Depends(get_db)):
    run = (db.query(BiasAuditRun).order_by(BiasAuditRun.run_at.desc())
           .first())
    if run is None:
        return {"available": False,
                "message": "No audit run yet. Run: python -m models.bias_audit"}
    return {"available": True, "run_at": run.run_at.isoformat(),
            "summary": run.summary, "notes": run.notes}


@app.get("/compare")
def compare(case_ids: str = Query(..., description="comma-separated, 2-4 ids"),
            db: Session = Depends(get_db)):
    ids = [i.strip() for i in case_ids.split(",") if i.strip()]
    if not 2 <= len(ids) <= 4:
        raise HTTPException(400, "Provide 2 to 4 case ids.")
    cases = []
    for cid in ids:
        c = db.get(Case, cid)
        if c is None:
            raise HTTPException(404, f"Case {cid} not found.")
        cases.append(_case_json(c))
    # Diff: skills a candidate matched that no other selected candidate did.
    for c in cases:
        others = set().union(*(set(o["matched_skills"]) for o in cases
                               if o is not c)) if len(cases) > 1 else set()
        c["unique_skills"] = sorted(set(c["matched_skills"]) - others)
    return {"cases": cases}


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _pipeline is not None,
            "match_method": MATCH_METHOD}
