"""
Database Connection Management
SQLAlchemy session factory for the SUNO system.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://suno:suno@localhost:5432/suno_clips"
)

# Strip Neon's ?sslmode=require query parameter (asyncpg/psycopg handle SSL automatically)
DATABASE_URL = DATABASE_URL.split("?")[0]

# Ensure we use psycopg3 for PostgreSQL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true"
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Session:
    """
    Get a database session.

    Usage in FastAPI:
    @app.get("/example")
    def example(db: Session = Depends(get_db)):
        ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database (create all tables)."""
    from suno.common.models import Base

    Base.metadata.create_all(bind=engine)
