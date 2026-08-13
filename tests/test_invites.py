import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def create_group_and_get_id(client, headers):
    r = await client.post("/groups", json={"name": "Invite Group"}, headers=headers)
    return r.json()["id"]


async def test_generate_invite_link(client: AsyncClient, auth_headers):
    group_id = await create_group_and_get_id(client, auth_headers)
    response = await client.post(f"/invites/{group_id}", headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert "short_code" in data
    assert "invite_url" in data
    assert data["is_active"] == True


async def test_list_invite_links(client: AsyncClient, auth_headers):
    group_id = await create_group_and_get_id(client, auth_headers)
    await client.post(f"/invites/{group_id}", headers=auth_headers)
    response = await client.get(f"/invites/{group_id}", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_join_via_invite(client: AsyncClient, auth_headers):
    import uuid
    group_id = await create_group_and_get_id(client, auth_headers)
    invite = await client.post(f"/invites/{group_id}", headers=auth_headers)
    short_code = invite.json()["short_code"]

    unique_email = f"joiner_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "Joiner", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={
        "email": unique_email, "password": "pass123"
    })
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post(f"/join/{short_code}", headers=headers2)
    assert response.status_code == 200
    assert response.json()["group_id"] == group_id


async def test_join_already_member(client: AsyncClient, auth_headers):
    group_id = await create_group_and_get_id(client, auth_headers)
    invite = await client.post(f"/invites/{group_id}", headers=auth_headers)
    short_code = invite.json()["short_code"]

    response = await client.post(f"/join/{short_code}", headers=auth_headers)
    assert response.status_code == 400
    assert "already a member" in response.json()["detail"]


async def test_deactivate_invite(client: AsyncClient, auth_headers):
    group_id = await create_group_and_get_id(client, auth_headers)
    invite = await client.post(f"/invites/{group_id}", headers=auth_headers)
    invite_id = invite.json()["id"]

    response = await client.delete(f"/invites/{invite_id}", headers=auth_headers)
    assert response.status_code == 204


async def test_join_inactive_invite(client: AsyncClient, auth_headers):
    import uuid
    group_id = await create_group_and_get_id(client, auth_headers)
    invite = await client.post(f"/invites/{group_id}", headers=auth_headers)
    invite_id = invite.json()["id"]
    short_code = invite.json()["short_code"]

    await client.delete(f"/invites/{invite_id}", headers=auth_headers)

    unique_email = f"joiner2_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "Joiner2", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={
        "email": unique_email, "password": "pass123"
    })
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post(f"/join/{short_code}", headers=headers2)
    assert response.status_code == 404


async def test_non_admin_cannot_generate_invite(client: AsyncClient, auth_headers):
    import uuid
    group_id = await create_group_and_get_id(client, auth_headers)

    unique_email = f"member_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={
        "name": "Member", "email": unique_email, "password": "pass123"
    })
    login = await client.post("/auth/login", json={
        "email": unique_email, "password": "pass123"
    })
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post(f"/invites/{group_id}", headers=headers2)
    assert response.status_code == 403