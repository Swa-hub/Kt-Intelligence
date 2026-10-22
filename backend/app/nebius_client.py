"""Centralised LLM client (OpenAI-compatible endpoint).

Every model call in the application goes through this module so the model,
endpoint, and auth can be changed in one place. Calls are made from the
backend only; the API key is never sent to the browser.

The default profile is Groq. Any OpenAI-compatible endpoint works by
changing LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in `.env`.
"""
from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI, APIError, APITimeoutError, AuthenticationError

from .config import settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Surfaced to the API layer so the frontend can show a clear message."""


class LLMNotConfigured(LLMError):
    """Raised when LLM_API_KEY is missing — we never silently stub a response."""


# Keep the old names as aliases so existing callers keep working.
NebiusError = LLMError
NebiusNotConfigured = LLMNotConfigured


def _client() -> OpenAI:
    if not settings.llm_api_key:
        raise LLMNotConfigured(
            "LLM_API_KEY is not set. Add it to backend/.env and restart the server."
        )
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def _embed_client() -> OpenAI:
    """Separate client for embeddings — lets you point embeddings at a
    different OpenAI-compatible provider (e.g. Nebius) while chat runs on
    another (e.g. Groq, which has no embeddings endpoint)."""
    key = settings.embeddings_api_key or settings.llm_api_key
    url = settings.embeddings_base_url or settings.llm_base_url
    if not key:
        raise LLMNotConfigured("EMBEDDINGS_API_KEY and LLM_API_KEY are both empty.")
    return OpenAI(api_key=key, base_url=url)


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    response_format: dict | None = None,
) -> str:
    try:
        client = _client()
        kwargs: dict[str, Any] = dict(
            model=model or settings.llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response_format is not None:
            kwargs["response_format"] = response_format
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
    except AuthenticationError as e:
        raise LLMError(f"LLM authentication failed: {e}") from e
    except APITimeoutError as e:
        raise LLMError("LLM request timed out.") from e
    except APIError as e:
        raise LLMError(f"LLM API error: {e}") from e


def embed(texts: list[str], *, model: str | None = None) -> list[list[float]] | None:
    """Return embeddings; None if embeddings are disabled."""
    model = model or settings.llm_embed_model
    if not model:
        return None
    try:
        client = _embed_client()
        resp = client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in resp.data]
    except LLMNotConfigured:
        raise
    except Exception as e:
        log.warning("Embedding failed, falling back to keyword retrieval: %s", e)
        return None


def is_configured() -> bool:
    return bool(settings.llm_api_key)


def demo_mode() -> bool:
    """True when no API key is configured. The app then returns clearly
    labelled sample data instead of erroring — useful for the walk-through
    on a machine that doesn't yet have credentials.
    Live-model claims never originate here.
    """
    return not is_configured()
