"""Reinicio seguro de la demo: solo toca demo_data/. Regenera DB + fixtures."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.make_fixtures as gen
from ia_debitos.contracts import Caso, Renglon
from ia_debitos.money import parse_importe
from ia_debitos.synthetic import SyntheticStore


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    demo = root / "demo_data"
    assert demo.resolve().is_relative_to(root.resolve()), "ruta insegura"
    db = demo / "demo.db"
    if db.exists():
        db.unlink()
    gen.main()
    store = SyntheticStore(str(db))
    for caso in gen.CASOS:
        rengs = tuple(
            Renglon(r["nro"], r["practica"], r["motivo"],
                    parse_importe(r["fact"]), parse_importe(r["liq"]))
            for r in caso["renglones"]
        )
        store.seed_caso(Caso(caso["id"], caso["financiador"], caso["factura"],
                             rengs, parse_importe(caso["total"])))
    print(f"demo.db regenerada ({len(gen.CASOS)} casos)")


if __name__ == "__main__":
    main()
