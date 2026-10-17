"""
Billing and Point-of-Sale service.
Handles cart calculations, sequential invoice numbering, atomic checkout, and inventory deduction.
"""
import sqlite3
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from db.connection import get_connection
from utils.currency import rupees_to_paise


def generate_next_bill_number(conn) -> str:
    """
    Generate sequential invoice number for current year (e.g. INV-2026-0001).
    Reads the highest sequence from database within transaction.
    """
    cur = conn.cursor()
    year = datetime.now().year
    prefix = f"INV-{year}-"

    cur.execute(
        """
        SELECT bill_no FROM bills
        WHERE bill_no LIKE ?
        ORDER BY id DESC LIMIT 1
        """,
        (f"{prefix}%",)
    )
    last_row = cur.fetchone()
    if not last_row:
        next_seq = 1
    else:
        try:
            last_seq = int(last_row["bill_no"].split("-")[-1])
            next_seq = last_seq + 1
        except Exception:
            next_seq = 1

    return f"{prefix}{next_seq:04d}"


def calculate_cart_summary(
    cart_items: List[Dict[str, Any]],
    discount_type: str = "Fixed (₹)",
    discount_val: float = 0.0
) -> Dict[str, Any]:
    """
    Calculate taxable subtotal, GST breakup, discounts, and grand total in integer paise.
    Uses standard retail MRP pricing (selling price is retail total inclusive of GST).
    """
    if not cart_items:
        return {
            "items_count": 0,
            "subtotal_paise": 0,
            "gst_total_paise": 0,
            "gross_total_paise": 0,
            "discount_paise": 0,
            "grand_total_paise": 0,
            "gst_slabs": {},
            "detailed_items": []
        }

    gross_total_paise = 0
    total_taxable_paise = 0
    total_gst_paise = 0
    gst_slabs = {}
    detailed_items = []

    for item in cart_items:
        unit_price = int(item["selling_price_paise"])
        qty = float(item["quantity"])
        gst_rate = float(item.get("gst_rate", 0.0))

        # Item gross total
        item_gross_paise = int(
            (Decimal(unit_price) * Decimal(str(qty))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

        # Base taxable price: Base = Gross / (1 + gst_rate/100)
        if gst_rate > 0:
            rate_factor = Decimal("1") + (Decimal(str(gst_rate)) / Decimal("100"))
            item_base_paise = int(
                (Decimal(item_gross_paise) / rate_factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            item_gst_paise = item_gross_paise - item_base_paise
        else:
            item_base_paise = item_gross_paise
            item_gst_paise = 0

        gross_total_paise += item_gross_paise
        total_taxable_paise += item_base_paise
        total_gst_paise += item_gst_paise

        rate_key = f"{gst_rate:.1f}%"
        if rate_key not in gst_slabs:
            gst_slabs[rate_key] = {"taxable": 0, "gst": 0}
        gst_slabs[rate_key]["taxable"] += item_base_paise
        gst_slabs[rate_key]["gst"] += item_gst_paise

        detailed_items.append({
            "product_id": item["id"],
            "name": item["name"],
            "unit": item.get("unit", "pcs"),
            "quantity": qty,
            "unit_price_paise": unit_price,
            "gst_rate": gst_rate,
            "taxable_paise": item_base_paise,
            "gst_amount_paise": item_gst_paise,
            "total_paise": item_gross_paise
        })

    # Discount calculation
    if discount_type == "Percentage (%)":
        pct = max(0.0, min(100.0, float(discount_val)))
        disc_paise = int(
            (Decimal(gross_total_paise) * (Decimal(str(pct)) / Decimal("100"))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
    else:
        disc_paise = max(0, rupees_to_paise(discount_val))

    disc_paise = min(gross_total_paise, disc_paise)
    grand_total_paise = gross_total_paise - disc_paise

    return {
        "items_count": len(cart_items),
        "subtotal_paise": total_taxable_paise,
        "gst_total_paise": total_gst_paise,
        "gross_total_paise": gross_total_paise,
        "discount_paise": disc_paise,
        "grand_total_paise": grand_total_paise,
        "gst_slabs": gst_slabs,
        "detailed_items": detailed_items
    }


def checkout_bill(
    customer_id: Optional[int],
    payment_mode: str,
    cart_items: List[Dict[str, Any]],
    discount_type: str = "Fixed (₹)",
    discount_val: float = 0.0,
    created_by: Optional[int] = 1,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Atomically save invoice, record snapshots, deduct inventory, and update customer credit.
    """
    if not cart_items:
        raise ValueError("Cart is empty. Add products before checking out.")
    if payment_mode not in ("cash", "upi", "card", "credit"):
        raise ValueError(f"Invalid payment mode: '{payment_mode}'.")
    if payment_mode == "credit" and not customer_id:
        raise ValueError("Customer must be selected for Credit (Udhaar) sales.")

    summary = calculate_cart_summary(cart_items, discount_type, discount_val)

    max_retries = 10
    for attempt in range(max_retries):
        conn = get_connection(db_path)
        try:
            with conn:
                cur = conn.cursor()

                # 1. Verify and deduct stock
                for item in summary["detailed_items"]:
                    p_id = item["product_id"]
                    req_qty = item["quantity"]
                    cur.execute("SELECT stock_qty, name FROM products WHERE id = ?", (p_id,))
                    prod = cur.fetchone()
                    if not prod:
                        raise ValueError(f"Product ID {p_id} no longer exists.")
                    if prod["stock_qty"] < req_qty:
                        raise ValueError(
                            f"Insufficient stock for '{prod['name']}'. Available: {prod['stock_qty']}, Requested: {req_qty}."
                        )

                # 2. Generate sequential invoice number
                bill_no = generate_next_bill_number(conn)

                # 3. Insert bill record
                cur.execute(
                    """
                    INSERT INTO bills (
                        bill_no, customer_id, payment_mode,
                        subtotal_paise, discount_paise, gst_total_paise, grand_total_paise,
                        status, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)
                    """,
                    (
                        bill_no,
                        customer_id,
                        payment_mode,
                        summary["subtotal_paise"],
                        summary["discount_paise"],
                        summary["gst_total_paise"],
                        summary["grand_total_paise"],
                        created_by
                    )
                )
                bill_id = cur.lastrowid

                # 4. Insert immutable line item snapshots and update stock
                for item in summary["detailed_items"]:
                    cur.execute(
                        """
                        INSERT INTO bill_items (
                            bill_id, product_id, product_name_snapshot,
                            unit_price_paise_snapshot, gst_rate_snapshot,
                            quantity, gst_amount_paise, total_paise
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            bill_id,
                            item["product_id"],
                            item["name"],
                            item["unit_price_paise"],
                            item["gst_rate"],
                            item["quantity"],
                            item["gst_amount_paise"],
                            item["total_paise"]
                        )
                    )

                    # Deduct stock
                    cur.execute(
                        "UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?",
                        (item["quantity"], item["product_id"])
                    )

                    # Audit stock log
                    cur.execute(
                        """
                        INSERT INTO stock_log (product_id, change_qty, reason, reference_id)
                        VALUES (?, ?, 'sale', ?)
                        """,
                        (item["product_id"], -item["quantity"], bill_no)
                    )

                # 5. If Credit (Udhaar), update customer's pending credit balance
                if payment_mode == "credit" and customer_id:
                    cur.execute(
                        """
                        UPDATE customers
                        SET credit_balance_paise = credit_balance_paise + ?
                        WHERE id = ?
                        """,
                        (summary["grand_total_paise"], customer_id)
                    )

                return {
                    "bill_id": bill_id,
                    "bill_no": bill_no,
                    "summary": summary
                }
        except sqlite3.IntegrityError as e:
            if "bills.bill_no" in str(e) and attempt < max_retries - 1:
                time.sleep(0.02 * (attempt + 1))
                continue
            raise
        finally:
            conn.close()


def get_bill_details(bill_id_or_no, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve full bill information including line items snapshot and customer details."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if isinstance(bill_id_or_no, int) or (isinstance(bill_id_or_no, str) and bill_id_or_no.isdigit()):
            cur.execute(
                """
                SELECT b.*, c.name as customer_name, c.phone as customer_phone
                FROM bills b
                LEFT JOIN customers c ON b.customer_id = c.id
                WHERE b.id = ?
                """,
                (int(bill_id_or_no),)
            )
        else:
            cur.execute(
                """
                SELECT b.*, c.name as customer_name, c.phone as customer_phone
                FROM bills b
                LEFT JOIN customers c ON b.customer_id = c.id
                WHERE b.bill_no = ?
                """,
                (str(bill_id_or_no).strip(),)
            )

        bill_row = cur.fetchone()
        if not bill_row:
            return None

        bill_data = dict(bill_row)

        # Fetch immutable line items snapshot
        cur.execute(
            """
            SELECT * FROM bill_items
            WHERE bill_id = ?
            ORDER BY id ASC
            """,
            (bill_data["id"],)
        )
        bill_data["items"] = [dict(r) for r in cur.fetchall()]
        return bill_data
    finally:
        conn.close()


def get_recent_bills(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve recent bills with customer names."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT b.id, b.bill_no, b.bill_date, b.payment_mode,
                   b.subtotal_paise, b.discount_paise, b.gst_total_paise, b.grand_total_paise,
                   b.status, c.name as customer_name, c.phone as customer_phone
            FROM bills b
            LEFT JOIN customers c ON b.customer_id = c.id
            ORDER BY b.id DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def cancel_bill(
    bill_id: int,
    cancelled_by: int = 1,
    reason: str = "Customer requested cancellation",
    db_path: Optional[str] = None
) -> bool:
    """
    Cancel an invoice atomically:
    1. Mark bill status as 'cancelled'.
    2. Restore inventory quantities in products table.
    3. Insert audit entries in stock_log.
    4. Revert customer credit (udhaar) if it was a credit sale.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
            bill = cur.fetchone()
            if not bill:
                raise ValueError(f"Invoice ID {bill_id} not found.")
            if bill["status"] == "cancelled":
                raise ValueError(f"Invoice {bill['bill_no']} is already cancelled.")

            # 1. Update bill status
            cur.execute(
                """
                UPDATE bills
                SET status = 'cancelled',
                    cancelled_by = ?,
                    cancellation_reason = ?
                WHERE id = ?
                """,
                (cancelled_by, reason.strip() or "Cancelled by operator", bill_id)
            )

            # 2. Fetch items to restore stock
            cur.execute("SELECT product_id, quantity FROM bill_items WHERE bill_id = ?", (bill_id,))
            items = cur.fetchall()

            for it in items:
                p_id = it["product_id"]
                qty = it["quantity"]
                if p_id:
                    # Restore stock
                    cur.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?", (qty, p_id))
                    # Stock log audit
                    cur.execute(
                        """
                        INSERT INTO stock_log (product_id, change_qty, reason, reference_id)
                        VALUES (?, ?, 'bill_cancelled', ?)
                        """,
                        (p_id, qty, bill["bill_no"])
                    )

            # 3. If credit sale, deduct debt from customer balance
            if bill["payment_mode"] == "credit" and bill["customer_id"]:
                cur.execute(
                    """
                    UPDATE customers
                    SET credit_balance_paise = credit_balance_paise - ?
                    WHERE id = ?
                    """,
                    (bill["grand_total_paise"], bill["customer_id"])
                )

        return True
    finally:
        conn.close()


def filter_bills(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    payment_mode: Optional[str] = None,
    status: Optional[str] = None,
    search_term: Optional[str] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Query bills with multifaceted filters."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        query = """
            SELECT b.id, b.bill_no, b.bill_date, b.payment_mode,
                   b.subtotal_paise, b.discount_paise, b.gst_total_paise, b.grand_total_paise,
                   b.status, b.cancellation_reason,
                   c.name as customer_name, c.phone as customer_phone
            FROM bills b
            LEFT JOIN customers c ON b.customer_id = c.id
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND date(b.bill_date) >= date(?)"
            params.append(start_date)
        if end_date:
            query += " AND date(b.bill_date) <= date(?)"
            params.append(end_date)
        if customer_id:
            query += " AND b.customer_id = ?"
            params.append(customer_id)
        if payment_mode and payment_mode != "All":
            query += " AND b.payment_mode = ?"
            params.append(payment_mode)
        if status and status != "All":
            query += " AND b.status = ?"
            params.append(status)
        if search_term and search_term.strip():
            term = f"%{search_term.strip()}%"
            query += " AND (b.bill_no LIKE ? OR c.name LIKE ? OR c.phone LIKE ?)"
            params.extend([term, term, term])

        query += " ORDER BY b.id DESC"
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
