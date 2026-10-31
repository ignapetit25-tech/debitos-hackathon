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
RECOVERY_METHODS = ("credit_note", "rebilling_paid")  # legacy, see record_recovery
RECOGNITION_KINDS = ("financier_credit_note", "provider_credit_note",
                     "treasury_confirmation", "rebilling_paid")
_CREDIT_KINDS = {"financier_credit_note", "provider_credit_note"}
_PAYMENT_KINDS = {"treasury_confirmation", "rebilling_paid"}
ACCOUNTING_KINDS = ("provider_credit_note",)


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
    if store.get_accepted(case_id, line_no):
        raise ValueError(f"line {line_no} was closed as accepted debit")
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
    if store.get_accepted(case_id, line_no):
        raise ValueError(f"line {line_no} was closed as accepted debit: "
                         f"no rebilling")
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
    """LEGACY (superseded by record_recognition): single recovery record
    with a generic method label. Kept readable for old records and unit
    tests; it is NOT part of the confirmed circuit (issuer, partial
    recognition and reconciliation live in recognitions)."""
# NOTE: original docstring preserved below for the old semantics.
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


def record_recognition(store: SyntheticStore, rebilling_id: str, kind: str,
                       amount_cents: int, reference: str, confirmed_by: str,
                       recorded_by: str, date: str, note: str = "") -> dict:
    """Partial or full recognition event against a rebilling invoice.

    The kind identifies the issuer and what the evidence proves
    (financier vs provider credit note vs treasury confirmation vs
    paid rebilling invoice); documentary recognition is never mixed
    with confirmed payment. Several documented events per rebilling
    are allowed; exact-duplicate references are refused. Amounts are
    observed facts; no closure status is derived from them. When a
    remainder is left, it is shown as balance in dispute ("saldo en
    disputa"), which may arrive as a new debit (then the new motive
    is registered and linked for reevaluation).
    """
    rb = store.get_rebilling(rebilling_id)
    if not rb:
        raise KeyError(f"rebilling not found: {rebilling_id}")
    if kind not in RECOGNITION_KINDS:
        raise ValueError(f"unknown recognition kind: {kind}")
    amount_cents = _need_int(amount_cents, "recognized amount")
    reference = _need(reference, "evidence reference")
    confirmed_by = _need(confirmed_by, "issuer or confirming sector")
    recorded_by = _need(recorded_by, "recording owner")
    date = _need(date, "date")
    norm = reference.strip().lower()
    if any(r["reference"].strip().lower() == norm
           for r in store.list_recognitions(rebilling_id)):
        raise ValueError(f"reference already recorded on {rebilling_id}: "
                         f"{reference.strip()[:80]}")
    rec = {"id": store.new_recognition_id(rebilling_id),
           "rebilling_id": rebilling_id, "kind": kind,
           "amount_cents": amount_cents, "reference": reference,
           "confirmed_by": confirmed_by, "recorded_by": recorded_by,
           "date": date.strip(), "note": (note or "").strip(),
           "created_at": _now()}
    store.save_recognition(rec)
    total = recognized_total(store, rebilling_id)
    rest = rb["amount_cents"] - total
    detail = (f"{rec['id']} {kind} {amount_cents}c {reference[:100]} "
              f"(confirmed by {confirmed_by}; recorded by {recorded_by})")
    if rest > 0:
        detail += (f"; recognized {total}c of {rb['amount_cents']}c: "
                   f"balance in dispute {rest}c (may arrive as a new debit)")
    elif rest < 0:
        detail += (f"; recognized {total}c EXCEEDS rebilled "
                   f"{rb['amount_cents']}c: reconcile")
    store.log(rb["case_id"], "recognition", detail,
              before="no recognition" if total == amount_cents else
              f"recognized {total - amount_cents}c",
              after=f"recognized {total}c")
    return rec


def recognized_total(store: SyntheticStore, rebilling_id: str) -> int:
    """Sum of non-duplicate recognition events (observed, not a rule)."""
    return sum(r["amount_cents"] for r in
               store.list_recognitions(rebilling_id)
               if not r["duplicate_of"])


def disputed_balance(store: SyntheticStore, rebilling_id: str) -> int:
    """Rebilled minus recognized; >0 means balance in dispute."""
    rb = store.get_rebilling(rebilling_id)
    if not rb:
        raise KeyError(f"rebilling not found: {rebilling_id}")
    return max(0, rb["amount_cents"] - recognized_total(store, rebilling_id))


def needs_reconciliation(store: SyntheticStore, rebilling_id: str) -> bool:
    """True when credit-note evidence coexists with payment evidence
    unlinked: they may describe the same recognition (confirmed
    ambiguous example). Never auto-merged; a human reconciles."""
    kinds = {r["kind"] for r in store.list_recognitions(rebilling_id)
             if not r["duplicate_of"]}
    return bool(kinds & _CREDIT_KINDS) and bool(kinds & _PAYMENT_KINDS)


