"""Case file: deterministic reconciliation + verifiable findings.

Answers: what the payer discounted, which documents back the
difference, and what the responsible team must check. All math in
whole cents; the model plays no part here.

Verified means: the reference exists and the citation matches the
document (normalized). It does NOT validate the interpretation.
"""
from __future__ import annotations

import re
from dataclasses import replace

from . import rules
from .contracts import Case, Finding, RuleRef
from .money import format_money, parse_amount

BACKED = "backed_difference"
INCONSISTENCY = "inconsistency"
INSUFFICIENT = "insufficient_evidence"
CLINICAL = "clinical_human"
NO_SHORTFALL = "no_shortfall"  # deterministic only: payer covered the agreed value

VALIDITY_RE = re.compile(r"VIGENCIA\s*:\s*(\d{4}-\d{2}-\d{2})\s*\.\.\s*(\d{4}-\d{2}-\d{2})")
SETTLEMENT_LINE_RE = re.compile(r"RENGLON\s+(\d+)\s*:\s*DEBITO\s+\$([\d.,]+)\s*MOTIVO\s*:\s*(.+)")
RATE_RE = re.compile(r"ARANCEL\s*:\s*(.+?)\s+\$([\d.,]+)")


def normalize_citation(text: str) -> str:
    return " ".join(rules.normalize(text or "").split())


def verify_finding(h: Finding, doc_text: str, doc_pages: int) -> tuple[bool, str]:
    if h.page < 1 or h.page > doc_pages:
        return False, f"page {h.page} missing (doc has {doc_pages})"
    frag = normalize_citation(h.excerpt)
    if len(frag) < 12:
        return False, "excerpt too short to verify"
    if frag not in normalize_citation(doc_text):
        return False, "excerpt not found in the document"
    return True, "reference exists and citation matches"


def parse_agreement(text: str) -> dict:
    m = VALIDITY_RE.search(text or "")
    rates = {}
    for mm in RATE_RE.finditer(text or ""):
        try:
            rates[mm.group(1).strip().upper()] = parse_amount("$" + mm.group(2))
        except ValueError:
            continue
    return {"validity": (m.group(1), m.group(2)) if m else None, "rates": rates}


def parse_settlement(text: str) -> dict:
    out = {}
    for mm in SETTLEMENT_LINE_RE.finditer(text or ""):
        try:
            out[int(mm.group(1))] = (parse_amount("$" + mm.group(2)), mm.group(3).strip())
        except ValueError:
            continue
    return out


def agreed_value(procedure: str, payer: str, date: str,
                 agreement_doc: dict | None,
                 rate_fn) -> tuple[int | None, str]:
    if agreement_doc and agreement_doc.get("text"):
        conv = parse_agreement(agreement_doc["text"])
        valid = conv["validity"]
        if not valid:
            return None, "agreement without readable validity"
        if not date:
            return None, "no service date: validity not comparable"
        if not (valid[0] <= date <= valid[1]):
            return None, f"service {date} outside validity {valid[0]}..{valid[1]}"
        val = conv["rates"].get(procedure.upper())
        if val is None:
            return None, f"procedure without rate in agreement ({valid[0]}..{valid[1]})"
        return val, f"agreement {valid[0]}..{valid[1]}"
    if not date:
        return None, "no service date: rate not comparable"
    ar = rate_fn(procedure, payer, date)
    if not ar:
        return None, "no agreed value applies on the date"
    source = f"{ar.get('agreement', 'rate')} {ar.get('version', '')} {ar['validity'][0]}..{ar['validity'][1]}".strip()
    if ar.get("overlapping"):
        source += " [overlapping validity: review]"
    return ar["value_cents"], source


def _hid(case_id: str, no: int, i: int) -> str:
    return f"H-{case_id}-R{no}-{i}"


