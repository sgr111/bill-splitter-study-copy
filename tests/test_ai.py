import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def setup_group_with_expense(client, headers):
    r = await client.post("/groups", json={"name": "AI Test Group"}, headers=headers)
    group_id = r.json()["id"]
    await client.post("/expenses", json={
        "group_id": group_id,
        "description": "Dinner at Restaurant",
        "total_amount": 600.0,
        "split_type": "equal"
    }, headers=headers)
    return group_id


async def test_categorize_food(client: AsyncClient, auth_headers):
    response = await client.post("/ai/categorize", json={
        "description": "Dinner at Barbeque Nation"
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "category" in data
    assert data["category"] in ["Food", "Transport", "Accommodation", "Entertainment", "Shopping", "Other"]


async def test_categorize_transport(client: AsyncClient, auth_headers):
    response = await client.post("/ai/categorize", json={
        "description": "Cab to airport"
    }, headers=auth_headers)
    assert response.status_code == 200
    assert "category" in response.json()


async def test_categorize_returns_valid_category(client: AsyncClient, auth_headers):
    response = await client.post("/ai/categorize", json={
        "description": "Hotel booking for 2 nights"
    }, headers=auth_headers)
    assert response.status_code == 200
    valid = ["Food", "Transport", "Accommodation", "Entertainment", "Shopping", "Other"]
    assert response.json()["category"] in valid


async def test_ask_question(client: AsyncClient, auth_headers):
    group_id = await setup_group_with_expense(client, auth_headers)
    response = await client.post("/ai/ask", json={
        "group_id": group_id,
        "question": "How much total has been spent?"
    }, headers=auth_headers)
    assert response.status_code == 200
    assert "answer" in response.json()
    assert len(response.json()["answer"]) > 0


async def test_ask_no_expenses(client: AsyncClient, auth_headers):
    r = await client.post("/groups", json={"name": "Empty Group"}, headers=auth_headers)
    group_id = r.json()["id"]
    response = await client.post("/ai/ask", json={
        "group_id": group_id,
        "question": "Who owes the most?"
    }, headers=auth_headers)
    assert response.status_code == 200
    assert "answer" in response.json()


async def test_ask_non_member(client: AsyncClient, auth_headers):
    import uuid
    group_id = await setup_group_with_expense(client, auth_headers)
    unique_email = f"nonmember_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "NonMember", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={
        "email": unique_email, "password": "pass123"
    })
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post("/ai/ask", json={
        "group_id": group_id,
        "question": "How much spent?"
    }, headers=headers2)
    assert response.status_code == 403


async def test_agent_run(client: AsyncClient, auth_headers):
    group_id = await setup_group_with_expense(client, auth_headers)
    response = await client.post(f"/ai/agent/{group_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "reminders" in data
    assert "final_report" in data


async def test_agent_non_member(client: AsyncClient, auth_headers):
    import uuid
    group_id = await setup_group_with_expense(client, auth_headers)
    unique_email = f"nonmember2_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "NonMember2", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={
        "email": unique_email, "password": "pass123"
    })
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(f"/ai/agent/{group_id}", headers=headers2)
    assert response.status_code == 403