"""Borradores deterministas (plantillas + datos del caso). Propuestas, no envíos."""
from __future__ import annotations

from .contracts import Caso
from .money import formato


def borrador_reclamo(caso: Caso, sector: str, detalle: str) -> dict:
    lineas = [f"- R{rl.nro} {rl.practica}: {rl.motivo} ({formato(rl.debito_cents)})"
              for rl in caso.renglones]
    cuerpo = (
        f"DATOS FICTICIOS — DEMOSTRACIÓN\nFinanciador: {caso.financiador}\n"
        f"Factura: {caso.factura} | Total debitado: {formato(caso.total_debito_cents)}\n"
        f"Sector derivado: {sector}\nDetalle: {detalle}\n\nRenglones:\n" + "\n".join(lineas) +
        "\n\nSe solicita revisión y extensión del motivo. [BORRADOR, requiere aprobación]"
    )
    return {"titulo": f"Borrador reclamo {caso.factura} ({caso.financiador})",
            "cuerpo": cuerpo}


def resumen_caso(caso: Caso, estado_propuesta: str) -> str:
    ok, dif = caso.validar()
    return (
        f"Caso {caso.id} [{caso.financiador} / {caso.factura}]: "
        f"{len(caso.renglones)} renglones, débito {formato(caso.total_debito_cents)}, "
        f"sumas {'OK' if ok else 'DIFIEREN ' + formato(dif)}, propuesta: {estado_propuesta}."
    )
