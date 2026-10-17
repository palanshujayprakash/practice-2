"""
Authentication and Role-based Access Control service.
Uses standard library hashlib.pbkdf2_hmac with random salt.
"""
import os
from typing import Optional, Tuple, Dict, Any, List
from db.connection import get_connection
from utils.security import hash_password, verify_password


def authenticate_user(username: str, password: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Authenticate user credentials.
    Returns dict with user details (id, username, role) if valid, else None.
    """
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, salt, role FROM users WHERE username = ?",
            (username.strip(),)
        )
        row = cur.fetchone()
        if not row:
            return None

        if verify_password(password, row["password_hash"], row["salt"]):
            return {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"]
            }
        return None
    finally:
        conn.close()


def create_user(username: str, password: str, role: str = "cashier", db_path: Optional[str] = None) -> int:
    """Create a new user with hashed password."""
    if role not in ("owner", "cashier"):
        raise ValueError(f"Invalid role: {role}. Must be 'owner' or 'cashier'.")

    pw_hash, salt = hash_password(password)
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (username, password_hash, salt, role)
                VALUES (?, ?, ?, ?)
                """,
                (username.strip(), pw_hash, salt, role)
            )
            return cur.lastrowid
    finally:
        conn.close()


def get_all_users(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all users without sensitive hash/salt."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, created_at FROM users ORDER BY id ASC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def change_user_password(user_id: int, new_password: str, db_path: Optional[str] = None) -> bool:
    """Change user password with fresh salt."""
    if not new_password or len(new_password) < 4:
        raise ValueError("Password must be at least 4 characters long.")

    pw_hash, salt = hash_password(new_password)
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                (pw_hash, salt, user_id)
            )
        return True
    finally:
        conn.close()

