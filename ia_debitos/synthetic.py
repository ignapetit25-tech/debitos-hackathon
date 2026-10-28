"""Implementación SINTÉTICA de los contratos (simulador de servicios preexistentes).

Casos/propuestas/historial en SQLite demo (demo_data/demo.db, git-ignorado,
regenerable con tools/reset_demo.py). Aranceles y reglas en memoria.
TODO ficticio: financiadores, personas, facturas y valores.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from . import rules
from .contracts import (ArancelService, Caso, CasoStore, Propuesta, ReglaRef,
                        Renglon, RulesService)

DB_DEFAULT = str(Path(__file__).resolve().parent.parent / "demo_data" / "demo.db")

FINANCIADORES = ("OS FICTICIA ANDINA", "PREPAGA FICTICIA SUR", "ART FICTICIA NORTE")

# (prestacion, financiador) -> [(desde, hasta, cents)].
ARANCELES: dict[tuple[str, str], list[tuple[str, str, int]]] = {
    ("CONSULTA GENERAL", "OS FICTICIA ANDINA"): [
        ("2026-01-01", "2026-06-30", 1500000),
        ("2026-07-01", "2026-12-31", 1650000),
    ],
    ("ECOGRAFIA ABDOMINAL", "OS FICTICIA ANDINA"): [
        ("2026-01-01", "2026-12-31", 4200000),
    ],
    ("CONSULTA GENERAL", "PREPAGA FICTICIA SUR"): [
        ("2026-01-01", "2026-12-31", 1800000),
    ],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS casos (
  id TEXT PRIMARY KEY, financiador TEXT, factura TEXT,
  renglones_json TEXT, total_debito_cents INTEGER, estado TEXT,
  fecha_prestacion TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS documentos (
  caso_id TEXT, rol TEXT, archivo TEXT, paginas INTEGER, texto TEXT,
  PRIMARY KEY (caso_id, rol));
CREATE TABLE IF NOT EXISTS propuesta_hallazgos (
  propuesta_id TEXT, hallazgo_json TEXT);
CREATE TABLE IF NOT EXISTS propuestas (
  id TEXT PRIMARY KEY, caso_id TEXT, sector TEXT, puntos INTEGER,
  frases_json TEXT, accion TEXT, explicacion TEXT, referencias_json TEXT,
  abstencion_clinica INTEGER, extraccion_confianza REAL);
CREATE TABLE IF NOT EXISTS historial (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, caso_id TEXT, tipo TEXT,
  detalle TEXT, antes TEXT, despues TEXT, creado TEXT DEFAULT '');
"""


