"""
Database connection management for SQLite.
Enforces foreign keys, WAL mode for concurrency, and dict-like row access.
"""
import os
import sqlite3
from pathlib import Path

# Default path relative to project root
DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "pos.db"

_CURRENT_DB_PATH = str(DEFAULT_DB_PATH)


def set_db_path(custom_path: str) -> None:
    """Override DB path (useful for testing or backup restoration)."""
    global _CURRENT_DB_PATH
    _CURRENT_DB_PATH = str(custom_path)


def get_db_path() -> str:
    """Return the active database file path."""
    return _CURRENT_DB_PATH


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """
    Get a new SQLite connection with foreign keys enabled and row_factory configured.
    """
    target_path = db_path or get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    conn = sqlite3.connect(target_path, check_same_thread=False, timeout=30.0, isolation_level="IMMEDIATE")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn
