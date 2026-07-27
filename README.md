<div align="center">

# Clearance

### Resume screening with a real audit trail — and honest numbers.

Every resume is **security-scanned**, **PII-redacted**, **classified**, **scored against a job description**, and **logged as an immutable case record** — behind **JWT authentication**, with a built-in **bias audit**. Nothing is scored before it is scanned and redacted, and that ordering is enforced in the backend, not implied by the UI.

**Decision support, not automation.** No score from this system should be the reason a human does not read a resume.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikit-learn&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js%2014-000000?style=flat-square&logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![JWT](https://img.shields.io/badge/Auth-JWT-FB015B?style=flat-square&logo=jsonwebtokens&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
<br/>
![Tests](https://img.shields.io/badge/tests-24%20passing-brightgreen?style=flat-square)
![Held-out accuracy](https://img.shields.io/badge/held--out%20accuracy-68.4%25-informational?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)

</div>

---

## Table of contents

- [Why this project exists](#why-this-project-exists)
- [System architecture](#system-architecture)
- [The screening pipeline](#the-screening-pipeline)
- [Data model](#data-model)
- [Authentication and abuse control](#authentication-and-abuse-control)
- [The honest numbers](#the-honest-numbers)
- [The data-leakage story](#the-data-leakage-story)
- [Screenshots](#screenshots)
- [Quickstart](#quickstart)
- [Trying it with the bundled demo](#trying-it-with-the-bundled-demo)
- [API reference](#api-reference)
- [Testing and CI](#testing-and-ci)
- [Privacy and security model](#privacy-and-security-model)
- [Project structure](#project-structure)
- [Technology choices](#technology-choices)
- [Limitations](#limitations)

---

## Why this project exists

The most-copied resume-classification notebook online reports about **99% accuracy**. That number is an artifact of **data leakage**: the dataset contains each resume many times over, so a random train/test split grades the model on documents it has already memorized.

Clearance is the version that tells the truth. It removes the leakage, proves the honest accuracy, ships a regression test that makes the bug impossible to reintroduce, and wraps the model in the things a real screening tool needs but demos usually skip: a security gate, PII redaction, an explainable score, an audit trail, authentication, and a fairness check.

---

## System architecture

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart TB
    subgraph Client["Frontend — Next.js 14 / TypeScript"]
        L["Login"]
        I["Intake / dropzone"]
        B["Batch table and grid + CSV export"]
        C["Compare view"]
        H["Case history"]
    end

    subgraph API["Backend — FastAPI"]
        AUTH["JWT auth + rate limiting"]
        ORCH["Enforced intake orchestrator"]
    end

    subgraph SVC["Processing layers"]
        SEC["Security scan"]
        PII["PII redaction"]
        ML["TF-IDF + LinearSVC + explainability"]
        MATCH["JD match + skill gap"]
    end

    DB[("SQLite audit trail<br/>via SQLAlchemy")]

    L -->|"token"| AUTH
    I --> AUTH
    B --> AUTH
    C --> AUTH
    H --> AUTH
    AUTH --> ORCH
    ORCH --> SEC --> PII --> ML --> MATCH --> DB
    DB -->|"JSON"| Client
```

Each layer is independent: the security, privacy, model, and matching modules can be swapped without touching the others. Optional dependencies (spaCy, sentence-transformers, oletools) upgrade behaviour automatically when present and are never required.

---

## The screening pipeline

The order is guaranteed in `api/main.py::_screen_one`, not in the UI. A file is never parsed until it has passed the security scan, and raw text never survives past redaction.

```mermaid
%%{init: {'theme':'neutral'}}%%
sequenceDiagram
    actor R as Recruiter
    participant F as Frontend
    participant A as FastAPI
    participant S as Security scan
    participant P as PII redaction
    participant M as Model + matcher
    participant DB as SQLite

    R->>F: Upload resume + JD
    F->>A: POST /screen  (Bearer token)
    A->>A: Verify JWT, enforce rate limit, cap upload size
    A->>S: Scan bytes (macros, PDF JavaScript/Launch)
    alt Unsafe
        S-->>DB: case status = rejected_unsafe (never parsed)
    else Safe
        A->>A: Extract text (in memory only)
        A->>P: Redact email / phone / URL / address / name
        Note over P: raw text dropped here — only redacted text continues
        A->>M: Classify + explain, score vs JD, skill gap
        M-->>DB: case + redacted text + skills + explanation + screened_by
    end
    DB-->>F: Case JSON
    F-->>R: Category, match %, skills, explanation, redacted preview
```

---

## Data model

One screening writes a linked set of rows across five tables. Rejects and errors still produce a `cases` row — that is what makes it an audit trail rather than a results list.

```mermaid
%%{init: {'theme':'neutral'}}%%
erDiagram
    USERS {
        string id PK
        string email
        string hashed_password
    }
    BATCHES {
        string id PK
        text jd_text
        datetime created_at
    }
    CASES {
        string id PK
        string batch_id FK
        string filename
        string category
        numeric match_pct
        string status
        text reject_reason
        string screened_by
        datetime created_at
    }
    REDACTED_RESUMES {
        string case_id PK
        text redacted_text
        json fields_redacted
    }
    SKILL_MATCHES {
        string case_id PK
        json matched_skills
        json missing_skills
    }
    EXPLANATIONS {
        string case_id PK
        json top_terms
    }
    BIAS_AUDIT_RUNS {
        string id PK
        json summary
        text notes
    }

    BATCHES ||--o{ CASES : contains
    CASES ||--|| REDACTED_RESUMES : has
    CASES ||--|| SKILL_MATCHES : has
    CASES ||--|| EXPLANATIONS : has
```

The only resume text stored anywhere is `redacted_resumes.redacted_text`. The raw file and unredacted text live only inside the request handler, in memory.

---

## Authentication and abuse control

Recruiters authenticate with email and password and receive a signed JWT. Every later request is verified by signature — stateless, no database hit per call. Each case records `screened_by`, so the audit trail captures **who** ran a screening, not just what happened.

```mermaid
%%{init: {'theme':'neutral'}}%%
sequenceDiagram
    actor U as Recruiter
    participant F as Frontend
    participant A as FastAPI
    participant DB as users table

    U->>F: email + password
    F->>A: POST /token
    A->>DB: look up user
    A->>A: bcrypt.verify(password, hash)
    A-->>F: signed JWT (HS256)
    F->>F: store token
    U->>F: open a protected page
    F->>A: GET /cases  (Authorization: Bearer ...)
    A->>A: verify signature -> allow or 401
    A-->>F: data
```

| Control | Value | Purpose |
|---|---|---|
| Passwords | bcrypt hash only | A database leak never exposes credentials |
| Token | JWT / HS256, signed with `CLEARANCE_SECRET_KEY` | Stateless auth, cannot be forged without the key |
| Rate limit — `/token` | 20 / minute per IP | Throttles credential guessing |
| Rate limit — `/screen` | 30 / minute per IP | Prevents endpoint abuse |
| Rate limit — `/batch` | 10 / minute per IP | Prevents mass upload abuse |
| Upload cap | 10 MB per file, read in chunks | Prevents memory-exhaustion uploads |

Secrets are read from the environment; the built-in key is for local development only. `/health` is intentionally public.

---

## The honest numbers

| Setup | Accuracy | f1_macro | Verdict |
|---|---|---|---|
| Repo dataset, duplicates left in (the original notebook) | **99.5%** | — | **Fake.** The test set is memorized training data. |
| Repo dataset, deduplicated first | 88.2% | 0.821 | Honest but fragile — a 34-document test set. |
| **Kaggle 2,484-resume dataset, 24 classes (this model)** | **68.4%** | **0.638** | Honest. CV winner LinearSVC. |

68% is the real state of TF-IDF plus linear models on 24-way resume classification; published results agree, and transformer fine-tunes reach the low-to-mid 80s. Because Clearance produces a **ranked shortlist**, `models/train.py` also reports **top-3 accuracy** — whether the true category is among the model's top three guesses — which is the metric that matches how the tool is actually used.

---

## The data-leakage story

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart LR
    subgraph Wrong["Original notebook — leakage"]
        D1["Dataset with duplicate resumes"] --> SP1["Random split"]
        SP1 --> TR1["Train"]
        SP1 --> TE1["Test"]
        TR1 -. same resume .-> TE1
        TE1 --> R1["~99% — memorization"]
    end

    subgraph Right["Clearance — leakage-free"]
        D2["Dataset"] --> DD["Deduplicate FIRST"]
        DD --> SP2["Stratified split"]
        SP2 --> TR2["Train"]
        SP2 --> TE2["Test (untouched)"]
        TR2 --> FIT["TF-IDF fitted inside a Pipeline<br/>(refit per CV fold)"]
        FIT --> R2["68.4% — honest generalization"]
    end
```

Two defenses, both enforced: deduplicate before splitting, and keep the vectorizer inside the `Pipeline` so cross-validation refits it per fold and validation text never leaks vocabulary. A regression test (`tests/test_no_leakage.py`) uses a booby-trapped vectorizer that raises the instant any held-out document reaches a `.fit()` call, so the bug cannot silently return.

---

## Screenshots

> Captured from the bundled demo (four resumes screened against the Senior Accountant JD).

<div align="center">

### Sign in — the API is access-controlled
<img src="docs/screenshots/01-login.png" alt="Login screen" width="820">

### Evidence intake
<img src="docs/screenshots/02-intake.png" alt="Intake dropzone and job description" width="820">

### Case card — category, match stamp, matched and missing skills, explanation, redacted text
<img src="docs/screenshots/03-case-card.png" alt="Single case result card" width="820">

### Ranked batch — table view, one-click CSV export, and the permanent bias-audit disclosure
<img src="docs/screenshots/04-batch-table.png" alt="Batch table view" width="820">

### Ranked batch — grid view
<img src="docs/screenshots/05-batch-grid.png" alt="Batch grid view" width="820">

### Side-by-side compare with unique-skill diff
<img src="docs/screenshots/07-compare.png" alt="Compare view" width="820">

### Case history and the permanent bias-audit disclosure
<img src="docs/screenshots/08-history-bias.png" alt="Case history and bias disclosure" width="820">

</div>

---

## Quickstart

Prerequisites: Python 3.10+, Node 18+.

### Option A — Docker (whole stack, one command)

```bash
docker compose up --build
```

Backend on `http://localhost:8000` (interactive docs at `/docs`), frontend on `http://localhost:3000`. The SQLite audit trail persists in a named volume.

### Option B — run each service directly

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` and sign in with the seeded demo recruiter:

```
email:    recruiter@clearance.local
password: demo1234
```

The trained model ships in `backend/artifacts/`, and `clearance.db` plus the demo user are created automatically on first startup. No database server, no migrations.

---

## Trying it with the bundled demo

The `demo_data/` folder contains four full resumes (with fake PII to demonstrate redaction) and a Senior Accountant job description. Screening all four produces a clean ranking:

| Candidate | Predicted category | JD match |
|---|---|---|
| Priya Sharma — Senior Accountant | ACCOUNTANT | 85.3% |
| Rohit Verma — Financial Analyst | FINANCE | 54.8% |
| Ananya Iyer — Data Analyst | FINANCE | 19.4% |
| Arjun Mehta — Sales Manager | BUSINESS-DEVELOPMENT | 6.1% |

In the UI, drop all four files on the intake screen and paste `demo_data/jd.txt` to reproduce the ranked batch, then select candidates and compare them. Every case shows `email, phone, url, address` redacted.

---

## API reference

| Method | Route | Auth | Purpose |
|---|---|---|---|
| POST | `/token` | public | Exchange email + password for a JWT |
| POST | `/screen` | required | One file + JD → scan → redact → classify → match → persist → case JSON |
| POST | `/batch` | required | Many files + one JD → one batch, one case per file, ranked |
| GET | `/cases/{id}` | required | Retrieve a past case |
| GET | `/cases?limit=N` | required | Most recent cases, newest first |
| GET | `/batches/{id}` | required | A past batch with all cases, ranked |
| GET | `/compare?case_ids=a,b[,c,d]` | required | 2–4 cases aligned, with per-candidate unique-skill diff |
| GET | `/bias-report` | required | Latest bias-audit run for the permanent disclosure |
| GET | `/health` | public | Model-loaded check and active match method |

Every scored case returns: `id`, `category`, `match_pct`, `status`, `screened_by`, `fields_redacted`, `redacted_preview`, `matched_skills`, `missing_skills`, `top_terms`, and `match_method`.

---

## Testing and CI

```bash
cd backend
pytest tests/ -v
```

| Test file | Guarantee it protects |
|---|---|
| `test_no_leakage.py` | No resume crosses the train/test boundary; held-out text never reaches `.fit()` |
| `test_pii.py` | Every PII field is removed and honestly reported; clean text is never over-redacted |
| `test_file_scan.py` | Clean files pass; macros, spoofed files, and executable PDF actions are rejected |
| `test_auth.py` | Login works, protected routes reject without a token and accept with one, and `screened_by` is recorded |

The PII, security, and auth tests build every fixture in memory and need no dataset. The whole suite runs in GitHub Actions (`.github/workflows/ci.yml`) on every push, so none of these guarantees can silently regress.

---

## Privacy and security model

**What is never stored** (memory-only inside one request, then dropped): the raw uploaded file, the unredacted text, and all identifying PII.

**What is stored**: redacted resume text, the derived category, score, skills, and explanation, and a note of which recruiter ran the screening.

**Security gate** (before any parsing):

- DOCX is inspected as a ZIP for the embedded macro payload; `.docm` / `.dotm` are rejected outright.
- PDF structure is parsed and only executing actions (`/JavaScript`, `/Launch`) are rejected; a benign go-to-page `/OpenAction` is allowed, so legitimate LaTeX and Canva exports are not false-rejected.
- Unsafe files are logged as `rejected_unsafe` and never parsed.

---

## Project structure

```
clearance/
├── backend/
│   ├── api/main.py              FastAPI app, JWT + rate limiting, enforced intake order
│   ├── security/
│   │   ├── file_scan.py         macro / PDF-action pre-check
│   │   └── auth.py              bcrypt hashing + JWT issue/verify
│   ├── preprocessing/
│   │   ├── cleaning.py          text normalisation for the model
│   │   └── pii.py               redaction; returns redacted text + what was masked
│   ├── models/
│   │   ├── train.py             dedup → split → 5-fold CV × 3 models → held-out report + top-3
│   │   ├── explain.py           exact linear-model term contributions
│   │   └── bias_audit.py        name-swap audit → bias_audit_runs
│   ├── matching/
│   │   ├── embeddings.py        JD match score (term coverage / sentence-transformers)
│   │   └── skill_gap.py         matched / missing skills vs the JD
│   ├── db/                      SQLAlchemy models + session
│   ├── tests/                   leakage, PII, file-scan, and auth guarantees
│   ├── artifacts/               trained model, CV tables, reports, confusion matrices
│   └── Dockerfile
├── frontend/
│   ├── app/                     App Router pages: login, intake, case, batch, compare, history
│   ├── components/              case card, nav, auth gate
│   ├── lib/api.ts               typed fetch wrapper with token handling
│   └── Dockerfile
├── demo_data/                   four sample resumes + a job description
├── docker-compose.yml
└── .github/workflows/ci.yml
```

---

## Technology choices

| Concern | Choice | Reason |
|---|---|---|
| API framework | FastAPI | Auto-generated interactive docs, type-driven validation, async file uploads |
| Model | TF-IDF + LinearSVC | Strong on small high-dimensional text; explanation is the model itself |
| Explainability | Exact `tfidf × coefficient` | No post-hoc approximation for a linear model |
| Database | SQLite via SQLAlchemy | Zero setup, single inspectable audit file; Postgres is a connection-string change |
| Auth | JWT (HS256) + bcrypt | Stateless verification; credentials never stored in plaintext |
| Frontend | Next.js 14 + TypeScript | App Router, typed API client, custom design system |

---

## Limitations

Stated because a screening tool that hides its limits is worse than none: 24-way single-label classification punishes genuinely multi-label resumes; the model is English-only; regex redaction misses names unless spaCy is installed, and no redactor catches every identifier; the skill list is curated, not learned; the bias audit covers first-name sensitivity only; exact-duplicate removal does not catch near-duplicates; and stored records have no automatic retention policy yet. The honest held-out accuracy is 68.4% — a ranked shortlist with visible explanations, not an automated decision-maker.
