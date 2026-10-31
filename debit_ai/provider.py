"""Provider interface + Meta Muse Spark (real) + simulated (explicit).

Meta: `openai` package pointed at api.meta.ai (calls Meta, not
OpenAI). Docs: https://dev.meta.ai/docs/quickstart
- base: META_BASE_URL (default https://api.meta.ai/v1)
- model: META_MODEL (default muse-spark-1.3)
- key: MODEL_API_KEY (required, explicit; never logged)
- protocol: responses (recommended, text.format) | chat (response_format)

No key or on error: reported clearly. NEVER silent fallback.
"""
from __future__ import annotations

import abc
import json
import os
import time


class ProviderError(Exception):
    pass


DEFAULT_MAX_INPUT_CHARS = 12000


def apply_input_budget(prompt: str, limit: int | None = None) -> tuple[str, dict]:
    """Preventive input cap: truncate BEFORE any provider call.

    Limit from `limit`, else IA_MAX_INPUT_CHARS (default 12000 chars).
    Returns (prompt_to_send, info) where info always carries
    input_chars/sent_chars/truncated for last_call records. A warning
    AFTER an overrun is not a limit: truncation happens here.
    """
    if limit is None:
        raw = os.environ.get("IA_MAX_INPUT_CHARS", "")
        if not raw.strip():
            limit = DEFAULT_MAX_INPUT_CHARS
        else:
            try:
                limit = int(raw)
            except ValueError:
                raise ProviderError(
                    "IA_MAX_INPUT_CHARS must be a number") from None
    if limit <= 0:
        raise ProviderError("IA_MAX_INPUT_CHARS must be > 0")
    info = {"input_chars": len(prompt), "sent_chars": min(len(prompt), limit),
            "truncated": len(prompt) > limit}
    if len(prompt) <= limit:
        return prompt, info
    cut = prompt[:limit]
    mark = f"\n[TRUNCATED by input budget: {len(prompt)}>{limit} chars]"
    return cut + mark, info


def _max_output_tokens(var: str, default: int) -> int:
    raw = os.environ.get(var, "")
    if not raw.strip():
        return default
    try:
        val = int(raw)
    except ValueError:
        raise ProviderError(f"{var} must be a number") from None
    if val <= 0:
        raise ProviderError(f"{var} must be > 0")
    return val


class Provider(abc.ABC):
    name: str = "base"
    last_call: dict  # last-call metadata (no credentials/documents)

    @abc.abstractmethod
    def complete_structured(
        self, prompt: str, schema: dict, schema_name: str = "response",
        protocol: str | None = None,
    ) -> dict:
        """Return parsed JSON honoring `schema` (minimal validation)."""


def _check_json_schema(data: object, schema: dict) -> dict:
    if not isinstance(data, dict):
        raise ProviderError("output is not a JSON object")
    for req in schema.get("required", []):
        if req not in data:
            raise ProviderError(f"missing required field: {req}")
    props = schema.get("properties", {})
    for key, val in data.items():
        expected = props.get(key, {}).get("type")
        if expected == "string" and not isinstance(val, str):
            raise ProviderError(f"field {key} must be a string")
        if expected == "number" and not isinstance(val, (int, float)):
            raise ProviderError(f"field {key} must be a number")
        if expected == "boolean" and not isinstance(val, bool):
            raise ProviderError(f"field {key} must be a boolean")
        if expected == "array" and not isinstance(val, list):
            raise ProviderError(f"field {key} must be an array")
    return data


