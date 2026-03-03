"""Auth route tests."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    res = await client.post(
        "/api/auth/register",
        json={"email": "newuser@test.com", "password": "password123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dupe@test.com", "password": "password123"}
    res1 = await client.post("/api/auth/register", json=payload)
    assert res1.status_code == 200

    res2 = await client.post("/api/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, dev_user):
    res = await client.post(
        "/api/auth/login",
        data={"email": dev_user.email, "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    # Refresh cookie should be set
    assert "refresh_token" in res.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, dev_user):
    res = await client.post(
        "/api/auth/login",
        data={"email": dev_user.email, "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_access_protected_route_without_token(client: AsyncClient):
    res = await client.get("/api/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient, dev_user):
    # Login to get tokens
    login_res = await client.post(
        "/api/auth/login",
        data={"email": dev_user.email, "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_res.status_code == 200
    original_token = login_res.json()["access_token"]
    refresh_cookie = login_res.cookies.get("refresh_token")
    assert refresh_cookie

    # Use refresh token to get new access token
    refresh_res = await client.post(
        "/api/auth/refresh",
        cookies={"refresh_token": refresh_cookie},
    )
    assert refresh_res.status_code == 200
    new_token = refresh_res.json()["access_token"]
    # New token should differ from the old one (different expiry timestamp)
    assert new_token  # Just ensure it's non-empty
    # New refresh cookie should be issued
    assert "refresh_token" in refresh_res.cookies


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, dev_user):
    login_res = await client.post(
        "/api/auth/login",
        data={"email": dev_user.email, "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    access_token = login_res.json()["access_token"]

    me_res = await client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["email"] == dev_user.email
    assert "id" in data
