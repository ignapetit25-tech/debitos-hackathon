"""Reproducible evaluation over synthetic fixtures. Measured numbers only.

Metrics: extraction (exact lines+total), routing (team vs
expected.json) and abstention: the system must route to a human on
clinical cases (expected_abstention=true) and produce an admin
proposal on the rest (false). An N/N abstention score is right in
BOTH directions on these cases; it proves no general accuracy or
clinical coverage.

Requires TESSDATA_PREFIX with spa for OCR.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from debit_ai import rules
from debit_ai.extract import extract
from debit_ai.money import parse_amount


def main() -> int:
    print("SCOPE=deterministic (extraction+rules; the model does NOT run)")
    print(f"IA_PROVIDER configured={os.environ.get('IA_PROVIDER', 'meta')}")
    print("These figures are NOT Meta or simulator metrics.")
    print()
    base = Path(__file__).resolve().parent.parent / "demo_data" / "generated"
    expected = json.loads((base / "expected.json").read_text(encoding="utf-8"))
    ext_ok = ext_n = der_ok = der_n = abs_ok = abs_n = 0
    for case in expected:
        ext = extract(str(base / case["pdf"]))
        ok_fields = (
            len(ext.lines) == len(case["lines"])
            and all(e["num"] == r["line_no"] and e["procedure"] == r["procedure"]
                    and e["reason"] == r["reason"]
                    and e["billed_cents"] == parse_amount(r["billed"])
                    and e["settled_cents"] == parse_amount(r["settled"])
                    for e, r in zip(ext.lines, case["lines"]))
            and ext.total_raw.replace(" ", "") == case["total"].replace("$", "").replace(" ", "")
            and not ext.flags
        )
        ext_n += 1
        ext_ok += ok_fields
        reasons = " | ".join(r["reason"] for r in case["lines"])
        ref = rules.evaluate(reasons)
        clin = rules.is_clinical(reasons)
        der_n += 1
        der_ok += ref.team == case["expected_team"]
        abs_n += 1
        abs_ok += (clin or ref.team == rules.PENDING) == case["expected_abstention"]
        print(f"{case['id']}: extraction={'OK' if ok_fields else 'FAIL'} "
              f"routing={ref.team} (exp {case['expected_team']}) "
              f"abstention={clin or ref.team == rules.PENDING}")
    print(f"\nEXTRACTION {ext_ok}/{ext_n}  ROUTING {der_ok}/{der_n}  ABSTENTION {abs_ok}/{abs_n}")
    print(f"({ext_n} controlled synthetic cases; abstention OK = routes to human "
          f"on clinical ones and proposes on admin ones. Proves no general accuracy.)")
    return 0 if (ext_ok, der_ok, abs_ok) == (ext_n, der_n, abs_n) else 1


if __name__ == "__main__":
    raise SystemExit(main())
