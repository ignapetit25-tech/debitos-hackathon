"""Per-line task circuit (confirmed owner process).

One case has many debit lines; one line may need many sector tasks.
Lifecycle per task:
  assigned -> pending_verification -> verified
                 \\-> returned -> (answer again) -> pending_verification
The sector answers WITH backing (document or precise reference);
DEBITOS verifies sufficiency and correspondence. Answering never
closes a task; only debitos verification does. Returns keep the
prior answer and state what is missing (kept for recurrent-issue
tracking: payer allegation vs sector verification vs debitos
confirmation are never mixed).

Then, per LINE (never mass close):
  resolution (individual) -> rebilling invoice -> recovery evidence.
A rebilling invoice is NOT recovered money. Recovery is confirmed
only by the payer's credit note or by cancellation (payment) of
the rebilling invoice, with evidence recorded. Partial payments
and receipt splitting are NOT defined: one rebilling per line and
one recovery per rebilling in this version.

Amounts are int cents. Checks are arithmetic only; no merit,
claimable-amount or overbilling conclusion is ever derived here.
"""
from __future__ import annotations

from datetime import datetime

from .synthetic import SyntheticStore

TEAMS = ("Agreements", "Billing", "Medical Audit", "Pharmacy")
STATES = ("assigned", "pending_verification", "verified", "returned")
RECOVERY_METHODS = ("credit_note", "rebilling_paid")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _need(value: str, what: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{what} is required")
    return value


def _need_int(value, what: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{what} must be an int >= 0 (cents)")
    return value


def _line_nos(store: SyntheticStore, case_id: str) -> set[int]:
    return {r.line_no for r in store.get_case(case_id).lines}


def create_task(store: SyntheticStore, case_id: str, line_no: int,
                team: str, motive: str, assignee: str = "") -> dict:
    """Assign a task: one line + one team + the literal motive it answers."""
    if line_no not in _line_nos(store, case_id):
        raise KeyError(f"line {line_no} not in case {case_id}")
    if team not in TEAMS:
        raise ValueError(f"unknown team: {team}")
    motive = _need(motive, "literal motive")
    task = {"id": store.new_task_id(case_id), "case_id": case_id,
            "line_no": line_no, "team": team, "motive": motive,
            "assignee": (assignee or "").strip(), "state": "assigned",
            "created_at": _now(), "updated_at": _now()}
    store.save_task(task)
    store.log(case_id, "task",
              f"{task['id']} L{line_no} -> {team}: {motive[:120]}",
              before="no task", after="assigned")
    return task


def answer_task(store: SyntheticStore, task_id: str, responder: str,
                response: str, backing_ref: str) -> dict:
    """Sector reply WITH backing. Moves to pending_verification; the
    task stays open (answering never closes it)."""
    task = store.get_task(task_id)
    if not task:
        raise KeyError(f"task not found: {task_id}")
    if task["state"] not in ("assigned", "returned"):
        raise ValueError(f"task {task_id} is {task['state']}, not answerable")
    responder = _need(responder, "responder")
    response = _need(response, "response")
    backing_ref = _need(backing_ref, "backing reference (document or "
                                     "precise accessible reference)")
    before = f"{task['state']}: {task['response'][:80]}"
    store.update_task(task_id, state="pending_verification",
                      responder=responder, response=response,
                      backing_ref=backing_ref, updated_at=_now())
    store.log(task["case_id"], "task",
              f"{task_id} answered by {responder}; backing: {backing_ref[:120]}",
              before=before, after="pending_verification")
    return store.get_task(task_id)


def verify_task(store: SyntheticStore, task_id: str, reviewer: str,
                note: str = "") -> dict:
    """Debitos accepts the backing as sufficient and corresponding."""
    task = store.get_task(task_id)
    if not task:
        raise KeyError(f"task not found: {task_id}")
    if task["state"] != "pending_verification":
        raise ValueError(f"task {task_id} is {task['state']}, "
                         f"nothing to verify")
    reviewer = _need(reviewer, "debitos reviewer")
    store.update_task(task_id, state="verified", return_note="",
                      updated_at=_now())
    store.log(task["case_id"], "task_verify",
              f"{task_id} verified by {reviewer}" + (f": {note}" if note else ""),
              before="pending_verification", after="verified")
    return store.get_task(task_id)


def return_task(store: SyntheticStore, task_id: str, reviewer: str,
                missing: str) -> dict:
    """Debitos sends the task back: the prior answer is preserved in
    history and the note states what must be completed/corrected."""
    task = store.get_task(task_id)
    if not task:
        raise KeyError(f"task not found: {task_id}")
    if task["state"] != "pending_verification":
        raise ValueError(f"task {task_id} is {task['state']}, "
                         f"nothing to return")
    reviewer = _need(reviewer, "debitos reviewer")
    missing = _need(missing, "what is missing (return note)")
    before = f"answer by {task['responder']}: {task['response'][:100]}"
    store.update_task(task_id, state="returned", return_note=missing,
                      updated_at=_now())
    store.log(task["case_id"], "task_return",
              f"{task_id} returned by {reviewer}: {missing[:160]}",
              before=before, after="returned")
    return store.get_task(task_id)


def task_returns(store: SyntheticStore, case_id: str) -> list[tuple]:
    """Return events for recurrent-issue tracking (team + cause kept)."""
    return [h for h in store.history(case_id) if h[1] == "task_return"]


def resolve_line(store: SyntheticStore, case_id: str, line_no: int,
                 decided_by: str, decision: str, note: str = "") -> dict:
    """Individual per-line administrative resolution. Requires every
    task of the line verified (pending ones are listed, never
    skipped). One resolution per line; no mass close."""
    if line_no not in _line_nos(store, case_id):
        raise KeyError(f"line {line_no} not in case {case_id}")
    if store.get_resolution(case_id, line_no):
        raise ValueError(f"line {line_no} already resolved")
    line_tasks = [t for t in store.list_tasks(case_id)
                  if t["line_no"] == line_no]
    if not line_tasks:
        raise ValueError(f"line {line_no} has no tasks to consider")
    pending = [f"{t['id']} ({t['state']})" for t in line_tasks
               if t["state"] != "verified"]
    if pending:
        raise ValueError("line still has unverified tasks: " +
                         ", ".join(pending))
    decided_by = _need(decided_by, "decided_by")
    decision = _need(decision, "administrative decision")
    res = {"id": f"R-{case_id}-L{line_no}", "case_id": case_id,
           "line_no": line_no, "decided_by": decided_by,
           "decision": decision, "note": (note or "").strip(),
           "created_at": _now()}
    store.save_resolution(res)
    store.log(case_id, "resolution",
              f"L{line_no} resolved by {decided_by}: {decision[:140]} "
              f"(considers {len(line_tasks)} task(s))",
              before="unresolved", after=res["id"])
    return res


def record_rebilling(store: SyntheticStore, case_id: str, line_no: int,
                     number: str, amount_cents: int, payer: str,
                     date: str = "", note: str = "") -> dict:
    """Register the rebilling invoice linked to the line resolution:
    original invoice -> line -> resolution -> rebilling. The new
    invoice is NOT recovered money. One rebilling per line."""
    res = store.get_resolution(case_id, line_no)
    if not res:
        raise ValueError(f"line {line_no} has no resolution yet")
    number = _need(number, "rebilling number")
    payer = _need(payer, "payer")
    amount_cents = _need_int(amount_cents, "rebilling amount")
    if any(r["line_no"] == line_no
           for r in store.list_rebillings(case_id)):
        raise ValueError(f"line {line_no} already has a rebilling "
                         f"(multi-rebilling is undefined: ask first)")
    rb = {"id": f"RB-{case_id}-L{line_no}", "case_id": case_id,
          "line_no": line_no, "resolution_id": res["id"], "number": number,
          "amount_cents": amount_cents, "payer": payer,
          "date": (date or "").strip(), "note": (note or "").strip(),
          "created_at": _now()}
    store.save_rebilling(rb)
    store.log(case_id, "rebilling",
              f"{rb['id']} {number} {amount_cents}c {payer} "
              f"(from {res['id']}; NOT recovered money)",
              before="no rebilling", after=rb["id"])
    return rb


def record_recovery(store: SyntheticStore, rebilling_id: str, method: str,
                    reference: str, confirmed_by: str,
                    amount_cents: int | None = None, date: str = "",
                    note: str = "") -> dict:
    """Confirm recovery with evidence: the payer's credit note or the
    cancelled (paid) rebilling invoice. The amount, when given, is an
    observed fact from the evidence; NO partial/complete status is
    derived from amounts. One recovery per rebilling."""
    rb = store.get_rebilling(rebilling_id)
    if not rb:
        raise KeyError(f"rebilling not found: {rebilling_id}")
    if method not in RECOVERY_METHODS:
        raise ValueError(f"unknown recovery method: {method}")
    if store.get_recovery_by_rebilling(rebilling_id):
        raise ValueError(f"{rebilling_id} already has a recorded recovery "
                         f"(partial/multiple payments undefined: ask first)")
    reference = _need(reference, "evidence reference")
    confirmed_by = _need(confirmed_by, "confirmed_by")
    if amount_cents is not None:
        amount_cents = _need_int(amount_cents, "evidence amount")
    rec = {"id": f"REC-{rebilling_id}", "rebilling_id": rebilling_id,
           "method": method, "reference": reference,
           "confirmed_by": confirmed_by, "amount_cents": amount_cents,
           "date": (date or "").strip(), "note": (note or "").strip(),
           "created_at": _now()}
    store.save_recovery(rec)
    store.log(rb["case_id"], "recovery",
              f"{rec['id']} via {method} {reference[:120]} "
              f"(confirmed by {confirmed_by})",
              before="not recovered", after="recovery recorded")
    return rec
