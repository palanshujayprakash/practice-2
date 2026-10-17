"""
Unit and Integration Tests for Phase 4 (ReportLab PDF Generation & Reprints)
"""
import os
import tempfile
import pytest
from db.connection import get_connection, set_db_path
from db.schema import init_db
from services.product_service import add_product
from services.customer_service import add_customer
from services.billing_service import checkout_bill, get_bill_details
from services.settings_service import update_shop_settings
from services.pdf_service import generate_bill_pdf


@pytest.fixture(autouse=True)
def temp_db():
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_pos_p4.db")
    set_db_path(test_db_path)
    init_db(test_db_path)
    yield test_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_generate_80mm_thermal_pdf(temp_db):
    """Verify generating 80mm thermal receipt produces valid PDF bytes."""
    p_id = add_product("Colgate 100g", 6500, barcode="89012345", stock_qty=50.0, db_path=temp_db)
    c_id = add_customer("Aakash Sharma", "9811122233", db_path=temp_db)

    cart = [{
        "id": p_id,
        "name": "Colgate 100g",
        "selling_price_paise": 6500,
        "gst_rate": 18.0,
        "unit": "pcs",
        "quantity": 2.0
    }]

    bill = checkout_bill(
        customer_id=c_id,
        payment_mode="upi",
        cart_items=cart,
        discount_type="Fixed (₹)",
        discount_val=10.0,
        db_path=temp_db
    )

    pdf_bytes = generate_bill_pdf(bill["bill_no"], paper_size_override="80mm", db_path=temp_db)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")


def test_generate_a4_invoice_pdf(temp_db):
    """Verify generating A4 tax invoice produces valid PDF bytes."""
    p_id = add_product("Basmati Rice 5kg", 45000, barcode="89098765", stock_qty=20.0, db_path=temp_db)

    cart = [{
        "id": p_id,
        "name": "Basmati Rice 5kg",
        "selling_price_paise": 45000,
        "gst_rate": 5.0,
        "unit": "pcs",
        "quantity": 1.0
    }]

    bill = checkout_bill(
        customer_id=None,
        payment_mode="cash",
        cart_items=cart,
        db_path=temp_db
    )

    pdf_bytes = generate_bill_pdf(bill["bill_id"], paper_size_override="A4", db_path=temp_db)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_pdf_with_logo_and_reprint(temp_db):
    """Verify PDF generation handles custom logo and allows reprinting historical bills."""
    # 1x1 transparent PNG bytes
    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r"
        b"\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    update_shop_settings(
        shop_name="Modern Kirana Store",
        address="Bazaar Road, Pune",
        phone="+91 98765 00000",
        gstin="27ABCDE1234F1Z5",
        bill_footer="Terms: No returns after 7 days.",
        paper_size="80mm",
        logo_blob=tiny_png,
        db_path=temp_db
    )

    p_id = add_product("Amul Butter 100g", 5600, stock_qty=30.0, db_path=temp_db)
    cart = [{
        "id": p_id,
        "name": "Amul Butter 100g",
        "selling_price_paise": 5600,
        "gst_rate": 12.0,
        "unit": "pcs",
        "quantity": 1.0
    }]

    bill = checkout_bill(
        customer_id=None,
        payment_mode="card",
        cart_items=cart,
        db_path=temp_db
    )

    # Reprint old bill
    pdf_reprint = generate_bill_pdf(bill["bill_no"], db_path=temp_db)
    assert pdf_reprint.startswith(b"%PDF-")
    assert len(pdf_reprint) > 500
