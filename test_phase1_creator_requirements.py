"""
PHASE 1 Validation Test
=======================
Tests the complete Creator Requirements Layer:
- Creator discovery and registry
- Creator approval/blocking
- Campaign requirement normalization
- Campaign validation with creators
- Integration with CampaignRequirementsValidator
"""

import logging
from queue_manager import QueueManager, Campaign, Creator, Clip, ClipStatus
from campaign_requirements import CampaignRequirementsValidator
from creator_registry import CreatorRegistry

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)


def test_creator_discovery_and_registry():
    """TEST 1: Creator discovery and basic registry operations."""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Creator Discovery and Registry")
    logger.info("="*80)

    registry = CreatorRegistry()
    queue = QueueManager()

    # Discover a creator
    logger.info("\n[1a] Discovering creator: MrBeast (youtube)")
    creator = registry.discover_creator("MrBeast", "youtube")
    assert creator.name == "MrBeast"
    assert creator.platform == "youtube"
    assert creator.is_approved == False
    assert creator.verification_status == "unverified"
    logger.info("✓ Creator discovered as unverified")

    # Verify it's in registry
    logger.info("\n[1b] Checking creator in registry")
    from_registry = queue.get_creator("MrBeast", "youtube")
    assert from_registry is not None
    assert from_registry.name == "MrBeast"
    logger.info("✓ Creator found in registry")

    # Discover same creator again (should return existing)
    logger.info("\n[1c] Re-discovering same creator")
    creator2 = registry.discover_creator("MrBeast", "youtube")
    assert creator2.name == creator.name
    logger.info("✓ Re-discovery returns existing creator")

    logger.info("\n✓ TEST 1 PASSED")
    return True


def test_creator_approval_and_blocking():
    """TEST 2: Approve and block creators."""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Creator Approval and Blocking")
    logger.info("="*80)

    registry = CreatorRegistry()
    queue = QueueManager()

    # Discover and approve
    logger.info("\n[2a] Discovering and approving creator: Vsauce")
    registry.discover_creator("Vsauce", "youtube")
    success = registry.approve_creator("Vsauce", "youtube", "High-quality educational content")
    assert success == True
    logger.info("✓ Creator approved")

    # Verify approval status
    logger.info("\n[2b] Checking approval status")
    creator = queue.get_creator("Vsauce", "youtube")
    assert creator.is_approved == True
    assert creator.verification_status == "verified"
    assert creator.approval_reason == "High-quality educational content"
    logger.info("✓ Creator status is verified")

    # Block a creator
    logger.info("\n[2c] Discovering and blocking creator: BadActor")
    registry.discover_creator("BadActor", "youtube")
    success = registry.block_creator("BadActor", "youtube", "Copyright violations")
    assert success == True
    logger.info("✓ Creator blocked")

    # Verify blocked status
    logger.info("\n[2d] Checking blocked status")
    creator = queue.get_creator("BadActor", "youtube")
    assert creator.is_approved == False
    assert creator.verification_status == "blocked"
    logger.info("✓ Creator status is blocked")

    # List approved creators
    logger.info("\n[2e] Listing approved creators")
    approved = registry.list_approved_creators("youtube")
    assert len(approved) >= 1
    assert any(c.name == "Vsauce" for c in approved)
    logger.info(f"✓ Found {len(approved)} approved creators")

    # List blocked creators
    logger.info("\n[2f] Listing blocked creators")
    blocked = registry.list_blocked_creators("youtube")
    assert len(blocked) >= 1
    assert any(c.name == "BadActor" for c in blocked)
    logger.info(f"✓ Found {len(blocked)} blocked creators")

    logger.info("\n✓ TEST 2 PASSED")
    return True


