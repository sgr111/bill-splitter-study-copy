import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def setup_group_with_expense(client, headers):
    r = await client.post("/groups", json={"name": "Settlement Group"}, headers=headers)
    group_id = r.json()["id"]
    await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Dinner",
        "total_amount": 900.0,
        "split_type": "equal"
    }, headers=headers)
    return group_id


async def test_record_settlement(client: AsyncClient, auth_headers, registered_user):
    import uuid
    unique_email = f"payee_{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post("/auth/register", json={
        "name": "Payee", "email": unique_email, "password": "pass123"
    })
    payee_id = r.json()["id"]
    group_id = await setup_group_with_expense(client, auth_headers)

    response = await client.post("/settlements", json={
        "group_id": group_id,
        "paid_to": payee_id,
        "amount": 300.0
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 300.0


async def test_list_settlements(client: AsyncClient, auth_headers, registered_user):
    import uuid
    unique_email = f"payee2_{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post("/auth/register", json={
        "name": "Payee2", "email": unique_email, "password": "pass123"
    })
    payee_id = r.json()["id"]
    group_id = await setup_group_with_expense(client, auth_headers)

    await client.post("/settlements", json={
        "group_id": group_id,
        "paid_to": payee_id,
        "amount": 150.0
    }, headers=auth_headers)

    response = await client.get(f"/settlements/{group_id}", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_settle_up_suggestions(client: AsyncClient, auth_headers):
    group_id = await setup_group_with_expense(client, auth_headers)
    response = await client.get(f"/settle-up/{group_id}", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_settlement_non_member(client: AsyncClient, auth_headers):
    import uuid
    unique_email = f"nonmember_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "NonMember", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={"email": unique_email, "password": "pass123"})
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    group_id = await setup_group_with_expense(client, auth_headers)

    response = await client.get(f"/settlements/{group_id}", headers=headers2)
    assert response.status_code == 403