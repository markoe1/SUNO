"""Client management route tests."""

import uuid
import pytest
from httpx import AsyncClient

from db.models_v2 import Client, ClientStatus, Editor, ClientClip, ClipStatus
from sqlalchemy import delete as sql_delete


async def _get_token(client: AsyncClient, user) -> str:
    res = await client.post(
        "/api/auth/login",
        data={"email": user.email, "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


# ---------------------------------------------------------------------------
# Client CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_client(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    res = await client.post(
        "/api/clients",
        json={
            "name": "Test Creator",
            "email": "creator@test.com",
            "niche": "fitness",
            "monthly_rate": 1500.0,
            "view_guarantee": 1000000,
            "clips_per_month": 60,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Test Creator"
    assert data["status"] == "LEAD"
    assert data["monthly_rate"] == 1500.0


@pytest.mark.asyncio
async def test_list_clients_empty(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    res = await client.get("/api/clients", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert isinstance(data["clients"], list)
    assert data["active_count"] == 0


@pytest.mark.asyncio
async def test_get_client(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)

    # Create first
    create_res = await client.post(
        "/api/clients",
        json={"name": "Get Test Client", "monthly_rate": 2000.0, "view_guarantee": 500000, "clips_per_month": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 201
    client_id = create_res.json()["id"]

    # Fetch
    get_res = await client.get(f"/api/clients/{client_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    assert get_res.json()["id"] == client_id


@pytest.mark.asyncio
async def test_update_client(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)

    create_res = await client.post(
        "/api/clients",
        json={"name": "Update Me", "monthly_rate": 1000.0, "view_guarantee": 500000, "clips_per_month": 20},
        headers={"Authorization": f"Bearer {token}"},
    )
    client_id = create_res.json()["id"]

    patch_res = await client.patch(
        f"/api/clients/{client_id}",
        json={"monthly_rate": 2500.0, "niche": "finance"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["monthly_rate"] == 2500.0
    assert patch_res.json()["niche"] == "finance"


@pytest.mark.asyncio
async def test_activate_client(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)

    create_res = await client.post(
        "/api/clients",
        json={"name": "Activate Me", "monthly_rate": 1500.0, "view_guarantee": 1000000, "clips_per_month": 60},
        headers={"Authorization": f"Bearer {token}"},
    )
    client_id = create_res.json()["id"]

    activate_res = await client.post(
        f"/api/clients/{client_id}/activate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert activate_res.status_code == 200
    assert activate_res.json()["status"] == "ACTIVE"
    assert activate_res.json()["onboarded_at"] is not None


@pytest.mark.asyncio
async def test_delete_client(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)

    create_res = await client.post(
        "/api/clients",
        json={"name": "Delete Me", "monthly_rate": 1000.0, "view_guarantee": 100000, "clips_per_month": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    client_id = create_res.json()["id"]

    delete_res = await client.delete(
        f"/api/clients/{client_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_res.status_code == 204

    # Should be soft-deleted (status = CHURNED)
    get_res = await client.get(f"/api/clients/{client_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "CHURNED"


@pytest.mark.asyncio
async def test_get_nonexistent_client(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/api/clients/{fake_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_clients_require_auth(client: AsyncClient):
    res = await client.get("/api/clients")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Editor CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_editor(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    res = await client.post(
        "/api/editors",
        json={"name": "Test Editor", "email": "editor@test.com", "rate_per_clip": 12.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Test Editor"
    assert data["rate_per_clip"] == 12.0
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_editors(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    res = await client.get("/api/editors", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ---------------------------------------------------------------------------
# Clip pipeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_advance_clip(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    headers = {"Authorization": f"Bearer {token}"}

    # Create client first
    c_res = await client.post(
        "/api/clients",
        json={"name": "Clip Pipeline Client", "monthly_rate": 1500.0, "view_guarantee": 500000, "clips_per_month": 30},
        headers=headers,
    )
    assert c_res.status_code == 201
    client_id = c_res.json()["id"]

    # Create clip
    clip_res = await client.post(
        "/api/client-clips",
        json={"client_id": client_id, "title": "Test Hook Clip"},
        headers=headers,
    )
    assert clip_res.status_code == 201
    clip_data = clip_res.json()
    assert clip_data["status"] == "RAW"
    clip_id = clip_data["id"]

    # Advance to EDITING
    status_res = await client.patch(
        f"/api/client-clips/{clip_id}/status",
        json={"status": "EDITING"},
        headers=headers,
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "EDITING"
