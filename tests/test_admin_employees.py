from fastapi.testclient import TestClient
from sqlmodel import Session

from database.models import Book, BookCopy, Loan
from database.models.users import UserRole
from tests.conftest import create_staff_in_db, register_user


def test_admin_employees_requires_auth(client: TestClient):
    assert client.get("/admin/employees").status_code == 401


def test_employee_forbidden_on_admin_api(authenticated_client: TestClient):
    r = authenticated_client.get("/admin/employees")
    assert r.status_code == 403


def test_admin_lists_staff(admin_client: TestClient):
    r = admin_client.get("/admin/employees")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any(x["email"] == "admin@example.com" for x in data["items"])


def test_admin_crud_employee(admin_client: TestClient):
    create = admin_client.post(
        "/admin/employees",
        json={
            "first_name": "Jane",
            "last_name": "Staff",
            "email": "jane.staff@example.com",
            "password": "password123",
        },
    )
    assert create.status_code == 201
    body = create.json()
    assert body["email"] == "jane.staff@example.com"
    assert body["role"] == "employee"
    uid = body["id"]

    one = admin_client.get(f"/admin/employees/{uid}")
    assert one.status_code == 200
    assert one.json()["first_name"] == "Jane"

    patched = admin_client.patch(
        f"/admin/employees/{uid}",
        json={"first_name": "Janet"},
    )
    assert patched.status_code == 200
    assert patched.json()["first_name"] == "Janet"

    deleted = admin_client.delete(f"/admin/employees/{uid}")
    assert deleted.status_code == 204
    assert admin_client.get(f"/admin/employees/{uid}").status_code == 404


def test_admin_cannot_delete_self(admin_client: TestClient, db_session: Session):
    me = admin_client.get("/auth/me").json()
    uid = me["id"]
    r = admin_client.delete(f"/admin/employees/{uid}")
    assert r.status_code == 400
    assert "own" in r.json()["detail"].lower()


def test_cannot_demote_last_admin(admin_client: TestClient):
    me = admin_client.get("/auth/me").json()
    uid = me["id"]
    r = admin_client.patch(f"/admin/employees/{uid}", json={"role": "employee"})
    assert r.status_code == 400
    assert "last admin" in r.json()["detail"].lower()


def test_cannot_delete_employee_with_loan(admin_client: TestClient, db_session: Session):
    emp = create_staff_in_db(
        db_session,
        email="withloan@example.com",
        role=UserRole.EMPLOYEE,
    )
    book = Book(title="Loaned", author="A")
    db_session.add(book)
    db_session.commit()
    db_session.refresh(book)
    copy = BookCopy(book_id=book.id)
    db_session.add(copy)
    db_session.commit()
    db_session.refresh(copy)
    loan = Loan(copy_id=copy.id, user_id=emp.id)
    db_session.add(loan)
    db_session.commit()

    r = admin_client.delete(f"/admin/employees/{emp.id}")
    assert r.status_code == 400
    assert "loan" in r.json()["detail"].lower()


def test_register_creates_employee(client: TestClient):
    data = register_user(client, email="reg@example.com")
    assert data["role"] == "employee"
    assert "id" in data
