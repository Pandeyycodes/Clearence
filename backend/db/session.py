"""Engine + session. SQLite file lives next to the backend package.

Set CLEARANCE_DB_URL to point anywhere else (including postgres://...) —
the models are dialect-agnostic.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base

DB_PATH = Path(__file__).resolve().parents[1] / "clearance.db"
DB_URL = os.environ.get("CLEARANCE_DB_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(DB_URL,
                       connect_args={"check_same_thread": False}
                       if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
