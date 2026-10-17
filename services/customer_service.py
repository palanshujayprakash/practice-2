"""
Customer directory & Udhaar (credit) ledger service.
"""
from typing import Optional, List, Dict, Any
from db.connection import get_connection


def get_all_customers(search_term: str = "", db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve customers matching optional search term (name or phone)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        query = "SELECT * FROM customers WHERE 1=1"
        params = []
        if search_term and search_term.strip():
            term = f"%{search_term.strip()}%"
            query += " AND (name LIKE ? OR phone LIKE ?)"
            params.extend([term, term])
        query += " ORDER BY name ASC"
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_customer_by_id(customer_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve single customer by ID."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_customer_by_phone(phone: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve single customer by exact phone number."""
    if not phone or not phone.strip():
        return None
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers WHERE phone = ?", (phone.strip(),))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_customer(
    name: str,
    phone: str,
    address: str = "",
    db_path: Optional[str] = None
) -> int:
    """Create a new customer with phone validation."""
    if not name or not name.strip():
        raise ValueError("Customer Name is mandatory.")
    clean_phone = phone.strip()
    if not clean_phone:
        raise ValueError("Phone number is mandatory.")

    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM customers WHERE phone = ?", (clean_phone,))
            existing = cur.fetchone()
            if existing:
                raise ValueError(f"Customer with phone '{clean_phone}' already exists (ID: {existing['id']}).")

            cur.execute(
                """
                INSERT INTO customers (name, phone, address, credit_balance_paise)
                VALUES (?, ?, ?, 0)
                """,
                (name.strip(), clean_phone, address.strip())
            )
            return cur.lastrowid
    finally:
        conn.close()


def update_customer_credit(
    customer_id: int,
    delta_paise: int,
    db_path: Optional[str] = None
) -> bool:
    """Adjust pending credit (udhaar). Positive increases debt, negative decreases."""
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE customers
                SET credit_balance_paise = credit_balance_paise + ?
                WHERE id = ?
                """,
                (delta_paise, customer_id)
            )
        return True
    finally:
        conn.close()


def get_customers_with_stats(search_term: str = "", db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve customers with total purchases and active invoices count."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        query = """
            SELECT c.*,
                   COUNT(b.id) as total_bills_count,
                   COALESCE(SUM(CASE WHEN b.status = 'completed' THEN b.grand_total_paise ELSE 0 END), 0) as total_spent_paise
            FROM customers c
            LEFT JOIN bills b ON c.id = b.customer_id
            WHERE 1=1
        """
        params = []
        if search_term and search_term.strip():
            term = f"%{search_term.strip()}%"
            query += " AND (c.name LIKE ? OR c.phone LIKE ?)"
            params.extend([term, term])

        query += " GROUP BY c.id ORDER BY c.name ASC"
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def record_customer_payment(
    customer_id: int,
    payment_amount_paise: int,
    payment_mode: str = "cash",
    notes: str = "",
    db_path: Optional[str] = None
) -> bool:
    """
    Settle customer's pending credit balance (udhaar).
    Reduces credit_balance_paise by payment_amount_paise.
    """
    if payment_amount_paise <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT credit_balance_paise, name FROM customers WHERE id = ?", (customer_id,))
            cust = cur.fetchone()
            if not cust:
                raise ValueError(f"Customer ID {customer_id} not found.")

            cur.execute(
                """
                UPDATE customers
                SET credit_balance_paise = MAX(0, credit_balance_paise - ?)
                WHERE id = ?
                """,
                (payment_amount_paise, customer_id)
            )
        return True
    finally:
        conn.close()


def update_customer_details(
    customer_id: int,
    name: str,
    phone: str,
    address: str = "",
    db_path: Optional[str] = None
) -> bool:
    """Update customer contact details."""
    if not name.strip() or not phone.strip():
        raise ValueError("Name and Phone are mandatory.")

    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM customers WHERE phone = ? AND id != ?", (phone.strip(), customer_id))
            if cur.fetchone():
                raise ValueError(f"Phone '{phone.strip()}' is already used by another customer.")

            cur.execute(
                """
                UPDATE customers
                SET name = ?, phone = ?, address = ?
                WHERE id = ?
                """,
                (name.strip(), phone.strip(), address.strip(), customer_id)
            )
        return True
    finally:
        conn.close()

