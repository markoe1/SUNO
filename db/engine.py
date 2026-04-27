from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://suno:suno@localhost:5432/suno_clips")

# Strip Neon's ?sslmode=require query parameter (asyncpg handles SSL automatically)
DATABASE_URL = DATABASE_URL.split("?")[0]

# Ensure we're using the async driver (asyncpg) not sync (psycopg2)
if DATABASE_URL and not "postgresql+asyncpg://" in DATABASE_URL:
    # Convert postgresql:// or postgres:// to postgresql+asyncpg://
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