class MetaProvider(Provider):
    """Real Meta Muse Spark provider. Requires MODEL_API_KEY."""

    name = "meta"

    def __init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError("missing openai package (pip install -r requirements.txt)") from exc
        key = os.environ.get("MODEL_API_KEY", "")
        if not key:
            raise ProviderError("missing MODEL_API_KEY in environment (.env)")
        self._client = OpenAI(
            base_url=os.environ.get("META_BASE_URL", "https://api.meta.ai/v1"),
            api_key=key,
        )
        self._model = os.environ.get("META_MODEL", "muse-spark-1.3")
        self._default_protocol = os.environ.get("META_PROTOCOL", "responses")
        self._max_out = _max_output_tokens("META_MAX_OUTPUT_TOKENS", 2000)
        self.last_call = {"provider": "meta", "status": "no-calls"}

    def complete_structured(self, prompt, schema, schema_name="response", protocol=None):
        proto = protocol or self._default_protocol
        meta = {"provider": "meta", "requested_model": self._model,
                "protocol": proto, "max_output_tokens": self._max_out,
                "input_chars": len(prompt)}
        t0 = time.monotonic()
        try:
            if proto == "responses":
                resp = self._client.responses.create(
                    model=self._model,
                    input=prompt,
                    max_output_tokens=self._max_out,
                    text={"format": {"type": "json_schema", "name": schema_name,
                                     "schema": schema, "strict": True}},
                )
                text = self._responses_text(resp)
            elif proto == "chat":
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self._max_out,
                    response_format={"type": "json_schema",
                                     "json_schema": {"name": schema_name,
                                                     "schema": schema,
                                                     "strict": True}},
                )
                text = resp.choices[0].message.content or ""
            else:
                raise ProviderError(f"unknown protocol: {proto}")
        except ProviderError:
            meta.update(status="error", latency_ms=self._ms(t0))
            self.last_call = meta
            raise
        except Exception as exc:  # short message, no bodies or keys
            meta.update(status="error",
                        error=type(exc).__name__, latency_ms=self._ms(t0))
            self.last_call = meta
            raise ProviderError(f"Meta error ({type(exc).__name__})") from None
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            meta.update(status="error", error="invalid JSON",
                        latency_ms=self._ms(t0))
            self.last_call = meta
            raise ProviderError("Meta returned invalid JSON") from None
        try:
            data = _check_json_schema(data, schema)
        except ProviderError as exc:
            meta.update(status="error", error=str(exc)[:80],
                        latency_ms=self._ms(t0))
            self.last_call = meta
            raise
        meta.update(status="ok", returned_model=getattr(resp, "model", ""),
                    response_id=getattr(resp, "id", ""),
                    latency_ms=self._ms(t0), usage=self._usage(resp))
        self.last_call = meta
        return data

    @staticmethod
    def _ms(t0: float) -> int:
        return int((time.monotonic() - t0) * 1000)

    @staticmethod
    def _usage(resp) -> dict:
        u = getattr(resp, "usage", None)
        if u is None:
            return {}
        out: dict = {}
        for k in ("input_tokens", "output_tokens", "prompt_tokens",
                  "completion_tokens", "total_tokens"):
            v = getattr(u, k, None)
            if v is not None:
                out[k] = v
        return out

    @staticmethod
    def _responses_text(resp) -> str:
        if getattr(resp, "output_text", None):
            return resp.output_text
        parts: list[str] = []
        for item in getattr(resp, "output", []) or []:
            for part in getattr(item, "content", []) or []:
                if getattr(part, "text", None):
                    parts.append(part.text)
        return "".join(parts)


