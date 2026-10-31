"""Standalone demo (stdlib http.server). 100% fictitious data.

127.0.0.1:8931. Provider per IA_PROVIDER (meta by default,
simulated explicit). Full UI: cases, proposal, draft,
human review and history with date/time.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from debit_ai import approvals, drafts, process, tasks
from debit_ai.agent import Agent
from debit_ai.provider import ProviderError, build_provider
from debit_ai.synthetic import SyntheticStore

PORT = int(os.environ.get("IA_DEMO_PORT", "8931"))
STATIC = Path(__file__).resolve().parent / "static"
HTML = (STATIC / "shell.html").read_text(encoding="utf-8")


def _prop_json(prop) -> dict:
    return {"id": prop.id, "case_id": prop.case_id, "team": prop.team,
            "rule": {"team": prop.rule.team, "points": prop.rule.points,
                     "phrases": list(prop.rule.phrases)},
            "action": prop.action, "explanation": prop.explanation,
            "references": list(prop.references),
            "needs_human": prop.needs_human,
            "extraction_confidence": prop.extraction_confidence}


GENERATED = Path(__file__).resolve().parent.parent / "demo_data" / "generated"


def _case_pdf(cid: str) -> Path | None:
    if not cid or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-" for c in cid):
        return None
    pdf = GENERATED / f"{cid}.pdf"
    return pdf if pdf.is_file() else None


def _hal_json(h) -> dict:
    return {"id": h.id, "case_id": h.case_id, "line_no": h.line_no,
            "kind": h.kind, "document": h.document, "page": h.page,
            "excerpt": h.excerpt, "interpretation": h.interpretation,
            "limitations": h.limitations, "verified": h.verified}


def _exp_json(inv: dict) -> dict:
    return {"lines": inv["lines"],
            "findings": [_hal_json(h) for h in inv["findings"]],
            "missing": inv["missing"],
            "rule": {"team": inv["rule"].team, "points": inv["rule"].points,
                     "phrases": list(inv["rule"].phrases)},
            "team": inv["team"], "action": inv["action"],
            "next_step": inv["next_step"],
            "sums_ok": inv["sums_ok"], "dif_cents": inv["dif_cents"],
            "total_ref_cents": inv["total_ref_cents"]}


def _case_json(case, docs: list | None = None) -> dict:
    pdf = _case_pdf(case.id)
    return {"id": case.id, "payer": case.payer, "pdf": pdf.name if pdf else None,
            "service_date": case.service_date,
            "documents": [{"role": d["role"], "filename": d["filename"]} for d in (docs or [])],
            "invoice": case.invoice, "status": case.status,
            "total_debit_cents": case.total_debit_cents,
            "lines": [{"line_no": r.line_no, "procedure": r.procedure,
                       "reason": r.reason,
                       "billed_cents": r.billed_cents,
                       "settled_cents": r.settled_cents,
                       "debit_cents": r.debit_cents}
                      for r in case.lines]}


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


class Handler(BaseHTTPRequestHandler):
    store: SyntheticStore
    agent: Agent

    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            url = urlparse(self.path)
            if url.path.startswith("/static/"):
                name = url.path[len("/static/"):]
                types = {"app.css": "text/css", "app.js": "text/javascript"}
                if name not in types:
                    _json(self, 404, {"error": "static file not found"})
                    return
                raw = (STATIC / name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", types[name] + "; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            elif url.path == "/":
                raw = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            elif url.path == "/api/provider":
                _json(self, 200, {"provider": self.agent.provider.name,
                                  "simulated": self.agent.provider.name == "simulated"})
            elif url.path == "/api/cases":
                _json(self, 200, {"cases": self.agent.query_status()})
            elif url.path == "/api/case":
                cid = parse_qs(url.query).get("case_id", [""])[0]
                _json(self, 200, {"case": _case_json(self.store.get_case(cid),
                                                    self.store.documents(cid))})
            elif url.path == "/api/casefile":
                cid = parse_qs(url.query).get("case_id", [""])[0]
                _json(self, 200, {"casefile": _exp_json(self.agent.investigate(cid))})
            elif url.path == "/api/proposals":
                cid = parse_qs(url.query).get("case_id", [""])[0]
                out = []
                for pid in self.store.list_proposals(cid):
                    prop = self.store.get_proposal(pid)
                    out.append({"id": pid, "team": prop["team"],
                                "action": prop["action"],
                                "degraded": "DEGRADED" in (prop["explanation"] or "")})
                _json(self, 200, {"proposals": out})
            elif url.path == "/api/agreements":
                payer = parse_qs(url.query).get("payer", [""])[0]
                _json(self, 200, {"agreements": self.store.payer_agreements(payer)})
            elif url.path == "/api/process":
                cid = parse_qs(url.query).get("case_id", [""])[0]
                case = self.store.get_case(cid)
                inv = self.agent.investigate(cid)
                revs = [h for h in self.store.history(cid) if h[1] == "review" and h[5]]
                since = revs[0][5][:10] if revs else None
                reviewer = revs[-1][4].rsplit(" by ", 1)[-1] if revs else ""
                chk = process.checklist(case, inv)
                if reviewer:
                    for it in chk:
                        if it["item"] == "Owner":
                            it["value"] = reviewer
                            it["state"] = "ok"
                _json(self, 200, {
                    "priority": process.priority(case.total_debit_cents),
                    "checklist": chk, "reviewer": reviewer,
                    "sla": {"since": since, "days": process.SLA_DAYS,
                            "due": process.add_business_days(since) if since else None}})
            elif url.path == "/api/circuit":
                cid = parse_qs(url.query).get("case_id", [""])[0]
                rbs = self.store.list_rebillings(cid)
                _json(self, 200, {
                    "tasks": self.store.list_tasks(cid),
                    "resolutions": self.store.list_resolutions(cid),
                    "rebillings": rbs,
                    "recoveries": self.store.list_recoveries(cid),
                    "recognitions": self.store.list_case_recognitions(cid),
                    "accepted": self.store.list_accepted(cid),
                    "accounting_docs": self.store.list_accounting_docs(cid),
                    "alerts": tasks.circuit_alerts(self.store, cid),
                    "rebilling_status": {
                        r["id"]: {
                            "recognized_cents": tasks.recognized_total(
                                self.store, r["id"]),
                            "disputed_cents": tasks.disputed_balance(
                                self.store, r["id"])} for r in rbs}})
            elif url.path == "/api/findings":
                pid = parse_qs(url.query).get("proposal_id", [""])[0]
                if not self.store.get_proposal(pid):
                    _json(self, 404, {"error": "proposal not found"})
                    return
                _json(self, 200, {"findings": self.store.get_findings(pid)})
            elif url.path == "/api/pdf":
                cid = parse_qs(url.query).get("case_id", [""])[0]
                role = parse_qs(url.query).get("role", [""])[0]
                try:
                    self.store.get_case(cid)
                except KeyError:
                    _json(self, 404, {"error": "case not found"})
                    return
                pdf = None
                if role in ("invoice", "settlement", "agreement"):
                    for d in self.store.documents(cid):
                        if d["role"] == role:
                            cand = GENERATED / Path(d["filename"]).name
                            pdf = cand if cand.is_file() else None
                else:
                    pdf = _case_pdf(cid)
                if pdf is None:
                    _json(self, 404, {"error": "case has no source PDF"})
                    return
                raw = pdf.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            elif url.path == "/api/history":
                cid = parse_qs(url.query).get("case_id", [""])[0]
                _json(self, 200, {"history": self.agent.history(cid)})
            elif url.path == "/api/draft":
                pid = parse_qs(url.query).get("proposal_id", [""])[0]
                prop = self.store.get_proposal(pid)
                if not prop:
                    _json(self, 404, {"error": "proposal not found"})
                    return
                case = self.store.get_case(prop["case_id"])
                inv = self.agent.investigate(case.id)
                _json(self, 200, drafts.build_draft(
                    case, prop["team"], prop["action"],
                    prop["explanation"][:300], tuple(inv["missing"])))
            else:
                _json(self, 404, {"error": "unknown route"})
        except Exception as exc:
            _json(self, 500, {"error": f"{type(exc).__name__}"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/propose":
                case = self.store.get_case(body["case_id"])
                ok, dif = self.agent.validate_case(case)
                prop = self.agent.propose(body["case_id"])
                _json(self, 200, {"sums_ok": ok, "dif_cents": dif,
                                  "proposal": _prop_json(prop)})
            elif self.path == "/api/task":
                task = tasks.create_task(
                    self.store, body["case_id"], body["line_no"],
                    body.get("team", ""), body.get("motive", ""),
                    body.get("assignee", ""))
                _json(self, 200, {"task": task})
            elif self.path == "/api/task/answer":
                task = tasks.answer_task(
                    self.store, body["task_id"], body.get("responder", ""),
                    body.get("response", ""), body.get("backing_ref", ""))
                _json(self, 200, {"task": task})
            elif self.path == "/api/task/verify":
                task = tasks.verify_task(
                    self.store, body["task_id"], body.get("reviewer", ""),
                    body.get("note", ""))
                _json(self, 200, {"task": task})
            elif self.path == "/api/task/return":
                task = tasks.return_task(
                    self.store, body["task_id"], body.get("reviewer", ""),
                    body.get("missing", ""))
                _json(self, 200, {"task": task})
            elif self.path == "/api/resolution":
                res = tasks.resolve_line(
                    self.store, body["case_id"], body["line_no"],
                    body.get("decided_by", ""), body.get("decision", ""),
                    body.get("note", ""))
                _json(self, 200, {"resolution": res})
            elif self.path == "/api/rebilling":
                rb = tasks.record_rebilling(
                    self.store, body["case_id"], body["line_no"],
                    body.get("number", ""), body.get("amount_cents"),
                    body.get("payer", ""), body.get("date", ""),
                    body.get("note", ""))
                _json(self, 200, {"rebilling": rb})
            elif self.path == "/api/recognition":
                rec = tasks.record_recognition(
                    self.store, body["rebilling_id"], body.get("kind", ""),
                    body.get("amount_cents"), body.get("reference", ""),
                    body.get("confirmed_by", ""), body.get("recorded_by", ""),
                    body.get("date", ""), body.get("note", ""))
                _json(self, 200, {"recognition": rec})
            elif self.path == "/api/reconcile":
                rec = tasks.reconcile_recognition(
                    self.store, body["event_id"], body["duplicate_of"],
                    body.get("reconciled_by", ""), body.get("note", ""))
                _json(self, 200, {"recognition": rec})
            elif self.path == "/api/accept-debit":
                acc = tasks.accept_debit(
                    self.store, body["case_id"], body["line_no"],
                    body.get("accepted_by", ""), body.get("origin", ""),
                    body.get("corrective", ""))
                _json(self, 200, {"accepted": acc})
            elif self.path == "/api/accounting-doc":
                doc = tasks.record_accounting_doc(
                    self.store, body["case_id"], body.get("line_no"),
                    body.get("kind", ""), body.get("number", ""),
                    body.get("recorded_by", ""), body.get("amount_cents"),
                    body.get("date", ""), body.get("note", ""))
                _json(self, 200, {"accounting_doc": doc})
            elif self.path == "/api/review":
                dec = approvals.review(
                    self.store, body["proposal_id"], body.get("reviewer", ""),
                    body.get("verdict", ""), body.get("note", ""))
                _json(self, 200, {"decision": {"proposal_id": dec.proposal_id, "reviewer": dec.reviewer, "verdict": dec.verdict, "note": dec.note}})
            else:
                _json(self, 404, {"error": "unknown route"})
        except (KeyError, ValueError) as exc:
            _json(self, 400, {"error": str(exc)[:200]})
        except Exception as exc:
            _json(self, 500, {"error": f"{type(exc).__name__}"})


def load_dotenv(path=None) -> int:
    """Load KEY=VALUE lines from a .env file (setdefault semantics).

    Returns the number of variables set. Never prints values: callers
    must only report the count. Missing file -> 0, no error.
    """
    target = Path(path) if path else Path(__file__).resolve().parent.parent / ".env"
    if not target.exists():
        return 0
    n = 0
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip().strip("'\"")
            n += 1
    return n


def main() -> None:
    load_dotenv()  # repo .env (if present); explicit env always wins
    try:
        provider = build_provider()
    except ProviderError as exc:
        print(f"Provider: ERROR ({exc}). Use IA_PROVIDER=simulated without a key.")
        raise SystemExit(1)
    store = SyntheticStore()
    Handler.store = store
    Handler.agent = Agent(store, provider)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"AI demo at http://127.0.0.1:{PORT}/ (provider={provider.name})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
