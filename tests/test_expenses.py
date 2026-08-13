import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def create_group(client, headers):
    r = await client.post("/groups", json={"name": "Expense Group"}, headers=headers)
    return r.json()["id"]


async def test_add_expense_equal(client: AsyncClient, auth_headers):
    group_id = await create_group(client, auth_headers)
    response = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Dinner",
        "total_amount": 900.0,
        "split_type": "equal"
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["split_type"] == "equal"


async def test_add_expense_unequal(client: AsyncClient, auth_headers):
    group_id = await create_group(client, auth_headers)
    user_id = (await client.get("/auth/me", headers=auth_headers)).json()["id"]
    response = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Hotel",
        "total_amount": 1000.0,
        "split_type": "unequal",
        "splits": [{"user_id": user_id, "amount_owed": 1000.0}]
    }, headers=auth_headers)
    assert response.status_code == 201


async def test_add_expense_percentage(client: AsyncClient, auth_headers):
    group_id = await create_group(client, auth_headers)
    user_id = (await client.get("/auth/me", headers=auth_headers)).json()["id"]
    response = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Cab",
        "total_amount": 500.0,
        "split_type": "percentage",
        "splits": [{"user_id": user_id, "percentage": 100.0}]
    }, headers=auth_headers)
    assert response.status_code == 201


async def test_add_expense_unequal_mismatch(client: AsyncClient, auth_headers):
    group_id = await create_group(client, auth_headers)
    user_id = (await client.get("/auth/me", headers=auth_headers)).json()["id"]
    response = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Bad Split",
        "total_amount": 1000.0,
        "split_type": "unequal",
        "splits": [{"user_id": user_id, "amount_owed": 500.0}]
    }, headers=auth_headers)
    assert response.status_code == 400


async def test_list_expenses(client: AsyncClient, auth_headers):
    group_id = await create_group(client, auth_headers)
    await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Lunch",
        "total_amount": 300.0,
        "split_type": "equal"
    }, headers=auth_headers)
    response = await client.get(f"/expenses/group/{group_id}", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_get_expense(client: AsyncClient, auth_headers):
    group_id = await create_group(client, auth_headers)
    create = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Snacks",
        "total_amount": 200.0,
        "split_type": "equal"
    }, headers=auth_headers)
    expense_id = create.json()["id"]
    response = await client.get(f"/expenses/{expense_id}", headers=auth_headers)
    assert response.status_code == 200


async def test_delete_expense(client: AsyncClient, auth_headers):
    group_id = await create_group(client, auth_headers)
    create = await client.post("/expenses", json={
        "group_id": group_id,
        "description": "To Delete",
        "total_amount": 100.0,
        "split_type": "equal"
    }, headers=auth_headers)
    expense_id = create.json()["id"]
    response = await client.delete(f"/expenses/{expense_id}", headers=auth_headers)
    assert response.status_code == 204