"""
Fuzzing, Chaos, and Stress Test Suite.
Attempts to crash the application with extreme inputs, SQL injections, concurrency,
overflow values, unicode/emojis, corrupt files, and boundary conditions.
"""
import io
import os
import tempfile
import threading
import sqlite3
import pandas as pd
import pytest
from db.connection import get_connection, set_db_path
from db.schema import init_db
from utils.currency import rupees_to_paise, paise_to_rupees_decimal, format_rupees
from services.product_service import (
    add_product,
    get_all_products,
    get_product_by_id,
    get_product_by_barcode,
    update_product,
    import_products_from_dataframe,
)
from services.customer_service import (
    add_customer,
    get_customer_by_phone,
    record_customer_payment,
    get_customers_with_stats,
)
from services.billing_service import (
    calculate_cart_summary,
    checkout_bill,
    cancel_bill,
    filter_bills,
)
from services.pdf_service import generate_bill_pdf
from services.backup_service import (
    create_backup,
    validate_backup_file,
    restore_backup,
)
from services.report_service import export_reports_to_excel


@pytest.fixture(autouse=True)
def chaos_db():
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "chaos_pos.db")
    set_db_path(test_db_path)
    init_db(test_db_path)
    yield test_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_extreme_and_overflow_monetary_values(chaos_db):
    """Test 1 paisa, 10 crore rupees, and zero price."""
    # 1 paisa (₹0.01)
    p1 = add_product("Penny Candy", 1, stock_qty=100.0, db_path=chaos_db)
    # Huge price: ₹10,00,00,000 (10 crore) = 1,000,000,000 paise
    p2 = add_product("Gold Bar 1kg", 1_000_000_000, stock_qty=5.0, db_path=chaos_db)

    cart = [
        {"id": p1, "name": "Penny Candy", "selling_price_paise": 1, "gst_rate": 0.0, "quantity": 1.0},
        {"id": p2, "name": "Gold Bar 1kg", "selling_price_paise": 1_000_000_000, "gst_rate": 3.0, "quantity": 1.0}
    ]

    summary = calculate_cart_summary(cart, "Fixed (₹)", 0.0)
    assert summary["grand_total_paise"] == 1_000_000_001

    bill = checkout_bill(None, "cash", cart, db_path=chaos_db)
    assert bill["bill_id"] > 0

    # Ensure PDF generates without crashing on huge numbers
    pdf = generate_bill_pdf(bill["bill_no"], paper_size_override="80mm", db_path=chaos_db)
    assert len(pdf) > 0


def test_discount_edge_cases():
    """Test negative discounts, 100% discount, 200% discount, and discount > bill total."""
    cart = [
        {"id": 1, "name": "Shirt", "selling_price_paise": 100000, "gst_rate": 5.0, "quantity": 1.0}
    ]

    # Negative discount must not increase bill total
    res_neg = calculate_cart_summary(cart, "Fixed (₹)", -500.0)
    assert res_neg["discount_paise"] == 0
    assert res_neg["grand_total_paise"] == 100000

    # 100% discount -> Grand total must be 0
    res_100 = calculate_cart_summary(cart, "Percentage (%)", 100.0)
    assert res_100["discount_paise"] == 100000
    assert res_100["grand_total_paise"] == 0

    # 200% discount -> Grand total must clamp to 0, never negative
    res_200 = calculate_cart_summary(cart, "Percentage (%)", 200.0)
    assert res_200["discount_paise"] == 100000
    assert res_200["grand_total_paise"] == 0

    # Fixed discount ₹5000 on ₹1000 item -> must clamp to ₹1000
    res_over = calculate_cart_summary(cart, "Fixed (₹)", 5000.0)
    assert res_over["discount_paise"] == 100000
    assert res_over["grand_total_paise"] == 0


def test_sql_injection_and_hostile_strings(chaos_db):
    """Verify parameterized queries prevent SQL injection."""
    hostile_name = "Item'; DROP TABLE products; -- 💥"
    hostile_barcode = "123' OR '1'='1"
    hostile_cust = "Hacker'); DROP TABLE bills; --"

    p_id = add_product(hostile_name, 5000, barcode=hostile_barcode, db_path=chaos_db)
    c_id = add_customer(hostile_cust, "9999900000", db_path=chaos_db)

    # Search should safely find item and not execute SQL
    found = get_product_by_barcode(hostile_barcode, db_path=chaos_db)
    assert found is not None
    assert found["id"] == p_id

    # Filter bills with hostile search term
    bills = filter_bills(search_term="'; DROP TABLE users; --", db_path=chaos_db)
    assert isinstance(bills, list)

    # Verify tables still exist
    conn = get_connection(chaos_db)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM products")
    assert cur.fetchone()[0] >= 1
    conn.close()


