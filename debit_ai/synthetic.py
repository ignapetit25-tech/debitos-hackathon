"""SYNTHETIC implementation of the contracts (stand-in for prior services).

Cases/proposals/history live in the demo SQLite (demo_data/demo.db,
git-ignored, rebuildable with tools/prepare_demo.py). Rates and rules are
in memory. ALL fictitious: payers, people, invoices and values.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from . import rules
from .contracts import (Case, CaseStore, LineItem, Proposal, RateService,
                        RuleRef, RulesService)

DB_DEFAULT = str(Path(__file__).resolve().parent.parent / "demo_data" / "demo.db")

PAYERS = ("OS FICTICIA ANDINA", "PREPAGA FICTICIA SUR", "ART FICTICIA NORTE")

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY, payer TEXT, invoice TEXT,
  lines_json TEXT, total_debit_cents INTEGER, status TEXT,
  service_date TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS documents (
  case_id TEXT, role TEXT, filename TEXT, pages INTEGER, text TEXT,
  pages_json TEXT DEFAULT '',
  PRIMARY KEY (case_id, role));
CREATE TABLE IF NOT EXISTS proposal_findings (
  proposal_id TEXT, finding_json TEXT);
CREATE TABLE IF NOT EXISTS agreements (
  id TEXT PRIMARY KEY, payer TEXT, version TEXT,
  valid_from TEXT, valid_to TEXT, rates_json TEXT);
CREATE TABLE IF NOT EXISTS followup (
  proposal_id TEXT PRIMARY KEY, decision TEXT, recoverable_cents INTEGER,
  accepted_cents INTEGER, owner TEXT, date TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS proposals (
  id TEXT PRIMARY KEY, case_id TEXT, team TEXT, points INTEGER,
  phrases_json TEXT, action TEXT, explanation TEXT, references_json TEXT,
  needs_human INTEGER, extraction_confidence REAL);
CREATE TABLE IF NOT EXISTS history (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, kind TEXT,
  detail TEXT, before_text TEXT, after_text TEXT, created_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, case_id TEXT, line_no INTEGER, team TEXT,
  motive TEXT, assignee TEXT DEFAULT '', state TEXT,
  responder TEXT DEFAULT '', response TEXT DEFAULT '',
  backing_ref TEXT DEFAULT '', return_note TEXT DEFAULT '',
  created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS resolutions (
  id TEXT PRIMARY KEY, case_id TEXT, line_no INTEGER,
  decided_by TEXT, decision TEXT, note TEXT DEFAULT '',
  created_at TEXT DEFAULT '',
  UNIQUE (case_id, line_no));
CREATE TABLE IF NOT EXISTS rebillings (
  id TEXT PRIMARY KEY, case_id TEXT, line_no INTEGER,
  resolution_id TEXT, number TEXT, amount_cents INTEGER,
  payer TEXT, date TEXT DEFAULT '', note TEXT DEFAULT '',
  created_at TEXT DEFAULT '',
  UNIQUE (case_id, line_no));
CREATE TABLE IF NOT EXISTS recoveries (
  id TEXT PRIMARY KEY, rebilling_id TEXT UNIQUE, method TEXT,
  reference TEXT, confirmed_by TEXT, amount_cents INTEGER,
  date TEXT DEFAULT '', note TEXT DEFAULT '',
  created_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS recognitions (
  id TEXT PRIMARY KEY, rebilling_id TEXT, kind TEXT, amount_cents INTEGER,
  reference TEXT, confirmed_by TEXT, recorded_by TEXT,
  date TEXT DEFAULT '', note TEXT DEFAULT '',
  duplicate_of TEXT DEFAULT '', created_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS accepted_debits (
  id TEXT PRIMARY KEY, case_id TEXT, line_no INTEGER,
  accepted_by TEXT, origin TEXT, corrective TEXT DEFAULT '',
  created_at TEXT DEFAULT '',
  UNIQUE (case_id, line_no));
CREATE TABLE IF NOT EXISTS accounting_docs (
  id TEXT PRIMARY KEY, case_id TEXT, line_no INTEGER,
  kind TEXT, number TEXT, amount_cents INTEGER,
  date TEXT DEFAULT '', note TEXT DEFAULT '',
  recorded_by TEXT DEFAULT '', created_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS shared_audits (
  id TEXT PRIMARY KEY, origin_rebilling_id TEXT, new_case_id TEXT,
  new_motive TEXT, requested_by TEXT, company_auditor TEXT,
  payer_side TEXT, channel TEXT, note TEXT DEFAULT '',
  created_at TEXT DEFAULT '',
  UNIQUE (origin_rebilling_id, new_case_id));
CREATE TABLE IF NOT EXISTS audit_conclusions (
  id TEXT PRIMARY KEY, audit_id TEXT UNIQUE, outcome TEXT,
  rebill_cents INTEGER, disputed_cents INTEGER, concluded_by TEXT,
  date TEXT DEFAULT '', note TEXT DEFAULT '',
  created_at TEXT DEFAULT '');
"""


