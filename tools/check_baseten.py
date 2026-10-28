"""Prueba mínima contra Baseten Model API (datos ficticios).

Uso (tras ingresar la clave en agent .env):
  .venv/bin/python -B tools/check_baseten.py

Imprime SOLO metadatos acotados: proveedor, modelo pedido/devuelto,
ID de respuesta, estado, latencia, consumo informado y hasta 300
caracteres de la respuesta. Jamás imprime la clave ni cuerpos de
error. Timeout explícito, sin reintentos. Falla explícito: nunca
simula una integración exitosa.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from check_meta import cargar_env_repo  # noqa: E402

from ia_debitos.agent import EXPLICACION_SCHEMA  # noqa: E402
from ia_debitos.provider import ProviderError, build_provider  # noqa: E402


def main() -> int:
    env_info = cargar_env_repo()
    os.environ["IA_PROVIDER"] = "baseten"  # forzado: prohibido simular aquí
    try:
        prov = build_provider()
    except ProviderError as exc:
        print(f"FALLO explicito (sin clave o sin SDK): {exc}")
        return 1
    assert prov.name == "baseten", f"proveedor inesperado: {prov.name}"
    prompt = (
        "Dato FICTICIO de prueba. Devolvé explicación de una línea "
        "para: BASE: Derivación a Convenios por reglas (10 pts: convenio). "
        "CASO: Financiador Ficticio Demo F-0001, 1 renglón."
    )
    t0 = time.monotonic()
    try:
        out = prov.complete_structured(prompt, EXPLICACION_SCHEMA, "explicacion")
    except ProviderError as exc:
        print(f"FALLO explicito de Baseten (mensaje corto, sin cuerpos): {exc}")
        return 1
    ms = int((time.monotonic() - t0) * 1000)
    txt = out.get("explicacion", "")
    if "SIMULADO" in txt:
        print("FALLO: respuesta con marca de simulador, no es Baseten real")
        return 1
    m = dict(getattr(prov, "last_call", {}) or {})
    print(f"env={env_info}")
    print(f"proveedor={m.get('proveedor')} estado={m.get('estado')}")
    print(f"modelo_pedido={m.get('modelo_pedido')}")
    print(f"modelo_devuelto={m.get('modelo_devuelto')}")
    print(f"respuesta_id={m.get('respuesta_id')}")
    print(f"protocolo={m.get('protocolo')} latencia_ms={ms} esquema=OK")
    print(f"uso={m.get('uso')} dudoso={out.get('dudoso')}")
    print(f"explicacion={txt[:300]}")
    print("clave_en_uso=SI (valor jamás impreso)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