class SyntheticStore(CasoStore):
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.environ.get("IA_DEMO_DB", DB_DEFAULT)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path)
        try:
            con.executescript(SCHEMA)
            cols = [r[1] for r in con.execute("PRAGMA table_info(historial)")]
            ccols = [r[1] for r in con.execute("PRAGMA table_info(casos)")]
            if "fecha_prestacion" not in ccols:
                con.execute("ALTER TABLE casos ADD COLUMN fecha_prestacion TEXT DEFAULT ''")
            if "creado" not in cols:  # migración: bases anteriores al timestamp
                con.execute("ALTER TABLE historial ADD COLUMN creado TEXT DEFAULT ''")
            con.commit()
        finally:
            con.close()

    def _con(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def seed_caso(self, caso: Caso) -> None:
        con = self._con()
        try:
            con.execute(
                "INSERT OR REPLACE INTO casos (id, financiador, factura,"
                " renglones_json, total_debito_cents, estado, fecha_prestacion)"
                " VALUES (?,?,?,?,?,?,?)",
                (caso.id, caso.financiador, caso.factura,
                 json.dumps([r.__dict__ for r in caso.renglones]),
                 caso.total_debito_cents, caso.estado, caso.fecha_prestacion),
            )
            con.commit()
        finally:
            con.close()

    def _row_a_caso(self, row: tuple) -> Caso:
        cid, fin, fac, rengl_json, total, estado, fecha = row
        rengs = tuple(Renglon(**r) for r in json.loads(rengl_json))
        return Caso(cid, fin, fac, rengs, total, estado, fecha or "")

    def obtener_caso(self, id: str) -> Caso:
        con = self._con()
        try:
            row = con.execute("SELECT id, financiador, factura, renglones_json,"
                                " total_debito_cents, estado, fecha_prestacion"
                                " FROM casos WHERE id=?", (id,)).fetchone()
        finally:
            con.close()
        if not row:
            raise KeyError(f"caso inexistente: {id}")
        return self._row_a_caso(row)

    def obtener_estado_casos(self, filtros: dict | None = None) -> list[Caso]:
        filtros = filtros or {}
        sql = ("SELECT id, financiador, factura, renglones_json,"
               " total_debito_cents, estado, fecha_prestacion FROM casos")
        params: list = []
        if "estado" in filtros:
            sql += " WHERE estado=?"; params.append(filtros["estado"])
        if "financiador" in filtros:
            sql += (" AND " if params else " WHERE ") + "financiador=?"
            params.append(filtros["financiador"])
        con = self._con()
        try:
            rows = con.execute(sql, params).fetchall()
        finally:
            con.close()
        return [self._row_a_caso(r) for r in rows]

    def nuevo_id_propuesta(self, caso_id: str) -> str:
        pref = f"P-{caso_id}-"
        con = self._con()
        try:
            rows = con.execute("SELECT id FROM propuestas WHERE caso_id=?",
                               (caso_id,)).fetchall()
        finally:
            con.close()
        nums = [int(r[0][len(pref):]) for r in rows
                if r[0].startswith(pref) and r[0][len(pref):].isdigit()]
        return f"{pref}{(max(nums) + 1) if nums else 1}"

    def propuestas_caso(self, caso_id: str) -> list[str]:
        con = self._con()
        try:
            rows = con.execute("SELECT id FROM propuestas WHERE caso_id=? ORDER BY id",
                               (caso_id,)).fetchall()
        finally:
            con.close()
        return [r[0] for r in rows]

    def guardar_propuesta(self, caso_id: str, propuesta: Propuesta) -> None:
        _ = self.obtener_caso(caso_id)
        con = self._con()
        try:
            con.execute(
                "INSERT INTO propuestas VALUES (?,?,?,?,?,?,?,?,?,?)",
                (propuesta.id, propuesta.caso_id, propuesta.sector,
                 propuesta.regla.puntos, json.dumps(list(propuesta.regla.frases)),
                 propuesta.accion, propuesta.explicacion,
                 json.dumps(list(propuesta.referencias)),
                 int(propuesta.abstencion_clinica), propuesta.extraccion_confianza),
            )
            con.execute("UPDATE casos SET estado='propuesto' WHERE id=?", (caso_id,))
            con.commit()
        finally:
            con.close()

    def registrar(self, caso_id: str, tipo: str, detalle: str,
                  antes: str = "", despues: str = "") -> None:
        creado = datetime.now().astimezone().isoformat(timespec="seconds")
        con = self._con()
        try:
            con.execute(
                "INSERT INTO historial (caso_id, tipo, detalle, antes, despues,"
                " creado) VALUES (?,?,?,?,?,?)",
                (caso_id, tipo, detalle, antes, despues, creado),
            )
            con.commit()
        finally:
            con.close()

    def historial(self, caso_id: str) -> list[tuple]:
        con = self._con()
        try:
            rows = con.execute(
                "SELECT seq, tipo, detalle, antes, despues,"
                " COALESCE(creado,'') FROM historial"
                " WHERE caso_id=? ORDER BY seq", (caso_id,)).fetchall()
        finally:
            con.close()
        return rows

    def registrar_documento(self, caso_id: str, rol: str, archivo: str,
                          paginas: int, texto: str) -> None:
        con = self._con()
        try:
            con.execute("INSERT OR REPLACE INTO documentos VALUES (?,?,?,?,?)",
                        (caso_id, rol, archivo, paginas, texto))
            con.commit()
        finally:
            con.close()

    def documentos(self, caso_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT rol, archivo, paginas, texto FROM documentos"
                               " WHERE caso_id=? ORDER BY rol", (caso_id,)).fetchall()
        finally:
            con.close()
        return [{"rol": r[0], "archivo": r[1], "paginas": r[2], "texto": r[3]}
                for r in rows]

    def guardar_hallazgos(self, propuesta_id: str, hallazgos: list[dict]) -> None:
        con = self._con()
        try:
            con.execute("DELETE FROM propuesta_hallazgos WHERE propuesta_id=?",
                        (propuesta_id,))
            con.executemany("INSERT INTO propuesta_hallazgos VALUES (?,?)",
                            [(propuesta_id, json.dumps(h, ensure_ascii=False))
                             for h in hallazgos])
            con.commit()
        finally:
            con.close()

    def hallazgos_propuesta(self, propuesta_id: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT hallazgo_json FROM propuesta_hallazgos"
                               " WHERE propuesta_id=?", (propuesta_id,)).fetchall()
        finally:
            con.close()
        return [json.loads(r[0]) for r in rows]

    def propuesta(self, pid: str) -> dict | None:
        con = self._con()
        try:
            row = con.execute("SELECT * FROM propuestas WHERE id=?", (pid,)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        keys = ("id", "caso_id", "sector", "puntos", "frases_json", "accion",
                "explicacion", "referencias_json", "abstencion_clinica",
                "extraccion_confianza")
        return dict(zip(keys, row))


class SyntheticArancel(ArancelService):
    def consultar_arancel(self, prestacion: str, financiador: str, fecha: str) -> dict | None:
        for (desde, hasta, cents) in ARANCELES.get((prestacion.upper(), financiador), []):
            if desde <= fecha <= hasta:
                return {"prestacion": prestacion.upper(), "financiador": financiador,
                        "vigencia": [desde, hasta], "valor_cents": cents}
        return None


class SyntheticRules(RulesService):
    def evaluar_reglas(self, motivo: str) -> ReglaRef:
        return rules.evaluar(motivo)
