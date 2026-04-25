#!/usr/bin/env python3
"""
Setup Whop Campaigns for SUNO
==============================
Discovers and configures active campaigns from your Whop account.
Run this once to initialize your campaigns.
"""

import os
import sys
from pathlib import Path

# LOAD .env BEFORE IMPORTS
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

import asyncio
import logging

sys.path.insert(0, str(Path(__file__).parent))

from services.whop_client import WhopClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_campaigns():
    """Discover and configure campaigns."""

    whop_api_key = os.getenv("WHOP_API_KEY")
    whop_company_id = os.getenv("WHOP_COMPANY_ID")

    if not whop_api_key or not whop_company_id:
        logger.error("❌ Missing WHOP_API_KEY or WHOP_COMPANY_ID in .env")
        return False

    logger.info("🔍 Discovering campaigns from Whop...")

    try:
        client = WhopClient()
        campaigns = client.list_campaigns()

        if not campaigns:
            logger.warning("⚠️  No campaigns found on your Whop account")
            logger.info("📋 Go to https://dashboard.whop.com to create campaigns")
            return False

        logger.info(f"\n✅ Found {len(campaigns)} campaigns:\n")

        for i, campaign in enumerate(campaigns, 1):
            logger.info(f"{i}. {campaign['name']}")
            logger.info(f"   CPM: ${campaign.get('cpm', 0):.2f} / 1K views")
            logger.info(f"   Budget: ${campaign.get('budget_remaining', 0):.2f} remaining")

            if campaign.get('drive_url'):
                logger.info(f"   Drive: {campaign['drive_url'][:60]}...")
            logger.info("")

        logger.info("=" * 60)
        logger.info("✅ Campaigns configured and ready!")
        logger.info("SUNO will now auto-download and post clips to these campaigns.")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"❌ Failed to fetch campaigns: {e}")
        logger.error("Make sure WHOP_API_KEY and WHOP_COMPANY_ID are correct in .env")
        return False


if __name__ == "__main__":
    success = asyncio.run(setup_campaigns())
    sys.exit(0 if success else 1)
