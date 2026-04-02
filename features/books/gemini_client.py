"""HTTP client for Google Gemini generateContent (REST)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx


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


def gemini_generate_content_json(
    *,
    api_key: str,
    model: str,
    base_url: str,
    system_instruction: str,
    user_text: str,
    temperature: float = 0.0,
    timeout_seconds: float = 180.0,
) -> dict[str, Any]:
    """
    POST to Gemini generateContent and parse the model text as JSON.

    ``base_url`` is the API root, e.g. ``https://generativelanguage.googleapis.com/v1beta``.
    ``model`` is the id only, e.g. ``gemini-2.0-flash`` (no ``models/`` prefix).

    Raises httpx.HTTPError on transport errors; ValueError on bad JSON.
    """
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
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, params=params, json=body)
        response.raise_for_status()
        data = response.json()

    text = _response_text(data)
    return _extract_json_object(text)
