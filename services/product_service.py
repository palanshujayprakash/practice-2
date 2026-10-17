"""
Product & Inventory service for catalog management, search, validation, and bulk import.
Handles integer paise conversion, barcode lookup, and inventory tracking.
"""
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
from db.connection import get_connection
from utils.currency import rupees_to_paise


def get_all_products(
    search_term: str = "",
    category: str = "All",
    active_only: bool = True,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve products matching optional search term and category."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        query = """
            SELECT id, barcode, name, category, unit,
                   purchase_price_paise, selling_price_paise,
                   gst_rate, stock_qty, min_stock_qty, is_active
            FROM products
            WHERE 1=1
        """
        params = []
        if active_only:
            query += " AND is_active = 1"
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)
        if search_term and search_term.strip():
            term = f"%{search_term.strip()}%"
            query += " AND (name LIKE ? OR barcode LIKE ?)"
            params.extend([term, term])

        query += " ORDER BY name ASC"
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_product_by_id(product_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch single product by ID."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_product_by_barcode(barcode: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch single active product by exact barcode."""
    if not barcode or not barcode.strip():
        return None
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM products WHERE barcode = ? AND is_active = 1",
            (barcode.strip(),)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_product(
    name: str,
    selling_price_paise: int,
    purchase_price_paise: int = 0,
    barcode: Optional[str] = None,
    category: str = "General",
    unit: str = "pcs",
    gst_rate: float = 0.0,
    stock_qty: float = 0.0,
    min_stock_qty: float = 5.0,
    db_path: Optional[str] = None
) -> int:
    """Add a new product with validation."""
    if not name or not name.strip():
        raise ValueError("Product Name cannot be empty.")
    if selling_price_paise < 0:
        raise ValueError("Selling price cannot be negative.")
    if purchase_price_paise < 0:
        raise ValueError("Purchase price cannot be negative.")
    if gst_rate < 0:
        raise ValueError("GST rate cannot be negative.")
    if stock_qty < 0:
        raise ValueError("Initial stock quantity cannot be negative.")
    if min_stock_qty < 0:
        raise ValueError("Minimum stock quantity cannot be negative.")

    barcode_val = barcode.strip() if barcode and barcode.strip() else None

    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            if barcode_val:
                cur.execute("SELECT id FROM products WHERE barcode = ?", (barcode_val,))
                if cur.fetchone():
                    raise ValueError(f"Product with barcode '{barcode_val}' already exists.")

            cur.execute(
                """
                INSERT INTO products (
                    barcode, name, category, unit,
                    purchase_price_paise, selling_price_paise,
                    gst_rate, stock_qty, min_stock_qty, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    barcode_val,
                    name.strip(),
                    category.strip() or "General",
                    unit.strip() or "pcs",
                    purchase_price_paise,
                    selling_price_paise,
                    float(gst_rate),
                    float(stock_qty),
                    float(min_stock_qty)
                )
            )
            prod_id = cur.lastrowid

            # Write initial stock log entry if stock > 0
            if stock_qty > 0:
                cur.execute(
                    """
                    INSERT INTO stock_log (product_id, change_qty, reason, reference_id)
                    VALUES (?, ?, 'initial_stock', 'product_creation')
                    """,
                    (prod_id, float(stock_qty))
                )
            return prod_id
    finally:
        conn.close()


def update_product(
    product_id: int,
    name: str,
    selling_price_paise: int,
    purchase_price_paise: int = 0,
    barcode: Optional[str] = None,
    category: str = "General",
    unit: str = "pcs",
    gst_rate: float = 0.0,
    stock_qty: float = 0.0,
    min_stock_qty: float = 5.0,
    is_active: int = 1,
    db_path: Optional[str] = None
) -> bool:
    """Update existing product details."""
    if not name or not name.strip():
        raise ValueError("Product Name cannot be empty.")
    if selling_price_paise < 0 or purchase_price_paise < 0:
        raise ValueError("Prices cannot be negative.")
    if gst_rate < 0:
        raise ValueError("GST rate cannot be negative.")
    if stock_qty < 0 or min_stock_qty < 0:
        raise ValueError("Stock levels cannot be negative.")

    barcode_val = barcode.strip() if barcode and barcode.strip() else None

    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            if barcode_val:
                cur.execute(
                    "SELECT id FROM products WHERE barcode = ? AND id != ?",
                    (barcode_val, product_id)
                )
                if cur.fetchone():
                    raise ValueError(f"Barcode '{barcode_val}' is already assigned to another product.")

            # Check previous stock for adjustment logging
            cur.execute("SELECT stock_qty FROM products WHERE id = ?", (product_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Product ID {product_id} not found.")

            old_stock = row["stock_qty"]
            diff = float(stock_qty) - float(old_stock)

            cur.execute(
                """
                UPDATE products
                SET barcode = ?, name = ?, category = ?, unit = ?,
                    purchase_price_paise = ?, selling_price_paise = ?,
                    gst_rate = ?, stock_qty = ?, min_stock_qty = ?, is_active = ?
                WHERE id = ?
                """,
                (
                    barcode_val,
                    name.strip(),
                    category.strip() or "General",
                    unit.strip() or "pcs",
                    purchase_price_paise,
                    selling_price_paise,
                    float(gst_rate),
                    float(stock_qty),
                    float(min_stock_qty),
                    int(is_active),
                    product_id
                )
            )

            if abs(diff) > 1e-4:
                cur.execute(
                    """
                    INSERT INTO stock_log (product_id, change_qty, reason, reference_id)
                    VALUES (?, ?, 'manual_adjustment', 'product_edit')
                    """,
                    (product_id, diff)
                )
        return True
    finally:
        conn.close()


def delete_product(product_id: int, soft_delete: bool = True, db_path: Optional[str] = None) -> bool:
    """Delete product (soft-delete by default to protect historical bill snapshots)."""
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            if soft_delete:
                cur.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
            else:
                cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
        return True
    finally:
        conn.close()


def get_low_stock_products(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve products where current stock <= minimum stock threshold."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, barcode, name, category, unit,
                   selling_price_paise, stock_qty, min_stock_qty
            FROM products
            WHERE is_active = 1 AND stock_qty <= min_stock_qty
            ORDER BY (stock_qty - min_stock_qty) ASC, name ASC
            """
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_all_categories(db_path: Optional[str] = None) -> List[str]:
    """Retrieve list of distinct product categories."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != '' ORDER BY category ASC")
        cats = [row["category"] for row in cur.fetchall()]
        if "General" not in cats:
            cats.insert(0, "General")
        return cats
    finally:
        conn.close()


def import_products_from_dataframe(df: pd.DataFrame, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Bulk import products from pandas DataFrame (from CSV or Excel).
    Expected columns (case-insensitive):
    - Name (required)
    - Selling Price / Price (required)
    - Barcode (optional)
    - Category (optional, default 'General')
    - Unit (optional, default 'pcs')
    - Purchase Price / Cost (optional, default 0)
    - GST Rate / GST (optional, default 0)
    - Stock / Quantity (optional, default 0)
    - Min Stock / Alert Stock (optional, default 5)
    """
    if df.empty:
        return {"success": 0, "errors": ["Uploaded file is empty."]}

    # Normalize column names
    col_map = {}
    for col in df.columns:
        c = str(col).strip().lower()
        if "name" in c or "item" in c or "title" in c:
            col_map["name"] = col
        elif "selling" in c or ("price" in c and "purchase" not in c and "cost" not in c):
            col_map["selling_price"] = col
        elif "cost" in c or "purchase" in c or "buy" in c:
            col_map["purchase_price"] = col
        elif "barcode" in c or "code" in c or "upc" in c or "sku" in c:
            col_map["barcode"] = col
        elif "category" in c or "cat" in c:
            col_map["category"] = col
        elif "unit" in c or "uom" in c:
            col_map["unit"] = col
        elif "gst" in c or "tax" in c:
            col_map["gst_rate"] = col
        elif "min" in c and "stock" in c:
            col_map["min_stock_qty"] = col
        elif "stock" in c or "qty" in c or "quantity" in c:
            col_map["stock_qty"] = col

    if "name" not in col_map or "selling_price" not in col_map:
        return {
            "success": 0,
            "errors": ["Missing mandatory columns: 'Name' and 'Selling Price'."]
        }

    success_count = 0
    errors = []

    for idx, row in df.iterrows():
        row_num = idx + 2
        name = str(row[col_map["name"]]).strip()
        if not name or name.lower() == "nan":
            errors.append(f"Row {row_num}: Missing product name.")
            continue

        try:
            raw_sp = row[col_map["selling_price"]]
            sp_paise = rupees_to_paise(raw_sp)
            if sp_paise < 0:
                errors.append(f"Row {row_num} ('{name}'): Selling price cannot be negative.")
                continue
        except Exception:
            errors.append(f"Row {row_num} ('{name}'): Invalid selling price format.")
            continue

        raw_pp = row.get(col_map.get("purchase_price"), 0)
        try:
            pp_paise = rupees_to_paise(raw_pp) if pd.notna(raw_pp) else 0
        except Exception:
            pp_paise = 0

        raw_barcode = row.get(col_map.get("barcode"), "")
        barcode = str(raw_barcode).strip() if pd.notna(raw_barcode) and str(raw_barcode).strip() != "nan" else None

        raw_cat = row.get(col_map.get("category"), "General")
        category = str(raw_cat).strip() if pd.notna(raw_cat) and str(raw_cat).strip() != "nan" else "General"

        raw_unit = row.get(col_map.get("unit"), "pcs")
        unit = str(raw_unit).strip() if pd.notna(raw_unit) and str(raw_unit).strip() != "nan" else "pcs"

        raw_gst = row.get(col_map.get("gst_rate"), 0.0)
        try:
            gst_rate = float(raw_gst) if pd.notna(raw_gst) else 0.0
        except Exception:
            gst_rate = 0.0

        raw_stock = row.get(col_map.get("stock_qty"), 0.0)
        try:
            stock_qty = float(raw_stock) if pd.notna(raw_stock) else 0.0
        except Exception:
            stock_qty = 0.0

        raw_min = row.get(col_map.get("min_stock_qty"), 5.0)
        try:
            min_stock = float(raw_min) if pd.notna(raw_min) else 5.0
        except Exception:
            min_stock = 5.0

        try:
            add_product(
                name=name,
                selling_price_paise=sp_paise,
                purchase_price_paise=pp_paise,
                barcode=barcode,
                category=category,
                unit=unit,
                gst_rate=gst_rate,
                stock_qty=stock_qty,
                min_stock_qty=min_stock,
                db_path=db_path
            )
            success_count += 1
        except Exception as e:
            errors.append(f"Row {row_num} ('{name}'): {str(e)}")

    return {"success": success_count, "errors": errors}
