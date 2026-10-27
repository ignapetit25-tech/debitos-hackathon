"""Adaptador REAL (JSON explícito). DESACTIVADO por defecto. NO VERIFICADO.

Mecanismo: intercambio de archivos JSON en un directorio acordado.
Jamás accede directo a la SQLite de producción. Montos entrantes se
revalidan (int centavos; se rechaza float).

No pudo verificarse sin recursos privados: documentado como limitación
en README. Activar solo con IA_DEMO_MODE=real + IA_REAL_DIR existente.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .contracts import ArancelService, Caso, CasoStore, Propuesta, ReglaRef, Renglon, RulesService

ACTIVO = os.environ.get("IA_DEMO_MODE", "synthetic").strip().lower() == "real"


def _real_dir() -> Path:
    d = os.environ.get("IA_REAL_DIR", "")
    if not ACTIVO or not d:
        raise RuntimeError("adaptador real desactivado (IA_DEMO_MODE != real)")
    p = Path(d)
    if not p.is_dir():
        raise RuntimeError(f"IA_REAL_DIR inexistente: {d}")
    return p


def _cents(valor: object, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(f"{campo} debe ser int centavos (rechazado float)")
    return valor


class RealStore(CasoStore):
    """Lee casos desde <IA_REAL_DIR>/casos/<id>.json, escribe propuestas."""

    def _leer(self, id: str) -> dict:
        ruta = _real_dir() / "casos" / f"{id}.json"
        return json.loads(ruta.read_text(encoding="utf-8"))

    def obtener_caso(self, id: str) -> Caso:
        data = self._leer(id)
        rengs = tuple(
            Renglon(int(r["nro"]), str(r["practica"]), str(r["motivo"]),
                    _cents(r["facturado_cents"], "facturado_cents"),
                    _cents(r["liquidado_cents"], "liquidado_cents"))
            for r in data["renglones"]
        )
        return Caso(str(data["id"]), str(data["financiador"]), str(data["factura"]),
                    rengs, _cents(data["total_debito_cents"], "total_debito_cents"),
                    str(data.get("estado", "nuevo")))

    def obtener_estado_casos(self, filtros: dict | None = None) -> list[Caso]:
        d = _real_dir() / "casos"
        casos = [self.obtener_caso(p.stem) for p in sorted(d.glob("*.json"))]
        filtros = filtros or {}
        return [c for c in casos
                if all(getattr(c, k, None) == v for k, v in filtros.items())]

    def guardar_propuesta(self, caso_id: str, propuesta: Propuesta) -> None:
        out = _real_dir() / "propuestas" / f"{propuesta.id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "id": propuesta.id, "caso_id": caso_id, "sector": propuesta.sector,
            "puntos": propuesta.regla.puntos, "frases": list(propuesta.regla.frases),
            "accion": propuesta.accion, "explicacion": propuesta.explicacion,
            "referencias": list(propuesta.referencias),
            "abstencion_clinica": propuesta.abstencion_clinica}, ensure_ascii=False,
            indent=2), encoding="utf-8")


class RealArancel(ArancelService):
    def consultar_arancel(self, prestacion, financiador, fecha):
        data = json.loads((_real_dir() / "aranceles.json").read_text(encoding="utf-8"))
        for a in data:
            if (a["prestacion"] == prestacion.upper() and a["financiador"] == financiador
                    and a["vigencia"][0] <= fecha <= a["vigencia"][1]):
                return {"prestacion": a["prestacion"], "financiador": a["financiador"],
                        "vigencia": a["vigencia"],
                        "valor_cents": _cents(a["valor_cents"], "valor_cents")}
        return None


class RealRules(RulesService):
    """Delega en reglas externas provistas por JSON (no ejecuta código ajeno)."""

    def evaluar_reglas(self, motivo: str) -> ReglaRef:
        data = json.loads((_real_dir() / "reglas.json").read_text(encoding="utf-8"))
        umbral = int(data.get("umbral", 3))
        mejor, frases = ("PENDIENTE_DE_VALIDACION", 0, ())
        texto = motivo.lower()
        for sector, grupos in data.get("sectores", {}).items():
            total, matched = 0, []
            for peso, frases_lista in grupos:
                for frase in frases_lista:
                    if frase.lower() in texto:
                        total += int(peso)
                        matched.append(frase)
            if total > mejor[1]:
                mejor = (sector, total, tuple(matched))
        if mejor[1] < umbral:
            return ReglaRef("PENDIENTE_DE_VALIDACION", mejor[1], ())
        return ReglaRef(mejor[0], mejor[1], mejor[2])
