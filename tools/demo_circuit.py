"""Build the fictitious task-circuit demo on a FRESH scratch DB.

Usage:
  .venv/bin/python -B tools/demo_circuit.py --db /tmp/circuit/demo.db
  .venv/bin/python -B tools/demo_circuit.py --db /tmp/circuit/demo.db \\
      --generated-dir /tmp/circuit/generated

Starts from a full prepare (refuses to overwrite: prepare_demo
protections apply), then adds case EXP-2501 (fictitious) walking
the confirmed circuit: multi-line file, Billing + Medical Audit
tasks, a line with complementary Agreements + Billing tasks, an
insufficient answer returned by debitos, a corrected answer with
verifiable backing, per-line resolutions, a linked rebilling
invoice with a PARTIAL recognition (balance in dispute shown),
and an accepted-debit closure with origin analysis. All evidence
is clearly labeled fictitious.

ALL actors are auto-test-* (sector responders, debitos
verification, resolution, recovery). This never touches the live
DB and never simulates the owner's personal approval. No paid
calls: no provider runs here.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.prepare_demo as prep
from debit_ai import tasks
from debit_ai.contracts import Case, LineItem
from debit_ai.synthetic import SyntheticStore

CASE = "EXP-2501"
DEB = "auto-test-debitos"


def build(db: str) -> dict:
    s = SyntheticStore(db)
    s.seed_case(Case(
        CASE, "OS FICTICIA ANDINA", "F-2501", (
            LineItem(1, "CONSULTA GENERAL", "Falta de autorización",
                     3000000, 0),
            LineItem(2, "DESCARTABLES",
                     "Falta de detalle que justifique descartables "
                     "en internación", 1850000, 0),
            LineItem(3, "PRACTICA QUIRURGICA",
                     "Prestación sin convenio para el plan del afiliado. "
                     "Falta de autorización", 4500000, 0),
        ), 9350000, "new", "2026-08-20"))
    t1 = tasks.create_task(s, CASE, 1, "Billing", "Falta de autorización")
    t2 = tasks.create_task(s, CASE, 2, "Medical Audit",
                           "Falta de detalle que justifique descartables "
                           "en internación")
    t3 = tasks.create_task(s, CASE, 3, "Agreements",
                           "Prestación sin convenio para el plan del afiliado")
    t4 = tasks.create_task(s, CASE, 3, "Billing", "Falta de autorización")
    # Insufficient answer -> debitos returns it.
    tasks.answer_task(s, t1["id"], "auto-test-billing",
                      "La autorización está en la historia clínica.", "HC")
    tasks.return_task(s, t1["id"], DEB,
                      "Referencia insuficiente: aportar el documento o una "
                      "referencia precisa (correo con fecha, número de "
                      "autorización o folio verificable).")
    # Corrected answer with verifiable backing -> verified.
    tasks.answer_task(s, t1["id"], "auto-test-billing",
                      "Autorización localizada en correo del financiador.",
                      "Correo 2026-08-20, autorización AUT-2501, adjunto "
                      "folio 2 (ficticio)")
    tasks.verify_task(s, t1["id"], DEB,
                      "Respaldo suficiente y correspondiente.")
    tasks.answer_task(s, t2["id"], "auto-test-auditor",
                      "Revisadas evolución médica y hoja de enfermería: se "
                      "puede refacturar descartables con fundamento en "
                      "fojas 12-14.",
                      "Evolución médica 2026-08-20, fojas 12-14 (ficticio)")
    tasks.verify_task(s, t2["id"], DEB, "Respaldo verificado.")
    tasks.answer_task(s, t3["id"], "auto-test-convenios",
                      "Presupuesto P-1186 del 2026-08-05 aplicable al plan; "
                      "condiciones: pago a 30 días.",
                      "Presupuesto P-1186 del 2026-08-05 (ficticio)")
    tasks.verify_task(s, t3["id"], DEB, "Presupuesto confirmado.")
    tasks.answer_task(s, t4["id"], "auto-test-billing",
                      "Autorización del financiador localizada.",
                      "Correo 2026-08-19, autorización AUT-2500, "
                      "folio 1 (ficticio)")
    tasks.verify_task(s, t4["id"], DEB, "Respaldo verificado.")
    # Individual per-line resolutions.
    tasks.resolve_line(s, CASE, 1, DEB,
                       "Refacturar práctica con autorización AUT-2501.")
    tasks.resolve_line(s, CASE, 3, DEB,
                       "Refacturar con presupuesto P-1186 y "
                       "autorización AUT-2500.")
    # L2 closes as accepted debit (verified, but the debit stands).
    tasks.accept_debit(s, CASE, 2, DEB,
                       "Detail never existed; billed in error.",
                       "Pre-invoice checklist for descartables.")
    # Partial recognition on L1: 10000 of 30000 -> balance in dispute.
    rb = tasks.record_rebilling(s, CASE, 1, "F-2501-R1", 3000000,
                                "OS FICTICIA ANDINA", "2026-09-02")
    tasks.record_recognition(s, rb["id"], "financier_credit_note",
                             1000000, "NC-8810 (FICTICIA)",
                             "OS FICTICIA ANDINA", DEB, "2026-09-20",
                             "Fictitious evidence for demo.")
    return {"case": CASE,
            "tasks": len(s.list_tasks(CASE)),
            "resolutions": len(s.list_resolutions(CASE)),
            "rebillings": len(s.list_rebillings(CASE)),
            "recognitions": len(s.list_case_recognitions(CASE)),
            "accepted": len(s.list_accepted(CASE)),
            "disputed_cents": tasks.disputed_balance(s, rb["id"]),
            "returns": len(tasks.task_returns(s, CASE))}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help="fresh demo DB (must not exist)")
    ap.add_argument("--generated-dir", default=None,
                    help="fixture PDFs dir (default: sibling 'generated')")
    ns = ap.parse_args(argv)
    gen = ns.generated_dir or str(Path(ns.db).parent / "generated")
    prep.main(ns.db, gen)
    summary = build(ns.db)
    print(f"circuit demo ready: {summary['case']} -> {ns.db} "
          f"({summary['tasks']} tasks, {summary['returns']} return(s), "
          f"{summary['resolutions']} resolutions, {summary['rebillings']} "
          f"rebilling(s), {summary['recognitions']} recognition(s), "
          f"{summary['accepted']} accepted, disputed "
          f"{summary['disputed_cents']}c)")
    return summary


if __name__ == "__main__":
    main()
