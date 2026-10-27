"""Reglas sintéticas NUEVAS para la demo (no copian el sistema preexistente).

Puntaje entero + umbral; si el motivo toca un disparador clínico, la
capa IA se abstiene: deriva a humanos sin recomendar aceptar/reclamar.
"""
from __future__ import annotations

import re
import unicodedata

from .contracts import ReglaRef

UMBRAL = 3
PENDIENTE = "PENDIENTE_DE_VALIDACION"

# Disparadores clínicos: tecnicismo médico que exige juicio humano.
DISPARADORES_CLINICOS = (
    "pertinencia medica",
    "justificacion clinica",
    "criterio medico",
    "segun parte quirurgico",
    "no se realizo la operacion",
)

# Juego mínimo de frases por sector, redactado para la demo.
PATRONES: dict[str, list[tuple[int, list[str]]]] = {
    "Convenios": [
        (3, ["valor del convenio", "valores del convenio",
              "diferencia de arancel", "valor pactado",
              "difiere del valor pactado"]),
        (1, ["convenio", "arancel", "pactado"]),
    ],
    "Facturación": [
        (3, ["coseguro no descontado", "coseguros no descontados",
              "falta de autorizacion", "sin autorizacion",
              "no adjunta documentacion", "facturado como exento",
              "facturado como gravado"]),
        (1, ["facturacion", "coseguro", "autorizacion", "documentacion"]),
    ],
    "Auditoría Médica": [
        (3, ["auditoria medica", "se reconoce", "se reconocen",
              "incluido en", "parte quirurgico"]),
        (1, ["clinica", "justificacion"]),
    ],
    "Farmacia": [
        (3, ["manual farmaceutico", "vademecum", "medicamento no reconocido"]),
        (1, ["medicamento", "farmacia"]),
    ],
}


def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def es_clinico(motivo: str) -> bool:
    texto = normalizar(motivo)
    return any(d in texto for d in DISPARADORES_CLINICOS)


def _coincide(frase: str, texto: str) -> bool:
    if len(frase) <= 3:
        return re.search(rf"\b{re.escape(frase)}\b", texto) is not None
    return frase in texto


def evaluar(motivo: str) -> ReglaRef:
    if not isinstance(motivo, str) or not motivo.strip():
        return ReglaRef(PENDIENTE, 0, ())
    texto = normalizar(motivo)
    puntajes: dict[str, int] = {}
    hits: dict[str, list[str]] = {}
    for sector, grupos in PATRONES.items():
        total, matched = 0, []
        for peso, frases in grupos:
            for frase in frases:
                if _coincide(frase, texto):
                    total += peso
                    matched.append(frase)
        if total:
            puntajes[sector], hits[sector] = total, matched
    if not puntajes:
        return ReglaRef(PENDIENTE, 0, ())
    mejor = max(puntajes.values())
    ganadores = [s for s, p in puntajes.items() if p == mejor]
    if len(ganadores) > 1 or mejor < UMBRAL:
        return ReglaRef(PENDIENTE, mejor, ())
    return ReglaRef(ganadores[0], mejor, tuple(hits[ganadores[0]]))
