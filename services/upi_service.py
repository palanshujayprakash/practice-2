"""
UPI Payment Service.
Generates dynamic NPCI-compliant UPI QR codes with exact bill amounts and merchant details.
Compatible with all Indian UPI Apps (Google Pay, PhonePe, Paytm, BHIM, Cred, Amazon Pay, etc.).
"""
import io
import urllib.parse
from typing import Optional
import qrcode


def build_upi_url(
    upi_id: str,
    payee_name: str,
    amount_rupees: float,
    note: str = "Retail Bill"
) -> str:
    """
    Construct standard NPCI UPI payment deep link URL.
    Format: upi://pay?pa=VPA&pn=NAME&am=AMOUNT&cu=INR&tn=NOTE
    """
    clean_upi = upi_id.strip() if upi_id and upi_id.strip() else "kirana@upi"
    clean_name = payee_name.strip() if payee_name and payee_name.strip() else "Retail Store"
    clean_note = note.strip() if note and note.strip() else "Retail Bill"
    valid_amount = max(0.0, float(amount_rupees))

    params = {
        "pa": clean_upi,
        "pn": clean_name,
        "am": f"{valid_amount:.2f}",
        "cu": "INR",
        "tn": clean_note,
    }
    return f"upi://pay?{urllib.parse.urlencode(params)}"


def generate_upi_qr_bytes(
    upi_id: str,
    payee_name: str,
    amount_rupees: float,
    note: str = "Retail Bill",
    box_size: int = 8
) -> bytes:
    """
    Generate high-contrast PNG QR code bytes for the dynamic UPI payment request.
    Uses error correction level M and crisp dark-on-white styling.
    """
    upi_url = build_upi_url(upi_id, payee_name, amount_rupees, note)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
