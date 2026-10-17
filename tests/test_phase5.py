"""
Unit and Integration Tests for Phase 5 (History, Cancellation, Customers & Reports)
"""
import io
import os
import tempfile
import openpyxl
import pandas as pd
import pytest
from db.connection import get_connection, set_db_path
from db.schema import init_db
from services.product_service import add_product, get_product_by_id
from services.customer_service import (
    add_customer,
    get_customer_by_id,
    get_customers_with_stats,
    record_customer_payment,
)
from services.billing_service import checkout_bill, cancel_bill, filter_bills, get_bill_details
from services.report_service import (
    get_sales_kpis,
    get_daily_sales_data,
    get_top_selling_products,
    get_gst_slab_breakdown,
    export_reports_to_excel,
)


@pytest.fixture(autouse=True)
def temp_db():
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_pos_p5.db")
    set_db_path(test_db_path)
    init_db(test_db_path)
    yield test_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_bill_cancellation_restores_stock_and_credit(temp_db):
    """Verify that cancelling a bill restores product inventory and reverses credit debt."""
    p_id = add_product("Atta 5kg", 25000, stock_qty=20.0, db_path=temp_db)
    c_id = add_customer("Mohan Lal", "9876543210", db_path=temp_db)

    cart = [{
        "id": p_id,
        "name": "Atta 5kg",
        "selling_price_paise": 25000,
        "gst_rate": 0.0,
        "unit": "pcs",
        "quantity": 2.0
    }]

    bill = checkout_bill(
        customer_id=c_id,
        payment_mode="credit",
        cart_items=cart,
        db_path=temp_db
    )

    # Stock should be 18, customer debt should be 50000
    p_after_sale = get_product_by_id(p_id, temp_db)
    assert p_after_sale["stock_qty"] == 18.0
    c_after_sale = get_customer_by_id(c_id, temp_db)
    assert c_after_sale["credit_balance_paise"] == 50000

    # Cancel bill
    ok = cancel_bill(bill["bill_id"], cancelled_by=1, reason="Customer canceled order", db_path=temp_db)
    assert ok is True

    # Verify bill status is cancelled
    details = get_bill_details(bill["bill_id"], temp_db)
    assert details["status"] == "cancelled"
    assert details["cancellation_reason"] == "Customer canceled order"

    # Verify stock restored to 20
    p_restored = get_product_by_id(p_id, temp_db)
    assert p_restored["stock_qty"] == 20.0

    # Verify credit debt reversed to 0
    c_reverted = get_customer_by_id(c_id, temp_db)
    assert c_reverted["credit_balance_paise"] == 0

    # Verify stock log entry
    conn = get_connection(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT * FROM stock_log WHERE product_id = ? AND reason = 'bill_cancelled'", (p_id,))
    assert cur.fetchone() is not None
    conn.close()


def test_customer_stats_and_payment_settlement(temp_db):
    """Verify customer purchase aggregation and udhaar debt settlement."""
    p_id = add_product("Milk 1L", 6000, stock_qty=50.0, db_path=temp_db)
    c_id = add_customer("Suman Devi", "9800011122", db_path=temp_db)

    cart = [{
        "id": p_id,
        "name": "Milk 1L",
        "selling_price_paise": 6000,
        "gst_rate": 0.0,
        "quantity": 3.0
    }]

    # Credit purchase of ₹180 (18000 paise)
    checkout_bill(customer_id=c_id, payment_mode="credit", cart_items=cart, db_path=temp_db)

    stats = get_customers_with_stats("Suman", temp_db)
    assert len(stats) == 1
    assert stats[0]["total_spent_paise"] == 18000
    assert stats[0]["credit_balance_paise"] == 18000
    assert stats[0]["total_bills_count"] == 1

    # Record partial payment of ₹100 (10000 paise)
    record_customer_payment(c_id, 10000, payment_mode="upi", db_path=temp_db)

    cust = get_customer_by_id(c_id, temp_db)
    assert cust["credit_balance_paise"] == 8000  # ₹80 remaining


def test_report_service_and_excel_export(temp_db):
    """Verify KPI calculations and multi-sheet openpyxl export."""
    p_id = add_product("Biscuits", 2000, gst_rate=12.0, stock_qty=100.0, db_path=temp_db)
    cart = [{
        "id": p_id,
        "name": "Biscuits",
        "selling_price_paise": 2000,
        "gst_rate": 12.0,
        "quantity": 5.0
    }]

    checkout_bill(customer_id=None, payment_mode="cash", cart_items=cart, db_path=temp_db)

    kpis = get_sales_kpis(db_path=temp_db)
    assert kpis["total_bills"] == 1
    assert kpis["total_revenue"] == 10000

    df_top = get_top_selling_products(limit=5, db_path=temp_db)
    assert not df_top.empty
    assert df_top.iloc[0]["Item"] == "Biscuits"
    assert df_top.iloc[0]["Quantity Sold"] == 5.0

    df_gst = get_gst_slab_breakdown(db_path=temp_db)
    assert not df_gst.empty
    assert "12.0%" in df_gst["GST Slab"].values

    # Test Excel Export
    excel_bytes = export_reports_to_excel(db_path=temp_db)
    assert len(excel_bytes) > 2000

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    sheet_names = wb.sheetnames
    assert "Invoices Summary" in sheet_names
    assert "GST Tax Slabs" in sheet_names
    assert "Top Selling Items" in sheet_names
    assert "Low Stock Inventory" in sheet_names
