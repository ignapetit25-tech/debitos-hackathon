"""One-command full demo setup: fixtures + DB + main case. No paid calls.

Usage:
  .venv/bin/python -B tools/prepare_demo.py --db demo_data/demo.db
  .venv/bin/python -B tools/prepare_demo.py --db /tmp/scratch/demo.db \\
      --generated-dir /tmp/scratch/generated

Safety (data-loss incident 2026-10-30, see TEST_REPORT.md):
- the destination is REQUIRED (--db or IA_DEMO_DB). There is no
  silent default: without an explicit target the command fails
  having changed nothing;
- a fresh DB is created; if the destination exists, ordinary
  preparation FAILS without touching it (/tmp included: a path
  you want to keep is never overwritten);
- --replace rebuilds an existing DB only together with
  --backup-to <new-path>: a VERIFIED backup is taken first
  (tools/backup_db.py: backup API + integrity + restore test)
  and any failure aborts BEFORE anything is deleted;
- replacing the DB the server uses (IA_DEMO_DB, else
  demo_data/demo.db) additionally requires --confirm-active-db.

Builds the target DB from scratch:
- 7 fixture cases with service dates (DEMO-DOCFALTA deliberately
  dateless, to show the pending-info path);
- EXP-900 with invoice + settlement + agreement, truly extracted.
Uses no provider and no keys.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.make_fixtures as gen
from debit_ai.contracts import Case, LineItem
from debit_ai.money import parse_amount
from debit_ai.synthetic import DB_DEFAULT, SyntheticStore
from tools.add_casefile import build_casefile
from tools.backup_db import backup_database


def active_db() -> Path:
    """The DB path the server would open with this environment."""
    return Path(os.environ.get("IA_DEMO_DB") or DB_DEFAULT).absolute()


def _same_file(a: Path, b: Path) -> bool:
    return a.absolute() == b.absolute()


def main(db_path=None, gen_dir=None, replace=False, backup_to=None,
         confirm_active=False) -> dict:
    raw = db_path or os.environ.get("IA_DEMO_DB")
    if not raw:
        raise ValueError("explicit destination required: pass --db PATH "
                         "or set IA_DEMO_DB; refusing silent default")
    db = Path(raw)
    if db.suffix != ".db":
        raise ValueError("target must be a .db file")
    out = Path(gen_dir) if gen_dir else ROOT / "demo_data" / "generated"
    backup_report = None
    if db.exists():
        if not replace:
            raise FileExistsError(
                f"refusing to overwrite existing DB: {db} (use --replace "
                f"--backup-to <new-path> for an explicit rebuild)")
        if _same_file(db, active_db()) and not confirm_active:
            raise PermissionError(
                f"destination is the active server DB: {db} (pass "
                f"--confirm-active-db to replace it; the server must be "
                f"restarted afterwards)")
        if not backup_to:
            raise ValueError("--replace requires --backup-to <new-path> "
                             "with a verified backup first")
        backup_report = backup_database(str(db), str(backup_to))
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
    if backup_report:
        summary["backup"] = backup_report["backup"]
        print(f"prior DB preserved at: {backup_report['backup']} "
              f"(sha256 {backup_report['sha256'][:16]}..., verified)")
    return summary


def cli(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=None,
                    help="destination DB (or IA_DEMO_DB); required")
    ap.add_argument("--generated-dir", default=None,
                    help="fixture PDFs dir (default demo_data/generated)")
    ap.add_argument("--replace", action="store_true",
                    help="rebuild an existing DB (needs --backup-to)")
    ap.add_argument("--backup-to", default=None,
                    help="verified-backup target for --replace (must not exist)")
    ap.add_argument("--confirm-active-db", action="store_true",
                    help="allow --replace of the DB the server uses")
    ns = ap.parse_args(argv)
    try:
        return main(ns.db, ns.generated_dir, ns.replace, ns.backup_to,
                    ns.confirm_active_db)
    except (ValueError, FileExistsError, PermissionError) as e:
        print(f"prepare_demo: error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
