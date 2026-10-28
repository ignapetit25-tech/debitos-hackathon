"""Caso expediente completo: factura + liquidacion + convenio (ficticios).

Genera 3 PDFs, extrae la factura de verdad, registra los documentos
con su texto y siembra el caso con fecha de prestacion. No resetea.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from make_fixtures import lineas_pdf, pdf_texto  # noqa: E402

from ia_debitos.contracts import Caso, Renglon  # noqa: E402
from ia_debitos.extract import extraer  # noqa: E402
from ia_debitos.synthetic import SyntheticStore  # noqa: E402

CASO = {
    "id": "EXP-900", "financiador": "OS FICTICIA ANDINA", "factura": "F-900",
    "total": "$58.500",
    "renglones": [
        {"nro": 1, "practica": "CONSULTA GENERAL",
         "motivo": "supera el valor del convenio",
         "fact": "$20.000", "liq": "$3.500"},
        {"nro": 2, "practica": "ECOGRAFIA ABDOMINAL",
         "motivo": "difiere del valor pactado en convenio",
         "fact": "$45.000", "liq": "$3.000"},
    ],
}
FECHA = "2026-08-10"
LIQUIDACION = [
    "DATOS FICTICIOS - DEMOSTRACION",
    "LIQUIDACION: F-900 FINANCIADOR: OS FICTICIA ANDINA",
    "RENGLON 1: DEBITO $16.500 MOTIVO: supera el valor del convenio",
    "RENGLON 2: DEBITO $42.000 MOTIVO: difiere del valor pactado en convenio",
]
CONVENIO = [
    "DATOS FICTICIOS - DEMOSTRACION",
    "CONVENIO OS FICTICIA ANDINA - ANEXO ARANCELARIO",
    "VIGENCIA: 2026-01-01..2026-12-31",
    "ARANCEL: CONSULTA GENERAL $16.500",
    "ARANCEL: ECOGRAFIA ABDOMINAL $42.000",
]


def texto_pdf(ruta: Path) -> str:
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(ruta)).pages)


def main() -> None:
    gen = ROOT / "demo_data" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    lineas = lineas_pdf(CASO)
    lineas.insert(3, f"FECHA PRESTACION: {FECHA}")
    pf = gen / f"{CASO['id']}-factura.pdf"
    pl = gen / f"{CASO['id']}-liquidacion.pdf"
    pc = gen / f"{CASO['id']}-convenio.pdf"
    pdf_texto(pf, lineas)
    pdf_texto(pl, LIQUIDACION)
    pdf_texto(pc, CONVENIO)
    print(f"{pf.name}, {pl.name}, {pc.name}")
    ext = extraer(str(pf))
    assert ext.origen == "texto" and not ext.dudosos, (ext.origen, ext.dudosos)
    assert len(ext.renglones) == 2, len(ext.renglones)
    assert ext.fecha_txt == FECHA, ext.fecha_txt
    rengs = tuple(Renglon(r["nro"], r["practica"], r["motivo"], r["facturado_cents"],
                           r["liquidado_cents"]) for r in ext.renglones)
    total = sum(r.debito_cents for r in rengs)
    caso = Caso(CASO["id"], CASO["financiador"], CASO["factura"], rengs, total,
                "nuevo", ext.fecha_txt)
    assert caso.validar() == (True, 0)
    s = SyntheticStore()
    s.seed_caso(caso)
    for rol, ruta in (("factura", pf), ("liquidacion", pl), ("convenio", pc)):
        s.registrar_documento(caso.id, rol, ruta.name, 1, texto_pdf(ruta))
    print(f"caso {caso.id}: 3 documentos, debito {total} cents, sumas OK")


if __name__ == "__main__":
    main()
