"""SQLAlchemy models — the audit trail.

Same schema as the project brief, mapped to SQLite: UUIDs become hex TEXT,
JSONB becomes SQLAlchemy's cross-dialect JSON. SQLite was a deliberate
choice: single-writer demo workload, zero setup, the entire audit trail is
one file (clearance.db) you can inspect with any SQLite browser. Swapping
to Postgres later is a one-line connection-string change because nothing
here is SQLite-specific.

Hard rule enforced across the codebase: the raw uploaded file and
unredacted text are NEVER written to this database. Only redacted text and
structured metadata are persisted.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return uuid.uuid4().hex


def _now():
    return datetime.now(timezone.utc)


class Batch(Base):
    __tablename__ = "batches"
    id = Column(String, primary_key=True, default=_uuid)
    jd_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_now)
    cases = relationship("Case", back_populates="batch")


class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True, default=_uuid)
    batch_id = Column(String, ForeignKey("batches.id"), nullable=True,
                      index=True)
    filename = Column(String, nullable=False)
    category = Column(String, nullable=True)
    match_pct = Column(Numeric(5, 2), nullable=True)
    status = Column(String, nullable=False)  # scored | rejected_unsafe | error
    reject_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now, index=True)

    batch = relationship("Batch", back_populates="cases")
    redacted = relationship("RedactedResume", uselist=False,
                            cascade="all, delete-orphan")
    skills = relationship("SkillMatch", uselist=False,
                          cascade="all, delete-orphan")
    explanation = relationship("Explanation", uselist=False,
                               cascade="all, delete-orphan")


class RedactedResume(Base):
    __tablename__ = "redacted_resumes"
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"),
                     primary_key=True)
    redacted_text = Column(Text, nullable=False)
    fields_redacted = Column(JSON, nullable=False)


class SkillMatch(Base):
    __tablename__ = "skill_matches"
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"),
                     primary_key=True)
    matched_skills = Column(JSON, nullable=False)
    missing_skills = Column(JSON, nullable=False)


class Explanation(Base):
    __tablename__ = "explanations"
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"),
                     primary_key=True)
    top_terms = Column(JSON, nullable=False)


class BiasAuditRun(Base):
    __tablename__ = "bias_audit_runs"
    id = Column(String, primary_key=True, default=_uuid)
    run_at = Column(DateTime, default=_now)
    summary = Column(JSON, nullable=False)
    notes = Column(Text, nullable=True)
