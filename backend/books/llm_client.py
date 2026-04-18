"""Shared LLM client supporting LM Studio (local) and Grok (hosted)."""
from __future__ import annotations

import os
from typing import Any

from requests import Session
from requests.exceptions import RequestException


class LLMServiceError(Exception):
    """Raised when a non-retryable LLM service error occurs."""


class LLMServiceTransientError(LLMServiceError):
    """Raised when an LLM service error may succeed on retry."""


def _provider() -> str:
    """Return active LLM provider key."""
    return os.getenv("LLM_PROVIDER", "lmstudio").strip().lower()


def _provider_config() -> dict[str, str]:
    """Resolve provider endpoint, model, and API key configuration."""
    provider = _provider()
    if provider == "grok":
        return {
            "base_url": os.getenv("GROK_BASE_URL", "https://api.x.ai/v1"),
            "model": os.getenv("GROK_MODEL", "grok-3-mini"),
            "api_key": os.getenv("GROK_API_KEY", ""),
            "provider": provider,
        }

    return {
        "base_url": os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
        "model": os.getenv("LM_STUDIO_MODEL", "llama-3.1-8b-instruct"),
        "api_key": os.getenv("LM_STUDIO_API_KEY", "lm-studio"),
        "provider": "lmstudio",
    }


def chat_completion(
    *,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> str:
    """Execute an OpenAI-compatible chat completion call and return text content."""
    cfg = _provider_config()
    endpoint = f"{cfg['base_url'].rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }
    payload: dict[str, Any] = {
        "model": cfg["model"],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    if cfg["provider"] == "grok" and not cfg["api_key"]:
        raise LLMServiceError("GROK_API_KEY is required when LLM_PROVIDER=grok.")

    with Session() as session:
        try:
            response = session.post(endpoint, headers=headers, json=payload, timeout=timeout_seconds)
        except RequestException as exc:
            raise LLMServiceTransientError(f"LLM request failed: {exc}") from exc

    if response.status_code in {429, 500, 502, 503, 504}:
        raise LLMServiceTransientError(f"LLM transient status {response.status_code}: {response.text[:300]}")

    if response.status_code >= 400:
        raise LLMServiceError(f"LLM returned {response.status_code}: {response.text[:500]}")

    try:
        body = response.json()
        return str(body["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMServiceError("Unexpected LLM response format.") from exc

