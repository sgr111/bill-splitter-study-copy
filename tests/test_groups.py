import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_group(client: AsyncClient, auth_headers):
    response = await client.post("/groups", json={"name": "Goa Trip"}, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Goa Trip"
    assert data["is_active"] == True


async def test_list_groups(client: AsyncClient, auth_headers):
    await client.post("/groups", json={"name": "Trip 1"}, headers=auth_headers)
    response = await client.get("/groups", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_get_group(client: AsyncClient, auth_headers):
    create = await client.post("/groups", json={"name": "My Group"}, headers=auth_headers)
    group_id = create.json()["id"]
    response = await client.get(f"/groups/{group_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == group_id


async def test_update_group(client: AsyncClient, auth_headers):
    create = await client.post("/groups", json={"name": "Old Name"}, headers=auth_headers)
    group_id = create.json()["id"]
    response = await client.put(f"/groups/{group_id}", json={"name": "New Name"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_delete_group(client: AsyncClient, auth_headers):
    create = await client.post("/groups", json={"name": "To Delete"}, headers=auth_headers)
    group_id = create.json()["id"]
    response = await client.delete(f"/groups/{group_id}", headers=auth_headers)
    assert response.status_code == 204


async def test_leave_group(client: AsyncClient, auth_headers, registered_user):
    import uuid
    unique_email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "User2", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={"email": unique_email, "password": "pass123"})
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    create = await client.post("/groups", json={"name": "Leave Group"}, headers=auth_headers)
    group_id = create.json()["id"]

    response = await client.post(f"/groups/{group_id}/leave", headers=auth_headers)
    assert response.status_code == 200


async def test_get_group_not_member(client: AsyncClient, auth_headers, registered_user):
    import uuid
    unique_email = f"other_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "Other", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={"email": unique_email, "password": "pass123"})
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    create = await client.post("/groups", json={"name": "Private Group"}, headers=auth_headers)
    group_id = create.json()["id"]

    response = await client.get(f"/groups/{group_id}", headers=headers2)
    assert response.status_code == 403