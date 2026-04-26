#!/usr/bin/env python
"""
Phase 6 Endpoint Validation Tests
Tests POST /api/campaigns and PATCH /api/me/workspace
"""

import requests
import json

BASE_URL = "https://suno-api-production.onrender.com"

def test_campaign_creation(test_email: str):
    """Test POST /api/campaigns endpoint."""
    print(f"\n{'='*70}")
    print(f"TEST 1: POST /api/campaigns")
    print(f"{'='*70}")

    payload = {
        "source_url": "https://www.tiktok.com/@creator/video/123456789",
        "source_type": "tiktok",
        "title": "Trending Dance Challenge",
        "keywords": ["dance", "trending", "viral"],
        "target_platforms": ["tiktok", "instagram"],
        "tone": "casual",
        "style": "trending",
        "duration_seconds": 30
    }

    print(f"\nRequest:")
    print(f"  Method: POST")
    print(f"  URL:    {BASE_URL}/api/campaigns")
    print(f"  Header: X-User-Email: {test_email}")
    print(f"  Body:   {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(
            f"{BASE_URL}/api/campaigns",
            json=payload,
            headers={"X-User-Email": test_email},
            timeout=10
        )

        print(f"\nResponse:")
        print(f"  Status: {response.status_code}")
        print(f"  Body:   {json.dumps(response.json(), indent=2)}")

        if response.status_code == 201:
            data = response.json()
            print(f"\nValidation:")
            print(f"  Campaign ID:       {data.get('id')} (OK)")
            print(f"  Source Type:       {data.get('source_type')} (OK)")
            print(f"  Title:             {data.get('title')} (OK)")
            print(f"  Available:         {data.get('available')} (OK)")
            print(f"\nSUCCESS: Campaign created")
            return True
        elif response.status_code == 409:
            print(f"\nINFO: Campaign already exists (duplicate)")
            return True
        else:
            print(f"\nERROR: Unexpected status {response.status_code}")
            return False

    except Exception as e:
        print(f"\nERROR: {e}")
        return False

def test_campaign_duplicate(test_email: str):
    """Test duplicate campaign prevention (409)."""
    print(f"\n{'='*70}")
    print(f"TEST 2: POST /api/campaigns - Duplicate Prevention")
    print(f"{'='*70}")

    payload = {
        "source_url": "https://www.tiktok.com/@creator/video/999999999",
        "source_type": "tiktok",
        "title": "Duplicate Test",
        "keywords": ["test"],
        "target_platforms": ["tiktok"]
    }

    print(f"\nCreating first campaign...")
    r1 = requests.post(
        f"{BASE_URL}/api/campaigns",
        json=payload,
        headers={"X-User-Email": test_email},
        timeout=10
    )
    print(f"  First request: {r1.status_code}")

    print(f"\nCreating duplicate campaign...")
    r2 = requests.post(
        f"{BASE_URL}/api/campaigns",
        json=payload,
        headers={"X-User-Email": test_email},
        timeout=10
    )
    print(f"  Second request: {r2.status_code}")

    if r2.status_code == 409:
        print(f"  Response: {r2.json()}")
        print(f"\nSUCCESS: Duplicate prevention working (409 Conflict)")
        return True
    else:
        print(f"\nERROR: Expected 409, got {r2.status_code}")
        return False

def test_workspace_update(test_email: str):
    """Test PATCH /api/me/workspace endpoint."""
    print(f"\n{'='*70}")
    print(f"TEST 3: PATCH /api/me/workspace")
    print(f"{'='*70}")

    # Get current state
    print(f"\nGetting current workspace state...")
    get_response = requests.get(
        f"{BASE_URL}/api/me/workspace",
        headers={"X-User-Email": test_email},
        timeout=10
    )
    if get_response.status_code != 200:
        print(f"ERROR: Cannot get workspace (status {get_response.status_code})")
        return False

    current = get_response.json()
    current_automation = current.get("automation_enabled")
    print(f"  Current automation_enabled: {current_automation}")

    # Update to opposite value
    new_value = not current_automation
    payload = {"automation_enabled": new_value}

    print(f"\nUpdating workspace...")
    print(f"  Payload: {json.dumps(payload)}")

    try:
        response = requests.patch(
            f"{BASE_URL}/api/me/workspace",
            json=payload,
            headers={"X-User-Email": test_email},
            timeout=10
        )

        print(f"\nResponse:")
        print(f"  Status: {response.status_code}")
        print(f"  Body:   {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            data = response.json()
            if data.get("automation_enabled") == new_value:
                print(f"\nValidation:")
                print(f"  automation_enabled: {data.get('automation_enabled')} (OK)")
                print(f"  workspace_id:       {data.get('workspace_id')} (OK)")
                print(f"  status:             {data.get('status')} (OK)")
                print(f"\nSUCCESS: Workspace updated correctly")
                return True
            else:
                print(f"\nERROR: Value not updated")
                return False
        else:
            print(f"\nERROR: Unexpected status {response.status_code}")
            return False

    except Exception as e:
        print(f"\nERROR: {e}")
        return False

def test_partial_update(test_email: str):
    """Test partial update (only automation_enabled field)."""
    print(f"\n{'='*70}")
    print(f"TEST 4: PATCH /api/me/workspace - Partial Update")
    print(f"{'='*70}")

    # Get workspace_id before update
    get1 = requests.get(
        f"{BASE_URL}/api/me/workspace",
        headers={"X-User-Email": test_email},
        timeout=10
    )
    workspace_id_before = get1.json().get("workspace_id")

    # Update only automation_enabled
    payload = {"automation_enabled": True}
    response = requests.patch(
        f"{BASE_URL}/api/me/workspace",
        json=payload,
        headers={"X-User-Email": test_email},
        timeout=10
    )

    if response.status_code != 200:
        print(f"ERROR: PATCH failed with {response.status_code}")
        return False

    data = response.json()
    workspace_id_after = data.get("workspace_id")

    print(f"Workspace ID (before): {workspace_id_before}")
    print(f"Workspace ID (after):  {workspace_id_after}")
    print(f"Automation enabled:    {data.get('automation_enabled')}")

    if workspace_id_before == workspace_id_after:
        print(f"\nSUCCESS: Workspace ID unchanged (partial update working)")
        return True
    else:
        print(f"\nERROR: Workspace ID changed (should not happen)")
        return False

def main():
    """Run all Phase 6 endpoint tests."""
    print(f"\n{'='*70}")
    print(f"PHASE 6 ENDPOINT VALIDATION TEST SUITE")
    print(f"{'='*70}")

    test_email = input("\nEnter test user email (created by membership.went_valid): ").strip()
    if not test_email:
        print("ERROR: Email required")
        return

    print(f"\nTesting with email: {test_email}")
    print(f"API Base URL: {BASE_URL}\n")

    results = {
        "Campaign Creation": test_campaign_creation(test_email),
        "Duplicate Prevention": test_campaign_duplicate(test_email),
        "Workspace Update": test_workspace_update(test_email),
        "Partial Update": test_partial_update(test_email),
    }

    print(f"\n{'='*70}")
    print(f"TEST RESULTS")
    print(f"{'='*70}")
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name:.<50} {status}")

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"\nSummary: {passed_count}/{total_count} tests passed")

if __name__ == "__main__":
    main()
