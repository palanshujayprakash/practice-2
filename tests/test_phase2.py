"""
Unit and Integration Tests for Phase 2 (Products, Inventory, Validation & Bulk Import)
"""
import os
import tempfile
import pandas as pd
import pytest
from db.connection import get_connection, set_db_path
from db.schema import init_db
from services.product_service import (
    add_product,
    get_all_products,
    get_product_by_id,
    get_product_by_barcode,
    update_product,
    delete_product,
    get_low_stock_products,
    import_products_from_dataframe,
)
from utils.currency import rupees_to_paise


@pytest.fixture(autouse=True)
def temp_db():
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_pos_p2.db")
    set_db_path(test_db_path)
    init_db(test_db_path)
    yield test_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_add_product_and_lookup(temp_db):
    """Verify adding product and looking up by ID and barcode."""
    p_id = add_product(
        name="Tata Salt 1kg",
        selling_price_paise=2800,
        purchase_price_paise=2400,
        barcode="890103000001",
        category="Grocery",
        unit="pcs",
        gst_rate=0.0,
        stock_qty=50.0,
        min_stock_qty=10.0,
        db_path=temp_db
    )
    assert p_id > 0

    p_by_id = get_product_by_id(p_id, temp_db)
    assert p_by_id is not None
    assert p_by_id["name"] == "Tata Salt 1kg"
    assert p_by_id["selling_price_paise"] == 2800
    assert p_by_id["stock_qty"] == 50.0

    p_by_barcode = get_product_by_barcode("890103000001", temp_db)
    assert p_by_barcode is not None
    assert p_by_barcode["id"] == p_id


def test_product_validations(temp_db):
    """Verify that negative price/stock and duplicate barcodes are rejected."""
    # Empty name
    with pytest.raises(ValueError, match="Product Name cannot be empty"):
        add_product(name="", selling_price_paise=1000, db_path=temp_db)

    # Negative selling price
    with pytest.raises(ValueError, match="Selling price cannot be negative"):
        add_product(name="Item A", selling_price_paise=-500, db_path=temp_db)

    # Negative stock
    with pytest.raises(ValueError, match="stock quantity cannot be negative"):
        add_product(name="Item B", selling_price_paise=1000, stock_qty=-5.0, db_path=temp_db)

    # Duplicate barcode
    add_product(name="Item 1", selling_price_paise=1000, barcode="BAR123", db_path=temp_db)
    with pytest.raises(ValueError, match="already exists"):
        add_product(name="Item 2", selling_price_paise=2000, barcode="BAR123", db_path=temp_db)


def test_product_update_and_audit_log(temp_db):
    """Verify editing product updates details and logs stock changes."""
    p_id = add_product(
        name="Sugar 1kg",
        selling_price_paise=4500,
        stock_qty=20.0,
        db_path=temp_db
    )

    # Update stock to 35
    ok = update_product(
        product_id=p_id,
        name="Sugar 1kg Madhur",
        selling_price_paise=4600,
        stock_qty=35.0,
        db_path=temp_db
    )
    assert ok is True

    updated = get_product_by_id(p_id, temp_db)
    assert updated["name"] == "Sugar 1kg Madhur"
    assert updated["selling_price_paise"] == 4600
    assert updated["stock_qty"] == 35.0

    # Verify stock log audit
    conn = get_connection(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT * FROM stock_log WHERE product_id = ?", (p_id,))
    logs = cur.fetchall()
    conn.close()
    assert len(logs) >= 2  # initial_stock + manual_adjustment


def test_low_stock_detection(temp_db):
    """Verify items below minimum threshold are flagged."""
    add_product(name="High Stock Item", selling_price_paise=1000, stock_qty=50.0, min_stock_qty=10.0, db_path=temp_db)
    add_product(name="Low Stock Item", selling_price_paise=1000, stock_qty=3.0, min_stock_qty=10.0, db_path=temp_db)

    low_items = get_low_stock_products(temp_db)
    assert len(low_items) == 1
    assert low_items[0]["name"] == "Low Stock Item"


def test_soft_delete(temp_db):
    """Verify soft deleting an item hides it from active catalog."""
    p_id = add_product(name="Discontinued Item", selling_price_paise=1000, db_path=temp_db)
    delete_product(p_id, soft_delete=True, db_path=temp_db)

    active_items = get_all_products(active_only=True, db_path=temp_db)
    assert all(p["id"] != p_id for p in active_items)

    all_items = get_all_products(active_only=False, db_path=temp_db)
    assert any(p["id"] == p_id for p in all_items)


def test_bulk_dataframe_import(temp_db):
    """Verify importing items from a pandas DataFrame with validation."""
    df = pd.DataFrame([
        {
            "Name": "Imported Soap 100g",
            "Selling Price": "35.50",
            "Purchase Price": "28.00",
            "Barcode": "890999001",
            "Category": "Personal Care",
            "Unit": "pcs",
            "GST Rate": 18.0,
            "Stock Qty": 40,
            "Min Stock Qty": 10
        },
        {
            "Name": "Imported Biscuits 200g",
            "Selling Price": "20.00",
            "Stock Qty": 100,
        },
        {
            "Name": "",  # Invalid row
            "Selling Price": "50.00"
        }
    ])

    res = import_products_from_dataframe(df, temp_db)
    assert res["success"] == 2
    assert len(res["errors"]) == 1

    prod = get_product_by_barcode("890999001", temp_db)
    assert prod is not None
    assert prod["name"] == "Imported Soap 100g"
    assert prod["selling_price_paise"] == 3550
    assert prod["purchase_price_paise"] == 2800
    assert prod["gst_rate"] == 18.0
