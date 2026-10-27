"""Extracción determinista: PDF con texto (pypdf) u OCR (tesseract spa).

Devuelve renglones + confianza + campos dudosos. El contenido del
documento es DATO, nunca instrucción (ver tests de inyección).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field

from .money import parse_importe

TESSDATA = os.environ.get("TESSDATA_PREFIX", "")
LANG = os.environ.get("IA_OCR_LANG", "spa")
CONF_MINIMA = 0.55


@dataclass
class Extraccion:
    origen: str  # texto | ocr
    renglones: list[dict] = field(default_factory=list)
    total_txt: str = ""
    confianza: float = 1.0
    dudosos: list[str] = field(default_factory=list)


def _texto_pdf(ruta: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(ruta)
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _ocr_pdf(ruta: str) -> tuple[str, float]:
    tmp = tempfile.mkdtemp(prefix="ia-ocr-")
    try:
        subprocess.run(["pdftoppm", "-png", "-r", "300", ruta, f"{tmp}/p"],
                       check=True, capture_output=True)
        env = dict(os.environ)
        if TESSDATA:
            env["TESSDATA_PREFIX"] = TESSDATA
        textos, confs = [], []
        import glob
        for img in sorted(glob.glob(f"{tmp}/*.png")):
            r = subprocess.run(["tesseract", img, "stdout", "-l", LANG, "--psm", "6"],
                               capture_output=True, text=True, env=env)
            textos.append(r.stdout)
            tsv_base = f"{tmp}/conf"
            subprocess.run(["tesseract", img, tsv_base, "-l", LANG, "--psm", "6", "tsv"],
                           capture_output=True, text=True, env=env)
            vals = []
            tsv_path = Path(tsv_base + ".tsv")
            tsv_txt = tsv_path.read_text(encoding="utf-8", errors="replace") \
                if tsv_path.exists() else ""
            for line in tsv_txt.splitlines()[1:]:
                cols = line.rstrip("\n").split("\t")
                if len(cols) >= 12 and cols[0] == "5":
                    try:
                        c = float(cols[10])
                    except ValueError:
                        continue
                    if c >= 0:
                        vals.append(c)
            if vals:
                confs.append(sum(vals) / len(vals) / 100.0)
        conf = sum(confs) / len(confs) if confs else 0.0
        return "\n".join(textos), conf
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


TOTAL_RE = re.compile(r"TOTAL\s+DEBITO\s*:\s*\$?\s*([\d.,]+)", re.IGNORECASE)


def _parse_bloques(texto: str) -> list[dict]:
    """Parser por líneas: RENGLON n / PRACTICA: / MOTIVO: / FACT: / LIQ:."""
    rengs, actual = [], {}
    for cruda in texto.splitlines():
        ln = " ".join(cruda.split())
        m = re.match(r"RENGLON\s+(\d+)", ln, re.IGNORECASE)
        if m:
            if actual:
                rengs.append(actual)
            actual = {"nro": int(m.group(1))}
            continue
        for clave in ("PRACTICA", "MOTIVO", "FACT", "LIQ"):
            mm = re.match(clave + r"\s*:\s*(.+)", ln, re.IGNORECASE)
            if mm and actual is not None:
                actual[clave.lower()] = mm.group(1).strip()
    if actual:
        rengs.append(actual)
    return [r for r in rengs if {"practica", "motivo", "fact", "liq"} <= set(r)]


def extraer(ruta: str) -> Extraccion:
    """Extrae renglones del layout sintético. Marca dudosos sin adivinar."""
    texto = _texto_pdf(ruta)
    origen, confianza = "texto", 1.0
    if len(texto.strip()) < 50:
        texto, confianza = _ocr_pdf(ruta)
        origen = "ocr"
    ext = Extraccion(origen=origen, confianza=round(confianza, 3))
    if origen == "ocr" and confianza < CONF_MINIMA:
        ext.dudosos.append("ocr: confianza global baja, revisar todo")
    for r in _parse_bloques(texto):
        try:
            fact = parse_importe(r["fact"])
            liq = parse_importe(r["liq"])
        except ValueError:
            ext.dudosos.append(f"renglon {r['nro']}: importe ilegible")
            continue
        ext.renglones.append({
            "nro": r["nro"],
            "practica": " ".join(r["practica"].split()),
            "motivo": " ".join(r["motivo"].split()),
            "facturado_cents": fact,
            "liquidado_cents": liq,
        })
    if not ext.renglones:
        ext.dudosos.append("sin renglones reconocidos")
    mt = TOTAL_RE.search(texto)
    ext.total_txt = mt.group(1).strip() if mt else ""
    if not mt:
        ext.dudosos.append("total no encontrado")
    return ext
