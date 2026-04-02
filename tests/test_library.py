from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlmodel import Session

from database.models.users import UserRole
from tests.conftest import create_staff_in_db, login_user

_EMPTY_PAGE = {"items": [], "total": 0, "limit": 20, "offset": 0}
_EMPTY_CLIENTS_PAGE = {"items": [], "total": 0, "limit": 20, "offset": 0}
_EMPTY_LOAN_HISTORY_PAGE = {"items": [], "total": 0, "limit": 20, "offset": 0}

_CHECKOUT_CLIENT = {
    "client": {
        "name": "Alex Reader",
        "email": "alex.reader@example.com",
        "phone": "555-0100",
    }
}


def test_library_requires_auth(client: TestClient):
    response = client.get("/library/books")
    assert response.status_code == 401
    assert client.post("/library/books/ai/enrich", json={"title": "T", "author": "A"}).status_code == 401
    assert client.get("/library/loans").status_code == 401
    assert client.get("/library/clients").status_code == 401
    assert client.post("/library/clients", json={"name": "A", "email": "a@a.com"}).status_code == 401
    assert client.get("/library/clients/1").status_code == 401
    assert client.patch("/library/clients/1", json={"name": "B"}).status_code == 401
    assert client.delete("/library/clients/1").status_code == 401
    assert client.get("/library/loans/history").status_code == 401


def test_books_crud(authenticated_client: TestClient):
    c = authenticated_client
    assert c.get("/library/books").json() == _EMPTY_PAGE

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
    assert book["total_copies"] == 1
    assert book["available_copies"] == 1
    assert book["is_checked_out"] is False

    listed = c.get("/library/books").json()
    assert listed["total"] == 1
    assert len(listed["items"]) == 1
    assert listed["items"][0]["id"] == book_id

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
    assert c.get("/library/books").json()["total"] == 1
    assert c.delete(f"/library/books/{book_id}").status_code == 204
    assert c.get("/library/books").json() == _EMPTY_PAGE
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
    assert by_title["total"] == 1
    assert len(by_title["items"]) == 1
    assert by_title["items"][0]["title"] == "Alpha Guide"

    by_author = c.get("/library/books", params={"q": "beta"}).json()
    assert by_author["total"] == 1

    by_isbn = c.get("/library/books", params={"q": "111"}).json()
    assert by_isbn["total"] == 1

    scifi = c.get("/library/books", params={"genre": "SciFi"}).json()
    assert scifi["total"] == 1
    assert scifi["items"][0]["genre"] == "SciFi"


def test_list_books_pagination(authenticated_client: TestClient):
    c = authenticated_client
    for i in range(4):
        c.post(
            "/library/books",
            json={"title": f"Book {i}", "author": "A", "isbn": f"pag-{i}"},
        )

    first = c.get("/library/books", params={"limit": 2, "offset": 0}).json()
    assert first["total"] == 4
    assert first["limit"] == 2
    assert first["offset"] == 0
    assert len(first["items"]) == 2
    assert first["items"][0]["title"] == "Book 0"
    assert first["items"][1]["title"] == "Book 1"

    second = c.get("/library/books", params={"limit": 2, "offset": 2}).json()
    assert second["total"] == 4
    assert second["items"][0]["title"] == "Book 2"
    assert second["items"][1]["title"] == "Book 3"


def test_checkout_second_attempt_fails(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "One Copy", "author": "A"},
    ).json()["id"]

    first = c.post(f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT)
    assert first.status_code == 201
    second = c.post(f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT)
    assert second.status_code == 400
    assert "copies" in second.json()["detail"].lower()


def test_checkout_sets_checked_out_flag(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Flag Book", "author": "A"},
    ).json()["id"]

    assert c.get(f"/library/books/{book_id}").json()["is_checked_out"] is False

    c.post(f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT)
    assert c.get(f"/library/books/{book_id}").json()["is_checked_out"] is True
    listed = c.get("/library/books").json()
    assert listed["items"][0]["is_checked_out"] is True


def test_checkin_flow(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Return Me", "author": "A"},
    ).json()["id"]

    loan_id = c.post(
        f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT
    ).json()["id"]
    checkin = c.post(f"/library/loans/{loan_id}/checkin")
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

    loan_id = c.post(
        f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT
    ).json()["id"]
    loans = c.get("/library/loans").json()
    assert len(loans) == 1
    assert loans[0]["loan_id"] == loan_id
    assert loans[0]["book_id"] == book_id
    assert loans[0]["book_title"] == "Loaned Title"
    assert loans[0]["book_author"] == "Loaned Author"
    assert loans[0]["client_name"] == "Alex Reader"
    assert loans[0]["client_email"] == "alex.reader@example.com"
    assert loans[0]["client_phone"] == "555-0100"
    assert loans[0]["due_at"] is None

    c.post(f"/library/loans/{loan_id}/checkin")
    assert c.get("/library/loans").json() == []


def test_checkin_no_active_loan_returns_404(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Never Out", "author": "A"},
    ).json()["id"]

    r = c.post("/library/loans/999999/checkin")
    assert r.status_code == 404


