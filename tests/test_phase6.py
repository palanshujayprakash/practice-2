"""
Unit and Integration Tests for Phase 6 (Safety, Authentication, Roles & Backup/Restore)
"""
import os
import tempfile
import pytest
from db.connection import get_connection, set_db_path, get_db_path
from db.schema import init_db
from utils.security import hash_password, verify_password
from services.auth_service import authenticate_user, create_user, change_user_password, get_all_users
from services.product_service import add_product, get_all_products
from services.backup_service import (
    create_backup,
    auto_daily_backup,
    list_backups,
    validate_backup_file,
    restore_backup,
)


@pytest.fixture(autouse=True)
def temp_db():
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_pos_p6.db")
    set_db_path(test_db_path)
    init_db(test_db_path)
    yield test_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_password_hashing_and_salting():
    """Verify that password hashing uses salt and constant-time comparison."""
    h1, s1 = hash_password("secret123")
    h2, s2 = hash_password("secret123")

    # Salts must be unique
    assert s1 != s2
    # Hashes must differ because of different salts
    assert h1 != h2

    # Verification must succeed with correct password
    assert verify_password("secret123", h1, s1) is True
    assert verify_password("wrongpass", h1, s1) is False


def test_user_creation_and_authentication(temp_db):
    """Verify owner and cashier accounts authentication."""
    # Test default owner
    owner = authenticate_user("admin", "admin123", temp_db)
    assert owner is not None
    assert owner["role"] == "owner"

    # Test default cashier
    cashier = authenticate_user("cashier", "cashier123", temp_db)
    assert cashier is not None
    assert cashier["role"] == "cashier"

    # Create new cashier
    new_uid = create_user("cashier_vikas", "pass456", role="cashier", db_path=temp_db)
    assert new_uid > 0

    vikas = authenticate_user("cashier_vikas", "pass456", temp_db)
    assert vikas is not None
    assert vikas["role"] == "cashier"


def test_password_change(temp_db):
    """Verify updating a user's password."""
    user = authenticate_user("admin", "admin123", temp_db)
    assert user is not None

    ok = change_user_password(user["id"], "newadmin2026", temp_db)
    assert ok is True

    # Old password must fail
    assert authenticate_user("admin", "admin123", temp_db) is None
    # New password must succeed
    assert authenticate_user("admin", "newadmin2026", temp_db) is not None


def test_db_backup_and_validation(temp_db):
    """Verify hot SQLite backup creation and structure validation."""
    add_product("Backup Test Product", 5000, db_path=temp_db)

    backup_path = create_backup(notes="test_run", db_path=temp_db)
    assert os.path.exists(backup_path)
    assert validate_backup_file(backup_path) is True

    backups = list_backups()
    assert len(backups) > 0


def test_db_restore(temp_db):
    """Verify restoring from a backup restores previous database state intact."""
    # 1. State A: add initial product
    add_product("Original Item", 10000, db_path=temp_db)
    backup_file = create_backup(notes="state_a", db_path=temp_db)

    # 2. State B: add a second product
    add_product("State B Item", 20000, db_path=temp_db)
    items_state_b = get_all_products(db_path=temp_db)
    assert len(items_state_b) == 2

    # 3. Restore to State A
    ok = restore_backup(backup_file, db_path=temp_db)
    assert ok is True

    # 4. Verify only Original Item exists now
    items_restored = get_all_products(db_path=temp_db)
    assert len(items_restored) == 1
    assert items_restored[0]["name"] == "Original Item"
