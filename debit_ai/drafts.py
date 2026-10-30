"""Deterministic drafts (templates + case data). Proposals, not sendings."""
from __future__ import annotations

from .contracts import Case
from .money import format_money

# Legacy actions stored before the routing taxonomy; rendered with the
# closest current template so old proposals keep a readable draft.
_LEGACY = {"claim": "route_team", "no_claim": "route_team"}


def _header(case: Case) -> str:
    return (
        f"FICTITIOUS DATA — DEMO\nPayer: {case.payer}\n"
        f"Invoice: {case.invoice} | Total debited: {format_money(case.total_debit_cents)}\n"
    )


def _lines(case: Case) -> str:
    return "\n".join(
        f"- L{rl.line_no} {rl.procedure}: {rl.reason} ({format_money(rl.debit_cents)})"
        for rl in case.lines)


def build_draft(case: Case, team: str, action: str, detail: str = "",
                missing: tuple = ()) -> dict:
    """Draft text for the proposal's action. Drafts propose, never send."""
    action = _LEGACY.get(action, action)
    if action == "route_team":
        body = (
            _header(case) + f"Routed team: {team}\nBasis: {detail}\n"
            f"\nLines (literal payer reasons):\n{_lines(case)}"
            "\n\nTeam verifies the checks; a human resolves. "
            "[DRAFT, requires approval]"
        )
        return {"title": f"Referral {case.invoice} ({case.payer})", "body": body}
    if action == "route_human":
        body = (
            _header(case) + f"Routed to: {team} (people)\nBasis: {detail}\n"
            "\nClinical content detected: no economic recommendation "
            "is made.\n" + f"{team} evaluates. [DRAFT, requires approval]"
        )
        return {"title": f"Clinical routing {case.invoice} ({case.payer})",
                "body": body}
    if action == "request_extension":
        items = "\n".join(f"- {m}" for m in missing) or "- (see proposal)"
        body = (
            _header(case) + f"Pending information for: {team}\nBasis: {detail}\n"
            f"\nMissing:\n{items}"
            "\n\nProvide the missing items; nothing is concluded "
            "meanwhile. [DRAFT, requires approval]"
        )
        return {"title": f"Information request {case.invoice} ({case.payer})",
                "body": body}
    raise ValueError(f"no draft for action: {action}")


def case_summary(case: Case, proposal_status: str) -> str:
    ok, dif = case.validate()
    return (
        f"Case {case.id} [{case.payer} / {case.invoice}]: "
        f"{len(case.lines)} lines, debit {format_money(case.total_debit_cents)}, "
        f"sums {'OK' if ok else 'DIFFER ' + format_money(dif)}, proposal: {proposal_status}."
    )
