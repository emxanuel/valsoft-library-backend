"""HTTP client for Google Gemini generateContent (REST)."""

from __future__ import annotations

import json
import logging
import random
import re
import threading
import time
from typing import Any, Callable

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)

_gemini_serialize_lock = threading.Lock()


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse JSON from model output; strip optional markdown fences."""
    raw = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*)\n?```\s*$", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = "Gemini returned invalid JSON"
        raise ValueError(msg) from exc
    if not isinstance(parsed, dict):
        msg = "Gemini JSON must be an object"
        raise ValueError(msg)
    return parsed


def _response_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates")
    if not candidates or not isinstance(candidates, list):
        msg = "Gemini response missing candidates"
        raise ValueError(msg)
    first = candidates[0]
    if not isinstance(first, dict):
        msg = "Gemini response invalid candidate shape"
        raise ValueError(msg)
    content = first.get("content")
    if not isinstance(content, dict):
        msg = "Gemini response missing content"
        raise ValueError(msg)
    parts = content.get("parts")
    if not parts or not isinstance(parts, list):
        msg = "Gemini response missing parts"
        raise ValueError(msg)
    texts: list[str] = []
    for p in parts:
        if isinstance(p, dict) and isinstance(p.get("text"), str):
            texts.append(p["text"])
    out = "".join(texts).strip()
    if not out:
        msg = "Gemini response empty text"
        raise ValueError(msg)
    return out


def _retry_delay_seconds(
    response: httpx.Response | None,
    *,
    attempt_index: int,
    backoff_base: float,
    backoff_max: float,
) -> float:
    if response is not None:
        ra = response.headers.get("Retry-After")
        if ra is not None:
            try:
                return min(backoff_max, float(ra.strip()))
            except ValueError:
                pass
    exp = min(backoff_max, backoff_base * (2**attempt_index))
    jitter = random.uniform(0.0, min(1.0, backoff_base * 0.5))
    return min(backoff_max, exp + jitter)


def _http_status_retryable(status_code: int) -> bool:
    if status_code == 429:
        return True
    return status_code in (500, 502, 503, 504)


def gemini_generate_content_json(
    *,
    api_key: str,
    model: str,
    base_url: str,
    system_instruction: str,
    user_text: str,
    temperature: float = 0.0,
    timeout_seconds: float = 180.0,
    on_retry: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """
    POST to Gemini generateContent and parse the model text as JSON.

    ``base_url`` is the API root, e.g. ``https://generativelanguage.googleapis.com/v1beta``.
    ``model`` is the id only, e.g. ``gemini-2.0-flash`` (no ``models/`` prefix).

    Retries transient HTTP statuses (429, 5xx) with backoff. Optional ``on_retry`` runs
    before each wait when a retry will occur.

    Raises httpx.HTTPError on non-retryable HTTP errors; ValueError on bad JSON.
    """
    settings = get_settings()
    max_retries = settings.GEMINI_MAX_RETRIES
    backoff_base = settings.GEMINI_RETRY_BACKOFF_BASE_SECONDS
    backoff_max = settings.GEMINI_RETRY_BACKOFF_MAX_SECONDS
    serialize = settings.GEMINI_SERIALIZE_REQUESTS

    base = base_url.rstrip("/")
    url = f"{base}/models/{model}:generateContent"
    params = {"key": api_key}
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_text}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
        },
    }
    connect = min(30.0, max(5.0, timeout_seconds / 6))
    timeout = httpx.Timeout(timeout_seconds, connect=connect)

    for attempt in range(max_retries + 1):
        try:
            def do_post() -> httpx.Response:
                with httpx.Client(timeout=timeout) as client:
                    return client.post(url, params=params, json=body)

            if serialize:
                with _gemini_serialize_lock:
                    response = do_post()
            else:
                response = do_post()

            response.raise_for_status()
            data = response.json()
            text = _response_text(data)
            return _extract_json_object(text)

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if attempt < max_retries and _http_status_retryable(status):
                delay = _retry_delay_seconds(
                    exc.response,
                    attempt_index=attempt,
                    backoff_base=backoff_base,
                    backoff_max=backoff_max,
                )
                logger.warning(
                    "gemini_http_retryable status=%s attempt=%s/%s sleep=%.2fs",
                    status,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                if on_retry:
                    on_retry()
                time.sleep(delay)
                continue
            raise