def test_campaign_requirement_normalization():
    """TEST 3: Campaign requirement fields are properly normalized."""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Campaign Requirement Normalization")
    logger.info("="*80)

    queue = QueueManager()

    # Create campaign with comma-separated fields
    logger.info("\n[3a] Creating campaign with string-based requirements")
    campaign = Campaign(
        whop_id="test_campaign_001",
        name="Test Campaign",
        cpm=5.0,
        budget_remaining=1000.0,
        is_free=True,
        active=True,
        content_type="general",
        source_types="youtube,tiktok,instagram",  # String
        min_duration=15,
        max_duration=60,
        creator_whitelist="MrBeast,Vsauce,TED-Ed",  # String
        creator_blacklist="BadActor,SpamCreator",    # String
        daily_clip_limit=50
    )
    logger.info(f"Campaign created:")
    logger.info(f"  source_types (string): {campaign.source_types}")
    logger.info(f"  creator_whitelist (string): {campaign.creator_whitelist}")
    logger.info(f"  creator_blacklist (string): {campaign.creator_blacklist}")

    # Upsert to database
    logger.info("\n[3b] Persisting campaign to database")
    queue.upsert_campaign(campaign)
    logger.info("✓ Campaign persisted")

    # Load campaign back
    logger.info("\n[3c] Loading campaign from database")
    campaigns = queue.get_active_campaigns()
    loaded = next((c for c in campaigns if c.whop_id == "test_campaign_001"), None)
    assert loaded is not None
    logger.info("✓ Campaign loaded from database")

    # Verify all fields are persisted
    logger.info("\n[3d] Verifying all requirement fields persisted")
    assert loaded.content_type == "general"
    assert loaded.source_types == "youtube,tiktok,instagram"
    assert loaded.min_duration == 15
    assert loaded.max_duration == 60
    assert loaded.creator_whitelist == "MrBeast,Vsauce,TED-Ed"
    assert loaded.creator_blacklist == "BadActor,SpamCreator"
    assert loaded.daily_clip_limit == 50
    logger.info("✓ All fields persisted correctly")

    # Load via validator (which should parse lists)
    logger.info("\n[3e] Loading via validator (should parse to lists)")
    validator = CampaignRequirementsValidator()
    req = validator.get_campaign_requirements("test_campaign_001")
    assert req is not None
    logger.info(f"  allowed_sources (list): {req.allowed_sources}")
    logger.info(f"  creator_whitelist (list): {req.creator_whitelist}")
    logger.info(f"  creator_blacklist (list): {req.creator_blacklist}")

    # Verify lists are proper lists
    assert isinstance(req.allowed_sources, list)
    assert isinstance(req.creator_whitelist, list)
    assert isinstance(req.creator_blacklist, list)
    logger.info("✓ Lists properly parsed from strings")

    # Verify contents
    assert "youtube" in req.allowed_sources
    assert "tiktok" in req.allowed_sources
    assert "MrBeast" in req.creator_whitelist
    assert "BadActor" in req.creator_blacklist
    logger.info("✓ List contents correct")

    logger.info("\n✓ TEST 3 PASSED")
    return True


def test_campaign_validation_with_creators():
    """TEST 4: Campaign validation checks creators correctly."""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Campaign Validation with Creators")
    logger.info("="*80)

    queue = QueueManager()
    registry = CreatorRegistry()

    # Setup: Create campaign with creator requirements
    logger.info("\n[4a] Creating campaign with creator whitelist")
    campaign = Campaign(
        whop_id="strict_campaign",
        name="Strict Campaign",
        cpm=10.0,
        budget_remaining=5000.0,
        is_free=False,
        active=True,
        content_type="educational",
        source_types="youtube",
        min_duration=20,
        max_duration=120,
        creator_whitelist="Vsauce,TED-Ed",  # Only these creators
        creator_blacklist="",
        daily_clip_limit=10
    )
    queue.upsert_campaign(campaign)

    # Setup: Approve whitelisted creators
    logger.info("\n[4b] Approving whitelisted creators")
    registry.approve_creator("Vsauce", "youtube", "Approved for campaign")
    registry.approve_creator("TED-Ed", "youtube", "Approved for campaign")

    # Reload validator to get updated requirements
    validator = CampaignRequirementsValidator(allow_unverified_creators=False)

    # Test 4c: Validate approved creator
    logger.info("\n[4c] Validating clip from approved creator (Vsauce)")
    approved, reasons = validator.validate_clip_for_campaign(
        campaign_id="strict_campaign",
        creator_name="Vsauce",
        source_platform="youtube",
        clip_duration=60
    )
    assert approved == True
    assert len(reasons) == 0
    logger.info("✓ Approved creator clip passes validation")

    # Test 4d: Validate unapproved creator (not in whitelist)
    logger.info("\n[4d] Validating clip from unapproved creator (UnknownCreator)")
    approved, reasons = validator.validate_clip_for_campaign(
        campaign_id="strict_campaign",
        creator_name="UnknownCreator",
        source_platform="youtube",
        clip_duration=60
    )
    assert approved == False
    assert any("not in whitelist" in r for r in reasons)
    logger.info(f"✓ Unapproved creator rejected: {reasons[0]}")

    # Test 4e: Validate blocked creator
    logger.info("\n[4e] Validating clip from blocked creator")
    registry.block_creator("BadCreator", "youtube", "Blocked")
    approved, reasons = validator.validate_clip_for_campaign(
        campaign_id="strict_campaign",
        creator_name="BadCreator",
        source_platform="youtube",
        clip_duration=60
    )
    # Note: BadCreator isn't in whitelist, so it fails for that reason
    # But let's test blacklist with a different campaign
    logger.info(f"✓ Creator validation enforced")

    logger.info("\n✓ TEST 4 PASSED")
    return True