class BasetenProvider(Provider):
    """Baseten Model API (OpenAI-compatible). Requires BASETEN_API_KEY.

    Base: BASETEN_BASE_URL (default https://inference.baseten.co/v1).
    Model: BASETEN_MODEL (default meta-models/muse-spark-open-1026).
    Chat protocol only (as documented by Baseten); explicit timeout and
    NO automatic retries. Docs: https://docs.baseten.co/quickstart
    """

    name = "baseten"

    def __init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError("missing openai package (pip install -r requirements.txt)") from exc
        key = os.environ.get("BASETEN_API_KEY", "")
        if not key:
            raise ProviderError("missing BASETEN_API_KEY in environment (.env)")
        try:
            timeout = float(os.environ.get("BASETEN_TIMEOUT", "60"))
        except ValueError:
            raise ProviderError("BASETEN_TIMEOUT must be a number") from None
        self._client = OpenAI(
            base_url=os.environ.get("BASETEN_BASE_URL", "https://inference.baseten.co/v1"),
            api_key=key,
            timeout=timeout,
            max_retries=0,
        )
        self._model = os.environ.get("BASETEN_MODEL", "meta-models/muse-spark-open-1026")
        self._max_out = _max_output_tokens("BASETEN_MAX_OUTPUT_TOKENS", 2000)
        self.last_call = {"provider": "baseten", "status": "no-calls"}

    def complete_structured(self, prompt, schema, schema_name="response", protocol=None):
        if protocol not in (None, "chat"):
            raise ProviderError(f"Baseten only supports chat, not: {protocol}")
        meta = {"provider": "baseten", "requested_model": self._model,
                "protocol": "chat", "max_output_tokens": self._max_out,
                "input_chars": len(prompt)}
        t0 = time.monotonic()
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self._max_out,
                response_format={"type": "json_schema",
                                 "json_schema": {"name": schema_name, "schema": schema,
                                                 "strict": True}},
            )
            text = resp.choices[0].message.content or ""
        except ProviderError:
            meta.update(status="error", latency_ms=self._ms(t0))
            self.last_call = meta
            raise
        except Exception as exc:  # short message, no bodies or keys
            meta.update(status="error", error=type(exc).__name__,
                        latency_ms=self._ms(t0))
            self.last_call = meta
            raise ProviderError(f"Baseten error ({type(exc).__name__})") from None
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            meta.update(status="error", error="invalid JSON", latency_ms=self._ms(t0))
            self.last_call = meta
            raise ProviderError("Baseten returned invalid JSON") from None
        try:
            data = _check_json_schema(data, schema)
        except ProviderError as exc:
            meta.update(status="error", error=str(exc)[:80], latency_ms=self._ms(t0))
            self.last_call = meta
            raise
        meta.update(status="ok", returned_model=getattr(resp, "model", ""),
                    response_id=getattr(resp, "id", ""),
                    latency_ms=self._ms(t0), usage=MetaProvider._usage(resp))
        self.last_call = meta
        return data

    @staticmethod
    def _ms(t0: float) -> int:
        return int((time.monotonic() - t0) * 1000)


class SimulatedProvider(Provider):
    """SIMULATED for tests without credentials. Proves nothing about Meta."""

    name = "simulated"

    def __init__(self, response_id: str = "demo") -> None:
        self._id = response_id
        self.last_call = {"provider": "simulated", "status": "no-calls"}

    def complete_structured(self, prompt, schema, schema_name="response", protocol=None):
        _ = (prompt, protocol)
        self.last_call = {"provider": "simulated", "status": "ok-simulated",
                          "returned_model": "local-simulator",
                          "latency_ms": 0, "usage": {}}
        if schema_name == "findings":
            return {"findings": [{
                "line_no": 0, "kind": "insufficient_evidence",
                "document": "invoice", "page": 1,
                "excerpt": "[SIMULATED] unlinked excerpt",
                "interpretation": "[SIMULATED] Review documents.",
                "limitations": "[SIMULATED] No real model."}]}
        if schema_name == "explanation":
            return {"explanation": f"[SIMULATED-{self._id}] Routing per rules.",
                    "uncertain": False}
        if schema_name == "draft":
            return {"title": "[SIMULATED] Draft",
                    "body": "[SIMULATED] Sample text for human review."}
        if schema_name == "query":
            return {"response": "[SIMULATED] Status summary.", "cases": []}
        return {k: ("[SIMULATED]" if v.get("type") == "string" else None)
                for k, v in schema.get("properties", {}).items()}


def build_provider(name: str | None = None) -> Provider:
    """'meta' (default), 'baseten' or 'simulated' (explicit). No silent fallback."""
    chosen = (name or os.environ.get("IA_PROVIDER", "meta")).strip().lower()
    if chosen == "simulated":
        return SimulatedProvider()
    if chosen == "meta":
        return MetaProvider()
    if chosen == "baseten":
        return BasetenProvider()
    raise ProviderError(f"unknown provider: {chosen}")
