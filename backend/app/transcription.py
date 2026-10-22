"""Audio/video transcription via the configured LLM provider's Whisper endpoint.

Groq exposes `whisper-large-v3-turbo` on the same OpenAI-compatible endpoint;
other providers that implement `/v1/audio/transcriptions` work too.
"""
from __future__ import annotations

from pathlib import Path

from openai import APIError, AuthenticationError, OpenAI

from .config import settings
from .nebius_client import LLMError, LLMNotConfigured


DEFAULT_WHISPER_MODEL = "whisper-large-v3-turbo"
AUDIO_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg", ".flac", ".mpeg", ".mpga"}


def is_audio(filename: str) -> bool:
    return Path(filename).suffix.lower() in AUDIO_EXTENSIONS


def transcribe(path: Path, *, model: str = DEFAULT_WHISPER_MODEL) -> str:
    if not settings.llm_api_key:
        raise LLMNotConfigured("LLM_API_KEY is not set — cannot transcribe audio.")
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    try:
        with path.open("rb") as f:
            resp = client.audio.transcriptions.create(model=model, file=f)
        return getattr(resp, "text", "") or ""
    except AuthenticationError as e:
        raise LLMError(f"Transcription auth failed: {e}") from e
    except APIError as e:
        raise LLMError(f"Transcription API error: {e}") from e
