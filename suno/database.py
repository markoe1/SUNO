"""
Database Connection Management (Sync)
For background workers, webhooks, and tests only.
FastAPI routes MUST use db/engine.py (async).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from db.engine import Base

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://suno:suno@localhost:5432/suno_clips"
)

# Strip Neon's ?sslmode=require query parameter
DATABASE_URL = DATABASE_URL.split("?")[0]

# Ensure we use psycopg2 for sync connections
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")

# Create sync engine
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
    """Get a database session (sync). For workers and webhooks only."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
