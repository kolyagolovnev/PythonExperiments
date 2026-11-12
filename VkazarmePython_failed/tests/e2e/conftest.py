import pytest
import httpx
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api/v1"

@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url=BASE_URL, follow_redirects=True)

@pytest.fixture
def user_credentials() -> Dict[str, Any]:
    return {
        "email": "test_user@example.com",
        "password": "StrongPass123",
    }

@pytest.fixture
def admin_credentials() -> Dict[str, Any]:
    # В реальном проекте это отдельный пользователь с ролью admin
    return {
        "email": "admin@example.com",
        "password": "AdminPass123",
    }

@pytest.fixture
def auth_token(client, user_credentials):
    resp = client.post("/account/signin", json=user_credentials)
    assert resp.status_code in (200, 201), f"Signin failed: {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, "No token returned"
    return token

@pytest.fixture
def admin_auth_token(client, admin_credentials):
    resp = client.post("/account/admin", json=admin_credentials)
    assert resp.status_code == 200, f"Admin signin failed: {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, "No admin token returned"
    return token

@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def admin_headers(admin_auth_token):
    return {"Authorization": f"Bearer {admin_auth_token}"}
