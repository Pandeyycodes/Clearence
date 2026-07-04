"""Skill-gap analysis: which skills the JD asks for, split into matched
(present in the resume) and missing.

Uses spaCy PhraseMatcher when available; otherwise a word-boundary regex
match over the same curated skill list. The list covers common technical,
data, business, and operations skills; extend SKILLS freely — everything
downstream (DB, API, UI, CSV export) adapts automatically.
"""
from __future__ import annotations

import re

SKILLS = [
    # programming / data
    "python", "java", "javascript", "typescript", "c++", "c#", "sql", "r",
    "scala", "go", "html", "css", "react", "angular", "vue", "next.js",
    "node.js", "django", "flask", "fastapi", "spring",
    "machine learning", "deep learning", "nlp", "computer vision",
    "data analysis", "data visualization", "statistics", "pandas", "numpy",
    "scikit-learn", "tensorflow", "pytorch", "keras", "spark", "hadoop",
    "tableau", "power bi", "excel", "etl", "data engineering", "airflow",
    # infra
    "aws", "azure", "gcp", "docker", "kubernetes", "linux", "git", "ci/cd",
    "terraform", "jenkins", "rest api", "graphql", "microservices",
    "postgresql", "mysql", "sqlite", "mongodb", "redis", "elasticsearch",
    # business / ops
    "project management", "agile", "scrum", "jira", "stakeholder management",
    "budgeting", "forecasting", "financial analysis", "accounting",
    "bookkeeping", "auditing", "payroll", "quickbooks", "sap", "erp",
    "salesforce", "crm", "sales", "negotiation", "lead generation",
    "marketing", "seo", "content marketing", "social media",
    "public relations", "copywriting", "recruiting", "onboarding",
    "training", "performance management", "customer service",
    "supply chain", "logistics", "procurement", "inventory management",
    "quality assurance", "compliance", "risk management",
    "communication", "leadership", "teamwork", "problem solving",
]

try:  # optional
    import spacy
    from spacy.matcher import PhraseMatcher
    try:
        _NLP = spacy.blank("en")
        _MATCHER = PhraseMatcher(_NLP.vocab, attr="LOWER")
        _MATCHER.add("SKILL", [_NLP.make_doc(s) for s in SKILLS])
    except Exception:
        _NLP = _MATCHER = None
except ImportError:
    _NLP = _MATCHER = None

_PATTERNS = {s: re.compile(rf"(?<![\w+#]){re.escape(s)}(?![\w+#])", re.I)
             for s in SKILLS}


def _skills_in(text: str) -> set[str]:
    if _MATCHER is not None:
        doc = _NLP.make_doc(text[:200_000])
        return {doc[s:e].text.lower() for _, s, e in _MATCHER(doc)}
    return {s for s, p in _PATTERNS.items() if p.search(text)}


def skill_gap(resume_text: str, jd_text: str) -> tuple[list[str], list[str]]:
    """Return (matched, missing): JD skills found / not found in resume."""
    jd_skills = _skills_in(jd_text)
    resume_skills = _skills_in(resume_text)
    matched = sorted(jd_skills & resume_skills)
    missing = sorted(jd_skills - resume_skills)
    return matched, missing
