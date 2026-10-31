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


def has_approved_review(store: SyntheticStore, proposal_id: str) -> bool:
    """True when a human approved this proposal (history is the record)."""
    prop = store.get_proposal(proposal_id)
    if not prop:
        return False
    for h in store.history(prop["case_id"]):
        if h[1] == "review" and (h[4] or "").startswith(
                f"proposal {proposal_id} approved"):
            return True
    return False


def _check_decision_amounts(decision: str, recoverable: int,
                            accepted: int) -> None:
    if decision == "pending":
        if recoverable or accepted:
            raise ValueError("pending reply must carry zero amounts")
    elif decision == "recovered":
        if recoverable <= 0 or accepted:
            raise ValueError("recovered reply needs pursued>0 and accepted 0")
    elif decision == "accepted":
        if accepted <= 0 or recoverable:
            raise ValueError("accepted reply needs accepted>0 and pursued 0")
    elif decision == "partial":
        if recoverable <= 0 or accepted <= 0:
            raise ValueError("partial reply needs both amounts > 0")


def followup(store: SyntheticStore, proposal_id: str, decision: str,
             recoverable_cents: int, accepted_cents: int,
             owner: str, date: str = "", note: str = "") -> dict:
    """LEGACY (superseded by debit_ai.tasks): team reply with amounts.

    Kept readable for old records and unit tests; it is NOT part of
    the confirmed circuit and has no UI/API anymore. Do not use for
    new flows: per-task answers, debitos verification, per-line
    resolution, rebilling and recovery live in debit_ai.tasks.

    Invariants (whole cents):
    - amounts are ints >= 0 and their sum never exceeds the case debit;
    - decision and amounts cohere (pending 0/0, recovered pursued>0,
      accepted accepted>0, partial both>0);
    - the proposal must carry an approved human review first.
    Corrections overwrite the stored reply, but history keeps
    before/after on every save. No accounting state is invented:
    decision=recovered asserts the pursued amount WAS recovered.
    """
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
    total = store.get_case(prop["case_id"]).total_debit_cents
    if recoverable_cents + accepted_cents > total:
        raise ValueError(
            f"amounts exceed case debit {total}")
    _check_decision_amounts(decision, recoverable_cents, accepted_cents)
    if not has_approved_review(store, proposal_id):
        raise ValueError("proposal needs an approved review before a team reply")
    prev = store.get_followup(proposal_id)
    before = ("no reply" if prev is None else
              f"{prev['decision']}: recoverable {prev['recoverable_cents']} "
              f"accepted {prev['accepted_cents']}")
    store.save_followup(proposal_id, decision, recoverable_cents,
                        accepted_cents, owner.strip(), date,
                        note.strip())
    store.log(prop["case_id"], "followup",
              f"{decision}: recoverable {recoverable_cents} accepted {accepted_cents}",
              before=before,
              after=f"reply {prop['team']} by {owner.strip()}")
    return store.get_followup(proposal_id)
