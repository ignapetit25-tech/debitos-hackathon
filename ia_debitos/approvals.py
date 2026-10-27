"""Revisión humana obligatoria. Sin aprobación no hay disposición final."""
from __future__ import annotations

from .contracts import Decision
from .synthetic import SyntheticStore

VEREDICTOS = ("aprobada", "rechazada")


def revisar(store: SyntheticStore, propuesta_id: str, revisor: str,
            veredicto: str, nota: str = "") -> Decision:
    """Registra la decisión humana y la deja en historial (antes/después)."""
    if veredicto not in VEREDICTOS:
        raise ValueError(f"veredicto inválido: {veredicto}")
    prop = store.propuesta(propuesta_id)
    if not prop:
        raise KeyError(f"propuesta inexistente: {propuesta_id}")
    if not revisor.strip():
        raise ValueError("se requiere revisor humano identificado")
    dec = Decision(propuesta_id, revisor.strip(), veredicto, nota.strip())
    antes = f"propuesta {veredicto} pendiente"
    despues = f"propuesta {prop['id']} {veredicto} por {dec.revisor}"
    store.registrar(prop["caso_id"], "revision",
                    f"{veredicto}: {dec.nota}" if dec.nota else veredicto,
                    antes, despues)
    return dec
