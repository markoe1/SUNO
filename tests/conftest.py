"""Pytest fixtures for SUNO Clips tests."""

import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Use SQLite for tests (aiosqlite driver)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_suno.db")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcy0hISE=")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-bytes-longgg")
os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "test-refresh-secret-key-32-bytes-!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("APP_ENV", "test")

# Force valid Fernet key for tests
from cryptography.fernet import Fernet
_TEST_KEY = Fernet.generate_key().decode()
os.environ["ENCRYPTION_KEY"] = _TEST_KEY

from db.engine import Base
from db.models import User, UserSecret, Campaign, Job, Submission
from services.auth import hash_password

TEST_DB_URL = "sqlite+aiosqlite:///./test_suno_clips.db"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    AsyncSession = async_sessionmaker(db_engine, expire_on_commit=False)
    async with AsyncSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    # Override the database dependency
    from db.engine import AsyncSessionLocal
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from api import deps

    AsyncTestSession = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with AsyncTestSession() as session:
            yield session

    from api.app import app
    app.dependency_overrides[deps.get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def dev_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="testuser@sunoclips.io",
        password_hash=hash_password("testpassword123"),
        tier="free",
        is_active=True,
        jobs_paused=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user
    # Cleanup
    await db_session.delete(user)
    await db_session.commit()


@pytest.fixture
def mock_whop_client(monkeypatch):
    """Mock WhopClient to avoid real HTTP calls."""
    from services import whop_client

    class _MockWhopClient:
        def __init__(self, cookies=None):
            self._cookies = cookies or {}

        def validate_session(self):
            return True

        def list_campaigns(self):
            return [
                {
                    "whop_campaign_id": "mock_camp_001",
                    "name": "Mock Campaign",
                    "cpm": 10.0,
                    "budget_remaining": 500.0,
                    "is_free": False,
                    "drive_url": "https://drive.google.com/mock",
                    "youtube_url": "https://youtube.com/mock",
                    "allowed_platforms": "TikTok,Instagram",
                    "active": True,
                }
            ]

        def submit_clip(self, campaign_id, clip_url):
            return {"success": True, "submission_id": "mock_sub_001", "error": None}

        def check_submission(self, submission_id):
            return {"submission_id": submission_id, "status": "submitted", "error": None}

        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(whop_client, "WhopClient", _MockWhopClient)
    return _MockWhopClient
