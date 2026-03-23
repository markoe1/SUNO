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

from sqlalchemy import event, delete as sql_delete, select
from db.engine import Base
from db.models import User, UserSecret, Campaign, Job, Submission  # noqa: F401
import db.models_v2  # noqa: F401 — register operator tables in Base.metadata
from db.models_v2 import Client, Editor, ClientClip, Invoice, PerformanceReport, ClipTemplate
from services.auth import hash_password

TEST_DB_PATH = "./test_suno_clips.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    # Always start with a clean DB to avoid stale-data failures
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    engine = create_async_engine(TEST_DB_URL, echo=False)

    # Enable FK constraints in SQLite so ondelete="CASCADE" works in teardown
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


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
    from slowapi import Limiter

    AsyncTestSession = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with AsyncTestSession() as session:
            yield session

    from api.app import app
    app.dependency_overrides[deps.get_db] = override_get_db

    # Disable rate limiting during tests
    app.state.limiter = Limiter(key_func=lambda: "test_key", enabled=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def dev_user(db_session):
    # Create a unique user for this test run
    unique_email = f"testuser_{uuid.uuid4().hex[:8]}@sunoclips.io"
    user = User(
        id=uuid.uuid4(),
        email=unique_email,
        password_hash=hash_password("testpassword123"),
        tier="free",
        is_active=True,
        jobs_paused=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user
    # Cleanup — delete in order to respect FK constraints
    # Get all client IDs for this user
    clients = await db_session.execute(select(Client.id).where(Client.user_id == user.id))
    client_ids = [row[0] for row in clients.all()]

    # Delete child records in dependency order
    for client_id in client_ids:
        await db_session.execute(sql_delete(ClientClip).where(ClientClip.client_id == client_id))
        await db_session.execute(sql_delete(Invoice).where(Invoice.client_id == client_id))
        await db_session.execute(sql_delete(PerformanceReport).where(PerformanceReport.client_id == client_id))

    # Delete user's records
    await db_session.execute(sql_delete(Job).where(Job.user_id == user.id))
    await db_session.execute(sql_delete(Submission).where(Submission.user_id == user.id))
    await db_session.execute(sql_delete(UserSecret).where(UserSecret.user_id == user.id))
    await db_session.execute(sql_delete(Client).where(Client.user_id == user.id))
    await db_session.execute(sql_delete(Editor).where(Editor.user_id == user.id))
    await db_session.execute(sql_delete(ClipTemplate).where(ClipTemplate.user_id == user.id))
    await db_session.execute(sql_delete(User).where(User.id == user.id))
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
