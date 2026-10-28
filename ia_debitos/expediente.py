"""Expediente administrativo: conciliacion determinista + hallazgos verificables.

Responde: que desconto el financiador, que documentacion respalda la
diferencia y que debe verificar el sector responsable. Todo calculo en
centavos enteros; el modelo no interviene aqui.

Verificado significa: la referencia existe y la cita coincide con el
documento (normalizada). NO valida que la interpretacion sea correcta.
"""
from __future__ import annotations

import re
from dataclasses import replace

from . import rules
from .contracts import Caso, Hallazgo, ReglaRef
from .money import formato, parse_importe

RESPALDADA = "diferencia_respaldada"
INCONSISTENCIA = "inconsistencia"
INSUFICIENTE = "evidencia_insuficiente"
CLINICO = "clinico_humano"

VIGENCIA_RE = re.compile(r"VIGENCIA\s*:\s*(\d{4}-\d{2}-\d{2})\s*\.\.\s*(\d{4}-\d{2}-\d{2})")
LIQ_RENGLON_RE = re.compile(r"RENGLON\s+(\d+)\s*:\s*DEBITO\s+\$([\d.,]+)\s*MOTIVO\s*:\s*(.+)")
ARANCEL_RE = re.compile(r"ARANCEL\s*:\s*(.+?)\s+\$([\d.,]+)")


def norm_cita(texto: str) -> str:
    return " ".join(rules.normalizar(texto or "").split())


def verificar_hallazgo(h: Hallazgo, texto_doc: str, paginas_doc: int) -> tuple[bool, str]:
    if h.pagina < 1 or h.pagina > paginas_doc:
        return False, f"pagina {h.pagina} inexistente (doc tiene {paginas_doc})"
    frag = norm_cita(h.fragmento)
    if len(frag) < 12:
        return False, "fragmento demasiado corto para verificar"
    if frag not in norm_cita(texto_doc):
        return False, "fragmento no encontrado en el documento"
    return True, "referencia existe y cita coincide"


def parse_convenio(texto: str) -> dict:
    m = VIGENCIA_RE.search(texto or "")
    aranceles = {}
    for mm in ARANCEL_RE.finditer(texto or ""):
        try:
            aranceles[mm.group(1).strip().upper()] = parse_importe("$" + mm.group(2))
        except ValueError:
            continue
    return {"vigencia": (m.group(1), m.group(2)) if m else None, "aranceles": aranceles}


def parse_liquidacion(texto: str) -> dict:
    out = {}
    for mm in LIQ_RENGLON_RE.finditer(texto or ""):
        try:
            out[int(mm.group(1))] = (parse_importe("$" + mm.group(2)), mm.group(3).strip())
        except ValueError:
            continue
    return out


def valor_convenido(prestacion: str, financiador: str, fecha: str,
                    doc_convenio: dict | None,
                    arancel_fn) -> tuple[int | None, str]:
    if doc_convenio and doc_convenio.get("texto"):
        conv = parse_convenio(doc_convenio["texto"])
        vig = conv["vigencia"]
        if not vig:
            return None, "convenio sin vigencia legible"
        if not fecha:
            return None, "sin fecha de prestacion: vigencia no contrastable"
        if not (vig[0] <= fecha <= vig[1]):
            return None, f"prestacion {fecha} fuera de vigencia {vig[0]}..{vig[1]}"
        val = conv["aranceles"].get(prestacion.upper())
        if val is None:
            return None, f"prestacion sin arancel en convenio ({vig[0]}..{vig[1]})"
        return val, f"convenio {vig[0]}..{vig[1]}"
    if not fecha:
        return None, "sin fecha de prestacion: arancel no contrastable"
    ar = arancel_fn(prestacion, financiador, fecha)
    if not ar:
        return None, "sin valor convenido aplicable a la fecha"
    fuente = f"{ar.get('convenio', 'arancel')} {ar.get('version', '')} {ar['vigencia'][0]}..{ar['vigencia'][1]}".strip()
    if ar.get("ambiguo"):
        fuente += " [solape de vigencias: revisar]"
    return ar["valor_cents"], fuente


def _hid(caso_id: str, nro: int, i: int) -> str:
    return f"H-{caso_id}-R{nro}-{i}"


