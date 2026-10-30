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

VALIDITY_RE = re.compile(r"VIGENCIA\s*:\s*(\d{4}-\d{2}-\d{2})\s*\.\.\s*(\d{4}-\d{2}-\d{2})")
SETTLEMENT_LINE_RE = re.compile(r"RENGLON\s+(\d+)\s*:\s*DEBITO\s+\$([\d.,]+)\s*MOTIVO\s*:\s*(.+)")
RATE_RE = re.compile(r"ARANCEL\s*:\s*(.+?)\s+\$([\d.,]+)")


def normalize_citation(text: str) -> str:
    return " ".join(rules.normalize(text or "").split())


def verify_finding(h: Finding, page_texts: list) -> tuple[bool, str]:
    """Textual match on the INDICATED page only.

    Verified means: the page exists and the excerpt matches it
    (normalized). It does NOT validate the interpretation.
    """
    if h.page < 1 or h.page > len(page_texts):
        return False, f"page {h.page} missing (doc has {len(page_texts)})"
    frag = normalize_citation(h.excerpt)
    if len(frag) < 12:
        return False, "excerpt too short to verify"
    if frag not in normalize_citation(page_texts[h.page - 1] or ""):
        return False, f"excerpt not found on page {h.page}"
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
        if doc != "invoice":
            pages = docs.get(doc, {}).get("page_texts", []) or [
                docs.get(doc, {}).get("text", "")]
        else:
            pages = [inv_txt or " ".join(r.reason for r in case.lines)]
        ok, _ = verify_finding(h, pages)
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
        # Pure arithmetic, no merit: signed differences, None when unknown.
        d1 = None if ref is None else r.billed_cents - ref
        d2 = None if ref is None else ref - r.settled_cents
        lines.append({"line_no": r.line_no, "procedure": r.procedure, "reason": r.reason,
                      "billed_cents": r.billed_cents,
                      "settled_cents": r.settled_cents,
                      "debit_cents": r.debit_cents,
                      "ref_cents": ref, "ref_source": source,
                      "diff_billed_ref_cents": d1,
                      "diff_ref_settled_cents": d2})
        if rules.is_clinical(r.reason):
            add(r.line_no, CLINICAL, "invoice", r.reason,
                "Reason with clinical content: routed to people.",
                "No economic recommendation; Medical Audit decides.")
        elif ref is None:
            missing.append(f"L{r.line_no}: {source}")
            add(r.line_no, INSUFFICIENT, "invoice", r.reason,
                f"Rate check pending: {source}.",
                "Pending information for this check: service date or "
                "current agreement. Nothing is concluded about merit.")
        else:
            add(r.line_no, BACKED, "invoice", r.reason,
                f"Billed {format_money(r.billed_cents)}; agreed "
                f"{format_money(ref)} ({source}); settled "
                f"{format_money(r.settled_cents)}; debit "
                f"{format_money(r.debit_cents)}. Arithmetic only: "
                f"billed-agreed {format_money(d1)}, "
                f"agreed-settled {format_money(d2)}.",
                "No merit conclusion: an arithmetic difference is not "
                "a payer reason. The team verifies; a human resolves.")
    refs = [l["ref_cents"] for l in lines]
    total_ref = sum(refs) if all(v is not None for v in refs) else None
    rule: RuleRef = rules.evaluate(" | ".join(r.reason for r in case.lines))
    kinds = {h.kind for h in findings}
    if CLINICAL in kinds:
        team, action = "Medical Audit", "route_human"
        step = "Route to people: there is clinical content."
    elif INCONSISTENCY in kinds or INSUFFICIENT in kinds or rule.team == rules.PENDING:
        team = rule.team if rule.team != rules.PENDING else rules.PENDING
        action = "request_extension"
        step = "Ask for clarification or missing documents before deciding."
    else:
        team, action = rule.team, "route_team"
        step = (f"Route to {rule.team} for verification. Totals: billed "
                f"{format_money(sum(l['billed_cents'] for l in lines))}, "
                f"agreed {format_money(total_ref)}, settled "
                f"{format_money(sum(l['settled_cents'] for l in lines))}, "
                f"debit {format_money(case.total_debit_cents)}. "
                f"Team verifies; human resolves.")
    return {"lines": lines, "findings": findings, "missing": missing,
            "rule": rule, "team": team, "action": action,
            "next_step": step, "sums_ok": ok_sum, "dif_cents": dif,
            "total_ref_cents": total_ref}
