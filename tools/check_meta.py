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


REPO_ROOT = Path(__file__).resolve().parent.parent


def cargar_env_repo() -> str:
    """Lee EXPLÍCITAMENTE REPO/.env (si existe). Devuelve estado legible."""
    env = REPO_ROOT / ".env"
    if not env.exists():
        return f"{env} (ausente)"
    n = 0
    for linea in env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))
            n += 1
    return f"{env} (cargado, {n} vars, valores jamás impresos)"


def main() -> int:
    env_info = cargar_env_repo()
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
