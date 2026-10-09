"""app/rms/llm.py — infra común LLM (Fase 3, 2026-10-07).

Cliente mínimo para GLM (Z.ai) con httpx. Key SOLO por env
(ZAI_API_KEY / ZAI_BASE_URL) — nunca hardcoded. Sin key configurada
`available()` devuelve False y los llamadores degradan con gracia
(OCR → error controlado, copiloto → mensaje "no configurado").

Uso:
    from app.rms.llm import chat_json, available
    if available():
        data = chat_json(messages=[...], max_tokens=2000)
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from loguru import logger

DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"
DEFAULT_MODEL = "glm-4.5-air"
TIMEOUT_S = 60.0
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # guardarraíl OCR: 8MB


class LLMError(RuntimeError):
    """LLM call failed (network, HTTP error, bad JSON)."""


def api_key() -> str | None:
    return os.getenv("ZAI_API_KEY") or None


def base_url() -> str:
    return os.getenv("ZAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def model() -> str:
    return os.getenv("ZAI_MODEL", DEFAULT_MODEL)


def available() -> bool:
    """True si hay key configurada. Los routers consultan esto antes."""
    return bool(api_key())


def chat(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
) -> str:
    """Chat completion → texto. Raises LLMError en cualquier fallo."""
    key = api_key()
    if not key:
        raise LLMError("ZAI_API_KEY no configurada")
    payload = {
        "model": model(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    try:
        r = httpx.post(
            f"{base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=TIMEOUT_S,
        )
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage") or {}
        logger.info(
            "llm usage: model={} prompt_tokens={} completion_tokens={} total_tokens={}",
            data.get("model", model()),
            usage.get("prompt_tokens", "?"),
            usage.get("completion_tokens", "?"),
            usage.get("total_tokens", "?"),
        )
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.warning("llm chat HTTP {}: {}", e.response.status_code, e.response.text[:200])
        raise LLMError(f"LLM HTTP {e.response.status_code}") from None
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as e:
        logger.warning("llm chat failed: {}", e)
        raise LLMError("LLM no respondió") from None


def chat_json(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = 2000,
    temperature: float = 0.1,
) -> Any:
    """Chat completion → JSON parseado (soporta ```json fences)."""
    text = chat(messages, max_tokens=max_tokens, temperature=temperature)
    return _extract_json(text)


def _extract_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating ``` fences and prose."""
    s = text.strip()
    if s.startswith("```"):
        # strip fence line(s)
        lines = s.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        s = "\n".join(lines).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # last resort: first { ... last }
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            return json.loads(s[i : j + 1])
        raise LLMError("LLM no devolvió JSON válido") from None
