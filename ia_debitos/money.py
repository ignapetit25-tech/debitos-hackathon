"""Dinero exacto en centavos (int). Jamás floats binarios.

Formato argentino aceptado: "$57.000", "57.000,00", "1.749.497,80".
"""
from __future__ import annotations

import re


def parse_importe(texto: str) -> int:
    """Convierte texto AR a centavos. Levanta ValueError si es inválido."""
    if not isinstance(texto, str):
        raise ValueError("importe no es texto")
    limpio = texto.strip().replace("$", "").replace(" ", "")
    if not re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d{1,2})?|-?\d+(,\d{1,2})?", limpio):
        raise ValueError(f"importe inválido: {texto!r}")
    if "," in limpio:
        enteros, dec = limpio.split(",")
        dec = (dec + "0")[:2]
    else:
        enteros, dec = limpio, "00"
    signo = -1 if enteros.startswith("-") else 1
    enteros = enteros.lstrip("-").replace(".", "")
    return signo * (int(enteros or 0) * 100 + int(dec))


def formato(cents: int) -> str:
    """Centavos a texto AR, ej. 5700000 -> '$57.000,00'."""
    if not isinstance(cents, int):
        raise ValueError("centavos debe ser int")
    signo = "-" if cents < 0 else ""
    cents = abs(cents)
    enteros, dec = divmod(cents, 100)
    grupo = f"{enteros:,}".replace(",", ".")
    return f"{signo}${grupo},{dec:02d}"


def validar_suma(renglones_cents: list[int], total_cents: int) -> tuple[bool, int]:
    """Devuelve (coincide, diferencia_en_centavos)."""
    suma = sum(renglones_cents)
    return suma == total_cents, suma - total_cents
