"""ISBN → bibliographic metadata via Open Library (no API key)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

# Open Library sometimes serves empty JSON to generic clients without a UA.
_HTTP_HEADERS = {
    "User-Agent": "ValsoftLibrary/1.0 (catalog enrichment; +https://openlibrary.org/dev/docs/api)",
    "Accept": "application/json",
}


@dataclass(frozen=True)
class IsbnLookupResult:
    title: str
    author: str
    published_year: Optional[int]
    cover_url: Optional[str]


def _normalize_isbn_core(isbn: str) -> Optional[str]:
    """Digits and trailing X only (ISBN-10 check digit)."""
    s = "".join(c for c in isbn.strip().upper() if c.isdigit() or c == "X")
    if not s:
        return None
    if len(s) not in (10, 13):
        return None
    return s


def isbn10_to_isbn13(isbn10: str) -> Optional[str]:
    """978-prefixed ISBN-13 for a valid ISBN-10 (including check X)."""
    s = isbn10.upper()
    if len(s) != 10 or s[-1] not in "0123456789X" or not s[:9].isdigit():
        return None
    body = "978" + s[:9]
    total = 0
    for i, ch in enumerate(body):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    check = (10 - (total % 10)) % 10
    return body + str(check)


def _bibkeys_for_books_api(core: str) -> str:
    """Comma-separated bibkeys; include ISBN-13 when staff entered ISBN-10."""
    keys: list[str] = [f"ISBN:{core}"]
    if len(core) == 10:
        isbn13 = isbn10_to_isbn13(core)
        if isbn13 and f"ISBN:{isbn13}" not in keys:
            keys.append(f"ISBN:{isbn13}")
    return ",".join(keys)


def _parse_publish_year(publish_date: object) -> Optional[int]:
    if publish_date is None:
        return None
    if isinstance(publish_date, int):
        return publish_date
    if not isinstance(publish_date, str):
        return None
    m = re.search(r"\b(19|20)\d{2}\b", publish_date)
    if m:
        return int(m.group())
    return None


def _authors_to_string(authors: object) -> str:
    if not isinstance(authors, list) or not authors:
        return ""
    names: list[str] = []
    for a in authors:
        if isinstance(a, dict) and isinstance(a.get("name"), str):
            n = a["name"].strip()
            if n:
                names.append(n)
    return ", ".join(names)


def _cover_url(book: dict[str, Any]) -> Optional[str]:
    cover = book.get("cover")
    if not isinstance(cover, dict):
        return None
    for key in ("medium", "large", "small"):
        u = cover.get(key)
        if isinstance(u, str) and u.startswith("https://"):
            return u
    return None


def _result_from_books_entry(book: dict[str, Any]) -> Optional[IsbnLookupResult]:
    title = book.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    author = _authors_to_string(book.get("authors"))
    pub_raw = book.get("publish_date")
    published_year = _parse_publish_year(pub_raw)
    cover = _cover_url(book)
    return IsbnLookupResult(
        title=title.strip(),
        author=author,
        published_year=published_year,
        cover_url=cover,
    )


def _first_nonempty_book_from_books_payload(data: dict[str, Any]) -> Optional[dict[str, Any]]:
    """``/api/books`` may return multiple keys; skip empty stubs."""
    for v in data.values():
        if isinstance(v, dict) and isinstance(v.get("title"), str) and v["title"].strip():
            return v
    return None


def _author_name_from_search(doc: dict[str, Any]) -> str:
    an = doc.get("author_name")
    if isinstance(an, list):
        return ", ".join(str(x).strip() for x in an if x)
    if isinstance(an, str):
        return an.strip()
    return ""


def _cover_from_search_doc(doc: dict[str, Any]) -> Optional[str]:
    ci = doc.get("cover_i")
    if isinstance(ci, int):
        return f"https://covers.openlibrary.org/b/id/{ci}-M.jpg"
    return None


def _result_from_search_doc(doc: dict[str, Any]) -> Optional[IsbnLookupResult]:
    title = doc.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    author = _author_name_from_search(doc)
    py = doc.get("first_publish_year")
    published_year: Optional[int] = None
    if isinstance(py, int):
        published_year = py
    elif isinstance(py, str) and py.isdigit():
        published_year = int(py)
    return IsbnLookupResult(
        title=title.strip(),
        author=author,
        published_year=published_year,
        cover_url=_cover_from_search_doc(doc),
    )


def _fetch_books_api(client: httpx.Client, base: str, bibkeys: str) -> Optional[dict[str, Any]]:
    url = f"{base}/api/books"
    r = client.get(
        url,
        params={"bibkeys": bibkeys, "format": "json", "jscmd": "data"},
        headers=_HTTP_HEADERS,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or not data:
        return None
    return _first_nonempty_book_from_books_payload(data)


def _fetch_search_api(client: httpx.Client, base: str, isbn_for_query: str) -> Optional[IsbnLookupResult]:
    """Work-level hit when ``/api/books`` has no edition for this ISBN."""
    url = f"{base}/search.json"
    r = client.get(
        url,
        params={"isbn": isbn_for_query, "limit": 1},
        headers=_HTTP_HEADERS,
    )
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, dict):
        return None
    docs = payload.get("docs")
    if not isinstance(docs, list) or not docs:
        return None
    first = docs[0]
    if not isinstance(first, dict):
        return None
    return _result_from_search_doc(first)


def fetch_open_library_by_isbn(
    isbn: str,
    *,
    timeout_seconds: Optional[float] = None,
) -> Optional[IsbnLookupResult]:
    """
    Resolve ISBN using Open Library ``/api/books``, then ``/search.json`` if needed.

    Returns ``None`` if not found or on transport/parse errors (logged at debug).
    """
    core = _normalize_isbn_core(isbn)
    if not core:
        return None

    t = timeout_seconds if timeout_seconds is not None else settings.ISBN_LOOKUP_TIMEOUT_SECONDS
    base = settings.OPEN_LIBRARY_BASE_URL.rstrip("/")
    bibkeys = _bibkeys_for_books_api(core)
    # Search prefers digits-only ISBN (no X issues in query)
    search_q = "".join(c for c in core if c.isdigit())
    if len(core) == 10 and core[-1] == "X":
        search_q = core  # e.g. 345678901X

    try:
        with httpx.Client(timeout=t, follow_redirects=True) as client:
            book = _fetch_books_api(client, base, bibkeys)
            if book:
                return _result_from_books_entry(book)
            # Many ISBNs only appear in work search, not in /api/books
            return _fetch_search_api(client, base, search_q)
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug("open_library_isbn_lookup_failed: %s", exc)
        return None
