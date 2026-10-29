"""Deterministic drafts (templates + case data). Proposals, not sendings."""
from __future__ import annotations

from .contracts import Case
from .money import format_money


def claim_draft(case: Case, team: str, detail: str) -> dict:
    lines = [f"- L{rl.line_no} {rl.procedure}: {rl.reason} ({format_money(rl.debit_cents)})"
             for rl in case.lines]
    body = (
        f"FICTITIOUS DATA — DEMO\nPayer: {case.payer}\n"
        f"Invoice: {case.invoice} | Total debited: {format_money(case.total_debit_cents)}\n"
        f"Routed team: {team}\nDetail: {detail}\n\nLines:\n" + "\n".join(lines) +
        "\n\nReview and reason extension requested. [DRAFT, requires approval]"
    )
    return {"title": f"Claim draft {case.invoice} ({case.payer})",
            "body": body}


def case_summary(case: Case, proposal_status: str) -> str:
    ok, dif = case.validate()
    return (
        f"Case {case.id} [{case.payer} / {case.invoice}]: "
        f"{len(case.lines)} lines, debit {format_money(case.total_debit_cents)}, "
        f"sums {'OK' if ok else 'DIFFER ' + format_money(dif)}, proposal: {proposal_status}."
    )
