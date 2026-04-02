"""Tests for Gemini HTTP client retries and serialization."""

from __future__ import annotations

import httpx
import pytest

from core.config import get_settings
from features.books import gemini_client


def _success_payload() -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": '{"suggestions": {}}'}],
                },
            },
        ],
    }


@pytest.fixture
def clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "m")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_gemini_retries_429_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    clear_settings_cache: None,
) -> None:
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "3")
    monkeypatch.setenv("GEMINI_SERIALIZE_REQUESTS", "false")
    get_settings.cache_clear()

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, request=request, headers={"Retry-After": "0"})
        return httpx.Response(200, json=_success_payload(), request=request)

    transport = httpx.MockTransport(handler)
    real_Client = httpx.Client

    def client_with_transport(*args: object, **kwargs: object) -> httpx.Client:
        kwargs = dict(kwargs)
        kwargs["transport"] = transport
        return real_Client(*args, **kwargs)

    monkeypatch.setattr(gemini_client.httpx, "Client", client_with_transport)
    sleeps: list[float] = []
    monkeypatch.setattr(gemini_client.time, "sleep", lambda s: sleeps.append(s))

    out = gemini_client.gemini_generate_content_json(
        api_key="key",
        model="gemini-test",
        base_url="https://example.com/v1beta",
        system_instruction="sys",
        user_text="{}",
    )
    assert out == {"suggestions": {}}
    assert calls["n"] == 2
    assert len(sleeps) == 1


def test_gemini_no_retry_on_400(
    monkeypatch: pytest.MonkeyPatch,
    clear_settings_cache: None,
) -> None:
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "5")
    monkeypatch.setenv("GEMINI_SERIALIZE_REQUESTS", "false")
    get_settings.cache_clear()

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": "bad"}, request=request)

    transport = httpx.MockTransport(handler)
    real_Client = httpx.Client

    def client_with_transport(*args: object, **kwargs: object) -> httpx.Client:
        kwargs = dict(kwargs)
        kwargs["transport"] = transport
        return real_Client(*args, **kwargs)

    monkeypatch.setattr(gemini_client.httpx, "Client", client_with_transport)
    monkeypatch.setattr(gemini_client.time, "sleep", lambda s: pytest.fail("should not sleep"))

    with pytest.raises(httpx.HTTPStatusError):
        gemini_client.gemini_generate_content_json(
            api_key="key",
            model="gemini-test",
            base_url="https://example.com/v1beta",
            system_instruction="sys",
            user_text="{}",
        )
    assert calls["n"] == 1


def test_gemini_on_retry_callback(
    monkeypatch: pytest.MonkeyPatch,
    clear_settings_cache: None,
) -> None:
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "2")
    monkeypatch.setenv("GEMINI_SERIALIZE_REQUESTS", "false")
    get_settings.cache_clear()

    n = {"v": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["v"] += 1
        if n["v"] == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json=_success_payload(), request=request)

    transport = httpx.MockTransport(handler)
    real_Client = httpx.Client

    def client_with_transport(*args: object, **kwargs: object) -> httpx.Client:
        kwargs = dict(kwargs)
        kwargs["transport"] = transport
        return real_Client(*args, **kwargs)

    monkeypatch.setattr(gemini_client.httpx, "Client", client_with_transport)
    monkeypatch.setattr(gemini_client.time, "sleep", lambda _s: None)

    retries: list[int] = []

    def on_retry() -> None:
        retries.append(1)

    gemini_client.gemini_generate_content_json(
        api_key="key",
        model="gemini-test",
        base_url="https://example.com/v1beta",
        system_instruction="sys",
        user_text="{}",
        on_retry=on_retry,
    )
    assert retries == [1]
