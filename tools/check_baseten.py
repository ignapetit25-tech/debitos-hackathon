"""Minimal check against the Baseten Model API (fictitious data).

Usage (after entering the key in agent .env):
  .venv/bin/python -B tools/check_baseten.py

Prints ONLY bounded metadata: provider, requested/returned model,
response ID, status, latency, reported usage and up to 300
characters of the response. Never prints the key or error
bodies. Explicit timeout, no retries. Fails explicitly: never
fakes a successful integration.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from check_meta import load_repo_env  # noqa: E402

from debit_ai.agent import EXPLANATION_SCHEMA  # noqa: E402
from debit_ai.provider import ProviderError, build_provider  # noqa: E402


def main() -> int:
    env_info = load_repo_env()
    os.environ["IA_PROVIDER"] = "baseten"  # forced: simulating forbidden here
    try:
        prov = build_provider()
    except ProviderError as exc:
        print(f"env={env_info}")
        print(f"Explicit FAIL (no key or no SDK): {exc}")
        return 1
    assert prov.name == "baseten", f"unexpected provider: {prov.name}"
    prompt = (
        "FICTITIOUS test datum. Return a one-line explanation "
        "for: BASE: Routing to Agreements per rules (10 pts: agreement). "
        "CASE: Demo Fictitious Payer F-0001, 1 line."
    )
    t0 = time.monotonic()
    try:
        out = prov.complete_structured(prompt, EXPLANATION_SCHEMA, "explanation")
    except ProviderError as exc:
        print(f"Explicit Baseten FAIL (short message, no bodies): {exc}")
        return 1
    ms = int((time.monotonic() - t0) * 1000)
    txt = out.get("explanation", "")
    if "SIMULATED" in txt:
        print("FAIL: response carries simulator tag, not real Baseten")
        return 1
    m = dict(getattr(prov, "last_call", {}) or {})
    print(f"env={env_info}")
    print(f"provider={m.get('provider')} status={m.get('status')}")
    print(f"requested_model={m.get('requested_model')}")
    print(f"returned_model={m.get('returned_model')}")
    print(f"response_id={m.get('response_id')}")
    print(f"protocol={m.get('protocol')} latency_ms={ms} schema=OK")
    print(f"usage={m.get('usage')} uncertain={out.get('uncertain')}")
    print(f"explanation={txt[:300]}")
    print("key_in_use=YES (value never printed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
