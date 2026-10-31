"""Exact money in integer cents. Never binary floats.

Accepted Argentine format: "$57.000", "57.000,00", "1.749.497,80".
"""
from __future__ import annotations

import re


def parse_amount(text: str) -> int:
    """AR text to cents. Raises ValueError when invalid."""
    if not isinstance(text, str):
        raise ValueError("amount is not text")
    clean = text.strip().replace("$", "").replace(" ", "")
    if not re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d{1,2})?|-?\d+(,\d{1,2})?", clean):
        raise ValueError(f"invalid amount: {text!r}")
    if "," in clean:
        whole, dec = clean.split(",")
        dec = (dec + "0")[:2]
    else:
        whole, dec = clean, "00"
    sign = -1 if whole.startswith("-") else 1
    whole = whole.lstrip("-").replace(".", "")
    return sign * (int(whole or 0) * 100 + int(dec))


def format_money_us(cents: int) -> str:
    """Cents to US text for the English UI, e.g. 5700000 -> '$57,000.00'."""
    if not isinstance(cents, int):
        raise ValueError("cents must be int")
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole, dec = divmod(cents, 100)
    return f"{sign}${whole:,}.{dec:02d}"


def format_money(cents: int) -> str:
    """Cents to AR text, e.g. 5700000 -> '$57.000,00'.

    Document-domain format (matches parse_amount); UI-facing strings
    use format_money_us instead."""
    if not isinstance(cents, int):
        raise ValueError("cents must be int")
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole, dec = divmod(cents, 100)
    grouped = f"{whole:,}".replace(",", ".")
    return f"{sign}${grouped},{dec:02d}"


def check_sum(line_cents: list[int], total_cents: int) -> tuple[bool, int]:
    """Returns (matches, difference_in_cents)."""
    total = sum(line_cents)
    return total == total_cents, total - total_cents
