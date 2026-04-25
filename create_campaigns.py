#!/usr/bin/env python3
"""
Create SUNO Campaigns on Whop
============================
Creates 3 test campaigns (TikTok, Instagram, YouTube) via Whop API.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env FIRST
load_dotenv(Path(__file__).parent / ".env", override=True)

import httpx
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

API_KEY = os.getenv("WHOP_API_KEY")
COMPANY_ID = os.getenv("WHOP_COMPANY_ID")
BASE_URL = "https://api.whop.com/api/v1"

if not API_KEY or not COMPANY_ID:
    logger.error("❌ WHOP_API_KEY or WHOP_COMPANY_ID not set in .env")
    sys.exit(1)

# Campaign definitions
CAMPAIGNS = [
    {
        "name": "TikTok Test",
        "budget": 200,
        "cpm": 6.00,
        "description": "SUNO clips for TikTok testing"
    },
    {
        "name": "Instagram Reels Test",
        "budget": 150,
        "cpm": 6.00,
        "description": "SUNO clips for Instagram Reels testing"
    },
    {
        "name": "YouTube Shorts Test",
        "budget": 150,
        "cpm": 6.00,
        "description": "SUNO clips for YouTube Shorts testing"
    }
]

def create_campaign(name: str, budget: float, cpm: float, description: str):
    """Create a single campaign via Whop API."""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "company_id": COMPANY_ID,
        "name": name,
        "budget": budget,
        "cpm": cpm,
        "description": description,
        "status": "active"
    }

    try:
        response = httpx.post(
            f"{BASE_URL}/ad_campaigns",
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code in (200, 201):
            data = response.json()
            campaign_id = data.get("id") or data.get("data", {}).get("id")
            logger.info(f"✅ Created: {name}")
            logger.info(f"   ID: {campaign_id}")
            logger.info(f"   Budget: ${budget} | CPM: ${cpm}")
            return campaign_id
        else:
            logger.error(f"❌ Failed to create {name}")
            logger.error(f"   Status: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return None

    except Exception as e:
        logger.error(f"❌ Error creating {name}: {e}")
        return None

def main():
    logger.info("=" * 60)
    logger.info("Creating SUNO Campaigns on Whop")
    logger.info("=" * 60)
    logger.info("")

    created = []
    for campaign in CAMPAIGNS:
        campaign_id = create_campaign(
            campaign["name"],
            campaign["budget"],
            campaign["cpm"],
            campaign["description"]
        )
        if campaign_id:
            created.append({
                "name": campaign["name"],
                "id": campaign_id,
                "budget": campaign["budget"]
            })
        logger.info("")

    logger.info("=" * 60)
    if created:
        logger.info(f"✅ Successfully created {len(created)}/{len(CAMPAIGNS)} campaigns")
        logger.info("")
        logger.info("Campaign Summary:")
        for c in created:
            logger.info(f"  • {c['name']} (ID: {c['id']}) - ${c['budget']} budget")
        logger.info("")
        logger.info("SUNO will now auto-discover and post clips to these campaigns.")
    else:
        logger.error("❌ No campaigns created. Check API key and permissions.")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
