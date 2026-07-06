"""Database engine and session factory."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal: Optional[sessionmaker] = None


def _database_url() -> str:
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    db_path = settings.PLATFORM_DB_PATH
    return f"sqlite:///{db_path}"


def is_db_enabled() -> bool:
    return True


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        url = _database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        logger.info("Platform database engine initialized: %s", url.split("@")[-1])
    return _engine


def get_session_factory() -> sessionmaker:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from app.db.base import Base
    from app.db import models  # noqa: F401

    eng = get_engine()
    Base.metadata.create_all(bind=eng)
    _ensure_schema_columns(eng)
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Platform database schema ready")


def _ensure_schema_columns(engine) -> None:
    """Add columns introduced after initial release (SQLite-safe)."""
    additions = {
        "fabrics": [("owner_id", "VARCHAR(64)")],
        "ontology_projects": [("owner_id", "VARCHAR(64)")],
    }
    with engine.connect() as conn:
        for table, columns in additions.items():
            existing = {
                row[1]
                for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            } if engine.dialect.name == "sqlite" else set()
            for col_name, col_type in columns:
                if engine.dialect.name == "sqlite":
                    if col_name in existing:
                        continue
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                else:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                        )
                    )
        conn.commit()
