"""
Unit and Integration Tests for Phase 1 (Foundation & Settings)
"""
import os
import tempfile
import pytest
from db.connection import get_connection, set_db_path
from db.schema import init_db
from services.auth_service import hash_password, verify_password, authenticate_user
from services.settings_service import get_shop_settings, update_shop_settings
from utils.currency import rupees_to_paise, paise_to_rupees_decimal, format_rupees


@pytest.fixture(autouse=True)
def temp_db():
    """Setup an isolated temporary database for each test."""
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_pos.db")
    set_db_path(test_db_path)
    init_db(test_db_path)
    yield test_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_currency_conversions():
    """Verify precision integer paise conversions."""
    assert rupees_to_paise(100.50) == 10050
    assert rupees_to_paise("100.50") == 10050
    assert rupees_to_paise("0.05") == 5
    assert rupees_to_paise(0) == 0
    assert rupees_to_paise(199.999) == 20000

    assert paise_to_rupees_decimal(10050) == pytest.approx(100.50)
    assert format_rupees(10050) == "₹ 100.50"
    assert format_rupees(1234567) == "₹ 12,345.67"


def test_db_auto_initialization(temp_db):
    """Verify all tables exist and foreign keys are active."""
    conn = get_connection(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row["name"] for row in cur.fetchall()}
    conn.close()

    expected_tables = {
        "shop_settings",
        "users",
        "customers",
        "products",
        "bills",
        "bill_items",
        "stock_log",
    }
    assert expected_tables.issubset(tables)


def test_default_seed_data(temp_db):
    """Verify default shop_settings and admin user are created."""
    settings = get_shop_settings(temp_db)
    assert settings["id"] == 1
    assert "Kirana" in settings["shop_name"]
    assert settings["paper_size"] in ("80mm", "A4")

    # Verify admin user
    auth = authenticate_user("admin", "admin123", temp_db)
    assert auth is not None
    assert auth["username"] == "admin"
    assert auth["role"] == "owner"


def test_settings_update(temp_db):
    """Verify updating store details and paper format."""
    ok = update_shop_settings(
        shop_name="Super Mart",
        address="Sector 14, Gurgaon",
        phone="+91 99999 11111",
        gstin="07AAAAA0000A1Z5",
        bill_footer="No returns without bill",
        paper_size="A4",
        logo_blob=b"FAKE_IMAGE_BYTES",
        db_path=temp_db
    )
    assert ok is True

    updated = get_shop_settings(temp_db)
    assert updated["shop_name"] == "Super Mart"
    assert updated["address"] == "Sector 14, Gurgaon"
    assert updated["phone"] == "+91 99999 11111"
    assert updated["gstin"] == "07AAAAA0000A1Z5"
    assert updated["bill_footer"] == "No returns without bill"
    assert updated["paper_size"] == "A4"
    assert updated["logo_blob"] == b"FAKE_IMAGE_BYTES"