def _proposal_key(pid: str) -> tuple:
    pre, _, num = pid.rpartition("-")
    return (pre, int(num) if num.isdigit() else -1, pid)


class SyntheticStore(CaseStore):
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.environ.get("IA_DEMO_DB", DB_DEFAULT)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path)
        try:
            con.executescript(SCHEMA)
            cols = [r[1] for r in
                    con.execute("PRAGMA table_info(documents)").fetchall()]
            if "pages_json" not in cols:
                con.execute("ALTER TABLE documents "
                            "ADD COLUMN pages_json TEXT DEFAULT ''")
                for cid, role, text in con.execute(
                        "SELECT case_id, role, text FROM documents"):
                    con.execute("UPDATE documents SET pages_json=? "
                                "WHERE case_id=? AND role=?",
                                (json.dumps([text or ""]), cid, role))
                con.execute("UPDATE documents SET pages_json=? "
                            "WHERE pages_json IS NULL", (json.dumps([""]),))
            con.commit()
            seed_agreements(self)
        finally:
            con.close()

    def _con(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def seed_case(self, case: Case) -> None:
        con = self._con()
        try:
            con.execute(
                "INSERT OR REPLACE INTO cases (id, payer, invoice,"
                " lines_json, total_debit_cents, status, service_date)"
                " VALUES (?,?,?,?,?,?,?)",
                (case.id, case.payer, case.invoice,
                 json.dumps([r.__dict__ for r in case.lines]),
                 case.total_debit_cents, case.status, case.service_date),
            )
            con.commit()
        finally:
            con.close()

    def _row_to_case(self, row: tuple) -> Case:
        cid, payer, inv, lines_json, total, status, date = row
        lines = tuple(LineItem(**r) for r in json.loads(lines_json))
        return Case(cid, payer, inv, lines, total, status, date or "")

    def get_case(self, id: str) -> Case:
        con = self._con()
        try:
            row = con.execute("SELECT id, payer, invoice, lines_json,"
                                " total_debit_cents, status, service_date"
                                " FROM cases WHERE id=?", (id,)).fetchone()
        finally:
            con.close()
        if not row:
            raise KeyError(f"case not found: {id}")
        return self._row_to_case(row)

    def list_cases(self, filters: dict | None = None) -> list[Case]:
        filters = filters or {}
        sql = ("SELECT id, payer, invoice, lines_json,"
               " total_debit_cents, status, service_date FROM cases")
        params: list = []
        if "status" in filters:
            sql += " WHERE status=?"; params.append(filters["status"])
        if "payer" in filters:
            sql += (" AND " if params else " WHERE ") + "payer=?"
            params.append(filters["payer"])
        con = self._con()
        try:
            rows = con.execute(sql, params).fetchall()
        finally:
            con.close()
        return [self._row_to_case(r) for r in rows]

    def new_proposal_id(self, case_id: str) -> str:
        pref = f"P-{case_id}-"
        con = self._con()
        try:
            rows = con.execute("SELECT id FROM proposals WHERE case_id=?",
                               (case_id,)).fetchall()
        finally:
            con.close()
        nums = [int(r[0][len(pref):]) for r in rows
                if r[0].startswith(pref) and r[0][len(pref):].isdigit()]
        return f"{pref}{(max(nums) + 1) if nums else 1}"

    def list_proposals(self, case_id: str) -> list[str]:
        con = self._con()
        try:
            rows = con.execute("SELECT id FROM proposals WHERE case_id=?",
                               (case_id,)).fetchall()
        finally:
            con.close()
        return sorted((r[0] for r in rows), key=_proposal_key)

    def save_proposal(self, case_id: str, proposal: Proposal) -> None:
        _ = self.get_case(case_id)
        con = self._con()
        try:
            con.execute(
                "INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?)",
                (proposal.id, proposal.case_id, proposal.team,
                 proposal.rule.points, json.dumps(list(proposal.rule.phrases)),
                 proposal.action, proposal.explanation,
                 json.dumps(list(proposal.references)),
                 int(proposal.needs_human), proposal.extraction_confidence),
            )
            con.execute("UPDATE cases SET status='proposed' WHERE id=?", (case_id,))
            con.commit()
        finally:
            con.close()

    def log(self, case_id: str, kind: str, detail: str,
            before: str = "", after: str = "") -> None:
        created = datetime.now().astimezone().isoformat(timespec="seconds")
        con = self._con()
        try:
            con.execute(
                "INSERT INTO history (case_id, kind, detail, before_text, after_text,"
                " created_at) VALUES (?,?,?,?,?,?)",
                (case_id, kind, detail, before, after, created),
            )
            con.commit()
        finally:
            con.close()

    def history(self, case_id: str) -> list[tuple]:
        con = self._con()
        try:
            rows = con.execute(
                "SELECT seq, kind, detail, before_text, after_text,"
                " COALESCE(created_at,'') FROM history"
                " WHERE case_id=? ORDER BY seq", (case_id,)).fetchall()
        finally:
            con.close()
        return rows

    def add_document(self, case_id: str, role: str, filename: str,
                     pages: int, text: str,
                     page_texts: list | None = None) -> None:
        if page_texts is None:
            page_texts = [text or ""] if pages == 1 else [""] * max(pages, 0)
        con = self._con()
        try:
            con.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?)",
                        (case_id, role, filename, pages, text,
                         json.dumps(list(page_texts), ensure_ascii=False)))
            con.commit()
        finally:
            con.close()

    def documents(self, case_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT role, filename, pages, text, pages_json"
                               " FROM documents WHERE case_id=? ORDER BY role",
                               (case_id,)).fetchall()
        finally:
            con.close()
        out = []
        for r in rows:
            try:
                pts = json.loads(r[4]) if r[4] else [r[3] or ""]
            except (ValueError, TypeError):
                pts = [r[3] or ""]
            out.append({"role": r[0], "filename": r[1], "pages": r[2],
                        "text": r[3], "page_texts": pts})
        return out

    def save_findings(self, proposal_id: str, findings: list[dict]) -> None:
        con = self._con()
        try:
            con.execute("DELETE FROM proposal_findings WHERE proposal_id=?",
                        (proposal_id,))
            con.executemany("INSERT INTO proposal_findings VALUES (?,?)",
                            [(proposal_id, json.dumps(h, ensure_ascii=False))
                             for h in findings])
            con.commit()
        finally:
            con.close()

    def get_findings(self, proposal_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT finding_json FROM proposal_findings"
                               " WHERE proposal_id=?", (proposal_id,)).fetchall()
        finally:
            con.close()
        return [json.loads(r[0]) for r in rows]

    def add_agreement(self, id: str, payer: str, version: str,
                      valid_from: str, valid_to: str, rates: dict) -> None:
        con = self._con()
        try:
            con.execute("INSERT OR REPLACE INTO agreements VALUES (?,?,?,?,?,?)",
                        (id, payer, version, valid_from, valid_to,
                         json.dumps(rates, ensure_ascii=False)))
            con.commit()
        finally:
            con.close()

    def payer_agreements(self, payer: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT id, version, valid_from, valid_to,"
                               " rates_json FROM agreements WHERE payer=?"
                               " ORDER BY valid_from", (payer,)).fetchall()
        finally:
            con.close()
        return [{"id": r[0], "version": r[1], "from": r[2], "to": r[3],
                 "rates": json.loads(r[4])} for r in rows]

    def current_agreement(self, payer: str, date: str) -> tuple[dict | None, bool]:
        cands = [c for c in self.payer_agreements(payer)
                 if c["from"] <= date <= c["to"]]
        if not cands:
            return None, False
        cands.sort(key=lambda c: c["from"], reverse=True)
        return cands[0], len(cands) > 1

    def save_followup(self, proposal_id: str, decision: str, recoverable: int,
                      accepted: int, owner: str, date: str,
                      note: str = "") -> None:
        if not self.get_proposal(proposal_id):
            raise KeyError(f"proposal not found: {proposal_id}")
        con = self._con()
        try:
            con.execute("INSERT OR REPLACE INTO followup VALUES (?,?,?,?,?,?,?)",
                        (proposal_id, decision, recoverable, accepted,
                         owner, date, note))
            con.commit()
        finally:
            con.close()

    def get_followup(self, proposal_id: str) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM followup WHERE proposal_id=?",
                              (proposal_id,)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return dict(zip(("proposal_id", "decision", "recoverable_cents",
                         "accepted_cents", "owner", "date", "note"), row))

    def new_task_id(self, case_id: str) -> str:
        pref = f"T-{case_id}-"
        con = self._con()
        try:
            rows = con.execute("SELECT id FROM tasks WHERE case_id=?",
                               (case_id,)).fetchall()
        finally:
            con.close()
        nums = [int(r[0][len(pref):]) for r in rows
                if r[0].startswith(pref) and r[0][len(pref):].isdigit()]
        return f"{pref}{(max(nums) + 1) if nums else 1}"

    def save_task(self, task: dict) -> None:
        con = self._con()
        try:
            con.execute(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (task["id"], task["case_id"], task["line_no"],
                 task["team"], task["motive"], task.get("assignee", ""),
                 task["state"], task.get("responder", ""),
                 task.get("response", ""), task.get("backing_ref", ""),
                 task.get("return_note", ""), task.get("created_at", ""),
                 task.get("updated_at", "")),
            )
            con.commit()
        finally:
            con.close()

    def update_task(self, tid: str, **fields) -> None:
        allowed = {"state", "responder", "response", "backing_ref",
                   "return_note", "assignee", "updated_at"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"bad task fields: {sorted(bad)}")
        con = self._con()
        try:
            for k, v in fields.items():
                con.execute(f"UPDATE tasks SET {k}=? WHERE id=?", (v, tid))
            con.commit()
        finally:
            con.close()

    def get_task(self, tid: str) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM tasks WHERE id=?",
                              (tid,)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return dict(zip(("id", "case_id", "line_no", "team", "motive",
                         "assignee", "state", "responder", "response",
                         "backing_ref", "return_note", "created_at",
                         "updated_at"), row))

    def list_tasks(self, case_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT * FROM tasks WHERE case_id=?",
                               (case_id,)).fetchall()
        finally:
            con.close()
        keys = ("id", "case_id", "line_no", "team", "motive",
                "assignee", "state", "responder", "response",
                "backing_ref", "return_note", "created_at", "updated_at")
        return sorted((dict(zip(keys, r)) for r in rows),
                      key=lambda d: (d["line_no"], d["id"]))

    def save_resolution(self, res: dict) -> None:
        con = self._con()
        try:
            con.execute("INSERT INTO resolutions VALUES (?,?,?,?,?,?,?)",
                        (res["id"], res["case_id"], res["line_no"],
                         res["decided_by"], res["decision"],
                         res.get("note", ""), res.get("created_at", "")))
            con.commit()
        finally:
            con.close()

    def get_resolution(self, case_id: str, line_no: int) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM resolutions WHERE case_id=? "
                              "AND line_no=?", (case_id, line_no)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return dict(zip(("id", "case_id", "line_no", "decided_by",
                         "decision", "note", "created_at"), row))

    def list_resolutions(self, case_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT * FROM resolutions WHERE case_id=?",
                               (case_id,)).fetchall()
        finally:
            con.close()
        keys = ("id", "case_id", "line_no", "decided_by", "decision",
                "note", "created_at")
        return sorted((dict(zip(keys, r)) for r in rows),
                      key=lambda d: d["line_no"])

    def save_rebilling(self, rb: dict) -> None:
        con = self._con()
        try:
            con.execute("INSERT INTO rebillings VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (rb["id"], rb["case_id"], rb["line_no"],
                         rb["resolution_id"], rb["number"],
                         rb["amount_cents"], rb["payer"],
                         rb.get("date", ""), rb.get("note", ""),
                         rb.get("created_at", "")))
            con.commit()
        finally:
            con.close()

    def get_rebilling(self, rid: str) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM rebillings WHERE id=?",
                              (rid,)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return dict(zip(("id", "case_id", "line_no", "resolution_id",
                         "number", "amount_cents", "payer", "date",
                         "note", "created_at"), row))

    def list_rebillings(self, case_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT * FROM rebillings WHERE case_id=?",
                               (case_id,)).fetchall()
        finally:
            con.close()
        keys = ("id", "case_id", "line_no", "resolution_id", "number",
                "amount_cents", "payer", "date", "note", "created_at")
        return sorted((dict(zip(keys, r)) for r in rows),
                      key=lambda d: d["line_no"])

    def save_recovery(self, rec: dict) -> None:
        con = self._con()
        try:
            con.execute("INSERT INTO recoveries VALUES (?,?,?,?,?,?,?,?,?)",
                        (rec["id"], rec["rebilling_id"], rec["method"],
                         rec["reference"], rec["confirmed_by"],
                         rec.get("amount_cents"), rec.get("date", ""),
                         rec.get("note", ""), rec.get("created_at", "")))
            con.commit()
        finally:
            con.close()

    def get_recovery_by_rebilling(self, rebilling_id: str) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM recoveries WHERE rebilling_id=?",
                              (rebilling_id,)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return dict(zip(("id", "rebilling_id", "method", "reference",
                         "confirmed_by", "amount_cents", "date", "note",
                         "created_at"), row))

    def list_recoveries(self, case_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute(
                "SELECT r.* FROM recoveries r JOIN rebillings b "
                "ON r.rebilling_id = b.id WHERE b.case_id=?", (case_id,)).fetchall()
        finally:
            con.close()
        keys = ("id", "rebilling_id", "method", "reference",
                "confirmed_by", "amount_cents", "date", "note",
                "created_at")
        return [dict(zip(keys, r)) for r in rows]

    def new_recognition_id(self, rebilling_id: str) -> str:
        pref = f"RC-{rebilling_id}-"
        con = self._con()
        try:
            n = con.execute("SELECT COUNT(*) FROM recognitions "
                            "WHERE rebilling_id=?", (rebilling_id,)).fetchone()[0]
        finally:
            con.close()
        return f"{pref}{n + 1}"

    def save_recognition(self, rec: dict) -> None:
        con = self._con()
        try:
            con.execute("INSERT INTO recognitions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (rec["id"], rec["rebilling_id"], rec["kind"],
                         rec["amount_cents"], rec["reference"],
                         rec["confirmed_by"], rec["recorded_by"],
                         rec.get("date", ""), rec.get("note", ""),
                         rec.get("duplicate_of", ""),
                         rec.get("created_at", "")))
            con.commit()
        finally:
            con.close()

    def get_recognition(self, rid: str) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM recognitions WHERE id=?",
                              (rid,)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return dict(zip(("id", "rebilling_id", "kind", "amount_cents",
                         "reference", "confirmed_by", "recorded_by",
                         "date", "note", "duplicate_of",
                         "created_at"), row))

    def list_recognitions(self, rebilling_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT * FROM recognitions WHERE rebilling_id=?",
                               (rebilling_id,)).fetchall()
        finally:
            con.close()
        keys = ("id", "rebilling_id", "kind", "amount_cents", "reference",
                "confirmed_by", "recorded_by", "date", "note",
                "duplicate_of", "created_at")
        return [dict(zip(keys, r)) for r in rows]

    def list_case_recognitions(self, case_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute(
                "SELECT r.* FROM recognitions r JOIN rebillings b "
                "ON r.rebilling_id = b.id WHERE b.case_id=?", (case_id,)).fetchall()
        finally:
            con.close()
        keys = ("id", "rebilling_id", "kind", "amount_cents", "reference",
                "confirmed_by", "recorded_by", "date", "note",
                "duplicate_of", "created_at")
        return [dict(zip(keys, r)) for r in rows]

    def mark_recognition_duplicate(self, rid: str, duplicate_of: str) -> None:
        con = self._con()
        try:
            con.execute("UPDATE recognitions SET duplicate_of=? WHERE id=?",
                        (duplicate_of, rid))
            con.commit()
        finally:
            con.close()

    def save_accepted(self, acc: dict) -> None:
        con = self._con()
        try:
            con.execute("INSERT INTO accepted_debits VALUES (?,?,?,?,?,?,?)",
                        (acc["id"], acc["case_id"], acc["line_no"],
                         acc["accepted_by"], acc["origin"],
                         acc.get("corrective", ""),
                         acc.get("created_at", "")))
            con.commit()
        finally:
            con.close()

    def get_accepted(self, case_id: str, line_no: int) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM accepted_debits WHERE case_id=? "
                              "AND line_no=?", (case_id, line_no)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return dict(zip(("id", "case_id", "line_no", "accepted_by",
                         "origin", "corrective", "created_at"), row))

    def list_accepted(self, case_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT * FROM accepted_debits WHERE case_id=?",
                               (case_id,)).fetchall()
        finally:
            con.close()
        keys = ("id", "case_id", "line_no", "accepted_by", "origin",
                "corrective", "created_at")
        return sorted((dict(zip(keys, r)) for r in rows),
                      key=lambda d: d["line_no"])

    def new_accounting_id(self, case_id: str) -> str:
        pref = f"AD-{case_id}-"
        con = self._con()
        try:
            n = con.execute("SELECT COUNT(*) FROM accounting_docs "
                            "WHERE case_id=?", (case_id,)).fetchone()[0]
        finally:
            con.close()
        return f"{pref}{n + 1}"

    def save_accounting_doc(self, doc: dict) -> None:
        con = self._con()
        try:
            con.execute("INSERT INTO accounting_docs VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (doc["id"], doc["case_id"], doc.get("line_no"),
                         doc["kind"], doc["number"], doc.get("amount_cents"),
                         doc.get("date", ""), doc.get("note", ""),
                         doc.get("recorded_by", ""),
                         doc.get("created_at", "")))
            con.commit()
        finally:
            con.close()

    def list_accounting_docs(self, case_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT * FROM accounting_docs WHERE case_id=?",
                               (case_id,)).fetchall()
        finally:
            con.close()
        keys = ("id", "case_id", "line_no", "kind", "number",
                "amount_cents", "date", "note", "recorded_by",
                "created_at")
        return [dict(zip(keys, r)) for r in rows]

    def new_shared_audit_id(self) -> str:
        con = self._con()
        try:
            n = con.execute("SELECT COUNT(*) FROM shared_audits").fetchone()[0]
        finally:
            con.close()
        return f"SA-{n + 1}"

    def save_shared_audit(self, au: dict) -> None:
        con = self._con()
        try:
            con.execute("INSERT INTO shared_audits VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (au["id"], au["origin_rebilling_id"], au["new_case_id"],
                         au["new_motive"], au["requested_by"],
                         au["company_auditor"], au["payer_side"],
                         au["channel"], au.get("note", ""),
                         au.get("created_at", "")))
            con.commit()
        finally:
            con.close()

    def list_shared_audits(self, case_id: str) -> list[dict]:
        """Audits touching a case: as dispute origin or as new debit."""
        con = self._con()
        try:
            rows = con.execute(
                "SELECT a.*, c.outcome, c.rebill_cents, c.disputed_cents, "
                "c.concluded_by, c.date, c.note, c.created_at "
                "FROM shared_audits a LEFT JOIN rebillings b "
                "ON a.origin_rebilling_id = b.id "
                "LEFT JOIN audit_conclusions c ON c.audit_id = a.id "
                "WHERE b.case_id=? OR a.new_case_id=?", (case_id, case_id)
            ).fetchall()
        finally:
            con.close()
        keys = ("id", "origin_rebilling_id", "new_case_id", "new_motive",
                "requested_by", "company_auditor", "payer_side",
                "channel", "note", "created_at")
        out = []
        for r in rows:
            d = dict(zip(keys, r[:10]))
            d["conclusion"] = None
            if r[10] is not None:
                d["conclusion"] = dict(zip(
                    ("outcome", "rebill_cents", "disputed_cents",
                     "concluded_by", "date", "note", "created_at"), r[10:17]))
            out.append(d)
        return out

    def save_conclusion(self, c: dict) -> None:
        con = self._con()
        try:
            con.execute("INSERT INTO audit_conclusions VALUES (?,?,?,?,?,?,?,?,?)",
                        (c["id"], c["audit_id"], c["outcome"],
                         c.get("rebill_cents"), c["disputed_cents"],
                         c["concluded_by"], c.get("date", ""),
                         c.get("note", ""), c.get("created_at", "")))
            con.commit()
        finally:
            con.close()

    def get_conclusion(self, audit_id: str) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM audit_conclusions WHERE audit_id=?",
                              (audit_id,)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return dict(zip(("id", "audit_id", "outcome", "rebill_cents",
                         "disputed_cents", "concluded_by", "date", "note",
                         "created_at"), row))

    def get_proposal(self, pid: str) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        keys = ("id", "case_id", "team", "points", "phrases_json", "action",
                "explanation", "references_json", "needs_human",
                "extraction_confidence")
        return dict(zip(keys, row))


