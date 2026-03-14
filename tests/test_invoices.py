"""Invoice route tests."""

import pytest
from httpx import AsyncClient


async def _get_token(client: AsyncClient, user) -> str:
    res = await client.post(
        "/api/auth/login",
        data={"email": user.email, "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


async def _create_client(client: AsyncClient, token: str, name: str = "Invoice Test Client") -> str:
    """Helper: create a client and return its id."""
    res = await client.post(
        "/api/clients",
        json={
            "name": name,
            "monthly_rate": 1500.0,
            "view_guarantee": 1000000,
            "clips_per_month": 60,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.asyncio
async def test_generate_invoice(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    client_id = await _create_client(client, token)

    res = await client.post(
        "/api/invoices/generate",
        json={
            "client_id": client_id,
            "month": "2026-03",
            "base_amount": 1500.0,
            "performance_bonus": 0.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["month"] == "2026-03"
    assert data["amount"] == 1500.0
    assert data["is_paid"] is False
    assert data["clips_delivered"] == 0  # no posted clips yet


@pytest.mark.asyncio
async def test_duplicate_invoice_rejected(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    client_id = await _create_client(client, token, name="Dupe Invoice Client")

    payload = {
        "client_id": client_id,
        "month": "2026-02",
        "base_amount": 1000.0,
        "performance_bonus": 0.0,
    }

    res1 = await client.post("/api/invoices/generate", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201

    res2 = await client.post("/api/invoices/generate", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_list_invoices(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    res = await client.get("/api/invoices/", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_mark_invoice_paid(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    client_id = await _create_client(client, token, name="Mark Paid Client")

    # Generate
    gen_res = await client.post(
        "/api/invoices/generate",
        json={"client_id": client_id, "month": "2026-01", "base_amount": 2000.0, "performance_bonus": 500.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen_res.status_code == 201
    invoice_id = gen_res.json()["id"]

    # Mark paid with a Whop transaction ID
    paid_res = await client.post(
        f"/api/invoices/{invoice_id}/mark-paid",
        json={"whop_transaction_id": "mem_abc123xyz"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert paid_res.status_code == 200
    data = paid_res.json()
    assert data["is_paid"] is True
    assert data["paid_at"] is not None
    assert data["whop_transaction_id"] == "mem_abc123xyz"


@pytest.mark.asyncio
async def test_mark_already_paid_invoice_fails(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    client_id = await _create_client(client, token, name="Double Paid Client")

    gen_res = await client.post(
        "/api/invoices/generate",
        json={"client_id": client_id, "month": "2025-12", "base_amount": 1500.0, "performance_bonus": 0.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    invoice_id = gen_res.json()["id"]

    await client.post(
        f"/api/invoices/{invoice_id}/mark-paid",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Try again — should 400
    res2 = await client.post(
        f"/api/invoices/{invoice_id}/mark-paid",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 400


@pytest.mark.asyncio
async def test_invoice_summary(client: AsyncClient, dev_user):
    token = await _get_token(client, dev_user)
    res = await client.get("/api/invoices/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "total_billed" in data
    assert "total_collected" in data
    assert "outstanding" in data
    assert "unpaid_count" in data


@pytest.mark.asyncio
async def test_invoices_require_auth(client: AsyncClient):
    res = await client.get("/api/invoices/")
    assert res.status_code == 401