def test_delete_checked_out_book_returns_400(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "On Loan", "author": "A"},
    ).json()["id"]
    c.post(f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT)

    r = c.delete(f"/library/books/{book_id}")
    assert r.status_code == 400


def test_delete_after_checkin_succeeds(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Returned", "author": "A"},
    ).json()["id"]
    loan_id = c.post(
        f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT
    ).json()["id"]
    c.post(f"/library/loans/{loan_id}/checkin")

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
    loan_id = borrower.post(
        f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT
    ).json()["id"]

    r = other.post(f"/library/loans/{loan_id}/checkin")
    assert r.status_code == 403


def test_admin_can_checkin_other_staff_loan(client: TestClient, db_session: Session):
    create_staff_in_db(
        db_session,
        email="emp@example.com",
        password="password123",
        first_name="Em",
        last_name="Ploy",
        role=UserRole.EMPLOYEE,
    )
    create_staff_in_db(
        db_session,
        email="admin@example.com",
        password="password123",
        first_name="Ad",
        last_name="Min",
        role=UserRole.ADMIN,
    )
    login_user(client, "emp@example.com", "password123")
    book_id = client.post(
        "/library/books",
        json={"title": "Admin checkin", "author": "A"},
    ).json()["id"]
    loan_id = client.post(
        f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT
    ).json()["id"]
    login_user(client, "admin@example.com", "password123")
    r = client.post(f"/library/loans/{loan_id}/checkin")
    assert r.status_code == 200
    assert r.json()["returned_at"] is not None


def test_two_copies_allow_two_concurrent_checkouts(
    authenticated_client_factory: Callable[..., TestClient],
):
    u1 = authenticated_client_factory(email="a1@example.com")
    u2 = authenticated_client_factory(email="a2@example.com")
    book_id = u1.post(
        "/library/books",
        json={"title": "Multi", "author": "A"},
    ).json()["id"]
    assert u1.post(f"/library/books/{book_id}/copies", json={}).status_code == 201

    detail = u1.get(f"/library/books/{book_id}").json()
    assert detail["total_copies"] == 2
    assert detail["available_copies"] == 2

    out1 = u1.post(f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT)
    out2 = u2.post(f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT)
    assert out1.status_code == 201
    assert out1.json()["copy_id"] != out2.json()["copy_id"]
    assert out2.status_code == 201

    detail2 = u1.get(f"/library/books/{book_id}").json()
    assert detail2["available_copies"] == 0
    assert detail2["is_checked_out"] is True


def test_copy_barcode_must_be_unique(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Bar", "author": "A"},
    ).json()["id"]
    assert (
        c.post(
            f"/library/books/{book_id}/copies",
            json={"barcode": "X-123"},
        ).status_code
        == 201
    )
    dup = c.post(
        f"/library/books/{book_id}/copies",
        json={"barcode": "X-123"},
    )
    assert dup.status_code == 400


def test_second_user_cannot_checkout_while_borrowed(
    authenticated_client_factory: Callable[..., TestClient],
):
    borrower = authenticated_client_factory(email="u1@example.com")
    other = authenticated_client_factory(email="u2@example.com")

    book_id = borrower.post(
        "/library/books",
        json={"title": "Single", "author": "A"},
    ).json()["id"]
    borrower.post(f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT)

    r = other.post(f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT)
    assert r.status_code == 400


def test_list_clients_empty(authenticated_client: TestClient):
    c = authenticated_client
    assert c.get("/library/clients").json() == _EMPTY_CLIENTS_PAGE


def test_list_clients_after_checkout(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Client Log", "author": "A"},
    ).json()["id"]
    assert c.get("/library/clients").json()["total"] == 0
    c.post(f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT)
    page = c.get("/library/clients").json()
    assert page["total"] == 1
    assert page["items"][0]["name"] == "Alex Reader"
    assert page["items"][0]["email"] == "alex.reader@example.com"
    assert page["items"][0]["phone"] == "555-0100"


