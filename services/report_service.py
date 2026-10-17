"""
Reporting & Business Analytics Service.
Generates daily/monthly sales velocity, top-selling items, GST tax slab breakdowns,
and multi-sheet Excel reports via openpyxl.
"""
import io
from typing import Optional, Dict, Any, List
import pandas as pd
from db.connection import get_connection
from services.product_service import get_low_stock_products
from utils.currency import paise_to_rupees_decimal, format_rupees


def get_sales_kpis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve overarching revenue, tax, and bills metrics for date range."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        query = """
            SELECT COUNT(id) as total_bills,
                   COALESCE(SUM(subtotal_paise), 0) as total_taxable,
                   COALESCE(SUM(gst_total_paise), 0) as total_gst,
                   COALESCE(SUM(discount_paise), 0) as total_discount,
                   COALESCE(SUM(grand_total_paise), 0) as total_revenue
            FROM bills
            WHERE status = 'completed'
        """
        params = []
        if start_date:
            query += " AND date(bill_date) >= date(?)"
            params.append(start_date)
        if end_date:
            query += " AND date(bill_date) <= date(?)"
            params.append(end_date)

        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else {
            "total_bills": 0,
            "total_taxable": 0,
            "total_gst": 0,
            "total_discount": 0,
            "total_revenue": 0
        }
    finally:
        conn.close()


def get_daily_sales_data(days: int = 30, db_path: Optional[str] = None) -> pd.DataFrame:
    """Retrieve daily revenue and bill counts for recent days."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date(bill_date) as sale_date,
                   COUNT(id) as bill_count,
                   COALESCE(SUM(grand_total_paise), 0) as revenue_paise,
                   COALESCE(SUM(gst_total_paise), 0) as gst_paise
            FROM bills
            WHERE status = 'completed' AND date(bill_date) >= date('now', '-' || ? || ' days')
            GROUP BY date(bill_date)
            ORDER BY sale_date ASC
            """,
            (days,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return pd.DataFrame(columns=["Date", "Revenue (₹)", "GST (₹)", "Bills Count"])

        data = []
        for r in rows:
            data.append({
                "Date": r["sale_date"],
                "Revenue (₹)": float(paise_to_rupees_decimal(r["revenue_paise"])),
                "GST (₹)": float(paise_to_rupees_decimal(r["gst_paise"])),
                "Bills Count": r["bill_count"]
            })
        return pd.DataFrame(data)
    finally:
        conn.close()


def get_top_selling_products(limit: int = 10, db_path: Optional[str] = None) -> pd.DataFrame:
    """Retrieve top-selling products by quantity and revenue."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT bi.product_name_snapshot as item_name,
                   SUM(bi.quantity) as total_qty,
                   SUM(bi.total_paise) as total_revenue_paise,
                   COUNT(DISTINCT bi.bill_id) as orders_count
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            WHERE b.status = 'completed'
            GROUP BY bi.product_name_snapshot
            ORDER BY total_qty DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return pd.DataFrame(columns=["Item", "Quantity Sold", "Revenue (₹)", "Orders Count"])

        data = []
        for r in rows:
            data.append({
                "Item": r["item_name"],
                "Quantity Sold": r["total_qty"],
                "Revenue (₹)": float(paise_to_rupees_decimal(r["total_revenue_paise"])),
                "Orders Count": r["orders_count"]
            })
        return pd.DataFrame(data)
    finally:
        conn.close()


