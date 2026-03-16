import pytest


@pytest.mark.asyncio
async def test_signup_success(client):
    res = await client.post("/api/auth/signup", json={
        "email": "new@example.com",
        "password": "password123",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]


@pytest.mark.asyncio
async def test_signup_duplicate_email(client):
    await client.post("/api/auth/signup", json={
        "email": "dup@example.com",
        "password": "password123",
    })
    res = await client.post("/api/auth/signup", json={
        "email": "dup@example.com",
        "password": "password456",
    })
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/auth/signup", json={
        "email": "login@example.com",
        "password": "password123",
    })
    res = await client.post("/api/auth/login", json={
        "email": "login@example.com",
        "password": "password123",
    })
    assert res.status_code == 200
    assert res.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/signup", json={
        "email": "wrong@example.com",
        "password": "password123",
    })
    res = await client.post("/api/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpass",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(auth_client):
    res = await auth_client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["data"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client):
    signup_res = await client.post("/api/auth/signup", json={
        "email": "refresh@example.com",
        "password": "password123",
    })
    refresh_token = signup_res.json()["data"]["refresh_token"]
    res = await client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert res.status_code == 200
    assert res.json()["data"]["access_token"]
