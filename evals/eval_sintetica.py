"""Evaluación reproducible sobre fixtures sintéticos. Solo números medidos.

Métricas: extracción (renglones+total exactos) y derivación (sector y
abstención vs expected.json). Requiere TESSDATA_PREFIX con spa para OCR.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ia_debitos import rules
from ia_debitos.extract import extraer
from ia_debitos.money import parse_importe


def main() -> int:
    base = Path(__file__).resolve().parent.parent / "demo_data" / "generated"
    expected = json.loads((base / "expected.json").read_text(encoding="utf-8"))
    ext_ok = ext_n = der_ok = der_n = abs_ok = abs_n = 0
    for caso in expected:
        ext = extraer(str(base / caso["pdf"]))
        ok_campos = (
            len(ext.renglones) == len(caso["renglones"])
            and all(e["nro"] == r["nro"] and e["practica"] == r["practica"]
                    and e["motivo"] == r["motivo"]
                    and e["facturado_cents"] == parse_importe(r["fact"])
                    and e["liquidado_cents"] == parse_importe(r["liq"])
                    for e, r in zip(ext.renglones, caso["renglones"]))
            and ext.total_txt.replace(" ", "") == caso["total"].replace("$", "").replace(" ", "")
            and not ext.dudosos
        )
        ext_n += 1
        ext_ok += ok_campos
        motivos = " | ".join(r["motivo"] for r in caso["renglones"])
        ref = rules.evaluar(motivos)
        clin = rules.es_clinico(motivos)
        der_n += 1
        der_ok += ref.sector == caso["esperado_sector"]
        abs_n += 1
        abs_ok += (clin or ref.sector == rules.PENDIENTE) == caso["esperado_abstencion"]
        print(f"{caso['id']}: extraccion={'OK' if ok_campos else 'FALLO'} "
              f"derivacion={ref.sector} (esp {caso['esperado_sector']}) "
              f"abstencion={clin or ref.sector == rules.PENDIENTE}")
    print(f"\nEXTRACCION {ext_ok}/{ext_n}  DERIVACION {der_ok}/{der_n}  ABSTENCION {abs_ok}/{abs_n}")
    return 0 if (ext_ok, der_ok, abs_ok) == (ext_n, der_n, abs_n) else 1


if __name__ == "__main__":
    raise SystemExit(main())
