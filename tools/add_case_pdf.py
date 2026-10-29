"""Add ONE fictitious case: build its PDF, truly extract it, seed it.

Does not reset the demo (keeps cases and history). Usage:
  .venv/bin/python -B tools/add_case_pdf.py
All fictitious, tagged FICTITIOUS DATA. Nothing real, nothing copied.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from make_fixtures import pdf_lines, text_pdf  # noqa: E402

from debit_ai.contracts import Case, LineItem  # noqa: E402
from debit_ai.extract import extract  # noqa: E402
from debit_ai.synthetic import SyntheticStore  # noqa: E402

CASE = {
    "id": "DEMO-META-3", "payer": "OS FICTICIA ANDINA",
    "invoice": "F-400", "total": "$31.000",
    "lines": [
        {"line_no": 1, "procedure": "CONSULTA GENERAL",
         "reason": "supera el valor del convenio en consulta de control",
         "billed": "$22.000", "settled": "$9.000"},
        {"line_no": 2, "procedure": "ECOGRAFIA ABDOMINAL",
         "reason": "diferencia contra valor del convenio vigente",
         "billed": "$30.000", "settled": "$12.000"},
    ],
}


def main() -> None:
    pdf = ROOT / "demo_data" / "generated" / f"{CASE['id']}.pdf"
    text_pdf(pdf, pdf_lines(CASE))
    print(f"{pdf.name} (text)")
    ext = extract(str(pdf))  # REAL extraction, not hand-seeded data
    assert ext.source == "text", ext.source
    assert not ext.flags, ext.flags
    assert len(ext.lines) == len(CASE["lines"]), len(ext.lines)
    lines = tuple(
        LineItem(r["num"], r["procedure"], r["reason"], r["billed_cents"],
                 r["settled_cents"]) for r in ext.lines
    )
    total = sum(r.debit_cents for r in lines)
    case = Case(CASE["id"], CASE["payer"], CASE["invoice"], lines, total)
    ok, dif = case.validate()
    assert ok and dif == 0, (ok, dif)
    SyntheticStore().seed_case(case)
    print(f"case {case.id}: {len(lines)} lines extracted, "
          f"debit {total} cents, sums OK, confidence {ext.confidence}")


if __name__ == "__main__":
    main()
