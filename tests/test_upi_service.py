"""
Unit tests for services/upi_service.py.
Verifies NPCI UPI URL construction and PNG QR code generation.
"""
import pytest
from services.upi_service import build_upi_url, generate_upi_qr_bytes


def test_build_upi_url_standard():
    url = build_upi_url(
        upi_id="store@okaxis",
        payee_name="Apna Kirana",
        amount_rupees=150.50,
        note="Bill INV-001"
    )
    assert url.startswith("upi://pay?")
    assert "pa=store%40okaxis" in url or "pa=store@okaxis" in url or "store" in url
    assert "am=150.50" in url
    assert "cu=INR" in url


def test_build_upi_url_fallbacks():
    # Blank or empty fields fallback safely without throwing
    url = build_upi_url(upi_id="", payee_name="", amount_rupees=-50.0, note="")
    assert "pa=kirana%40upi" in url or "pa=kirana@upi" in url or "kirana" in url
    assert "am=0.00" in url
    assert "cu=INR" in url


def test_generate_upi_qr_bytes():
    qr_bytes = generate_upi_qr_bytes(
        upi_id="merchant@upi",
        payee_name="Test Store",
        amount_rupees=299.0,
        note="Grocery Bill"
    )
    assert isinstance(qr_bytes, bytes)
    assert len(qr_bytes) > 500  # Valid PNG image size
    # PNG signature check: \x89PNG\r\n\x1a\n
    assert qr_bytes.startswith(b"\x89PNG\r\n\x1a\n")