def test_clients_crud(authenticated_client: TestClient):
    c = authenticated_client
    create = c.post(
        "/library/clients",
        json={
            "name": "Patron One",
            "email": "patron.one@example.com",
            "phone": "555-0001",
        },
    )
    assert create.status_code == 201
    body = create.json()
    client_id = body["id"]
    assert body["name"] == "Patron One"
    assert body["email"] == "patron.one@example.com"
    assert body["phone"] == "555-0001"

    dup = c.post(
        "/library/clients",
        json={"name": "Other", "email": "Patron.One@Example.com"},
    )
    assert dup.status_code == 400
    assert "email" in dup.json()["detail"].lower()

    assert c.get("/library/clients/99999").status_code == 404

    one = c.get(f"/library/clients/{client_id}")
    assert one.status_code == 200
    assert one.json()["name"] == "Patron One"

    patched = c.patch(
        f"/library/clients/{client_id}",
        json={"name": "Patron Updated"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Patron Updated"

    assert c.delete(f"/library/clients/{client_id}").status_code == 204
    assert c.get(f"/library/clients/{client_id}").status_code == 404


def test_update_client_email_conflict(authenticated_client: TestClient):
    c = authenticated_client
    a = c.post(
        "/library/clients",
        json={"name": "A", "email": "a_unique@example.com"},
    ).json()["id"]
    b = c.post(
        "/library/clients",
        json={"name": "B", "email": "b_unique@example.com"},
    ).json()["id"]
    r = c.patch(f"/library/clients/{b}", json={"email": "a_unique@example.com"})
    assert r.status_code == 400


def test_delete_client_blocked_when_loan_exists(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Tied", "author": "A"},
    ).json()["id"]
    loan_id = c.post(
        f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT
    ).json()["id"]
    page = c.get("/library/clients").json()
    assert page["total"] == 1
    patron_id = page["items"][0]["id"]

    r = c.delete(f"/library/clients/{patron_id}")
    assert r.status_code == 400
    assert "loan" in r.json()["detail"].lower()

    c.post(f"/library/loans/{loan_id}/checkin")
    r2 = c.delete(f"/library/clients/{patron_id}")
    assert r2.status_code == 400
    assert "loan" in r2.json()["detail"].lower()


def test_staff_loan_history_empty(authenticated_client: TestClient):
    c = authenticated_client
    assert c.get("/library/loans/history").json() == _EMPTY_LOAN_HISTORY_PAGE


def test_staff_loan_history_after_checkin(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Hist Book", "author": "A"},
    ).json()["id"]
    loan_id = c.post(
        f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT
    ).json()["id"]
    assert c.get("/library/loans/history").json()["total"] == 0
    c.post(f"/library/loans/{loan_id}/checkin")
    page = c.get("/library/loans/history").json()
    assert page["total"] == 1
    assert page["items"][0]["loan_id"] == loan_id
    assert page["items"][0]["returned_at"] is not None
    assert page["items"][0]["book_title"] == "Hist Book"


def test_staff_loan_history_pagination(authenticated_client: TestClient):
    c = authenticated_client
    loan_ids: list[int] = []
    for i in range(3):
        book_id = c.post(
            "/library/books",
            json={"title": f"P{i}", "author": "A"},
        ).json()["id"]
        loan_id = c.post(
            f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT
        ).json()["id"]
        c.post(f"/library/loans/{loan_id}/checkin")
        loan_ids.append(loan_id)
    total = c.get("/library/loans/history").json()["total"]
    assert total == 3
    page1 = c.get("/library/loans/history", params={"limit": 2, "offset": 0}).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    page2 = c.get("/library/loans/history", params={"limit": 2, "offset": 2}).json()
    assert len(page2["items"]) == 1


def test_client_loan_history_requires_valid_client(authenticated_client: TestClient):
    c = authenticated_client
    assert c.get("/library/loans/history", params={"client_id": 999999}).status_code == 404


def test_client_loan_history_open_and_returned(authenticated_client: TestClient):
    c = authenticated_client
    book_id = c.post(
        "/library/books",
        json={"title": "Open And Done", "author": "A"},
    ).json()["id"]
    loan_open = c.post(
        f"/library/books/{book_id}/checkout", json=_CHECKOUT_CLIENT
    ).json()["id"]
    patron_id = c.get("/library/clients").json()["items"][0]["id"]

    book2_id = c.post(
        "/library/books",
        json={"title": "Returned Only", "author": "B"},
    ).json()["id"]
    loan_done = c.post(
        f"/library/books/{book2_id}/checkout", json=_CHECKOUT_CLIENT
    ).json()["id"]
    c.post(f"/library/loans/{loan_done}/checkin")

    page = c.get(
        "/library/loans/history",
        params={"client_id": patron_id},
    ).json()
    assert page["total"] == 2
    by_loan = {row["loan_id"]: row for row in page["items"]}
    assert by_loan[loan_open]["returned_at"] is None
    assert by_loan[loan_open]["staff_email"] == "user@example.com"
    assert by_loan[loan_done]["returned_at"] is not None
    assert by_loan[loan_done]["staff_email"] == "user@example.com"


def test_two_staff_same_patron_client_history(
    authenticated_client_factory: Callable[..., TestClient],
):
    u1 = authenticated_client_factory(email="s1@example.com")
    u2 = authenticated_client_factory(email="s2@example.com")

    b1 = u1.post(
        "/library/books",
        json={"title": "B1", "author": "A"},
    ).json()["id"]
    u1.post(f"/library/books/{b1}/checkout", json=_CHECKOUT_CLIENT)
    patron_id = u1.get("/library/clients").json()["items"][0]["id"]

    b2 = u2.post(
        "/library/books",
        json={"title": "B2", "author": "A"},
    ).json()["id"]
    u2.post(f"/library/books/{b2}/checkout", json=_CHECKOUT_CLIENT)

    page = u1.get(
        "/library/loans/history",
        params={"client_id": patron_id},
    ).json()
    assert page["total"] == 2
    emails = {row["staff_email"] for row in page["items"]}
    assert emails == {"s1@example.com", "s2@example.com"}

    assert u1.get("/library/loans/history").json()["total"] == 0
    assert u2.get("/library/loans/history").json()["total"] == 0
