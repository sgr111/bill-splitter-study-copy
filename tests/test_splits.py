import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def create_expense(client, headers):
    r = await client.post("/groups", json={"name": "Split Group"}, headers=headers)
    group_id = r.json()["id"]
    e = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Test Expense",
        "total_amount": 600.0,
        "split_type": "equal"
    }, headers=headers)
    return e.json()["id"]


async def test_get_splits(client: AsyncClient, auth_headers):
    expense_id = await create_expense(client, auth_headers)
    response = await client.get(f"/splits/{expense_id}", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_settle_own_split(client: AsyncClient, auth_headers):
    expense_id = await create_expense(client, auth_headers)
    splits = await client.get(f"/splits/{expense_id}", headers=auth_headers)
    split_id = splits.json()[0]["id"]
    response = await client.post(f"/splits/{split_id}/settle", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["is_settled"] == True


async def test_settle_others_split(client: AsyncClient, auth_headers):
    import uuid
    unique_email = f"other_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "Other", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={"email": unique_email, "password": "pass123"})
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    expense_id = await create_expense(client, auth_headers)
    splits = await client.get(f"/splits/{expense_id}", headers=auth_headers)
    split_id = splits.json()[0]["id"]

    response = await client.post(f"/splits/{split_id}/settle", headers=headers2)
    assert response.status_code == 403