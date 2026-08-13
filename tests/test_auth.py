import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_success(client: AsyncClient):
    import uuid
    unique_email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post("/auth/register", json={
        "name": "New User",
        "email": unique_email,
        "password": "password123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == unique_email
    assert "id" in data
    assert "password" not in data


async def test_get_me_no_token(client: AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_register_duplicate_email(client: AsyncClient, registered_user):
    response = await client.post("/auth/register", json={
        "name": "Duplicate",
        "email": registered_user["email"],
        "password": "password123"
    })
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


async def test_login_success(client: AsyncClient, registered_user):
    response = await client.post("/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"]
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, registered_user):
    response = await client.post("/auth/login", json={
        "email": registered_user["email"],
        "password": "wrongpassword"
    })
    assert response.status_code == 401


async def test_login_wrong_email(client: AsyncClient):
    response = await client.post("/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "password123"
    })
    assert response.status_code == 401


async def test_get_me_success(client: AsyncClient, registered_user, auth_headers):
    response = await client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == registered_user["email"]
    assert data["name"] == registered_user["name"]


async def test_get_me_invalid_token(client: AsyncClient):
    response = await client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert response.status_code == 401


async def test_refresh_token_success(client: AsyncClient, registered_user):
    login_response = await client.post("/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"]
    })
    refresh_token = login_response.json()["refresh_token"]
    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_refresh_token_invalid(client: AsyncClient):
    response = await client.post("/auth/refresh", json={"refresh_token": "invalidtoken"})
    assert response.status_code == 401