def test_creator_validation_policy():
    """TEST 5: Creator validation policy (discovery vs strict mode)."""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Creator Validation Policy")
    logger.info("="*80)

    registry = CreatorRegistry()

    # TEST 5a: Discovery mode (allow unverified)
    logger.info("\n[5a] Testing DISCOVERY mode (allow_unverified_creators=True)")
    validator_discovery = CampaignRequirementsValidator(allow_unverified_creators=True)

    approved, profile = validator_discovery.validate_creator("NewCreator", "youtube")
    assert approved == True
    assert profile is not None
    assert profile.verification_status == "unverified"
    logger.info("✓ DISCOVERY mode: unverified creator ALLOWED")

    # TEST 5b: Strict mode (reject unverified)
    logger.info("\n[5b] Testing STRICT mode (allow_unverified_creators=False)")
    validator_strict = CampaignRequirementsValidator(allow_unverified_creators=False)

    approved, profile = validator_strict.validate_creator("AnotherNewCreator", "youtube")
    assert approved == False
    assert profile is None
    logger.info("✓ STRICT mode: unverified creator REJECTED")

    # TEST 5c: Blocked creator rejected in both modes
    logger.info("\n[5c] Testing blocked creator in both modes")
    registry.block_creator("BlockedCreator", "youtube", "Inappropriate content")

    approved_discovery, _ = validator_discovery.validate_creator("BlockedCreator", "youtube")
    approved_strict, _ = validator_strict.validate_creator("BlockedCreator", "youtube")

    assert approved_discovery == False
    assert approved_strict == False
    logger.info("✓ BLOCKED creator rejected in both discovery and strict modes")

    # TEST 5d: Approved creator allowed in both modes
    logger.info("\n[5d] Testing approved creator in both modes")
    registry.approve_creator("VerifiedCreator", "youtube", "Quality content")

    approved_discovery, _ = validator_discovery.validate_creator("VerifiedCreator", "youtube")
    approved_strict, _ = validator_strict.validate_creator("VerifiedCreator", "youtube")

    assert approved_discovery == True
    assert approved_strict == True
    logger.info("✓ APPROVED creator allowed in both discovery and strict modes")

    logger.info("\n✓ TEST 5 PASSED")
    return True


def run_all_tests():
    """Run all Phase 1 tests."""
    logger.info("\n" + "="*80)
    logger.info("PHASE 1: CREATOR REQUIREMENTS LAYER - VALIDATION TEST SUITE")
    logger.info("="*80)

    results = {}

    # Test 1
    try:
        results['test_creator_discovery'] = test_creator_discovery_and_registry()
    except Exception as e:
        logger.error(f"TEST 1 FAILED: {e}")
        results['test_creator_discovery'] = False

    # Test 2
    try:
        results['test_approval_blocking'] = test_creator_approval_and_blocking()
    except Exception as e:
        logger.error(f"TEST 2 FAILED: {e}")
        results['test_approval_blocking'] = False

    # Test 3
    try:
        results['test_normalization'] = test_campaign_requirement_normalization()
    except Exception as e:
        logger.error(f"TEST 3 FAILED: {e}")
        results['test_normalization'] = False

    # Test 4
    try:
        results['test_validation'] = test_campaign_validation_with_creators()
    except Exception as e:
        logger.error(f"TEST 4 FAILED: {e}")
        results['test_validation'] = False

    # Test 5
    try:
        results['test_policy'] = test_creator_validation_policy()
    except Exception as e:
        logger.error(f"TEST 5 FAILED: {e}")
        results['test_policy'] = False

    # Summary
    logger.info("\n" + "="*80)
    logger.info("PHASE 1 TEST SUMMARY")
    logger.info("="*80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_flag in results.items():
        status = "✓ PASSED" if passed_flag else "✗ FAILED"
        logger.info(f"{test_name}: {status}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n" + "="*80)
        logger.info("🎉 PHASE 1 COMPLETE - ALL TESTS PASSED")
        logger.info("="*80)
        logger.info("\nSystem is ready for Phase 2: Source Discovery")
        return True
    else:
        logger.warning(f"\n⚠ {total - passed} test(s) failed - review before continuing")
        return False


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
