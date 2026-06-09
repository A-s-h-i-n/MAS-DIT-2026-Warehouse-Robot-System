"""LM Studio client (OpenAI-compatible local LLM).

Thin async wrapper around the chat-completions endpoint exposed by LM Studio
(default http://localhost:1234/v1). Used by the Scheduler Agent for AI-based
task allocation. All calls are best-effort: any failure returns ``None`` so the
caller can fall back to the heuristic scheduler.
"""
from __future__ import annotations

import json
import logging
import re

import httpx

from backend.config import settings

logger = logging.getLogger("wms.llm")

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


async def is_available() -> bool:
    """Quick reachability check against the LM Studio /models endpoint."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.LMSTUDIO_URL}/models")
            return r.status_code == 200
    except Exception:
        return False


async def chat(messages: list[dict], *, temperature: float = 0.0,
               max_tokens: int = 512) -> str | None:
    """Call the chat-completions endpoint; return the message content or None."""
    payload = {
        "model": settings.LMSTUDIO_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.LMSTUDIO_TIMEOUT) as client:
            r = await client.post(
                f"{settings.LMSTUDIO_URL}/chat/completions", json=payload
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("LM Studio call failed: %s", exc)
        return None


def extract_json(content: str) -> dict | None:
    """Pull the first JSON object out of a model response (lenient parsing)."""
    if not content:
        return None
    # Try the whole string first, then the first {...} block.
    for candidate in (content, (_JSON_RE.search(content) or [None])[0]):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    return None
