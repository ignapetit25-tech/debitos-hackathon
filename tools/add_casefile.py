"""Full casefile case: invoice + settlement + agreement (fictitious).

Builds 3 PDFs, truly extracts the invoice, registers the documents
with their text, and seeds the case with a service date. No reset.
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
    "id": "EXP-900", "payer": "OS FICTICIA ANDINA", "invoice": "F-900",
    "total": "$58.500",
    "lines": [
        {"line_no": 1, "procedure": "CONSULTA GENERAL",
         "reason": "supera el valor del convenio",
         "billed": "$20.000", "settled": "$3.500"},
        {"line_no": 2, "procedure": "ECOGRAFIA ABDOMINAL",
         "reason": "difiere del valor pactado en convenio",
         "billed": "$45.000", "settled": "$3.000"},
    ],
}
DATE = "2026-08-10"
SETTLEMENT = [
    "DATOS FICTICIOS - DEMOSTRACION",
    "LIQUIDACION: F-900 FINANCIADOR: OS FICTICIA ANDINA",
    "RENGLON 1: DEBITO $16.500 MOTIVO: supera el valor del convenio",
    "RENGLON 2: DEBITO $42.000 MOTIVO: difiere del valor pactado en convenio",
]
AGREEMENT = [
    "DATOS FICTICIOS - DEMOSTRACION",
    "CONVENIO OS FICTICIA ANDINA - ANEXO ARANCELARIO",
    "VIGENCIA: 2026-01-01..2026-12-31",
    "ARANCEL: CONSULTA GENERAL $16.500",
    "ARANCEL: ECOGRAFIA ABDOMINAL $42.000",
]


def pdf_pages(path: Path) -> list[str]:
    from pypdf import PdfReader
    return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]


def build_casefile(store, gen_dir) -> "Case":
    """Build EXP-900 + 3 PDFs into `store`, PDFs under `gen_dir`."""
    from pathlib import Path as _P
    gen = _P(gen_dir)
    gen.mkdir(parents=True, exist_ok=True)
    lines = pdf_lines(CASE)
    lines.insert(3, f"FECHA PRESTACION: {DATE}")
    pf = gen / f"{CASE['id']}-invoice.pdf"
    pl = gen / f"{CASE['id']}-settlement.pdf"
    pc = gen / f"{CASE['id']}-agreement.pdf"
    text_pdf(pf, lines)
    text_pdf(pl, SETTLEMENT)
    text_pdf(pc, AGREEMENT)
    print(f"{pf.name}, {pl.name}, {pc.name}")
    ext = extract(str(pf))
    assert ext.source == "text" and not ext.flags, (ext.source, ext.flags)
    assert len(ext.lines) == 2, len(ext.lines)
    assert ext.date_raw == DATE, ext.date_raw
    lines = tuple(LineItem(r["num"], r["procedure"], r["reason"], r["billed_cents"],
                           r["settled_cents"]) for r in ext.lines)
    total = sum(r.debit_cents for r in lines)
    case = Case(CASE["id"], CASE["payer"], CASE["invoice"], lines, total,
                "new", ext.date_raw)
    assert case.validate() == (True, 0)
    store.seed_case(case)
    for role, path in (("invoice", pf), ("settlement", pl), ("agreement", pc)):
        texts = pdf_pages(path)
        store.add_document(case.id, role, path.name, len(texts),
                           "\n".join(texts), texts)
    print(f"case {case.id}: 3 documents, debit {total} cents, sums OK")
    return case


def main() -> None:
    build_casefile(SyntheticStore(), ROOT / "demo_data" / "generated")


if __name__ == "__main__":
    main()