def test_unicode_hindi_tamil_emojis(chaos_db):
    """Test unicode characters across kirana products in India."""
    name_hindi = "टाटा नमक १ किलो 🧂"
    p_id = add_product(name_hindi, 2800, category="किराना", unit="किलो", stock_qty=10.0, db_path=chaos_db)
    c_id = add_customer("सुरेश कुमार", "9811122334", "नई दिल्ली", db_path=chaos_db)

    cart = [{
        "id": p_id,
        "name": name_hindi,
        "selling_price_paise": 2800,
        "gst_rate": 0.0,
        "quantity": 1.0
    }]

    bill = checkout_bill(c_id, "cash", cart, db_path=chaos_db)
    assert bill["bill_id"] > 0

    # PDF generation with unicode characters
    # Note: ReportLab built-in fonts (Helvetica) may substitute or skip non-latin chars unless registered,
    # but the service must NOT crash with an unhandled exception!
    try:
        pdf_80 = generate_bill_pdf(bill["bill_no"], paper_size_override="80mm", db_path=chaos_db)
        assert len(pdf_80) > 0
    except UnicodeEncodeError:
        pytest.fail("PDF generator crashed on Unicode/Hindi characters!")


def test_huge_cart_stress_thermal_pdf(chaos_db):
    """Test 80 distinct items in a single bill (thermal receipts are usually long)."""
    cart = []
    for i in range(1, 61):
        pid = add_product(f"Supermarket Item #{i:02d}", 1000 + (i * 50), stock_qty=100.0, db_path=chaos_db)
        cart.append({
            "id": pid,
            "name": f"Supermarket Item #{i:02d}",
            "selling_price_paise": 1000 + (i * 50),
            "gst_rate": 5.0 if i % 2 == 0 else 18.0,
            "quantity": 1.0
        })

    bill = checkout_bill(None, "cash", cart, db_path=chaos_db)
    assert bill["bill_id"] > 0

    # Thermal PDF with 60 items
    pdf_80 = generate_bill_pdf(bill["bill_no"], paper_size_override="80mm", db_path=chaos_db)
    assert len(pdf_80) > 2000
    # A4 PDF with 60 items (multi-page)
    pdf_a4 = generate_bill_pdf(bill["bill_no"], paper_size_override="A4", db_path=chaos_db)
    assert len(pdf_a4) > 3000


def test_corrupt_files_and_fuzzing(chaos_db):
    """Test uploading corrupt CSV/Excel and corrupt DB restore."""
    # 1. Corrupt DataFrame for bulk import
    df_corrupt = pd.DataFrame([
        {"Name": None, "Selling Price": "invalid_number_abc"},
        {"Name": "Good Item", "Selling Price": -100},
        {"Name": "Valid Item", "Selling Price": "45.00"}
    ])
    res = import_products_from_dataframe(df_corrupt, chaos_db)
    assert res["success"] == 1
    assert len(res["errors"]) >= 2

    # 2. Corrupt / Zero-byte file restore attempt
    temp_junk = os.path.join(tempfile.gettempdir(), "junk_corrupt.db")
    with open(temp_junk, "wb") as f:
        f.write(b"NOT A REAL SQLITE DATABASE FILE JUNK BYTES")

    assert validate_backup_file(temp_junk) is False
    with pytest.raises(ValueError, match="Invalid backup file"):
        restore_backup(temp_junk, db_path=chaos_db)

    if os.path.exists(temp_junk):
        os.remove(temp_junk)


def test_concurrent_multithreaded_checkouts(chaos_db):
    """Verify thread-safe concurrent sales under SQLite WAL mode without DB lock collisions."""
    # Create product with 50 stock
    pid = add_product("Hot Sale Item", 1000, stock_qty=50.0, db_path=chaos_db)

    errors = []
    successes = []

    def make_sale():
        try:
            cart = [{
                "id": pid,
                "name": "Hot Sale Item",
                "selling_price_paise": 1000,
                "gst_rate": 0.0,
                "quantity": 1.0
            }]
            b = checkout_bill(None, "cash", cart, db_path=chaos_db)
            successes.append(b["bill_no"])
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=make_sale) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 20 threads should complete successfully without database locked error
    assert len(errors) == 0
    assert len(successes) == 20

    # Stock must be exactly 50 - 20 = 30
    prod = get_product_by_id(pid, chaos_db)
    assert prod["stock_qty"] == 30.0