def investigate(store, case: Case, rate_fn) -> dict:
    docs = {d["role"]: d for d in store.documents(case.id)}
    inv_txt = docs.get("invoice", {}).get("text", "")
    lines, findings, missing = [], [], []
    nh = 0

    def add(line_no: int, kind: str, doc: str, excerpt: str, interpretation: str, lim: str = "") -> None:
        nonlocal nh
        nh += 1
        h = Finding(_hid(case.id, line_no, nh), case.id, line_no, kind, doc, 1, excerpt, interpretation, lim)
        text = docs.get(doc, {}).get("text", "") if doc != "invoice" else (
            inv_txt or " ".join(r.reason for r in case.lines))
        ok, _ = verify_finding(h, text, docs.get(doc, {}).get("pages", 1))
        findings.append(replace(h, verified=ok))

    liq = parse_settlement(docs.get("settlement", {}).get("text", ""))
    for r in case.lines:
        if r.line_no in liq and liq[r.line_no][0] != r.debit_cents:
            missing.append(f"L{r.line_no}: settlement says {format_money(liq[r.line_no][0])}, "
                           f"invoice gives {format_money(r.debit_cents)}")
            add(r.line_no, INCONSISTENCY, "settlement",
                f"RENGLON {r.line_no}: DEBITO {format_money(liq[r.line_no][0])}",
                f"The settlement debits {format_money(liq[r.line_no][0])} but billed minus "
                f"settled gives {format_money(r.debit_cents)}.",
                "Reconcile documents before routing.")
    ok_sum, dif = case.validate()
    if not ok_sum:
        missing.append(f"inconsistent sums: dif {format_money(dif)}")
        add(0, INCONSISTENCY, "invoice", case.lines[0].reason if case.lines else "case",
            f"Line debits differ from the total by {format_money(dif)}.",
            "Check lines against the invoice before routing.")
    for r in case.lines:
        ref, source = agreed_value(r.procedure, case.payer,
                                   case.service_date, docs.get("agreement"),
                                   rate_fn)
        over = None if ref is None else max(0, r.billed_cents - ref)
        gap = None if ref is None else max(0, ref - r.settled_cents)
        lines.append({"line_no": r.line_no, "procedure": r.procedure, "reason": r.reason,
                      "billed_cents": r.billed_cents,
                      "settled_cents": r.settled_cents,
                      "debit_cents": r.debit_cents,
                      "ref_cents": ref, "ref_source": source,
                      "overbilled_cents": over, "payment_gap_cents": gap})
        if rules.is_clinical(r.reason):
            add(r.line_no, CLINICAL, "invoice", r.reason,
                "Reason with clinical content: routed to people.",
                "No economic recommendation; Medical Audit decides.")
        elif ref is None:
            missing.append(f"L{r.line_no}: {source}")
            add(r.line_no, INSUFFICIENT, "invoice", r.reason,
                f"Agreed value cannot be set: {source}.",
                "Stop: ask for service date or current agreement.")
        elif gap > 0:
            add(r.line_no, BACKED, "invoice", r.reason,
                f"Billed {format_money(r.billed_cents)} vs agreed "
                f"{format_money(ref)} ({source}); settled "
                f"{format_money(r.settled_cents)}. Overbilled "
                f"{format_money(over)}; payment shortfall "
                f"{format_money(gap)} (founded amount).",
                "Backs amounts, not the legal merit of the claim.")
        elif gap == 0:
            add(r.line_no, NO_SHORTFALL, "invoice", r.reason,
                f"Settled {format_money(r.settled_cents)} covers agreed "
                f"{format_money(ref)} ({source}); debit "
                f"{format_money(r.debit_cents)} equals overbilling of "
                f"{format_money(over)}. No payment shortfall.",
                "No economic recommendation: a human must accept the "
                "debit or adjust billing.")
    gaps = [l["payment_gap_cents"] for l in lines]
    overs = [l["overbilled_cents"] for l in lines]
    total_gap = sum(gaps) if all(g is not None for g in gaps) else None
    total_over = sum(overs) if all(o is not None for o in overs) else None
    rule: RuleRef = rules.evaluate(" | ".join(r.reason for r in case.lines))
    kinds = {h.kind for h in findings}
    if CLINICAL in kinds:
        team, action = "Medical Audit", "route_human"
        step = "Route to people: there is clinical content."
    elif INCONSISTENCY in kinds or INSUFFICIENT in kinds or rule.team == rules.PENDING:
        team = rule.team if rule.team != rules.PENDING else rules.PENDING
        action = "request_extension"
        step = "Ask for clarification or missing documents before deciding."
    elif total_gap and total_gap > 0:
        team, action = rule.team, "claim"
        step = (f"Backed: route to {rule.team} for claiming "
                f"{format_money(total_gap)} of "
                f"{format_money(case.total_debit_cents)} debit "
                f"(overbilled {format_money(total_over)} is not claimable).")
    else:
        team, action = rule.team, "no_claim"
        step = ("No payment shortfall: debit matches overbilling; "
                "a human must accept the debit or adjust billing.")
    return {"lines": lines, "findings": findings, "missing": missing,
            "rule": rule, "team": team, "action": action,
            "next_step": step, "sums_ok": ok_sum, "dif_cents": dif,
            "total_gap_cents": total_gap,
            "total_overbilled_cents": total_over}
