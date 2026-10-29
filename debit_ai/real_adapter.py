"""REAL adapter (explicit JSON). DISABLED by default. UNVERIFIED.

Mechanism: JSON file exchange in an agreed directory.
Never touches the production SQLite directly. Incoming amounts are
revalidated (int cents; floats rejected).

Could not be verified without private resources: documented as a
limitation in README. Enable only with IA_DEMO_MODE=real + an
existing IA_REAL_DIR.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import rules
from .contracts import Case, CaseStore, LineItem, Proposal, RateService, RuleRef, RulesService

ACTIVE = os.environ.get("IA_DEMO_MODE", "synthetic").strip().lower() == "real"


def _real_dir() -> Path:
    d = os.environ.get("IA_REAL_DIR", "")
    if not ACTIVE or not d:
        raise RuntimeError("real adapter disabled (IA_DEMO_MODE != real)")
    p = Path(d)
    if not p.is_dir():
        raise RuntimeError(f"IA_REAL_DIR missing: {d}")
    return p


def _cents(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be int cents (float rejected)")
    return value


class RealStore(CaseStore):
    """Reads cases from <IA_REAL_DIR>/cases/<id>.json, writes proposals."""

    def _read(self, id: str) -> dict:
        path = _real_dir() / "cases" / f"{id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def get_case(self, id: str) -> Case:
        data = self._read(id)
        lines = tuple(
            LineItem(int(r["line_no"]), str(r["procedure"]), str(r["reason"]),
                     _cents(r["billed_cents"], "billed_cents"),
                     _cents(r["settled_cents"], "settled_cents"))
            for r in data["lines"]
        )
        return Case(str(data["id"]), str(data["payer"]), str(data["invoice"]),
                    lines, _cents(data["total_debit_cents"], "total_debit_cents"),
                    str(data.get("status", "new")))

    def list_cases(self, filters: dict | None = None) -> list[Case]:
        d = _real_dir() / "cases"
        cases = [self.get_case(p.stem) for p in sorted(d.glob("*.json"))]
        filters = filters or {}
        return [c for c in cases
                if all(getattr(c, k, None) == v for k, v in filters.items())]

    def save_proposal(self, case_id: str, proposal: Proposal) -> None:
        out = _real_dir() / "proposals" / f"{proposal.id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "id": proposal.id, "case_id": case_id, "team": proposal.team,
            "points": proposal.rule.points, "phrases": list(proposal.rule.phrases),
            "action": proposal.action, "explanation": proposal.explanation,
            "references": list(proposal.references),
            "needs_human": proposal.needs_human}, ensure_ascii=False,
            indent=2), encoding="utf-8")


class RealRates(RateService):
    def get_rate(self, procedure, payer, date):
        data = json.loads((_real_dir() / "rates.json").read_text(encoding="utf-8"))
        for a in data:
            if (a["procedure"] == procedure.upper() and a["payer"] == payer
                    and a["validity"][0] <= date <= a["validity"][1]):
                return {"procedure": a["procedure"], "payer": a["payer"],
                        "validity": a["validity"],
                        "value_cents": _cents(a["value_cents"], "value_cents")}
        return None


class RealRules(RulesService):
    """Delegates to external rules provided as JSON (runs no foreign code)."""

    def evaluate_rules(self, reason: str) -> RuleRef:
        data = json.loads((_real_dir() / "rules.json").read_text(encoding="utf-8"))
        threshold = int(data.get("threshold", 3))
        best = (rules.PENDING, 0, ())
        text = reason.lower()
        for team, groups in data.get("teams", {}).items():
            total, matched = 0, []
            for weight, phrase_list in groups:
                for phrase in phrase_list:
                    if phrase.lower() in text:
                        total += int(weight)
                        matched.append(phrase)
            if total > best[1]:
                best = (team, total, tuple(matched))
        if best[1] < threshold:
            return RuleRef(rules.PENDING, best[1], ())
        return RuleRef(best[0], best[1], best[2])
