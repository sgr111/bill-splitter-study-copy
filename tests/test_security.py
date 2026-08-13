import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def get_user_b_headers(client):
    import uuid
    unique_email = f"userb_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "User B", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={
        "email": unique_email, "password": "pass123"
    })
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_idor_group_access(client: AsyncClient, auth_headers):
    headers_b = await get_user_b_headers(client)
    create = await client.post("/groups", json={"name": "User A Group"}, headers=auth_headers)
    group_id = create.json()["id"]
    response = await client.get(f"/groups/{group_id}", headers=headers_b)
    assert response.status_code == 403


async def test_idor_expense_access(client: AsyncClient, auth_headers):
    headers_b = await get_user_b_headers(client)
    group = await client.post("/groups", json={"name": "A Group"}, headers=auth_headers)
    group_id = group.json()["id"]
    expense = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Secret",
        "total_amount": 500.0,
        "split_type": "equal"
    }, headers=auth_headers)
    expense_id = expense.json()["id"]
    response = await client.get(f"/expenses/{expense_id}", headers=headers_b)
    assert response.status_code == 403


async def test_idor_split_access(client: AsyncClient, auth_headers):
    headers_b = await get_user_b_headers(client)
    group = await client.post("/groups", json={"name": "A Group"}, headers=auth_headers)
    group_id = group.json()["id"]
    expense = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Secret",
        "total_amount": 500.0,
        "split_type": "equal"
    }, headers=auth_headers)
    expense_id = expense.json()["id"]
    response = await client.get(f"/splits/{expense_id}", headers=headers_b)
    assert response.status_code == 403


async def test_idor_settle_split(client: AsyncClient, auth_headers):
    headers_b = await get_user_b_headers(client)
    group = await client.post("/groups", json={"name": "A Group"}, headers=auth_headers)
    group_id = group.json()["id"]
    expense = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Secret",
        "total_amount": 500.0,
        "split_type": "equal"
    }, headers=auth_headers)
    expense_id = expense.json()["id"]
    splits = await client.get(f"/splits/{expense_id}", headers=auth_headers)
    split_id = splits.json()[0]["id"]
    response = await client.post(f"/splits/{split_id}/settle", headers=headers_b)
    assert response.status_code == 403


async def test_idor_delete_expense(client: AsyncClient, auth_headers):
    headers_b = await get_user_b_headers(client)
    group = await client.post("/groups", json={"name": "A Group"}, headers=auth_headers)
    group_id = group.json()["id"]
    expense = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Secret",
        "total_amount": 500.0,
        "split_type": "equal"
    }, headers=auth_headers)
    expense_id = expense.json()["id"]
    response = await client.delete(f"/expenses/{expense_id}", headers=headers_b)
    assert response.status_code == 403


async def test_idor_update_group(client: AsyncClient, auth_headers):
    headers_b = await get_user_b_headers(client)
    group = await client.post("/groups", json={"name": "A Group"}, headers=auth_headers)
    group_id = group.json()["id"]
    response = await client.put(f"/groups/{group_id}", json={"name": "Hacked"}, headers=headers_b)
    assert response.status_code == 403


async def test_no_auth_token(client: AsyncClient):
    response = await client.get("/groups")
    assert response.status_code == 401


async def test_invalid_token(client: AsyncClient):
    response = await client.get("/groups", headers={"Authorization": "Bearer faketoken"})
    assert response.status_code == 401