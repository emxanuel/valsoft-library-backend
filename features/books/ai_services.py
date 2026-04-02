"""AI-assisted book metadata enrichment (suggestions only; grounded on DB duplicates)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, Optional

from sqlalchemy import and_, or_
from sqlmodel import Session, col, select

from core.config import get_settings
from database.models.books import Book
from features.books.gemini_client import gemini_generate_content_json
from features.books.isbn_lookup import IsbnLookupResult, fetch_open_library_by_isbn
from features.books.schemas import (
    BookAiEnrichRequest,
    BookAiEnrichResponse,
    BookAiEnrichSuggestions,
    DuplicateCandidate,
)

logger = logging.getLogger(__name__)

_MAX_CANDIDATES = 10


def normalize_isbn(s: str | None) -> str | None:
    if not s or not str(s).strip():
        return None
    return "".join(c for c in str(s).strip() if c.isdigit() or c.upper() == "X")


def find_duplicate_candidates(
    session: Session,
    req: BookAiEnrichRequest,
) -> list[DuplicateCandidate]:
    """Return likely duplicate active books (deterministic, DB-grounded)."""
    filters: list = [col(Book.deleted_at).is_(None)]
    if req.exclude_book_id is not None:
        filters.append(col(Book.id) != req.exclude_book_id)

    t = req.title.strip()
    a = req.author.strip()
    or_terms: list = []
    if t:
        or_terms.append(col(Book.title).ilike(f"%{t}%"))
    if a:
        or_terms.append(col(Book.author).ilike(f"%{a}%"))
    isbn_stripped = (req.isbn or "").strip()
    if isbn_stripped:
        or_terms.append(col(Book.isbn).ilike(f"%{isbn_stripped}%"))

    if not or_terms:
        return []

    stmt = select(Book).where(and_(*filters, or_(*or_terms))).limit(50)

    books = list(session.exec(stmt).all())
    out: list[DuplicateCandidate] = []
    seen: set[int] = set()

    n_req = normalize_isbn(req.isbn)
    t_req = t.lower()
    a_req = a.lower()

    for b in books:
        if b.id is None or b.id in seen:
            continue
        reason = _duplicate_reason(req, b, n_req=n_req, t_req=t_req, a_req=a_req)
        if reason:
            seen.add(b.id)
            out.append(
                DuplicateCandidate(
                    book_id=b.id,
                    title=b.title,
                    author=b.author,
                    isbn=b.isbn,
                    reason=reason,
                )
            )
        if len(out) >= _MAX_CANDIDATES:
            break

    return out


def _duplicate_reason(
    req: BookAiEnrichRequest,
    book: Book,
    *,
    n_req: str | None,
    t_req: str,
    a_req: str,
) -> str | None:
    n_b = normalize_isbn(book.isbn)
    if n_req and n_b and n_req == n_b:
        return "ISBN matches an existing catalog entry"
    bt = book.title.lower()
    ba = book.author.lower()
    if len(t_req) >= 3 and len(a_req) >= 2:
        title_overlap = t_req in bt or bt in t_req
        author_overlap = a_req in ba or ba in a_req
        if title_overlap and author_overlap:
            return "Similar title and author to an existing catalog entry"
    return None


def _merge_req_with_lookup(
    req: BookAiEnrichRequest,
    lookup: Optional[IsbnLookupResult],
) -> BookAiEnrichRequest:
    if not lookup:
        return req
    title = (req.title or "").strip() or lookup.title
    author = (req.author or "").strip() or lookup.author
    py = req.published_year if req.published_year is not None else lookup.published_year
    return req.model_copy(
        update={
            "title": title,
            "author": author,
            "published_year": py,
        },
    )


def _merge_lookup_into_suggestions(
    suggestions: BookAiEnrichSuggestions,
    req: BookAiEnrichRequest,
    lookup: Optional[IsbnLookupResult],
) -> BookAiEnrichSuggestions:
    if not lookup:
        return suggestions
    d = suggestions.model_dump()
    if not (d.get("title") or "").strip():
        d["title"] = lookup.title
    if not (d.get("author") or "").strip():
        d["author"] = lookup.author or None
    if d.get("published_year") is None and lookup.published_year is not None:
        d["published_year"] = lookup.published_year
    if not (d.get("image_url") or "").strip() and lookup.cover_url:
        d["image_url"] = lookup.cover_url
    isbn_staff = (req.isbn or "").strip()
    if not (d.get("isbn") or "").strip() and isbn_staff:
        d["isbn"] = isbn_staff
    return BookAiEnrichSuggestions.model_validate(d)


def _parse_suggestions(raw: dict) -> BookAiEnrichSuggestions:
    sug = raw.get("suggestions")
    if sug is None or not isinstance(sug, dict):
        return BookAiEnrichSuggestions()
    def _str_or_none(v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v).strip() or None

    def _int_or_none(v: object) -> int | None:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
        return None

    return BookAiEnrichSuggestions(
        title=_str_or_none(sug.get("title")),
        author=_str_or_none(sug.get("author")),
        isbn=_str_or_none(sug.get("isbn")),
        description=_str_or_none(sug.get("description")),
        published_year=_int_or_none(sug.get("published_year")),
        genre=_str_or_none(sug.get("genre")),
        image_url=_str_or_none(sug.get("image_url")),
    )


def enrich_book_metadata(
    session: Session,
    req: BookAiEnrichRequest,
    *,
    gemini_call: Optional[Callable[..., dict[str, Any]]] = None,
    isbn_lookup: Optional[Callable[[str], Optional[IsbnLookupResult]]] = None,
    on_progress: Optional[Callable[[str, Optional[str]], None]] = None,
) -> BookAiEnrichResponse:
    """
    Return AI suggestions plus duplicate candidates.

    `gemini_call` is injectable for tests (defaults to gemini_generate_content_json).
    Optional `on_progress(step, message)` reports coarse pipeline steps for streaming UIs.
    """
    def _emit(step: str, message: Optional[str] = None) -> None:
        if on_progress is not None:
            on_progress(step, message)

    settings = get_settings()
    if not settings.GEMINI_API_KEY or not str(settings.GEMINI_API_KEY).strip():
        msg = "GEMINI_API_KEY is not configured"
        raise ValueError(msg)
    if not settings.GEMINI_MODEL or not str(settings.GEMINI_MODEL).strip():
        msg = "GEMINI_MODEL is not configured"
        raise ValueError(msg)

    _emit("starting", "Preparing enrichment…")

    lookup: Optional[IsbnLookupResult] = None
    isbn_stripped = (req.isbn or "").strip()
    lookup_fn = isbn_lookup or fetch_open_library_by_isbn
    if isbn_stripped:
        _emit("isbn_lookup", "Looking up ISBN…")
        lookup = lookup_fn(isbn_stripped)

    merged_req = _merge_req_with_lookup(req, lookup)
    _emit("duplicate_check", "Checking catalog for similar titles…")
    duplicate_candidates = find_duplicate_candidates(session, merged_req)
    requires_confirmation = len(duplicate_candidates) > 0

    dup_lines = "\n".join(
        f"- id={d.book_id} title={d.title!r} author={d.author!r} isbn={d.isbn!r} ({d.reason})"
        for d in duplicate_candidates
    ) or "(none)"

    staff_image = (req.image_url or "").strip() or None
    if not staff_image and lookup and lookup.cover_url:
        staff_image = lookup.cover_url

    system = (
        "You are a library cataloging assistant. "
        "Return ONLY valid JSON with a single key \"suggestions\" whose value is an object. "
        "Fields in suggestions may include: title, author, isbn, description, published_year, "
        "genre, image_url. Omit keys you are unsure about. "
        "When isbn_lookup is present, use its title, author, published_year, and cover_url as "
        "authoritative for those fields (copy into suggestions). Still write description and genre; "
        "you may use isbn_lookup context for genre. "
        "Otherwise use public bibliographic knowledge; the staff may provide ISBN or rough title. "
        "For image_url, prefer a stable HTTPS URL to a cover image when you can name a reliable source; "
        "otherwise omit image_url. "
        "description should be 2-4 sentences suitable for a library catalog. "
        "If duplicate candidates are listed, still fill suggestions when possible, but do not claim "
        "the book is unique."
    )
    user_payload: dict[str, Any] = {
        "staff_input": {
            "title": merged_req.title,
            "author": merged_req.author,
            "isbn": req.isbn,
            "description": req.description,
            "published_year": merged_req.published_year,
            "genre": req.genre,
            "image_url": staff_image,
        },
        "existing_catalog_candidates": dup_lines,
    }
    if lookup:
        user_payload["isbn_lookup"] = {
            "source": "open_library",
            "title": lookup.title,
            "author": lookup.author,
            "published_year": lookup.published_year,
            "cover_url": lookup.cover_url,
        }
    user = json.dumps(user_payload, ensure_ascii=False)

    call = gemini_call or gemini_generate_content_json
    try:
        _emit("gemini", "Requesting AI suggestions…")
        call_kwargs: dict[str, Any] = {
            "api_key": settings.GEMINI_API_KEY.strip(),
            "model": settings.GEMINI_MODEL.strip(),
            "base_url": settings.GEMINI_BASE_URL,
            "system_instruction": system,
            "user_text": user,
            "temperature": 0.0,
            "timeout_seconds": settings.GEMINI_HTTP_TIMEOUT_SECONDS,
        }
        if on_progress is not None:
            call_kwargs["on_retry"] = lambda: _emit(
                "gemini_retry",
                "Retrying after a temporary API error…",
            )
        raw = call(**call_kwargs)
    except Exception as exc:
        logger.exception("gemini_book_enrich_failed")
        msg = f"AI enrichment failed: {exc}"
        raise ValueError(msg) from exc

    suggestions = _merge_lookup_into_suggestions(
        _parse_suggestions(raw),
        req,
        lookup,
    )
    return BookAiEnrichResponse(
        suggestions=suggestions,
        duplicate_candidates=duplicate_candidates,
        requires_confirmation=requires_confirmation,
    )
