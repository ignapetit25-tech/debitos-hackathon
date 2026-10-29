"""Minimal authenticated check against Meta Muse Spark (fictitious data).

Usage:  MODEL_API_KEY=... .venv/bin/python -B tools/check_meta.py
        (or with MODEL_API_KEY in .env, git-ignored)

Prints ONLY metadata: provider, model, protocol, latency and
schema result. Never prints the key or error bodies.
Fails explicitly if the key is missing or Meta answers badly: no
simulator fallback in this script (IA_PROVIDER is forced to meta).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from debit_ai.agent import EXPLANATION_SCHEMA
from debit_ai.provider import ProviderError, build_provider


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_repo_env() -> str:
    """Read REPO/.env EXPLICITLY (if present). Return readable status."""
    env = REPO_ROOT / ".env"
    if not env.exists():
        return f"{env} (missing)"
    n = 0
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))
            n += 1
    return f"{env} (loaded, {n} vars, values never printed)"


def main() -> int:
    env_info = load_repo_env()
    os.environ["IA_PROVIDER"] = "meta"  # forced: simulating forbidden here
    try:
        prov = build_provider()
    except ProviderError as exc:
        print(f"Explicit FAIL (no key or no SDK): {exc}")
        return 1
    assert prov.name == "meta", f"unexpected provider: {prov.name}"
    prompt = (
        "FICTITIOUS test datum. Return a one-line explanation "
        "for: BASE: Routing to Agreements per rules (10 pts: agreement). "
        "CASE: Demo Fictitious Payer F-0001, 1 line."
    )
    t0 = time.monotonic()
    try:
        out = prov.complete_structured(prompt, EXPLANATION_SCHEMA, "explanation")
    except ProviderError as exc:
        print(f"Explicit Meta FAIL (short message, no bodies): {exc}")
        return 1
    ms = int((time.monotonic() - t0) * 1000)
    txt = out.get("explanation", "")
    if "SIMULATED" in txt:
        print("FAIL: response carries simulator tag, not real Meta")
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
