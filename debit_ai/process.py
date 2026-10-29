"""Deterministic back-office process: priority, SLA, checklist, follow-up."""
from __future__ import annotations

from datetime import date

from . import rules

P1_ABOVE = 100000000  # $1.000.000 in cents
P2_ABOVE = 50000000  # $500.000 in cents
SLA_DAYS = 5


def priority(total_cents: int) -> str:
    if total_cents > P1_ABOVE:
        return "P1"
    if total_cents >= P2_ABOVE:
        return "P2"
    return "P3"


def add_business_days(from_iso: str, n: int = SLA_DAYS) -> str:
    cur = date.fromisoformat(from_iso[:10])
    k = 0
    while k < n:
        cur = cur.fromordinal(cur.toordinal() + 1)
        if cur.weekday() < 5:
            k += 1
    return cur.isoformat()


def checklist(case, inv: dict) -> list[dict]:
    reasons = rules.normalize(" ".join(r.reason for r in case.lines))
    return [
        {"item": "Lines", "value": str(len(case.lines)), "state": "ok"},
        {"item": "Sums", "value": "reconciled" if inv["sums_ok"] else "differs",
         "state": "ok" if inv["sums_ok"] else "bad"},
        {"item": "Copays", "value": "identified" if "coseguro" in reasons else "not identified",
         "state": "ok" if "coseguro" in reasons else "warn"},
        {"item": "Agreement", "value": inv["lines"][0]["ref_source"] if inv["lines"] else "—",
         "state": "ok" if all(r["ref_cents"] is not None for r in inv["lines"]) else "warn"},
        {"item": "Owner", "value": "pending review", "state": "warn"},
    ]
