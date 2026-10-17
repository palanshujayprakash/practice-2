"""
Database Schema DDL and auto-initialization module.
Enforces table integrity, foreign keys, and indexes for fast POS queries.
"""
from typing import Optional
from db.connection import get_connection
from utils.security import hash_password

SCHEMA_SQL = """
-- 1. Shop Configuration & Printer Profile
CREATE TABLE IF NOT EXISTS shop_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    shop_name TEXT NOT NULL DEFAULT 'My Kirana & General Store',
    address TEXT DEFAULT '123 Main Bazaar Road',
    phone TEXT DEFAULT '+91 98765 43210',
    gstin TEXT DEFAULT '',
    bill_footer TEXT DEFAULT 'Thank you! Visit again.',
    paper_size TEXT NOT NULL DEFAULT '80mm', -- '80mm' thermal or 'A4'
    logo_blob BLOB,
    upi_id TEXT DEFAULT 'kirana@upi',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Users & Role-Based Access Control
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'cashier')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Customer Ledger
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    address TEXT DEFAULT '',
    credit_balance_paise INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

-- 4. Products & Inventory
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT UNIQUE,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'General',
    unit TEXT DEFAULT 'pcs',
    purchase_price_paise INTEGER NOT NULL DEFAULT 0,
    selling_price_paise INTEGER NOT NULL,
    gst_rate REAL NOT NULL DEFAULT 0.0,
    stock_qty REAL NOT NULL DEFAULT 0.0,
    min_stock_qty REAL NOT NULL DEFAULT 5.0,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);

-- 5. Invoices (Bills)
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_no TEXT UNIQUE NOT NULL,
    bill_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_id INTEGER REFERENCES customers(id),
    payment_mode TEXT NOT NULL CHECK (payment_mode IN ('cash', 'upi', 'card', 'credit')),
    subtotal_paise INTEGER NOT NULL,
    discount_paise INTEGER NOT NULL DEFAULT 0,
    gst_total_paise INTEGER NOT NULL DEFAULT 0,
    grand_total_paise INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed', 'cancelled')),
    created_by INTEGER REFERENCES users(id),
    cancelled_by INTEGER REFERENCES users(id),
    cancellation_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_bills_date ON bills(bill_date);
CREATE INDEX IF NOT EXISTS idx_bills_bill_no ON bills(bill_no);
CREATE INDEX IF NOT EXISTS idx_bills_customer ON bills(customer_id);

-- 6. Bill Items (Historical Snapshot)
CREATE TABLE IF NOT EXISTS bill_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id),
    product_name_snapshot TEXT NOT NULL,
    unit_price_paise_snapshot INTEGER NOT NULL,
    gst_rate_snapshot REAL NOT NULL,
    quantity REAL NOT NULL,
    gst_amount_paise INTEGER NOT NULL,
    total_paise INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bill_items_bill_id ON bill_items(bill_id);

-- 7. Inventory Audit Trail
CREATE TABLE IF NOT EXISTS stock_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    change_qty REAL NOT NULL,
    reason TEXT NOT NULL,
    reference_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_stock_log_product ON stock_log(product_id);
"""


def init_db(db_path: Optional[str] = None) -> bool:
    """
    Initialize database schema and seed default settings and admin owner user if missing.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA_SQL)

            # Seed default shop settings (id=1)
            cur = conn.cursor()
            cur.execute("SELECT id FROM shop_settings WHERE id = 1")
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO shop_settings (id, shop_name, address, phone, gstin, bill_footer, paper_size)
                    VALUES (1, 'Apna Kirana & General Store', 'Shop No. 4, Market Complex', '+91 98765 43210', '29ABCDE1234F1Z5', 'Thank you! Visit again.', '80mm')
                    """
                )
            else:
                # Migration check: Ensure upi_id column exists
                try:
                    cur.execute("ALTER TABLE shop_settings ADD COLUMN upi_id TEXT DEFAULT 'kirana@upi'")
                except Exception:
                    pass

            # Seed default owner user ('admin' / 'admin123')
            cur.execute("SELECT id FROM users WHERE username = 'admin'")
            if not cur.fetchone():
                pw_hash, salt = hash_password("admin123")
                cur.execute(
                    """
                    INSERT INTO users (username, password_hash, salt, role)
                    VALUES ('admin', ?, ?, 'owner')
                    """,
                    (pw_hash, salt)
                )

            # Seed default cashier user ('cashier' / 'cashier123')
            cur.execute("SELECT id FROM users WHERE username = 'cashier'")
            if not cur.fetchone():
                c_hash, c_salt = hash_password("cashier123")
                cur.execute(
                    """
                    INSERT INTO users (username, password_hash, salt, role)
                    VALUES ('cashier', ?, ?, 'cashier')
                    """,
                    (c_hash, c_salt)
                )

        return True
    finally:
        conn.close()
