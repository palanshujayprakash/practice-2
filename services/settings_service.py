"""
Shop settings service for managing profile, GSTIN, paper sizing, and logo.
"""
from typing import Optional, Dict, Any
from db.connection import get_connection


def get_shop_settings(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve the shop settings record (id=1)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, shop_name, address, phone, gstin, bill_footer, paper_size, logo_blob, upi_id, updated_at
            FROM shop_settings
            WHERE id = 1
            """
        )
        row = cur.fetchone()
        if row:
            d = dict(row)
            if not d.get("upi_id"):
                d["upi_id"] = "kirana@upi"
            return d
        return {
            "id": 1,
            "shop_name": "Apna Kirana & General Store",
            "address": "123 Main Bazaar Road",
            "phone": "+91 98765 43210",
            "gstin": "",
            "bill_footer": "Thank you! Visit again.",
            "paper_size": "80mm",
            "logo_blob": None,
            "upi_id": "kirana@upi",
            "updated_at": None,
        }
    finally:
        conn.close()


def update_shop_settings(
    shop_name: str,
    address: str,
    phone: str,
    gstin: str,
    bill_footer: str,
    paper_size: str = "80mm",
    logo_blob: Optional[bytes] = None,
    keep_existing_logo: bool = True,
    upi_id: str = "kirana@upi",
    db_path: Optional[str] = None
) -> bool:
    """
    Update shop settings row id=1.
    If keep_existing_logo is True and logo_blob is None, the current logo is preserved.
    """
    if not shop_name.strip():
        raise ValueError("Shop Name cannot be empty.")
    if paper_size not in ("80mm", "A4"):
        raise ValueError("Invalid paper size. Must be '80mm' or 'A4'.")

    clean_upi = upi_id.strip() if upi_id and upi_id.strip() else "kirana@upi"

    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.cursor()
            if logo_blob is not None:
                cur.execute(
                    """
                    UPDATE shop_settings
                    SET shop_name = ?, address = ?, phone = ?, gstin = ?, bill_footer = ?, paper_size = ?, logo_blob = ?, upi_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                    """,
                    (shop_name.strip(), address.strip(), phone.strip(), gstin.strip(), bill_footer.strip(), paper_size, logo_blob, clean_upi)
                )
            elif not keep_existing_logo:
                # User explicitly removed logo
                cur.execute(
                    """
                    UPDATE shop_settings
                    SET shop_name = ?, address = ?, phone = ?, gstin = ?, bill_footer = ?, paper_size = ?, logo_blob = NULL, upi_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                    """,
                    (shop_name.strip(), address.strip(), phone.strip(), gstin.strip(), bill_footer.strip(), paper_size, clean_upi)
                )
            else:
                # Keep existing logo
                cur.execute(
                    """
                    UPDATE shop_settings
                    SET shop_name = ?, address = ?, phone = ?, gstin = ?, bill_footer = ?, paper_size = ?, upi_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                    """,
                    (shop_name.strip(), address.strip(), phone.strip(), gstin.strip(), bill_footer.strip(), paper_size, clean_upi)
                )
        return True
    finally:
        conn.close()
