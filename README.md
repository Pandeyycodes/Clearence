# Clearance

**Resume screening with a real audit trail — and honest numbers.**

Every resume that enters Clearance is security-scanned, PII-redacted, classified into a job category, scored against a job description, and logged as a retrievable case record. Nothing gets scored before it is scanned and redacted, and that ordering is enforced in the backend, not just implied by the UI.

The project began as an audit of a widely-copied resume-screening notebook that reports ~99% accuracy. That number is an artifact of **data leakage** — the dataset contains each resume 4–12 times, so a random train/test split grades the model on resumes it memorized. Clearance reproduces the bug, fixes it, ships a regression test that makes it impossible to reintroduce, and reports the real numbers. See [The honest numbers](#the-honest-numbers).

---

## Table of contents

- [Architecture](#architecture)
- [Features](#features)
- [The honest numbers](#the-honest-numbers)
- [Quickstart](#quickstart)
  - [1. Backend](#1-backend)
  - [2. Frontend](#2-frontend)
  - [3. Test it with a resume](#3-test-it-with-a-resume)
- [Retraining the model](#retraining-the-model)
- [Running the bias audit](#running-the-bias-audit)
- [Running the test suite](#running-the-test-suite)
- [API reference](#api-reference)
- [Database](#database)
- [Project structure](#project-structure)
- [Methodology](#methodology)
- [Privacy guarantee](#privacy-guarantee)
- [Design system](#design-system)
- [Optional upgrades](#optional-upgrades)
- [Deployment](#deployment)
- [Limitations](#limitations)

---

## Architecture

```
                        ┌──────────────────────── backend (FastAPI) ───────────────────────┐
 resume file ──────────►│ 1. security/file_scan.py   macro & PDF-JavaScript pre-check      │
 (pdf/docx/txt)         │        │  unsafe → case row: status='rejected_unsafe' (no parse) │
 + JD text              │ 2. text extraction         in memory only, never persisted       │
                        │ 3. preprocessing/pii.py    redact emails/phones/urls/addresses   │
                        │        │  raw text discarded here — only redacted text survives  │
                        │ 4. models/…                TF-IDF + LinearSVC category           │
                        │        │                   + models/explain.py top terms         │
                        │ 5. matching/embeddings.py  JD match score (term coverage)        │
                        │    matching/skill_gap.py   matched / missing skills              │
                        │ 6. db/…  (SQLite)          case + redacted text + skills +       │
                        │                            explanation written as one record     │
                        └──────────────────────────────┬────────────────────────────────--┘
                                                       │ JSON
                        ┌──────────────────────────────▼──────────────────────────────────┐
                        │ frontend (Next.js App Router, TypeScript, custom design system)  │
                        │ intake → processing checklist → case card (redaction sweep +     │
                        │ stamp) · batch table/grid + CSV export · compare view ·          │
                        │ case history · permanent bias-audit disclosure                   │
                        └───────────────────────────────────────────────────────────────--┘
```

## Features

**Pipeline**
- Leakage-free training: dedup before split, split before fit, vectorizer fitted on train only, enforced by a failing test if violated
- 5-fold stratified cross-validation comparing LinearSVC / LogisticRegression / RandomForest (all `class_weight='balanced'`), winner chosen on `f1_macro`
- Held-out classification report + confusion matrix saved to `backend/artifacts/`
- Per-prediction explainability: exact TF-IDF × coefficient contributions (no post-hoc approximation — the model is linear, so the explanation is the model)
- Name-swap bias audit (12 masculine/feminine name pairs × resume sample), results stored verbatim in the database and surfaced permanently in the UI

**Screening service**
- Security pre-check before any parsing: VBA macros in DOCX (zip inspection, `olevba` if installed); for PDFs, structural parsing that rejects only actions that execute something (`/JavaScript`, `/Launch` — on open, on pages, or in annotations). A bare `/OpenAction` that just navigates to page 1 is allowed: LaTeX, Canva, and many resume exporters add one, and rejecting it would false-positive on legitimate resumes
- PII redaction (emails, phones, URLs/profiles, street addresses; person names when spaCy is installed) — the raw file and unredacted text are never written to disk, database, or logs
- JD match score kept deliberately separate from the category classifier (see [Methodology](#methodology))
- Skill-gap analysis: which JD skills the resume covers and which it lacks
- Full audit trail: every screening — including rejected and errored files — is a retrievable case row

**Frontend**
- Case File / Evidence Intake design system (paper palette, IBM Plex Mono data, hairline rules, near-zero radii)
- Intake dropzone → live processing checklist → case card with a one-time redaction-sweep + rotated-stamp animation (respects `prefers-reduced-motion`)
- Batch view: sortable table ⇄ grid toggle, CSV export, checkbox selection → side-by-side compare view with skill-diff highlighting
- Case history backed by the database
- Bias-audit disclosure permanently visible on batch views — not a dismissible modal

## The honest numbers

| Setup | Accuracy | f1_macro | Verdict |
|---|---|---|---|
| Repo dataset, duplicates left in (the original notebook) | **99.5%** | — | **Fake.** 962 rows, only 166 unique resumes; the test set is memorized training data. |
| Repo dataset, deduplicated first | 88.2% | 0.821 | Honest but fragile — the test set is 34 documents. |
| **Kaggle 2,484-resume dataset, 24 classes (this model)** | **68.4%** | **0.638** | Honest. CV winner LinearSVC; per-class report and confusion matrix in `backend/artifacts/`. |

68% is the real state of TF-IDF + linear models on 24-way resume classification; published results on the same dataset agree, and transformer fine-tunes reach roughly the low-to-mid 80s. Part of the ceiling is the labels: a consultant's resume genuinely reads like business development (CONSULTANT recall: 0.17). Full analysis, including what would raise the number honestly and what wouldn't, is in [`RESULTS.md`](RESULTS.md).

## Quickstart

Prerequisites: **Python 3.10+**, **Node 18+**. Tested on Linux/macOS; Windows works with the usual `venv\Scripts\activate` substitutions.

Clone, then:

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn api.main:app --reload --port 8000
```

That's it — the trained model ships in `backend/artifacts/model_archive.joblib` and the SQLite database (`backend/clearance.db`) is created automatically on first startup. No database server, no migrations, no environment variables.

Sanity check: open **http://localhost:8000/docs** (interactive Swagger UI for every route) or:

```bash
curl http://localhost:8000/health
# {"status":"ok","model_loaded":true,"match_method":"jd-term-coverage (tfidf)"}
```

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**. The frontend talks to `http://localhost:8000` by default; point it elsewhere with `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

### 3. Test it with a resume

**In the UI:** drop any `.pdf`, `.docx`, or `.txt` resume on the intake screen, paste a job description, press **Screen resume**. You'll see the processing checklist, then the case card: category, JD match stamp, matched/missing skill chips, the model's top terms, and the redacted text that was stored. Drop **multiple** files to get a ranked batch instead — sort it, export CSV, tick 2–4 checkboxes and press **Compare selected**.

**From the command line:**

```bash
# single resume
curl -X POST http://localhost:8000/screen \
  -F "file=@/path/to/resume.pdf" \
  -F "jd_text=Senior accountant. Requirements: accounting, general ledger, financial reporting, auditing, Excel."

# ranked batch
curl -X POST http://localhost:8000/batch \
  -F "files=@resume1.pdf" -F "files=@resume2.pdf" \
  -F "jd_text=..."
```

**Test the security scan** (this file is rejected before parsing and logged as `rejected_unsafe`):

```bash
printf '%%PDF-1.4 /OpenAction /JavaScript (app.alert(1))' > evil.pdf
curl -X POST http://localhost:8000/screen -F "file=@evil.pdf" -F "jd_text=x"
```

Everything you screen appears under **Case history** in the UI, backed by `GET /cases`.

## Retraining the model

The datasets are not committed (56 MB+). To retrain from scratch:

1. Download the [Kaggle resume dataset](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset) (`archive.zip`) → place `Resume.csv` at `data/Resume/Resume.csv`.
2. Optionally, [UpdatedResumeDataSet.csv](https://www.kaggle.com/datasets/gauravduttakiit/resume-dataset) → `data/Resume-Screening-main/DataSet/UpdatedResumeDataSet.csv` (used only to reproduce the leakage comparison).
3. From `backend/`:

```bash
python models/train.py
```

This deduplicates, splits, runs the 3-model 5-fold CV comparison, evaluates the winner once on the held-out set, and writes to `backend/artifacts/`: the model, `cv_comparison_*.csv`, `classification_report_*.txt`, `confusion_matrix_*.png`, and `summary_*.json`. Takes a few minutes on a laptop (RandomForest CV dominates the time).

## Running the bias audit

Requires the dataset from the previous section. From `backend/`:

```bash
python -m models.bias_audit
```

Swaps 12 masculine/feminine-coded name pairs into a 100-resume sample (1,200 comparisons), counts how often the predicted category changes because of the name alone, and writes the full result — distributions, flip examples, and an honest scope note — to the `bias_audit_runs` table. The UI's batch view reads the latest run via `GET /bias-report` and displays it permanently. Last recorded run: **0 flips in 1,200 comparisons (0.00%)**, with the explicit caveat that this measures first-name sensitivity only and does not certify the system as unbiased.

## Running the test suite

```bash
cd backend
pytest tests/ -v
```

`tests/test_no_leakage.py` contains the anti-leakage guarantee:
- `test_no_duplicates_cross_split` — fails if any resume text appears in both train and test.
- `test_vectorizer_never_fits_test_text` — a booby-trapped `TfidfVectorizer` that raises the moment any held-out document reaches a `.fit()` call, then asserts that the trap actually fires.

(The tests skip automatically if the dataset hasn't been downloaded.)

## API reference

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/screen` | One file + JD → scan → redact → classify → match → persist → full case JSON |
| `POST` | `/batch` | Multiple files + one JD → one batch row, one case per file → ranked list |
| `GET` | `/cases/{id}` | Retrieve a past case (history / "case file" view) |
| `GET` | `/cases?limit=N` | Most recent cases, newest first |
| `GET` | `/batches/{id}` | A past batch with all of its cases, ranked |
| `GET` | `/compare?case_ids=a,b[,c,d]` | 2–4 cases aligned for side-by-side view, plus per-candidate `unique_skills` diff |
| `GET` | `/bias-report` | Latest bias audit run for the permanent UI disclosure |
| `GET` | `/health` | Model-loaded check + active match method |

Every scored case returns: `id`, `category`, `match_pct`, `status`, `fields_redacted`, `redacted_preview`, `matched_skills`, `missing_skills`, `top_terms` (term + weight), and `match_method` (the API tells you which matcher is active rather than letting the UI imply a fancier one).

## Database

**SQLite by design.** This is a single-writer demo workload; SQLite gives a zero-setup, fully inspectable audit trail in one file (`backend/clearance.db` — open it with any SQLite browser). The models are written in dialect-agnostic SQLAlchemy, so moving to Postgres is a connection-string change:

```bash
export CLEARANCE_DB_URL=postgresql://user:pass@host/clearance
```

Schema (five tables, one audit trail):

| Table | One row per | Key columns |
|---|---|---|
| `batches` | batch run against one JD | `jd_text` |
| `cases` | screening attempt (including rejects/errors) | `filename`, `category`, `match_pct`, `status`, `reject_reason`, `batch_id` |
| `redacted_resumes` | scored case | `redacted_text`, `fields_redacted` — the only resume text that exists anywhere |
| `skill_matches` | scored case | `matched_skills`, `missing_skills` |
| `explanations` | scored case | `top_terms` |
| `bias_audit_runs` | audit run (model-level, independent of cases) | `summary`, `notes` |

## Project structure

```
clearance/
├── backend/
│   ├── api/main.py                  # FastAPI app, CORS, all routes, the enforced intake order
│   ├── db/
│   │   ├── models.py                # SQLAlchemy schema (audit trail)
│   │   └── session.py               # engine/session; CLEARANCE_DB_URL override
│   ├── preprocessing/
│   │   ├── cleaning.py              # minimal text normalisation
│   │   └── pii.py                   # redaction; returns redacted text + what was masked
│   ├── security/file_scan.py        # macro/JS pre-check; rejects before parsing
│   ├── models/
│   │   ├── train.py                 # dedup → split → 5-fold CV × 3 models → held-out report
│   │   ├── explain.py               # exact linear-model term contributions
│   │   └── bias_audit.py            # name-swap audit → bias_audit_runs
│   ├── matching/
│   │   ├── embeddings.py            # JD match score (term coverage / sentence-transformers)
│   │   └── skill_gap.py             # matched/missing skills vs the JD
│   ├── tests/test_no_leakage.py     # the anti-leakage guarantee
│   ├── artifacts/                   # trained model, CV tables, reports, confusion matrices
│   └── requirements.txt
├── frontend/
│   ├── app/                         # Next.js App Router pages (intake, case, batch, compare, history)
│   ├── components/case.tsx          # case card, chips, stamp, terms, bias disclosure
│   ├── lib/api.ts                   # typed fetch wrapper for every backend route
│   └── app/globals.css              # the Case File design system (tokens + signature animation)
├── RESULTS.md                       # full experiment write-up
└── README.md
```

## Methodology

**Why dedup-then-split is non-negotiable.** With duplicates, the test set contains documents the model saw during training; the reported score measures memorization, not generalization. Reproduced in `RESULTS.md`: 99.5% → 88.2% on the same data once duplicates are removed.

**Why the vectorizer lives inside the Pipeline.** `cross_val_score` on a `Pipeline` refits TF-IDF per fold, so validation folds never leak vocabulary or document frequencies into training. Fitting the vectorizer on all data before CV is the second-most-common leak in text classification, and it's structurally impossible here.

**Why LinearSVC won.** On ~2k documents in a 100k-dimensional sparse space, a max-margin linear separator generalizes better than RandomForest's axis-aligned splits, and edged out logistic regression on the many small, vocabulary-distinctive classes. CV table in `backend/artifacts/cv_comparison_archive.csv`.

**Why the category and the JD match are two numbers, not one.** The classifier answers *"what kind of resume is this?"* using supervised labels; the match score answers *"how well does this resume cover this specific JD?"* and needs no labels. Blending them would produce a single unexplainable number and let a strong category prediction mask a poor JD fit (or vice versa). The UI shows both, separately, always.

**How the match score works (and what it claims).** Default: **JD term coverage** — the idf-weighted share of the JD's content terms (1–2 grams) present in the resume, calibrated on real matched/mismatched pairs (on-target pairs score ~45–60 raw vs ~10–15 off-target, rescaled to a readable 0–100). If `sentence-transformers` is installed, cosine similarity of MiniLM embeddings is used instead. The API reports which method produced every score.

## Privacy guarantee

The raw uploaded file and the unredacted extracted text exist **only inside the request handler, in memory**. They are:
- never written to the database (only `redacted_resumes.redacted_text` is stored),
- never written to disk,
- never logged,
- explicitly deleted (`del`) as soon as redaction completes.

This is enforced in `api/main.py::_screen_one`, not promised by a UI label. Files that fail the security scan are never even parsed — they get a case row with `status='rejected_unsafe'` and nothing else.

## Design system

Case File / Evidence Intake. Paper tones (`#EDE6D6` canvas, `#F7F3E9` cards), ink chrome (`#1B2430`), amber stamp (`#C9922E`) for match signal, flag red (`#A3402C`) for rejects and missing skills, hairline rules, 0–2px radii. IBM Plex Mono for anything that is data (scores, timestamps, filenames); Public Sans for prose. One signature moment — the 400ms redaction sweep followed by the rotated match-percentage stamp — used exactly once, on a fresh single-case result; batch and compare views stay quiet. Visible 2px focus rings, single-column collapse on mobile, and every animation is disabled under `prefers-reduced-motion`.

## Optional upgrades

All optional — the app runs fully offline without them:

| Install | What improves |
|---|---|
| `pip install spacy && python -m spacy download en_core_web_sm` | Person-name redaction via NER (regex tiers stay active regardless) |
| `pip install sentence-transformers` | JD match switches to MiniLM embedding similarity; `match_method` in responses updates automatically |
| `pip install oletools` | Deeper VBA macro analysis on DOCX in addition to the zip check |

## Deployment

- **Backend** needs a real Python runtime (the model is loaded in memory): Render, Railway, or Fly.io. Set `CLEARANCE_DB_URL` if you want managed Postgres; otherwise mount a volume for `clearance.db`.
- **Frontend** on Vercel; set `NEXT_PUBLIC_API_URL` to the deployed backend.
- Add your deployed frontend origin to `allow_origins` in `backend/api/main.py`.

## Limitations

Stated because a screening tool that hides its limits is worse than no tool: 24-way single-label classification punishes genuinely multi-label resumes; the model is English-only; regex redaction misses names unless spaCy is installed, and no redactor catches every identifier; the skill list is curated, not learned, so unlisted skills are invisible to the gap analysis; the bias audit covers first-name sensitivity only; exact-duplicate removal doesn't catch near-duplicates (MinHash is the next step); and the honest held-out accuracy is 68.4% — a ranked shortlist with visible explanations, not an automated decision-maker. **No score from this system should be the reason a human doesn't read a resume.**
