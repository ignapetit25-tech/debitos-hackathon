"""Safe demo reset: only touches demo_data/. Rebuilds DB + fixtures."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.make_fixtures as gen
from debit_ai.contracts import Case, LineItem
from debit_ai.money import parse_amount
from debit_ai.synthetic import SyntheticStore


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    demo = root / "demo_data"
    assert demo.resolve().is_relative_to(root.resolve()), "unsafe path"
    db = demo / "demo.db"
    if db.exists():
        db.unlink()
    gen.main()
    store = SyntheticStore(str(db))
    for case in gen.CASES:
        lines = tuple(
            LineItem(r["line_no"], r["procedure"], r["reason"],
                     parse_amount(r["billed"]), parse_amount(r["settled"]))
            for r in case["lines"]
        )
        store.seed_case(Case(case["id"], case["payer"], case["invoice"],
                             lines, parse_amount(case["total"])))
    print(f"demo.db rebuilt ({len(gen.CASES)} cases)")


if __name__ == "__main__":
    main()
