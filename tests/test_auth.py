from fastapi.testclient import TestClient

from tests.conftest import login_user, register_user


def test_register_returns_user_read(client: TestClient):
    data = register_user(
        client,
        email="new@example.com",
        password="password123",
        first_name="New",
        last_name="User",
    )
    assert data["email"] == "new@example.com"
    assert data["first_name"] == "New"
    assert data["last_name"] == "User"
    assert data["role"] == "employee"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_register_duplicate_email_returns_400(client: TestClient):
    register_user(client, email="dup@example.com")
    response = client.post(
        "/auth/register",
        json={
            "first_name": "A",
            "last_name": "B",
            "email": "dup@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 400
    assert "already" in response.json()["detail"].lower()


def test_login_success(client: TestClient):
    register_user(client, email="login@example.com", password="secretpass99")
    response = client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "secretpass99"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "user" in body
    assert body["user"]["email"] == "login@example.com"


def test_login_wrong_password_returns_401(client: TestClient):
    register_user(client, email="x@example.com", password="rightpass")
    response = client.post(
        "/auth/login",
        json={"email": "x@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


def test_me_with_session_returns_200(client: TestClient):
    register_user(client, email="me@example.com")
    login_user(client, "me@example.com", "password123")
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_me_without_cookie_returns_401(client: TestClient):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_logout_invalidates_session(client: TestClient):
    register_user(client, email="out@example.com")
    login_user(client, "out@example.com", "password123")
    assert client.get("/auth/me").status_code == 200

    logout = client.post("/auth/logout")
    assert logout.status_code == 204

    assert client.get("/auth/me").status_code == 401
