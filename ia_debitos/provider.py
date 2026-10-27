"""Interfaz de proveedor + Meta Muse Spark (real) + simulado (explícito).

Meta: paquete `openai` apuntando a api.meta.ai (llama a Meta, no a
OpenAI). Docs: https://dev.meta.ai/docs/quickstart
- base: META_BASE_URL (default https://api.meta.ai/v1)
- modelo: META_MODEL (default muse-spark-1.3)
- clave: MODEL_API_KEY (obligatoria, explícita; jamás se registra)
- protocolo: responses (recomendado, text.format) | chat (response_format)

Sin clave o ante error: se informa claro. NUNCA fallback silencioso.
"""
from __future__ import annotations

import abc
import json
import os
import time


class ProviderError(Exception):
    pass


class Provider(abc.ABC):
    name: str = "base"
    last_call: dict  # metadatos última llamada (sin credenciales/documentos)

    @abc.abstractmethod
    def complete_structured(
        self, prompt: str, schema: dict, schema_name: str = "respuesta",
        protocol: str | None = None,
    ) -> dict:
        """Devuelve JSON parseado que cumple `schema` (validación mínima)."""


def _check_json_schema(data: object, schema: dict) -> dict:
    if not isinstance(data, dict):
        raise ProviderError("salida no es objeto JSON")
    for req in schema.get("required", []):
        if req not in data:
            raise ProviderError(f"falta campo requerido: {req}")
    props = schema.get("properties", {})
    for key, val in data.items():
        esperado = props.get(key, {}).get("type")
        if esperado == "string" and not isinstance(val, str):
            raise ProviderError(f"campo {key} debe ser string")
        if esperado == "number" and not isinstance(val, (int, float)):
            raise ProviderError(f"campo {key} debe ser number")
        if esperado == "boolean" and not isinstance(val, bool):
            raise ProviderError(f"campo {key} debe ser boolean")
        if esperado == "array" and not isinstance(val, list):
            raise ProviderError(f"campo {key} debe ser array")
    return data


class MetaProvider(Provider):
    """Proveedor real Meta Muse Spark. Requiere MODEL_API_KEY."""

    name = "meta"

    def __init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError("falta paquete openai (pip install -r requirements.txt)") from exc
        key = os.environ.get("MODEL_API_KEY", "")
        if not key:
            raise ProviderError("falta MODEL_API_KEY en entorno (.env)")
        self._client = OpenAI(
            base_url=os.environ.get("META_BASE_URL", "https://api.meta.ai/v1"),
            api_key=key,
        )
        self._model = os.environ.get("META_MODEL", "muse-spark-1.3")
        self._default_protocol = os.environ.get("META_PROTOCOL", "responses")
        self.last_call = {"proveedor": "meta", "estado": "sin-llamadas"}

    def complete_structured(self, prompt, schema, schema_name="respuesta", protocol=None):
        proto = protocol or self._default_protocol
        meta = {"proveedor": "meta", "modelo_pedido": self._model,
                "protocolo": proto}
        t0 = time.monotonic()
        try:
            if proto == "responses":
                resp = self._client.responses.create(
                    model=self._model,
                    input=prompt,
                    text={"format": {"type": "json_schema", "name": schema_name,
                                     "schema": schema, "strict": True}},
                )
                texto = self._responses_text(resp)
            elif proto == "chat":
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_schema",
                                     "json_schema": {"name": schema_name,
                                                     "schema": schema,
                                                     "strict": True}},
                )
                texto = resp.choices[0].message.content or ""
            else:
                raise ProviderError(f"protocolo desconocido: {proto}")
        except ProviderError:
            meta.update(estado="error", latencia_ms=self._ms(t0))
            self.last_call = meta
            raise
        except Exception as exc:  # mensaje corto, sin cuerpos ni claves
            meta.update(estado="error",
                        error=type(exc).__name__, latencia_ms=self._ms(t0))
            self.last_call = meta
            raise ProviderError(f"error Meta ({type(exc).__name__})") from None
        try:
            data = json.loads(texto)
        except (json.JSONDecodeError, TypeError):
            meta.update(estado="error", error="JSON inválido",
                        latencia_ms=self._ms(t0))
            self.last_call = meta
            raise ProviderError("Meta devolvió JSON inválido") from None
        try:
            data = _check_json_schema(data, schema)
        except ProviderError as exc:
            meta.update(estado="error", error=str(exc)[:80],
                        latencia_ms=self._ms(t0))
            self.last_call = meta
            raise
        meta.update(estado="ok", modelo_devuelto=getattr(resp, "model", ""),
                    respuesta_id=getattr(resp, "id", ""),
                    latencia_ms=self._ms(t0), uso=self._uso(resp))
        self.last_call = meta
        return data

    @staticmethod
    def _ms(t0: float) -> int:
        return int((time.monotonic() - t0) * 1000)

    @staticmethod
    def _uso(resp) -> dict:
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
        partes: list[str] = []
        for item in getattr(resp, "output", []) or []:
            for part in getattr(item, "content", []) or []:
                if getattr(part, "text", None):
                    partes.append(part.text)
        return "".join(partes)


class SimulatedProvider(Provider):
    """SIMULADO para pruebas sin credenciales. No demuestra nada sobre Meta."""

    name = "simulated"

    def __init__(self, respuestoid: str = "demo") -> None:
        self._id = respuestoid
        self.last_call = {"proveedor": "simulated", "estado": "sin-llamadas"}

    def complete_structured(self, prompt, schema, schema_name="respuesta", protocol=None):
        _ = (prompt, protocol)
        self.last_call = {"proveedor": "simulated", "estado": "ok-simulado",
                          "modelo_devuelto": "simulador-local",
                          "latencia_ms": 0, "uso": {}}
        if schema_name == "explicacion":
            return {"explicacion": f"[SIMULADO-{self._id}] Derivación según reglas.",
                    "dudoso": False}
        if schema_name == "borrador":
            return {"titulo": "[SIMULADO] Borrador de reclamo",
                    "cuerpo": "[SIMULADO] Texto de ejemplo para revisión humana."}
        if schema_name == "consulta":
            return {"respuesta": "[SIMULADO] Resumen de estados.", "casos": []}
        return {k: ("[SIMULADO]" if v.get("type") == "string" else None)
                for k, v in schema.get("properties", {}).items()}


def build_provider(nombre: str | None = None) -> Provider:
    """'meta' (default) o 'simulated' (explícito). Sin fallback silencioso."""
    elegido = (nombre or os.environ.get("IA_PROVIDER", "meta")).strip().lower()
    if elegido == "simulated":
        return SimulatedProvider()
    if elegido == "meta":
        return MetaProvider()
    raise ProviderError(f"proveedor desconocido: {elegido}")
