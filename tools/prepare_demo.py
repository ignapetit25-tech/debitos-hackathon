"""One-command full demo setup: fixtures + DB + main case. No paid calls.

Usage:  .venv/bin/python -B tools/prepare_demo.py
Target: demo_data/demo.db (+ demo_data/generated), or IA_DEMO_DB.

Rebuilds the target DB from scratch (deletes it first):
- 7 fixture cases with service dates (DEMO-DOCFALTA deliberately
  dateless, to show the pending-info path);
- EXP-900 with invoice + settlement + agreement, truly extracted.
Uses no provider and no keys. To preserve a live DB, point
IA_DEMO_DB at a copy: this script never reads another DB.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.make_fixtures as gen
from debit_ai.contracts import Case, LineItem
from debit_ai.money import parse_amount
from debit_ai.synthetic import SyntheticStore
from tools.add_casefile import build_casefile


def main(db_path=None, gen_dir=None) -> dict:
    default_db = ROOT / "demo_data" / "demo.db"
    db = Path(db_path or os.environ.get("IA_DEMO_DB") or default_db)
    if db.suffix != ".db":
        raise ValueError("target must be a .db file")
    out = Path(gen_dir) if gen_dir else ROOT / "demo_data" / "generated"
    if db.exists():
        db.unlink()
    gen.main(out)
    store = SyntheticStore(str(db))
    for case in gen.CASES:
        lines = tuple(
            LineItem(r["line_no"], r["procedure"], r["reason"],
                     parse_amount(r["billed"]), parse_amount(r["settled"]))
            for r in case["lines"]
        )
        store.seed_case(Case(case["id"], case["payer"], case["invoice"],
                             lines, parse_amount(case["total"]), "new",
                             case.get("service_date", "")))
    exp = build_casefile(store, out)
    summary = {"db": str(db), "cases": len(gen.CASES) + 1,
               "main_case": exp.id,
               "documents": len(store.documents(exp.id))}
    print(f"demo ready: {summary['cases']} cases -> {db} "
          f"(main {exp.id}, {summary['documents']} documents)")
    return summary


if __name__ == "__main__":
    main()
