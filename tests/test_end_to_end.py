"""
End-to-End Integration Test verifying Definition of Done.
Tests full POS lifecycle: Search Item -> Add to Cart -> Discount -> Save Bill -> Generate PDF -> Stock Reduced -> Data Survives Restart.
"""
import os
import sqlite3
import tempfile
import pytest
from db.connection import get_connection, set_db_path
from db.schema import init_db
from services.product_service import add_product, get_product_by_barcode, get_product_by_id
from services.customer_service import add_customer, get_customer_by_id
from services.billing_service import checkout_bill, get_bill_details
from services.pdf_service import generate_bill_pdf


@pytest.fixture
def isolated_db():
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_e2e_pos.db")
    set_db_path(test_db_path)
    init_db(test_db_path)
    yield test_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_complete_sale_end_to_end_and_restart(isolated_db):
    """
    Definition of Done verification:
    1. Search item by barcode.
    2. Add to cart.
    3. Apply discount.
    4. Save bill (checkout).
    5. Generate PDF (both 80mm and A4).
    6. Verify stock reduced and logged.
    7. Simulate app restart and verify persistence.
    """
    # Step 1: Catalog setup
    prod_id = add_product(
        name="Fortune Sunflower Oil 1L",
        selling_price_paise=14500,  # ₹145.00
        purchase_price_paise=13000,
        barcode="8901030383792",
        category="Grocery",
        unit="ltr",
        gst_rate=5.0,
        stock_qty=50.0,
        min_stock_qty=10.0,
        db_path=isolated_db
    )
    cust_id = add_customer("Aakash Verma", "9812345678", "Shop Lane, Delhi", db_path=isolated_db)

    # Step 2: Search item by barcode (simulates scanner)
    found_item = get_product_by_barcode("8901030383792", db_path=isolated_db)
    assert found_item is not None
    assert found_item["id"] == prod_id
    assert found_item["stock_qty"] == 50.0

    # Step 3: Add to cart with quantity 2
    cart = [{
        "id": found_item["id"],
        "name": found_item["name"],
        "selling_price_paise": found_item["selling_price_paise"],
        "unit": found_item["unit"],
        "gst_rate": found_item["gst_rate"],
        "quantity": 2.0
    }]

    # Step 4: Checkout with ₹10 discount (1000 paise) via UPI
    bill_res = checkout_bill(
        customer_id=cust_id,
        payment_mode="upi",
        cart_items=cart,
        discount_type="Fixed (₹)",
        discount_val=10.0,
        db_path=isolated_db
    )

    bill_id = bill_res["bill_id"]
    bill_no = bill_res["bill_no"]

    # Gross: 2 * 14500 = 29000, Discount: 1000, Grand Total: 28000
    assert bill_res["summary"]["gross_total_paise"] == 29000
    assert bill_res["summary"]["discount_paise"] == 1000
    assert bill_res["summary"]["grand_total_paise"] == 28000

    # Step 5: Generate PDF receipts
    pdf_80mm = generate_bill_pdf(bill_no, paper_size_override="80mm", db_path=isolated_db)
    pdf_a4 = generate_bill_pdf(bill_no, paper_size_override="A4", db_path=isolated_db)

    assert pdf_80mm.startswith(b"%PDF-")
    assert pdf_a4.startswith(b"%PDF-")
    assert len(pdf_80mm) > 500
    assert len(pdf_a4) > 1000

    # Step 6: Verify stock reduced from 50 to 48
    prod_after = get_product_by_id(prod_id, db_path=isolated_db)
    assert prod_after["stock_qty"] == 48.0

    # Step 7: Simulate complete application shutdown & restart
    # Open fresh database connection from disk
    fresh_conn = sqlite3.connect(isolated_db)
    fresh_conn.row_factory = sqlite3.Row

    # Verify bill persisted
    cur = fresh_conn.cursor()
    cur.execute("SELECT * FROM bills WHERE bill_no = ?", (bill_no,))
    saved_bill = cur.fetchone()
    assert saved_bill is not None
    assert saved_bill["grand_total_paise"] == 28000
    assert saved_bill["payment_mode"] == "upi"
    assert saved_bill["status"] == "completed"

    # Verify line items snapshot persisted
    cur.execute("SELECT * FROM bill_items WHERE bill_id = ?", (bill_id,))
    saved_items = cur.fetchall()
    assert len(saved_items) == 1
    assert saved_items[0]["product_name_snapshot"] == "Fortune Sunflower Oil 1L"
    assert saved_items[0]["unit_price_paise_snapshot"] == 14500
    assert saved_items[0]["quantity"] == 2.0

    # Verify inventory audit log persisted
    cur.execute("SELECT * FROM stock_log WHERE reference_id = ?", (bill_no,))
    log_entry = cur.fetchone()
    assert log_entry is not None
    assert log_entry["change_qty"] == -2.0
    assert log_entry["reason"] == "sale"

    fresh_conn.close()
