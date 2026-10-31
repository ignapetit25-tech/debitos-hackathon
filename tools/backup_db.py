"""Verifiable SQLite backups for the demo DB. No paid calls.

Usage:
  .venv/bin/python -B tools/backup_db.py --db demo_data/demo.db \\
      --to demo_data/backups/demo-20261031-120000.db

A backup is reported VALID only when ALL of these hold:
1. the source passes PRAGMA integrity_check;
2. the copy is made with the sqlite3 backup API (safe against
   torn copies of a DB another process has open);
3. the backup passes PRAGMA integrity_check;
4. a restore test copies the backup to a separate temp path and
   every table matches the source (row counts + content hash).

The target must NOT exist (never silently overwrite a backup).
A file alone is not a valid backup: only a full pass is.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


def _tables(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def content_fingerprint(con: sqlite3.Connection) -> dict[str, dict]:
    """Per-table {rows, sha256} over deterministically ordered rows."""
    fp = {}
    for table in _tables(con):
        rows = con.execute(f'SELECT * FROM "{table}"').fetchall()
        ordered = sorted(repr(r) for r in rows)
        h = hashlib.sha256("\n".join(ordered).encode("utf-8")).hexdigest()
        fp[table] = {"rows": len(rows), "sha256": h}
    return fp


def integrity_ok(con: sqlite3.Connection) -> bool:
    return con.execute("PRAGMA integrity_check").fetchall() == [("ok",)]


def _fail(path: Path, msg: str) -> None:
    path.unlink(missing_ok=True)
    raise ValueError(msg)


def backup_database(src: str, dst: str) -> dict:
    """Verified backup of src into dst (dst must not exist)."""
    s, d = Path(src), Path(dst)
    if not s.is_file():
        raise ValueError(f"source DB not found: {s}")
    if d.exists():
        raise FileExistsError(f"refusing to overwrite existing backup: {d}")
    d.parent.mkdir(parents=True, exist_ok=True)
    src_con = sqlite3.connect(f"file:{s}?mode=ro", uri=True)
    try:
        if not integrity_ok(src_con):
            raise ValueError(f"source DB failed integrity_check: {s}")
        want = content_fingerprint(src_con)
    finally:
        src_con.close()
    dst_con = sqlite3.connect(str(d))
    try:
        src_ro = sqlite3.connect(f"file:{s}?mode=ro", uri=True)
        try:
            src_ro.backup(dst_con)
        finally:
            src_ro.close()
        if not integrity_ok(dst_con):
            _fail(d, f"backup failed integrity_check: {d}")
        if content_fingerprint(dst_con) != want:
            _fail(d, f"backup content differs from source: {d}")
    finally:
        dst_con.close()
    tmpdir = Path(tempfile.mkdtemp(prefix="restore-test-"))
    try:
        trial = tmpdir / "restore.db"
        bak_con = sqlite3.connect(f"file:{d}?mode=ro", uri=True)
        try:
            trial_con = sqlite3.connect(str(trial))
            try:
                bak_con.backup(trial_con)
            finally:
                trial_con.close()
        finally:
            bak_con.close()
        trial_con = sqlite3.connect(str(trial))
        try:
            if not integrity_ok(trial_con):
                _fail(d, f"restore test failed integrity_check: {d}")
            if content_fingerprint(trial_con) != want:
                _fail(d, f"restore test content differs: {d}")
        finally:
            trial_con.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    blob = d.read_bytes()
    return {"source": str(s), "backup": str(d),
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "tables": {t: v["rows"] for t, v in want.items()},
            "integrity": "ok", "restore_test": "ok", "valid": True}


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help="source demo DB")
    ap.add_argument("--to", required=True, help="backup target (must not exist)")
    ns = ap.parse_args(argv)
    try:
        rep = backup_database(ns.db, ns.to)
    except (ValueError, FileExistsError, sqlite3.Error) as e:
        print(f"backup_db: error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"VALID backup: {rep['backup']} ({rep['bytes']} bytes, "
          f"sha256 {rep['sha256'][:16]}..., "
          f"tables {rep['tables']}, integrity ok, restore test ok)")
    return rep


if __name__ == "__main__":
    main()
