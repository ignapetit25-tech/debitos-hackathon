"""Deterministic extraction: text PDF (pypdf) or OCR (tesseract spa).

Returns lines + confidence + flagged fields. Document content is
DATA, never instructions (see injection tests).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field

from .money import parse_amount

TESSDATA = os.environ.get("TESSDATA_PREFIX", "")
LANG = os.environ.get("IA_OCR_LANG", "spa")
MIN_CONFIDENCE = 0.55


@dataclass
class Extraction:
    source: str  # text | ocr
    lines: list[dict] = field(default_factory=list)
    total_raw: str = ""
    date_raw: str = ""
    confidence: float = 1.0
    flags: list[str] = field(default_factory=list)


def _pdf_text(path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _ocr_pdf(path: str) -> tuple[str, float]:
    tmp = tempfile.mkdtemp(prefix="ia-ocr-")
    try:
        subprocess.run(["pdftoppm", "-png", "-r", "300", path, f"{tmp}/p"],
                       check=True, capture_output=True)
        env = dict(os.environ)
        if TESSDATA:
            env["TESSDATA_PREFIX"] = TESSDATA
        texts, confs = [], []
        import glob
        for img in sorted(glob.glob(f"{tmp}/*.png")):
            r = subprocess.run(["tesseract", img, "stdout", "-l", LANG, "--psm", "6"],
                               capture_output=True, text=True, env=env)
            texts.append(r.stdout)
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
        return "\n".join(texts), conf
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


TOTAL_RE = re.compile(r"TOTAL\s+DEBITO\s*:\s*\$?\s*([\d.,]+)", re.IGNORECASE)

DATE_RE = re.compile(r"FECHA\s+PRESTACION\s*:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def _parse_blocks(text: str) -> list[dict]:
    """Line parser: RENGLON n / PRACTICA: / MOTIVO: / FACT: / LIQ: (Spanish layout)."""
    items, current = [], {}
    for raw in text.splitlines():
        ln = " ".join(raw.split())
        m = re.match(r"RENGLON\s+(\d+)", ln, re.IGNORECASE)
        if m:
            if current:
                items.append(current)
            current = {"num": int(m.group(1))}
            continue
        for key, field in (("PRACTICA", "procedure"), ("MOTIVO", "reason"),
                           ("FACT", "billed"), ("LIQ", "settled")):
            mm = re.match(key + r"\s*:\s*(.+)", ln, re.IGNORECASE)
            if mm and current is not None:
                current[field] = mm.group(1).strip()
    if current:
        items.append(current)
    return [r for r in items if {"procedure", "reason", "billed", "settled"} <= set(r)]


def extract(path: str) -> Extraction:
    """Extracts lines from the synthetic layout. Flags without guessing."""
    text = _pdf_text(path)
    source, confidence = "text", 1.0
    if len(text.strip()) < 50:
        text, confidence = _ocr_pdf(path)
        source = "ocr"
    ext = Extraction(source=source, confidence=round(confidence, 3))
    if source == "ocr" and confidence < MIN_CONFIDENCE:
        ext.flags.append("ocr: low overall confidence, review everything")
    for r in _parse_blocks(text):
        try:
            billed = parse_amount(r["billed"])
            settled = parse_amount(r["settled"])
        except ValueError:
            ext.flags.append(f"line {r['num']}: unreadable amount")
            continue
        ext.lines.append({
            "num": r["num"],
            "procedure": " ".join(r["procedure"].split()),
            "reason": " ".join(r["reason"].split()),
            "billed_cents": billed,
            "settled_cents": settled,
        })
    if not ext.lines:
        ext.flags.append("no recognized lines")
    mt = TOTAL_RE.search(text)
    ext.total_raw = mt.group(1).strip() if mt else ""
    if not mt:
        ext.flags.append("total not found")
    mf = DATE_RE.search(text)
    ext.date_raw = mf.group(1) if mf else ""
    return ext