def get_gst_slab_breakdown(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[str] = None
) -> pd.DataFrame:
    """Calculate GST collected across tax slabs (0%, 5%, 12%, 18%, 28%)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        query = """
            SELECT bi.gst_rate_snapshot as slab,
                   COALESCE(SUM(bi.total_paise - bi.gst_amount_paise), 0) as taxable_paise,
                   COALESCE(SUM(bi.gst_amount_paise), 0) as gst_paise,
                   COALESCE(SUM(bi.total_paise), 0) as gross_paise
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            WHERE b.status = 'completed'
        """
        params = []
        if start_date:
            query += " AND date(b.bill_date) >= date(?)"
            params.append(start_date)
        if end_date:
            query += " AND date(b.bill_date) <= date(?)"
            params.append(end_date)

        query += " GROUP BY bi.gst_rate_snapshot ORDER BY bi.gst_rate_snapshot ASC"
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return pd.DataFrame(columns=["GST Slab", "Taxable (₹)", "CGST (₹)", "SGST (₹)", "Total GST (₹)", "Gross (₹)"])

        data = []
        for r in rows:
            taxable = float(paise_to_rupees_decimal(r["taxable_paise"]))
            tot_gst = float(paise_to_rupees_decimal(r["gst_paise"]))
            gross = float(paise_to_rupees_decimal(r["gross_paise"]))
            half_gst = round(tot_gst / 2.0, 2)
            data.append({
                "GST Slab": f"{r['slab']}%",
                "Taxable (₹)": taxable,
                "CGST (₹)": half_gst,
                "SGST (₹)": round(tot_gst - half_gst, 2),
                "Total GST (₹)": tot_gst,
                "Gross (₹)": gross
            })
        return pd.DataFrame(data)
    finally:
        conn.close()


def export_reports_to_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[str] = None
) -> bytes:
    """Generate multi-tab Excel workbook containing sales, GST, item sales, and low stock."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()

        # 1. Bills data
        b_query = """
            SELECT b.bill_no, b.bill_date, b.payment_mode, b.status,
                   c.name as customer_name, c.phone as customer_phone,
                   b.subtotal_paise, b.discount_paise, b.gst_total_paise, b.grand_total_paise
            FROM bills b
            LEFT JOIN customers c ON b.customer_id = c.id
            WHERE 1=1
        """
        b_params = []
        if start_date:
            b_query += " AND date(b.bill_date) >= date(?)"
            b_params.append(start_date)
        if end_date:
            b_query += " AND date(b.bill_date) <= date(?)"
            b_params.append(end_date)
        b_query += " ORDER BY b.id DESC"

        cur.execute(b_query, b_params)
        bills_raw = [dict(r) for r in cur.fetchall()]

        bills_df_data = []
        for r in bills_raw:
            bills_df_data.append({
                "Bill No": r["bill_no"],
                "Date": r["bill_date"],
                "Customer": r["customer_name"] or "Walk-in",
                "Phone": r["customer_phone"] or "-",
                "Payment Mode": r["payment_mode"].upper(),
                "Taxable (₹)": float(paise_to_rupees_decimal(r["subtotal_paise"])),
                "GST (₹)": float(paise_to_rupees_decimal(r["gst_total_paise"])),
                "Discount (₹)": float(paise_to_rupees_decimal(r["discount_paise"])),
                "Total (₹)": float(paise_to_rupees_decimal(r["grand_total_paise"])),
                "Status": r["status"].upper(),
            })
        df_bills = pd.DataFrame(bills_df_data)

        # 2. GST Breakdown
        df_gst = get_gst_slab_breakdown(start_date, end_date, db_path)

        # 3. Top Items
        df_top = get_top_selling_products(limit=50, db_path=db_path)

        # 4. Low Stock
        low_items = get_low_stock_products(db_path)
        low_df_data = []
        for it in low_items:
            low_df_data.append({
                "Barcode": it["barcode"] or "-",
                "Item Name": it["name"],
                "Category": it["category"],
                "Stock": it["stock_qty"],
                "Min Alert": it["min_stock_qty"],
                "Selling Price (₹)": float(paise_to_rupees_decimal(it["selling_price_paise"]))
            })
        df_low = pd.DataFrame(low_df_data)

        # Write to openpyxl buffer
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_bills.to_excel(writer, sheet_name="Invoices Summary", index=False)
            df_gst.to_excel(writer, sheet_name="GST Tax Slabs", index=False)
            df_top.to_excel(writer, sheet_name="Top Selling Items", index=False)
            df_low.to_excel(writer, sheet_name="Low Stock Inventory", index=False)

        return buffer.getvalue()
    finally:
        conn.close()
