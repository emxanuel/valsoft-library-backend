from collections.abc import Callable

from fastapi.testclient import TestClient


def test_library_requires_auth(client: TestClient):
    response = client.get("/library/books")
    assert response.status_code == 401
    assert client.get("/library/loans").status_code == 401


def test_books_crud(authenticated_client: TestClient):
    c = authenticated_client
    assert c.get("/library/books").json() == []

    create = c.post(
        "/library/books",
        json={
            "title": "The Book",
            "author": "Ann Author",
            "isbn": "978-123",
            "description": "Desc",
            "published_year": 2020,
            "genre": "Fiction",
        },
    )
    assert create.status_code == 201
    book = create.json()
    book_id = book["id"]
    assert book["title"] == "The Book"
    assert book["is_checked_out"] is False

    listed = c.get("/library/books").json()
    assert len(listed) == 1
    assert listed[0]["id"] == book_id

    one = c.get(f"/library/books/{book_id}")
    assert one.status_code == 200
    assert one.json()["title"] == "The Book"

    patched = c.patch(
        f"/library/books/{book_id}",
        json={"title": "Renamed"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Renamed"

    deleted = c.delete(f"/library/books/{book_id}")
    assert deleted.status_code == 204
    assert c.get(f"/library/books/{book_id}").status_code == 404


def test_soft_delete_removes_book_from_catalog(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Removed", "author": "A", "isbn": "soft-del-1"},
    ).json()["id"]
    assert len(c.get("/library/books").json()) == 1
    assert c.delete(f"/library/books/{book_id}").status_code == 204
    assert c.get("/library/books").json() == []
    assert c.get(f"/library/books/{book_id}").status_code == 404


def test_isbn_reusable_after_soft_delete(authenticated_client: TestClient):
    c = authenticated_client
    isbn = "978-0000000001"
    first_id = c.post(
        "/library/books",
        json={"title": "First", "author": "A", "isbn": isbn},
    ).json()["id"]
    assert c.delete(f"/library/books/{first_id}").status_code == 204
    second = c.post(
        "/library/books",
        json={"title": "Second", "author": "B", "isbn": isbn},
    )
    assert second.status_code == 201
    assert second.json()["isbn"] == isbn


def test_list_books_search_q_and_genre(authenticated_client: TestClient):
    c = authenticated_client
    c.post(
        "/library/books",
        json={
            "title": "Alpha Guide",
            "author": "Beta Writer",
            "isbn": "111",
            "genre": "SciFi",
        },
    )
    c.post(
        "/library/books",
        json={
            "title": "Other",
            "author": "Gamma",
            "isbn": "222",
            "genre": "History",
        },
    )

    by_title = c.get("/library/books", params={"q": "alpha"}).json()
    assert len(by_title) == 1
    assert by_title[0]["title"] == "Alpha Guide"

    by_author = c.get("/library/books", params={"q": "beta"}).json()
    assert len(by_author) == 1

    by_isbn = c.get("/library/books", params={"q": "111"}).json()
    assert len(by_isbn) == 1

    scifi = c.get("/library/books", params={"genre": "SciFi"}).json()
    assert len(scifi) == 1
    assert scifi[0]["genre"] == "SciFi"


def test_checkout_second_attempt_fails(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "One Copy", "author": "A"},
    ).json()["id"]

    first = c.post(f"/library/books/{book_id}/checkout", json={})
    assert first.status_code == 201
    second = c.post(f"/library/books/{book_id}/checkout", json={})
    assert second.status_code == 400
    assert "already" in second.json()["detail"].lower()


def test_checkout_sets_checked_out_flag(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Flag Book", "author": "A"},
    ).json()["id"]

    assert c.get(f"/library/books/{book_id}").json()["is_checked_out"] is False

    c.post(f"/library/books/{book_id}/checkout", json={})
    assert c.get(f"/library/books/{book_id}").json()["is_checked_out"] is True
    listed = c.get("/library/books").json()
    assert listed[0]["is_checked_out"] is True


def test_checkin_flow(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Return Me", "author": "A"},
    ).json()["id"]

    c.post(f"/library/books/{book_id}/checkout", json={})
    checkin = c.post(f"/library/books/{book_id}/checkin")
    assert checkin.status_code == 200
    assert checkin.json()["returned_at"] is not None
    assert c.get(f"/library/books/{book_id}").json()["is_checked_out"] is False


def test_list_my_open_loans(authenticated_client: TestClient):
    c = authenticated_client
    assert c.get("/library/loans").json() == []

    book_id = c.post(
        "/library/books",
        json={"title": "Loaned Title", "author": "Loaned Author"},
    ).json()["id"]

    assert c.get("/library/loans").json() == []

    c.post(f"/library/books/{book_id}/checkout", json={})
    loans = c.get("/library/loans").json()
    assert len(loans) == 1
    assert loans[0]["book_id"] == book_id
    assert loans[0]["book_title"] == "Loaned Title"
    assert loans[0]["book_author"] == "Loaned Author"
    assert loans[0]["due_at"] is None

    c.post(f"/library/books/{book_id}/checkin")
    assert c.get("/library/loans").json() == []


def test_checkin_no_active_loan_returns_404(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Never Out", "author": "A"},
    ).json()["id"]

    r = c.post(f"/library/books/{book_id}/checkin")
    assert r.status_code == 404


def test_delete_checked_out_book_returns_400(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "On Loan", "author": "A"},
    ).json()["id"]
    c.post(f"/library/books/{book_id}/checkout", json={})

    r = c.delete(f"/library/books/{book_id}")
    assert r.status_code == 400


def test_delete_after_checkin_succeeds(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Returned", "author": "A"},
    ).json()["id"]
    c.post(f"/library/books/{book_id}/checkout", json={})
    c.post(f"/library/books/{book_id}/checkin")

    r = c.delete(f"/library/books/{book_id}")
    assert r.status_code == 204


def test_non_borrower_cannot_checkin(
    authenticated_client_factory: Callable[..., TestClient],
):
    borrower = authenticated_client_factory(email="borrower@example.com")
    other = authenticated_client_factory(email="other@example.com")

    book_id = borrower.post(
        "/library/books",
        json={"title": "Shared", "author": "A"},
    ).json()["id"]
    borrower.post(f"/library/books/{book_id}/checkout", json={})

    r = other.post(f"/library/books/{book_id}/checkin")
    assert r.status_code == 403


def test_second_user_cannot_checkout_while_borrowed(
    authenticated_client_factory: Callable[..., TestClient],
):
    borrower = authenticated_client_factory(email="u1@example.com")
    other = authenticated_client_factory(email="u2@example.com")

    book_id = borrower.post(
        "/library/books",
        json={"title": "Single", "author": "A"},
    ).json()["id"]
    borrower.post(f"/library/books/{book_id}/checkout", json={})

    r = other.post(f"/library/books/{book_id}/checkout", json={})
    assert r.status_code == 400
