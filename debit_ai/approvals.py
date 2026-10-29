"""Mandatory human review. No approval, no final disposition."""
from __future__ import annotations

from .contracts import Decision
from .synthetic import SyntheticStore

VERDICTS = ("approved", "rejected")
FOLLOWUP_DECISIONS = ("recovered", "partial", "accepted", "pending")


def review(store: SyntheticStore, proposal_id: str, reviewer: str,
           verdict: str, note: str = "") -> Decision:
    """Record the human decision, leaving it in history (before/after)."""
    if verdict not in VERDICTS:
        raise ValueError(f"invalid verdict: {verdict}")
    prop = store.get_proposal(proposal_id)
    if not prop:
        raise KeyError(f"proposal not found: {proposal_id}")
    if not reviewer.strip():
        raise ValueError("an identified human reviewer is required")
    dec = Decision(proposal_id, reviewer.strip(), verdict, note.strip())
    before = f"proposal {verdict} pending"
    after = f"proposal {prop['id']} {verdict} by {dec.reviewer}"
    store.log(prop["case_id"], "review",
              f"{verdict}: {dec.note}" if dec.note else verdict,
              before, after)
    return dec


def followup(store: SyntheticStore, proposal_id: str, decision: str,
             recoverable_cents: int, accepted_cents: int,
             owner: str, date: str = "", note: str = "") -> dict:
    """Team reply: response with amounts, owner and date."""
    from datetime import date as _date
    if decision not in FOLLOWUP_DECISIONS:
        raise ValueError(f"invalid decision: {decision}")
    for name, v in (("recoverable", recoverable_cents), ("accepted", accepted_cents)):
        if type(v) is not int or v < 0:
            raise ValueError(f"{name} must be an int >= 0")
    if not owner.strip():
        raise ValueError("an identified owner is required")
    if not date:
        date = _date.today().isoformat()
    else:
        _date.fromisoformat(date[:10])
        date = date[:10]
    prop = store.get_proposal(proposal_id)
    if not prop:
        raise KeyError(f"proposal not found: {proposal_id}")
    store.save_followup(proposal_id, decision, recoverable_cents,
                        accepted_cents, owner.strip(), date,
                        note.strip())
    store.log(prop["case_id"], "followup",
              f"{decision}: recoverable {recoverable_cents} accepted {accepted_cents}",
              before="routing without reply",
              after=f"reply {prop['team']} by {owner.strip()}")
    return store.get_followup(proposal_id)
