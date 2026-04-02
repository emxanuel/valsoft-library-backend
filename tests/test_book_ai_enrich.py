"""Tests for POST /library/books/ai/enrich (Gemini mocked)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.config import get_settings
from features.books import ai_services
from features.books.isbn_lookup import IsbnLookupResult


def _fake_gemini(**_kwargs: object) -> dict:
    return {
        "suggestions": {
            "description": "A concise catalog description.",
            "genre": "Science Fiction",
            "published_year": 1999,
        }
    }


def _fake_gemini_genre_only(**_kwargs: object) -> dict:
    return {"suggestions": {"genre": "Essays"}}


@pytest.fixture(autouse=True)
def mock_open_library_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_services,
        "fetch_open_library_by_isbn",
        lambda _isbn: None,
    )


@pytest.fixture
def gemini_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_ai_enrich_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/library/books/ai/enrich",
        json={"title": "T", "author": "A"},
    )
    assert r.status_code == 401


def test_ai_enrich_returns_suggestions_and_duplicates_on_isbn_match(
    authenticated_client: TestClient,
    gemini_configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_services, "gemini_generate_content_json", _fake_gemini)

    c = authenticated_client
    isbn = "978-1234567890"
    created = c.post(
        "/library/books",
        json={
            "title": "Existing Title",
            "author": "Existing Author",
            "isbn": isbn,
        },
    )
    assert created.status_code == 201
    book_id = created.json()["id"]

    r = c.post(
        "/library/books/ai/enrich",
        json={
            "title": "Different Title",
            "author": "Different Author",
            "isbn": isbn,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["requires_confirmation"] is True
    assert len(data["duplicate_candidates"]) >= 1
    dup = next(d for d in data["duplicate_candidates"] if d["book_id"] == book_id)
    assert dup["title"] == "Existing Title"
    assert "ISBN" in dup["reason"]
    assert data["suggestions"]["genre"] == "Science Fiction"
    assert data["suggestions"]["description"]


def test_ai_enrich_exclude_book_id_omits_self(
    authenticated_client: TestClient,
    gemini_configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_services, "gemini_generate_content_json", _fake_gemini)

    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Solo", "author": "Writer", "isbn": "978-0000000002"},
    ).json()["id"]

    r = c.post(
        "/library/books/ai/enrich",
        json={
            "title": "Solo",
            "author": "Writer",
            "isbn": "978-0000000002",
            "exclude_book_id": book_id,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["requires_confirmation"] is False
    assert data["duplicate_candidates"] == []


def test_ai_enrich_isbn_only_returns_suggestions(
    authenticated_client: TestClient,
    gemini_configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_services, "gemini_generate_content_json", _fake_gemini)

    r = authenticated_client.post(
        "/library/books/ai/enrich",
        json={
            "title": "",
            "author": "",
            "isbn": "978-1111111111",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["requires_confirmation"] is False
    assert data["duplicate_candidates"] == []
    assert data["suggestions"]["genre"] == "Science Fiction"


def test_ai_enrich_isbn_only_duplicate_when_isbn_exists(
    authenticated_client: TestClient,
    gemini_configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_services, "gemini_generate_content_json", _fake_gemini)

    c = authenticated_client
    isbn = "978-2222222222"
    created = c.post(
        "/library/books",
        json={
            "title": "On Shelf",
            "author": "Author Name",
            "isbn": isbn,
        },
    )
    assert created.status_code == 201
    book_id = created.json()["id"]

    r = c.post(
        "/library/books/ai/enrich",
        json={
            "title": "",
            "author": "",
            "isbn": isbn,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["requires_confirmation"] is True
    dup = next(d for d in data["duplicate_candidates"] if d["book_id"] == book_id)
    assert dup["title"] == "On Shelf"
    assert "ISBN" in dup["reason"]


def test_ai_enrich_isbn_lookup_fills_title_author_when_gemini_omits(
    authenticated_client: TestClient,
    gemini_configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_services, "gemini_generate_content_json", _fake_gemini_genre_only)
    monkeypatch.setattr(
        ai_services,
        "fetch_open_library_by_isbn",
        lambda _isbn: IsbnLookupResult(
            title="Catalog Title",
            author="Catalog Author",
            published_year=2010,
            cover_url="https://covers.openlibrary.org/b/id/1-M.jpg",
        ),
    )

    r = authenticated_client.post(
        "/library/books/ai/enrich",
        json={
            "title": "",
            "author": "",
            "isbn": "978-0000000003",
        },
    )
    assert r.status_code == 200, r.text
    s = r.json()["suggestions"]
    assert s["title"] == "Catalog Title"
    assert s["author"] == "Catalog Author"
    assert s["published_year"] == 2010
    assert s["genre"] == "Essays"
    assert s["image_url"] == "https://covers.openlibrary.org/b/id/1-M.jpg"
    assert s["isbn"] == "978-0000000003"


def test_ai_enrich_422_when_title_author_isbn_all_empty(
    authenticated_client: TestClient,
    gemini_configured: None,
) -> None:
    r = authenticated_client.post(
        "/library/books/ai/enrich",
        json={
            "title": "",
            "author": "",
            "isbn": "",
        },
    )
    assert r.status_code == 422


def test_ai_enrich_503_when_gemini_not_configured(
    authenticated_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GEMINI_MODEL", "")
    get_settings.cache_clear()
    try:
        r = authenticated_client.post(
            "/library/books/ai/enrich",
            json={"title": "T", "author": "A"},
        )
        assert r.status_code == 503
        body = r.json()
        detail = body.get("detail") or body.get("message", "")
        assert "not configured" in str(detail).lower()
    finally:
        get_settings.cache_clear()