def reconcile_recognition(store: SyntheticStore, event_id: str,
                          duplicate_of_id: str, reconciled_by: str,
                          note: str = "") -> dict:
    """Human decision: event_id duplicates duplicate_of_id, so it is
    excluded from recognized totals. Both evidences are preserved."""
    ev = store.get_recognition(event_id)
    base = store.get_recognition(duplicate_of_id)
    if not ev or not base:
        raise KeyError("recognition event not found")
    if ev["rebilling_id"] != base["rebilling_id"]:
        raise ValueError("events belong to different rebillings")
    if event_id == duplicate_of_id:
        raise ValueError("an event cannot duplicate itself")
    if base["duplicate_of"]:
        raise ValueError(f"{duplicate_of_id} is itself a duplicate")
    reconciled_by = _need(reconciled_by, "reconciled_by")
    store.mark_recognition_duplicate(event_id, duplicate_of_id)
    rb = store.get_rebilling(ev["rebilling_id"])
    store.log(rb["case_id"], "reconcile",
              f"{event_id} duplicates {duplicate_of_id} "
              f"(by {reconciled_by})" + (f": {note}" if note else ""),
              before="counted", after="excluded from totals")
    return store.get_recognition(event_id)


def accept_debit(store: SyntheticStore, case_id: str, line_no: int,
                 accepted_by: str, origin: str,
                 corrective: str = "") -> dict:
    """Terminal closure "accepted debit" ("debito aceptado"): debitos
    recognizes the debit stands (own institutional error). Records who
    accepted, the analyzed origin and the corrective line to fix the
    root cause. Requires every task of the line verified; excludes
    resolution/rebilling (closure, not a step toward them)."""
    if line_no not in _line_nos(store, case_id):
        raise KeyError(f"line {line_no} not in case {case_id}")
    if store.get_accepted(case_id, line_no):
        raise ValueError(f"line {line_no} already closed as accepted debit")
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
    accepted_by = _need(accepted_by, "accepted_by")
    origin = _need(origin, "analyzed origin")
    acc = {"id": f"A-{case_id}-L{line_no}", "case_id": case_id,
           "line_no": line_no, "accepted_by": accepted_by, "origin": origin,
           "corrective": (corrective or "").strip(), "created_at": _now()}
    store.save_accepted(acc)
    store.log(case_id, "accepted",
              f"L{line_no} accepted by {accepted_by}: {origin[:140]}",
              before="open", after=acc["id"])
    return acc


def record_accounting_doc(store: SyntheticStore, case_id: str,
                          line_no: int | None, kind: str, number: str,
                          recorded_by: str, amount_cents: int | None = None,
                          date: str = "", note: str = "") -> dict:
    """Accounting-issued document (provider credit note via Contables),
    recorded SEPARATELY from the debitos resolution: no mandatory
    order is imposed, and the document never proves authorization nor
    closes the analysis. Mismatches stay visible (circuit_alerts)."""
    if kind not in ACCOUNTING_KINDS:
        raise ValueError(f"unknown accounting kind: {kind}")
    if line_no is not None and line_no not in _line_nos(store, case_id):
        raise KeyError(f"line {line_no} not in case {case_id}")
    _ = store.get_case(case_id)
    number = _need(number, "document number")
    recorded_by = _need(recorded_by, "recorded_by")
    if amount_cents is not None:
        amount_cents = _need_int(amount_cents, "document amount")
    doc = {"id": store.new_accounting_id(case_id), "case_id": case_id,
           "line_no": line_no, "kind": kind, "number": number,
           "amount_cents": amount_cents, "date": (date or "").strip(),
           "note": (note or "").strip(), "recorded_by": recorded_by,
           "created_at": _now()}
    store.save_accounting_doc(doc)
    where = f"L{line_no}" if line_no is not None else "case"
    store.log(case_id, "accounting_doc",
              f"{doc['id']} {kind} {number} on {where} "
              f"(recorded by {recorded_by}; not an authorization)",
              before="no document", after=doc["id"])
    return doc


def _line_closed(store: SyntheticStore, case_id: str, line_no: int) -> bool:
    return bool(store.get_resolution(case_id, line_no) or
                store.get_accepted(case_id, line_no))


def circuit_alerts(store: SyntheticStore, case_id: str) -> list[str]:
    """Visible mismatches, never auto-resolved: accounting documents
    without debitos closure, ambiguous recognitions, over-recognition."""
    alerts = []
    _ = store.get_case(case_id)
    rbs = store.list_rebillings(case_id)
    if not (store.list_resolutions(case_id) or store.list_accepted(case_id)):
        case_docs = [d for d in store.list_accounting_docs(case_id)
                     if d["line_no"] is None]
        for d in case_docs:
            alerts.append(f"provider credit note {d['number']} recorded "
                          f"without debitos resolution (documents do not "
                          f"substitute authorization)")
    for d in store.list_accounting_docs(case_id):
        if d["line_no"] is not None and not _line_closed(
                store, case_id, d["line_no"]):
            alerts.append(f"provider credit note {d['number']} on "
                          f"L{d['line_no']} without debitos closure "
                          f"(documents do not substitute authorization)")
    for rb in rbs:
        if needs_reconciliation(store, rb["id"]):
            alerts.append(f"{rb['id']}: credit-note and payment evidence "
                          f"coexist unlinked (possible duplicate: reconcile)")
        over = recognized_total(store, rb["id"]) - rb["amount_cents"]
        if over > 0:
            alerts.append(f"{rb['id']}: recognized exceeds rebilled by "
                          f"{over}c: reconcile")
    return alerts