AGREEMENTS_SEED = [
    ("CONV-AND-2025", "OS FICTICIA ANDINA", "v2025", "2025-01-01", "2026-06-30",
     {"CONSULTA GENERAL": 1500000, "ECOGRAFIA ABDOMINAL": 4000000}),
    ("CONV-AND-2026", "OS FICTICIA ANDINA", "v2026", "2026-06-01", "2026-12-31",
     {"CONSULTA GENERAL": 1650000, "ECOGRAFIA ABDOMINAL": 4200000}),
    ("CONV-SUR-2026", "PREPAGA FICTICIA SUR", "v2026", "2026-01-01", "2026-12-31",
     {"CONSULTA GENERAL": 1800000}),
    ("CONV-NOR-2026", "ART FICTICIA NORTE", "v2026", "2026-01-01", "2026-12-31",
     {"CONSULTA GENERAL": 1500000, "ECOGRAFIA ABDOMINAL": 4000000}),
]


def seed_agreements(store: "SyntheticStore") -> int:
    n = 0
    for id, payer, ver, valid_from, valid_to, rates in AGREEMENTS_SEED:
        if not [c for c in store.payer_agreements(payer) if c["id"] == id]:
            store.add_agreement(id, payer, ver, valid_from, valid_to, rates)
            n += 1
    return n


class SyntheticRates(RateService):
    def __init__(self, store: "SyntheticStore | None" = None) -> None:
        self._store = store

    def get_rate(self, procedure: str, payer: str, date: str) -> dict | None:
        if self._store is None:
            return None
        conv, _amb = self._store.current_agreement(payer, date)
        if not conv:
            return None
        val = conv["rates"].get(procedure.upper())
        if val is None:
            return None
        return {"procedure": procedure.upper(), "payer": payer,
                "validity": [conv["from"], conv["to"]], "value_cents": val,
                "agreement": conv["id"], "version": conv["version"],
                "overlapping": _amb}


class SyntheticRules(RulesService):
    def evaluate_rules(self, reason: str) -> RuleRef:
        return rules.evaluate(reason)
