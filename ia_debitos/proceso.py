"""Proceso administrativo determinista: prioridad, SLA, checklist, seguimiento."""
from __future__ import annotations

from datetime import date

from . import rules

P1_DESDE = 100000000  # $1.000.000 en centavos
P2_DESDE = 50000000  # $500.000 en centavos
SLA_DIAS = 5


def prioridad(total_cents: int) -> str:
    if total_cents > P1_DESDE:
        return "P1"
    if total_cents >= P2_DESDE:
        return "P2"
    return "P3"


def sumar_habiles(desde_iso: str, n: int = SLA_DIAS) -> str:
    actual = date.fromisoformat(desde_iso[:10])
    k = 0
    while k < n:
        actual = actual.fromordinal(actual.toordinal() + 1)
        if actual.weekday() < 5:
            k += 1
    return actual.isoformat()


def checklist(caso, inv: dict) -> list[dict]:
    motivos = rules.normalizar(" ".join(r.motivo for r in caso.renglones))
    return [
        {"item": "Renglones", "valor": str(len(caso.renglones)), "estado": "ok"},
        {"item": "Sumas", "valor": "conciliado" if inv["sumas_ok"] else "difiere",
         "estado": "ok" if inv["sumas_ok"] else "mal"},
        {"item": "Coseguros", "valor": "identificados" if "coseguro" in motivos else "no identificados",
         "estado": "ok" if "coseguro" in motivos else "aviso"},
        {"item": "Convenio", "valor": inv["renglones"][0]["fuente_ref"] if inv["renglones"] else "—",
         "estado": "ok" if all(r["ref_cents"] is not None for r in inv["renglones"]) else "aviso"},
        {"item": "Responsable", "valor": "pendiente de revisión", "estado": "aviso"},
    ]
