"""
Cryptographic password hashing utilities using standard library hashlib and secrets.
"""
import hashlib
import secrets
from typing import Optional, Tuple


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Generate salted PBKDF2-HMAC-SHA256 password hash.
    Returns (hex_hash, hex_salt).
    """
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000
    )
    return key.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify password against stored hash and salt in constant time."""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, stored_hash)
