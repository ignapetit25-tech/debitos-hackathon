"""SYNTHETIC implementation of the contracts (stand-in for prior services).

Cases/proposals/history live in the demo SQLite (demo_data/demo.db,
git-ignored, rebuildable with tools/reset_demo.py). Rates and rules are
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
"""


class SyntheticStore(CaseStore):
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.environ.get("IA_DEMO_DB", DB_DEFAULT)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path)
        try:
            con.executescript(SCHEMA)
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
            rows = con.execute("SELECT id FROM proposals WHERE case_id=? ORDER BY id",
                               (case_id,)).fetchall()
        finally:
            con.close()
        return [r[0] for r in rows]

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
                     pages: int, text: str) -> None:
        con = self._con()
        try:
            con.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?)",
                        (case_id, role, filename, pages, text))
            con.commit()
        finally:
            con.close()

    def documents(self, case_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT role, filename, pages, text FROM documents"
                               " WHERE case_id=? ORDER BY role", (case_id,)).fetchall()
        finally:
            con.close()
        return [{"role": r[0], "filename": r[1], "pages": r[2], "text": r[3]}
                for r in rows]

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
