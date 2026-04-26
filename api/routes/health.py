"""Health and readiness endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    try:
        from workers.queue import redis_conn
        redis_conn.ping()
    except Exception as exc:
        redis_status = f"error: {exc}"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {"status": overall, "db": db_status, "redis": redis_status}


@router.get("/ready")
async def ready():
    try:
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from sqlalchemy import create_engine
        import os

        sync_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://suno:suno@localhost:5432/suno_clips",
        ).replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        # Strip Neon's ?sslmode parameter
        sync_url = sync_url.split("?")[0]

        engine = create_engine(sync_url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current = context.get_current_revision()

        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "alembic.ini")
        script = ScriptDirectory.from_config(
            __import__("alembic.config", fromlist=["Config"]).Config(config_path)
        )
        head = script.get_current_head()
        engine.dispose()

        return {"ready": current == head, "current": current, "head": head}
    except Exception as exc:
        return {"ready": False, "error": str(exc)}
