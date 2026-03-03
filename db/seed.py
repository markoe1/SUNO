"""Dev seed — creates tables, dev user, and sample campaigns."""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Ensure project root is on path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from db.engine import Base, DATABASE_URL
from db.models import User, Campaign
from services.auth import hash_password


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncSession() as session:
        # Dev user
        result = await session.execute(select(User).where(User.email == "dev@sunoclips.io"))
        existing = result.scalar_one_or_none()
        if not existing:
            user = User(
                id=uuid.uuid4(),
                email="dev@sunoclips.io",
                password_hash=hash_password("devpassword123"),
                tier="pro",
                is_active=True,
                jobs_paused=False,
            )
            session.add(user)
            print("Created dev user: dev@sunoclips.io / devpassword123")
        else:
            print("Dev user already exists, skipping.")

        # Sample campaigns
        campaigns_data = [
            {
                "whop_campaign_id": "camp_001_viral_beats",
                "name": "Viral Beats Summer 2026",
                "cpm": 12.50,
                "budget_remaining": 5000.00,
                "is_free": False,
                "drive_url": "https://drive.google.com/drive/folders/sample001",
                "youtube_url": "https://www.youtube.com/watch?v=sample001",
                "allowed_platforms": "TikTok,Instagram,YouTube",
                "active": True,
            },
            {
                "whop_campaign_id": "camp_002_hiphop_free",
                "name": "Hip Hop Showcase (Free)",
                "cpm": 0.00,
                "budget_remaining": None,
                "is_free": True,
                "drive_url": "https://drive.google.com/drive/folders/sample002",
                "youtube_url": "https://www.youtube.com/watch?v=sample002",
                "allowed_platforms": "TikTok,YouTube",
                "active": True,
            },
        ]

        for c in campaigns_data:
            result = await session.execute(
                select(Campaign).where(Campaign.whop_campaign_id == c["whop_campaign_id"])
            )
            if not result.scalar_one_or_none():
                session.add(Campaign(id=uuid.uuid4(), **c))
                print(f"Created campaign: {c['name']}")
            else:
                print(f"Campaign already exists: {c['name']}")

        await session.commit()

    await engine.dispose()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
