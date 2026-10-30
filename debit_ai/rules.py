"""Synthetic NEW rules for the demo (they do not copy the prior system).

Integer score + threshold; when a reason hits a clinical trigger,
the AI layer abstains: it routes to humans without recommending accept/claim.

Phrase lists match Spanish document text (fictitious memos).
"""
from __future__ import annotations

import re
import unicodedata

from .contracts import RuleRef

THRESHOLD = 3
PENDING = "PENDING_VALIDATION"

# Clinical triggers: medical jargon requiring human judgment.
CLINICAL_TRIGGERS = (
    # Confirmed by the debit owner: "La medicación utilizada no
    # corresponde al cuadro del paciente" -> Medical Audit evaluates.
    "no corresponde al cuadro",
    "pertinencia medica",
    "justificacion clinica",
    "criterio medico",
    "segun parte quirurgico",
    "no se realizo la operacion",
)

# Minimal phrase set per team, written for the demo.
PATTERNS: dict[str, list[tuple[int, list[str]]]] = {
    "Agreements": [
        (3, ["valor del convenio", "valores del convenio",
              "diferencia de arancel", "valor pactado",
              "difiere del valor pactado"]),
        (1, ["convenio", "arancel", "pactado"]),
    ],
    "Billing": [
        (3, ["coseguro no descontado", "coseguros no descontados",
              "falta de autorizacion", "sin autorizacion",
              "no adjunta documentacion", "facturado como exento",
              "facturado como gravado"]),
        (1, ["facturacion", "coseguro", "autorizacion", "documentacion"]),
    ],
    "Medical Audit": [
        (3, ["auditoria medica", "se reconoce", "se reconocen",
              "incluido en", "parte quirurgico"]),
        (1, ["clinica", "justificacion"]),
    ],
    "Pharmacy": [
        (3, ["manual farmaceutico", "vademecum", "medicamento no reconocido"]),
        (1, ["medicamento", "farmacia"]),
    ],
}


def normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def is_clinical(reason: str) -> bool:
    text = normalize(reason)
    return any(d in text for d in CLINICAL_TRIGGERS)


def _matches(phrase: str, text: str) -> bool:
    if len(phrase) <= 3:
        return re.search(rf"\b{re.escape(phrase)}\b", text) is not None
    return phrase in text


def evaluate(reason: str) -> RuleRef:
    if not isinstance(reason, str) or not reason.strip():
        return RuleRef(PENDING, 0, ())
    text = normalize(reason)
    scores: dict[str, int] = {}
    hits: dict[str, list[str]] = {}
    for team, groups in PATTERNS.items():
        total, matched = 0, []
        for weight, phrases in groups:
            for phrase in phrases:
                if _matches(phrase, text):
                    total += weight
                    matched.append(phrase)
        if total:
            scores[team], hits[team] = total, matched
    if not scores:
        return RuleRef(PENDING, 0, ())
    best = max(scores.values())
    winners = [s for s, p in scores.items() if p == best]
    if len(winners) > 1 or best < THRESHOLD:
        return RuleRef(PENDING, best, ())
    return RuleRef(winners[0], best, tuple(hits[winners[0]]))
