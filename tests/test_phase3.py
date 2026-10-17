"""
Unit and Integration Tests for Phase 3 (Billing Engine, Cart Math, Checkout & Stock Deduction)
"""
import os
import tempfile
import pytest
from db.connection import get_connection, set_db_path
from db.schema import init_db
from services.product_service import add_product, get_product_by_id
from services.customer_service import add_customer, get_customer_by_id
from services.billing_service import (
    calculate_cart_summary,
    checkout_bill,
    generate_next_bill_number,
)


@pytest.fixture(autouse=True)
def temp_db():
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_pos_p3.db")
    set_db_path(test_db_path)
    init_db(test_db_path)
    yield test_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_cart_calculation_math():
    """Verify GST breakup and grand total calculation."""
    cart = [
        {
            "id": 1,
            "name": "Tax Free Rice 1kg",
            "selling_price_paise": 6000,  # ₹60.00
            "unit": "kg",
            "gst_rate": 0.0,
            "quantity": 2.0
        },
        {
            "id": 2,
            "name": "Noodles 100g (12% GST)",
            "selling_price_paise": 11200,  # ₹112.00
            "unit": "pcs",
            "gst_rate": 12.0,
            "quantity": 1.0
        }
    ]

    # No discount
    res = calculate_cart_summary(cart, "Fixed (₹)", 0.0)
    assert res["gross_total_paise"] == (6000 * 2) + 11200  # 23200 (₹232.00)
    # Noodles base = 11200 / 1.12 = 10000, GST = 1200
    assert res["gst_slabs"]["12.0%"]["gst"] == 1200
    assert res["gst_slabs"]["12.0%"]["taxable"] == 10000
    assert res["subtotal_paise"] == 12000 + 10000  # 22000
    assert res["gst_total_paise"] == 1200
    assert res["grand_total_paise"] == 23200

    # Test Fixed Discount (₹32 = 3200 paise)
    res_disc = calculate_cart_summary(cart, "Fixed (₹)", 32.0)
    assert res_disc["discount_paise"] == 3200
    assert res_disc["grand_total_paise"] == 20000

    # Test Percentage Discount (10%)
    res_pct = calculate_cart_summary(cart, "Percentage (%)", 10.0)
    assert res_pct["discount_paise"] == 2320
    assert res_pct["grand_total_paise"] == 20880


def test_sequential_bill_numbering(temp_db):
    """Verify sequential bill number format."""
    conn = get_connection(temp_db)
    b1 = generate_next_bill_number(conn)
    assert b1.startswith("INV-")
    assert b1.endswith("-0001")
    conn.close()


def test_atomic_checkout_flow(temp_db):
    """Verify end-to-end checkout: bill, items, stock reduction, audit log."""
    # 1. Create product with stock=20
    p_id = add_product(
        name="Tata Salt",
        selling_price_paise=2800,
        gst_rate=0.0,
        stock_qty=20.0,
        db_path=temp_db
    )

    # 2. Create customer
    c_id = add_customer(name="Ramesh Kumar", phone="9876500001", db_path=temp_db)

    cart = [{
        "id": p_id,
        "name": "Tata Salt",
        "selling_price_paise": 2800,
        "gst_rate": 0.0,
        "unit": "pcs",
        "quantity": 3.0
    }]

    # 3. Checkout cash sale
    res = checkout_bill(
        customer_id=c_id,
        payment_mode="cash",
        cart_items=cart,
        discount_type="Fixed (₹)",
        discount_val=0.0,
        db_path=temp_db
    )

    assert res["bill_id"] > 0
    assert res["bill_no"].endswith("-0001")
    assert res["summary"]["grand_total_paise"] == 8400

    # 4. Verify product stock reduced from 20 to 17
    prod = get_product_by_id(p_id, temp_db)
    assert prod["stock_qty"] == 17.0

    # 5. Verify stock log contains the sale entry
    conn = get_connection(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT * FROM stock_log WHERE product_id = ? AND reason = 'sale'", (p_id,))
    log_entry = cur.fetchone()
    assert log_entry is not None
    assert log_entry["change_qty"] == -3.0
    assert log_entry["reference_id"] == res["bill_no"]

    # 6. Verify immutable bill_items snapshot
    cur.execute("SELECT * FROM bill_items WHERE bill_id = ?", (res["bill_id"],))
    item_rows = cur.fetchall()
    assert len(item_rows) == 1
    assert item_rows[0]["product_name_snapshot"] == "Tata Salt"
    assert item_rows[0]["unit_price_paise_snapshot"] == 2800
    assert item_rows[0]["quantity"] == 3.0
    assert item_rows[0]["total_paise"] == 8400
    conn.close()


def test_credit_sale_updates_customer_udhaar(temp_db):
    """Verify that a credit sale increments customer udhaar balance."""
    p_id = add_product(name="Notebook", selling_price_paise=5000, stock_qty=10.0, db_path=temp_db)
    c_id = add_customer(name="Suresh Verma", phone="9876500002", db_path=temp_db)

    cart = [{
        "id": p_id,
        "name": "Notebook",
        "selling_price_paise": 5000,
        "gst_rate": 0.0,
        "quantity": 2.0
    }]

    res = checkout_bill(
        customer_id=c_id,
        payment_mode="credit",
        cart_items=cart,
        db_path=temp_db
    )

    cust = get_customer_by_id(c_id, temp_db)
    # 2 * 5000 = 10000 paise (₹100)
    assert cust["credit_balance_paise"] == 10000


def test_insufficient_stock_fails_checkout(temp_db):
    """Verify that checkout raises error and rolls back if stock is insufficient."""
    p_id = add_product(name="Limited Item", selling_price_paise=1000, stock_qty=2.0, db_path=temp_db)

    cart = [{
        "id": p_id,
        "name": "Limited Item",
        "selling_price_paise": 1000,
        "gst_rate": 0.0,
        "quantity": 5.0
    }]

    with pytest.raises(ValueError, match="Insufficient stock"):
        checkout_bill(
            customer_id=None,
            payment_mode="cash",
            cart_items=cart,
            db_path=temp_db
        )

    # Verify stock remained untouched
    prod = get_product_by_id(p_id, temp_db)
    assert prod["stock_qty"] == 2.0
