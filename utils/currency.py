"""
Currency utilities for offline POS.
All internal monetary calculations are performed in integer paise to avoid IEEE-754 float inaccuracies.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Union

NumberLike = Union[int, float, str, Decimal]


def rupees_to_paise(amount: NumberLike) -> int:
    """
    Convert an amount in Rupees (e.g., 100.50, '100.50') to integer paise (10050).
    Uses Decimal with ROUND_HALF_UP.
    """
    if amount is None:
        return 0
    d = Decimal(str(amount).strip() or "0")
    paise = (d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(paise)


def paise_to_rupees_decimal(paise: int) -> Decimal:
    """
    Convert integer paise (e.g. 10050) to Decimal rupees (Decimal('100.50')).
    """
    return (Decimal(paise or 0) / Decimal("100")).quantize(Decimal("0.01"))


def format_rupees(paise: int, symbol: bool = True) -> str:
    """
    Format integer paise for UI display (e.g. '₹100.50' or '100.50').
    Handles negative numbers gracefully.
    """
    sign = "-" if paise < 0 else ""
    abs_paise = abs(paise)
    rupees_part = abs_paise // 100
    paise_part = abs_paise % 100
    prefix = "₹ " if symbol else ""
    return f"{sign}{prefix}{rupees_part:,}.{paise_part:02d}"
