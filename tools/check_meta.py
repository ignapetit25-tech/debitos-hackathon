"""Prueba mínima autenticada contra Meta Muse Spark (datos ficticios).

Uso:  MODEL_API_KEY=... .venv/bin/python -B tools/check_meta.py
      (o con MODEL_API_KEY en .env, git-ignorado)

Imprime SOLO metadatos: proveedor, modelo, protocolo, latencia y
resultado del esquema. Jamás imprime la clave ni cuerpos de error.
Falla explícito si falta la clave o Meta responde mal: no hay
fallback al simulador en este script (IA_PROVIDER se fuerza a meta).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ia_debitos.agent import EXPLICACION_SCHEMA
from ia_debitos.provider import ProviderError, build_provider


def _cargar_env() -> None:
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for linea in env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def main() -> int:
    _cargar_env()
    os.environ["IA_PROVIDER"] = "meta"  # forzado: prohibido simular aquí
    try:
        prov = build_provider()
    except ProviderError as exc:
        print(f"FALLO explicito (sin clave o sin SDK): {exc}")
        return 1
    assert prov.name == "meta", f"proveedor inesperado: {prov.name}"
    prompt = (
        "Dato FICTICIO de prueba. Devolvé explicación de una línea "
        "para: BASE: Derivación a Convenios por reglas (10 pts: convenio). "
        "CASO: Financiador Ficticio Demo F-0001, 1 renglón."
    )
    t0 = time.monotonic()
    try:
        out = prov.complete_structured(prompt, EXPLICACION_SCHEMA, "explicacion")
    except ProviderError as exc:
        print(f"FALLO explicito de Meta (mensaje corto, sin cuerpos): {exc}")
        return 1
    ms = int((time.monotonic() - t0) * 1000)
    txt = out.get("explicacion", "")
    if "SIMULADO" in txt:
        print("FALLO: respuesta con marca de simulador, no es Meta real")
        return 1
    print(f"proveedor={prov.name}")
    print(f"modelo={os.environ.get('META_MODEL', 'muse-spark-1.3')}")
    print(f"protocolo={os.environ.get('META_PROTOCOL', 'responses')}")
    print(f"latencia_ms={ms} esquema=OK dudoso={out.get('dudoso')}")
    print(f"explicacion={txt[:300]}")
    print("clave_en_uso=SI (longitud no mostrada, valor jamás impreso)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
