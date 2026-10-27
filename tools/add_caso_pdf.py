"""Agrega UN caso ficticio: genera su PDF, lo extrae de verdad y lo siembra.

No resetea la demo (conserva casos e historial). Uso:
  .venv/bin/python -B tools/add_caso_pdf.py
Todo ficticio, marcado DATOS FICTICIOS. Nada real, nada copiado.
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
    "id": "DEMO-META-3", "financiador": "OS FICTICIA ANDINA",
    "factura": "F-400", "total": "$31.000",
    "renglones": [
        {"nro": 1, "practica": "CONSULTA GENERAL",
         "motivo": "supera el valor del convenio en consulta de control",
         "fact": "$22.000", "liq": "$9.000"},
        {"nro": 2, "practica": "ECOGRAFIA ABDOMINAL",
         "motivo": "diferencia contra valor del convenio vigente",
         "fact": "$30.000", "liq": "$12.000"},
    ],
}


def main() -> None:
    pdf = ROOT / "demo_data" / "generated" / f"{CASO['id']}.pdf"
    pdf_texto(pdf, lineas_pdf(CASO))
    print(f"{pdf.name} (texto)")
    ext = extraer(str(pdf))  # extracción REAL, no datos sembrados a mano
    assert ext.origen == "texto", ext.origen
    assert not ext.dudosos, ext.dudosos
    assert len(ext.renglones) == len(CASO["renglones"]), len(ext.renglones)
    rengs = tuple(
        Renglon(r["nro"], r["practica"], r["motivo"], r["facturado_cents"],
                r["liquidado_cents"]) for r in ext.renglones
    )
    total = sum(r.debito_cents for r in rengs)
    caso = Caso(CASO["id"], CASO["financiador"], CASO["factura"], rengs, total)
    ok, dif = caso.validar()
    assert ok and dif == 0, (ok, dif)
    SyntheticStore().seed_caso(caso)
    print(f"caso {caso.id}: {len(rengs)} renglones extraídos, "
          f"débito {total} cents, sumas OK, confianza {ext.confianza}")


if __name__ == "__main__":
    main()
