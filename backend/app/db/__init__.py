"""Platform database layer (PostgreSQL or SQLite)."""

from app.db.session import get_db, get_engine, init_db, is_db_enabled

__all__ = ["get_engine", "get_db", "init_db", "is_db_enabled"]