def investigar(store, caso: Caso, arancel_fn) -> dict:
    docs = {d["rol"]: d for d in store.documentos(caso.id)}
    fac_txt = docs.get("factura", {}).get("texto", "")
    renglones, hallazgos, faltantes = [], [], []
    nh = 0

    def add(rn: int, tipo: str, doc: str, frag: str, interp: str, lim: str = "") -> None:
        nonlocal nh
        nh += 1
        h = Hallazgo(_hid(caso.id, rn, nh), caso.id, rn, tipo, doc, 1, frag, interp, lim)
        texto = docs.get(doc, {}).get("texto", "") if doc != "factura" else (
            fac_txt or " ".join(r.motivo for r in caso.renglones))
        ok, _ = verificar_hallazgo(h, texto, docs.get(doc, {}).get("paginas", 1))
        hallazgos.append(replace(h, verificado=ok))

    liq = parse_liquidacion(docs.get("liquidacion", {}).get("texto", ""))
    for r in caso.renglones:
        if r.nro in liq and liq[r.nro][0] != r.debito_cents:
            faltantes.append(f"R{r.nro}: liquidacion dice {formato(liq[r.nro][0])}, "
                             f"factura da {formato(r.debito_cents)}")
            add(r.nro, INCONSISTENCIA, "liquidacion",
                f"RENGLON {r.nro}: DEBITO {formato(liq[r.nro][0])}",
                f"La liquidacion debita {formato(liq[r.nro][0])} pero factura menos "
                f"liquidado da {formato(r.debito_cents)}.",
                "Conciliar documentos antes de derivar.")
    ok_sum, dif = caso.validar()
    if not ok_sum:
        faltantes.append(f"sumas inconsistentes: dif {formato(dif)}")
        add(0, INCONSISTENCIA, "factura", caso.renglones[0].motivo if caso.renglones else "caso",
            f"La suma de debitos difiere del total en {formato(dif)}.",
            "Revisar renglones contra factura antes de derivar.")
    for r in caso.renglones:
        ref, fuente = valor_convenido(r.practica, caso.financiador,
                                      caso.fecha_prestacion, docs.get("convenio"),
                                      arancel_fn)
        renglones.append({"nro": r.nro, "practica": r.practica, "motivo": r.motivo,
                          "facturado_cents": r.facturado_cents,
                          "liquidado_cents": r.liquidado_cents,
                          "debito_cents": r.debito_cents,
                          "ref_cents": ref, "fuente_ref": fuente})
        if rules.es_clinico(r.motivo):
            add(r.nro, CLINICO, "factura", r.motivo,
                "Motivo con contenido clinico: se deriva a personas.",
                "Sin recomendacion economica; Auditoria Medica decide.")
        elif ref is None:
            faltantes.append(f"R{r.nro}: {fuente}")
            add(r.nro, INSUFICIENTE, "factura", r.motivo,
                f"No puede determinarse valor convenido: {fuente}.",
                "Detenerse: pedir fecha de prestacion o convenio vigente.")
        elif r.facturado_cents > ref:
            add(r.nro, RESPALDADA, "factura", r.motivo,
                f"Facturado {formato(r.facturado_cents)} supera {fuente.split(' ', 1)[0]} "
                f"{formato(ref)}; liquidado {formato(r.liquidado_cents)}. "
                f"Diferencia a conciliar: {formato(r.debito_cents)}.",
                "Respalda montos, no la procedencia juridica del reclamo.")
        else:
            faltantes.append(f"R{r.nro}: facturado no supera valor convenido")
            add(r.nro, INCONSISTENCIA, "factura", r.motivo,
                f"Facturado {formato(r.facturado_cents)} no supera valor "
                f"{formato(ref)} ({fuente}): el debito requiere revision.",
                "No reclamar sin entender por que se debito.")
    regla: ReglaRef = rules.evaluar(" | ".join(r.motivo for r in caso.renglones))
    tipos = {h.tipo for h in hallazgos}
    if CLINICO in tipos:
        sector, accion = "Auditoría Médica", "derivar_humano"
        paso = "Derivar a personas: hay contenido clinico."
    elif INCONSISTENCIA in tipos or INSUFICIENTE in tipos or regla.sector == rules.PENDIENTE:
        sector = regla.sector if regla.sector != rules.PENDIENTE else rules.PENDIENTE
        accion = "pedir_extension"
        paso = "Pedir aclaracion o documentacion faltante antes de decidir."
    else:
        sector, accion = regla.sector, "reclamar"
        paso = f"Respaldado: derivar a {regla.sector} para reclamo."
    return {"renglones": renglones, "hallazgos": hallazgos, "faltantes": faltantes,
            "regla": regla, "sector": sector, "accion": accion,
            "siguiente_paso": paso, "sumas_ok": ok_sum, "dif_cents": dif}
