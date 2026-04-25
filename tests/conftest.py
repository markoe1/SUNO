"""Pytest configuration and fixtures for SUNO tests."""

import os
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Set test encryption key before imports that need it
os.environ.setdefault("ENCRYPTION_KEY", "ePKjTQPyV2Db1B7MPwKFhAGCYHCUehl229RZd9gYLNk=")

# Use synchronous SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    from suno.common.models import Base
    Base.metadata.create_all(bind=engine)

    return engine


@pytest.fixture(scope="function")
def test_db_session(test_engine, monkeypatch):
    """Provide a test database session and patch SessionLocal."""
    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )

    session = TestSessionLocal()

    # Monkeypatch suno.database.SessionLocal to use test session
    import suno.database
    monkeypatch.setattr(suno.database, "SessionLocal", lambda: session)

    yield session

    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def db_session(test_db_session):
    """Alias for test_db_session for backward compatibility."""
    return test_db_session


@pytest.fixture(scope="function")
def client(db_session):
    """Provide an AsyncClient for FastAPI testing."""
    from httpx import AsyncClient, ASGITransport
    from api.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")
