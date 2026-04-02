"""Health, metrics, and request correlation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.config import get_settings
from core.create_app import create_app
from database.session import get_session


@pytest.fixture
def metrics_client(db_session, monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "true")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_health_live(client: TestClient):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ready(client: TestClient):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_exposes_prometheus(metrics_client: TestClient):
    r = metrics_client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "http_requests" in body or "http_request" in body
    assert "db_pool_connections_in_use" in body


def test_request_id_header_generated(client: TestClient):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert "x-request-id" in {k.lower(): v for k, v in r.headers.items()}
    rid = r.headers.get("X-Request-ID") or r.headers.get("x-request-id")
    assert rid and len(rid) > 0


def test_request_id_header_echo(client: TestClient):
    r = client.get("/health/live", headers={"X-Request-ID": "custom-req-id"})
    assert r.headers.get("X-Request-ID") == "custom-req-id"
