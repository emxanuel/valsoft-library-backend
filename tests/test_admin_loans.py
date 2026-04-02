"""GET /admin/loans — all open loans with assigned staff (admin only)."""

from fastapi.testclient import TestClient

from tests.test_library import _CHECKOUT_CLIENT


def test_admin_loans_requires_auth(client: TestClient):
    assert client.get("/admin/loans").status_code == 401


def test_employee_forbidden_admin_loans(authenticated_client: TestClient):
    assert authenticated_client.get("/admin/loans").status_code == 403


def test_admin_lists_all_open_loans_two_staff(
    admin_client: TestClient,
    authenticated_client_factory,
):
    emp1 = authenticated_client_factory(email="emp1@example.com")
    emp2 = authenticated_client_factory(email="emp2@example.com")

    b1 = emp1.post(
        "/library/books",
        json={"title": "Book One", "author": "A", "isbn": "admin-loans-1"},
    ).json()
    b2 = emp2.post(
        "/library/books",
        json={"title": "Book Two", "author": "B", "isbn": "admin-loans-2"},
    ).json()

    emp1.post(f"/library/books/{b1['id']}/checkout", json=_CHECKOUT_CLIENT)
    emp2.post(f"/library/books/{b2['id']}/checkout", json=_CHECKOUT_CLIENT)

    r = admin_client.get("/admin/loans")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert len(data["items"]) == 2
    emails = {x["staff_email"] for x in data["items"]}
    assert emails == {"emp1@example.com", "emp2@example.com"}
    titles = {x["book_title"] for x in data["items"]}
    assert titles == {"Book One", "Book Two"}
    for item in data["items"]:
        assert "staff_user_id" in item
        assert "staff_first_name" in item
        assert "staff_last_name" in item


def test_admin_open_loans_pagination(
    admin_client: TestClient,
    authenticated_client_factory,
):
    emp = authenticated_client_factory(email="pager@example.com")
    for i in range(3):
        book = emp.post(
            "/library/books",
            json={
                "title": f"P{i}",
                "author": "A",
                "isbn": f"pag-{i}",
            },
        ).json()
        emp.post(f"/library/books/{book['id']}/checkout", json=_CHECKOUT_CLIENT)

    page1 = admin_client.get("/admin/loans", params={"limit": 2, "offset": 0}).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2

    page2 = admin_client.get("/admin/loans", params={"limit": 2, "offset": 2}).json()
    assert page2["total"] == 3
    assert len(page2["items"]) == 1
