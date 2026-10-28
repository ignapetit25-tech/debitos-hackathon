"""Revisión humana obligatoria. Sin aprobación no hay disposición final."""
from __future__ import annotations

from .contracts import Decision
from .synthetic import SyntheticStore

VEREDICTOS = ("aprobada", "rechazada")
DECISIONES_SEG = ("recuperado", "parcial", "aceptado", "pendiente")


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


def seguimiento(store: SyntheticStore, propuesta_id: str, decision: str,
                recuperable_cents: int, aceptado_cents: int,
                responsable: str, fecha: str = "", nota: str = "") -> dict:
    """Devolución del sector: respuesta con montos, responsable y fecha."""
    from datetime import date as _date
    if decision not in DECISIONES_SEG:
        raise ValueError(f"decisión inválida: {decision}")
    for nombre, v in (("recuperable", recuperable_cents), ("aceptado", aceptado_cents)):
        if type(v) is not int or v < 0:
            raise ValueError(f"{nombre} debe ser entero >= 0")
    if not responsable.strip():
        raise ValueError("se requiere responsable identificado")
    if not fecha:
        fecha = _date.today().isoformat()
    else:
        _date.fromisoformat(fecha[:10])
        fecha = fecha[:10]
    prop = store.propuesta(propuesta_id)
    if not prop:
        raise KeyError(f"propuesta inexistente: {propuesta_id}")
    store.guardar_seguimiento(propuesta_id, decision, recuperable_cents,
                              aceptado_cents, responsable.strip(), fecha,
                              nota.strip())
    store.registrar(prop["caso_id"], "seguimiento",
                    f"{decision}: recuperable {recuperable_cents} aceptado {aceptado_cents}",
                    antes="derivación sin respuesta",
                    despues=f"respuesta {prop['sector']} por {responsable.strip()}")
    return store.seguimiento(propuesta_id)
