"""
Database Backup & Disaster Recovery Service.
Uses SQLite Online Backup API for 100% thread-safe hot snapshots without locking the database.
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from db.connection import get_connection, get_db_path


def get_backup_dir() -> Path:
    """Return Path to backup directory and ensure it exists."""
    db_file = Path(get_db_path())
    backup_dir = db_file.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_backup(notes: str = "manual", db_path: Optional[str] = None) -> str:
    """
    Perform a hot online backup using SQLite's backup API.
    Returns the absolute path to the newly created backup file.
    """
    source_path = db_path or get_db_path()
    backup_dir = get_backup_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_notes = "".join(c for c in notes if c.isalnum() or c in ("_", "-"))
    filename = f"pos_backup_{timestamp}_{clean_notes}.db"
    dest_path = backup_dir / filename

    src_conn = sqlite3.connect(source_path)
    dst_conn = sqlite3.connect(str(dest_path))
    try:
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        return str(dest_path)
    finally:
        dst_conn.close()
        src_conn.close()


def auto_daily_backup(db_path: Optional[str] = None) -> Optional[str]:
    """
    Check if a backup for today already exists; if not, create one.
    Returns path if a backup was created, else None.
    """
    backup_dir = get_backup_dir()
    today_str = datetime.now().strftime("%Y%m%d")

    # Check existing files
    for fname in os.listdir(backup_dir):
        if today_str in fname and fname.endswith(".db"):
            return None  # Already backed up today

    return create_backup(notes="auto_daily", db_path=db_path)


def list_backups() -> List[Dict[str, Any]]:
    """List available backups ordered from newest to oldest."""
    backup_dir = get_backup_dir()
    backups = []

    for fname in os.listdir(backup_dir):
        if fname.endswith(".db"):
            fpath = backup_dir / fname
            stat = fpath.stat()
            backups.append({
                "filename": fname,
                "filepath": str(fpath),
                "size_kb": round(stat.st_size / 1024, 1),
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

    backups.sort(key=lambda x: x["created_at"], reverse=True)
    return backups


def validate_backup_file(backup_path: str) -> bool:
    """Validate that target file is a healthy SQLite database containing POS tables."""
    if not os.path.exists(backup_path):
        return False
    conn = None
    try:
        conn = sqlite3.connect(backup_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        required_tables = {"shop_settings", "products", "bills", "users"}
        return required_tables.issubset(tables)
    except Exception:
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def restore_backup(backup_path: str, db_path: Optional[str] = None) -> bool:
    """
    Restore database from a validated backup file using SQLite online backup API.
    """
    if not validate_backup_file(backup_path):
        raise ValueError("Invalid backup file. Required POS tables are missing or corrupted.")

    target_path = db_path or get_db_path()

    # Create safety snapshot of current DB before restoring
    try:
        create_backup(notes="pre_restore_safety", db_path=target_path)
    except Exception:
        pass

    src_conn = sqlite3.connect(backup_path)
    dst_conn = sqlite3.connect(target_path)
    try:
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        return True
    finally:
        dst_conn.close()
        src_conn.close()
