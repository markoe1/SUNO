"""
GATE 5: Platform Adapter Execution Test
Tests all 5 platform adapters (TikTok, Instagram, YouTube, Twitter, Bluesky)
and error handling.
"""

from suno.posting.adapters.base import PostingStatus

def test_adapter_interface():
    """Test 5A: All adapters implement correct interface."""
    from suno.posting.adapters import get_adapter, get_supported_platforms

    platforms = get_supported_platforms()
    assert len(platforms) == 5, f"Should support 5 platforms, got {len(platforms)}"

    expected = ["tiktok", "instagram", "youtube", "twitter", "bluesky"]
    for platform in expected:
        assert platform in platforms, f"Platform {platform} should be supported"
        adapter = get_adapter(platform)
        assert adapter is not None, f"Should get adapter for {platform}"
        print(f"  ✓ {platform.upper()}: {adapter.__class__.__name__}")

    print(f"✅ Test 5A PASS: All 5 adapters available")
    return True

def test_adapter_payload_validation():
    """Test 5B: Adapters validate and prepare payloads correctly."""
    from suno.posting.adapters import get_adapter

    # Test TikTok
    tiktok = get_adapter("tiktok")
    payload = tiktok.prepare_payload(
        clip_url="https://example.com/video.mp4",
        caption="Test caption #trending",
        hashtags=["test", "clip"],
        metadata={"job_id": 1},
    )

    assert "video_url" in payload, "Payload should have video_url"
    assert "caption" in payload, "Payload should have caption"
    assert len(payload["caption"]) <= 2200, "TikTok caption should be <= 2200 chars"
    print(f"  ✓ TikTok payload valid (caption: {len(payload['caption'])} chars)")

    # Test Instagram
    instagram = get_adapter("instagram")
    payload = instagram.prepare_payload(
        clip_url="https://example.com/video.mp4",
        caption="Instagram caption",
        hashtags=["insta"],
        metadata={"job_id": 1},
    )

    assert "caption" in payload, "Payload should have caption"
    print(f"  ✓ Instagram payload valid")

    # Test YouTube
    youtube = get_adapter("youtube")
    payload = youtube.prepare_payload(
        clip_url="https://example.com/video.mp4",
        caption="YouTube caption",
        hashtags=["youtube"],
        metadata={"job_id": 1},
    )

    assert "title" in payload or "description" in payload, "Payload should have title or description"
    print(f"  ✓ YouTube payload valid")

    # Test Twitter
    twitter = get_adapter("twitter")
    payload = twitter.prepare_payload(
        clip_url="https://example.com/video.mp4",
        caption="Tweet text",
        hashtags=["twitter"],
        metadata={"job_id": 1},
    )

    assert "text" in payload or "caption" in payload, "Payload should have text or caption"
    print(f"  ✓ Twitter payload valid")

    # Test Bluesky
    bluesky = get_adapter("bluesky")
    payload = bluesky.prepare_payload(
        clip_url="https://example.com/video.mp4",
        caption="Bluesky post",
        hashtags=["bluesky"],
        metadata={"job_id": 1},
    )

    assert "text" in payload or "caption" in payload, "Payload should have text or caption"
    print(f"  ✓ Bluesky payload valid")

    print(f"✅ Test 5B PASS: All adapters prepare payloads correctly")
    return True

def test_adapter_error_classification():
    """Test 5C: Adapters classify errors correctly (retryable vs permanent)."""
    from suno.posting.adapters.base import PlatformAdapter

    # Create test adapter
    class TestAdapter(PlatformAdapter):
        @property
        def platform_name(self):
            return "test"

        def validate_account(self, creds):
            return True

        def prepare_payload(self, *args, **kwargs):
            return {}

        def post(self, creds, payload):
            return None

        def submit_result(self, creds, url, source_url):
            return True

    adapter = TestAdapter()

    # Test error classification
    test_cases = [
        (429, PostingStatus.RETRYABLE_ERROR, "Rate limit"),
        (503, PostingStatus.RETRYABLE_ERROR, "Service unavailable"),
        (502, PostingStatus.RETRYABLE_ERROR, "Bad gateway"),
        (504, PostingStatus.RETRYABLE_ERROR, "Gateway timeout"),
        (500, PostingStatus.RETRYABLE_ERROR, "Server error"),
        (401, PostingStatus.PERMANENT_ERROR, "Unauthorized"),
        (403, PostingStatus.PERMANENT_ERROR, "Forbidden"),
        (400, PostingStatus.PERMANENT_ERROR, "Bad request"),
        (404, PostingStatus.PERMANENT_ERROR, "Not found"),
    ]

    for code, expected_status, desc in test_cases:
        status = adapter._classify_error(code, desc)
        assert status == expected_status, f"Code {code} should be {expected_status}, got {status}"
        print(f"  ✓ HTTP {code}: {status.value}")

    print(f"✅ Test 5C PASS: Error classification correct")
    return True

def test_adapter_result_structure():
    """Test 5D: Adapter results have consistent structure."""
    from suno.posting.adapters.base import PostingResult, PostingStatus

    # Test success result
    result_success = PostingResult(
        status=PostingStatus.SUCCESS,
        posted_url="https://tiktok.com/@user/video/123",
        post_id="123",
    )

    assert result_success.is_success() == True
    assert result_success.is_retryable() == False
    assert result_success.is_permanent_failure() == False
    print(f"  ✓ Success result: {result_success.status.value}")

    # Test retryable error
    result_retryable = PostingResult(
        status=PostingStatus.RETRYABLE_ERROR,
        error_message="Rate limited, retry later",
    )

    assert result_retryable.is_success() == False
    assert result_retryable.is_retryable() == True
    assert result_retryable.is_permanent_failure() == False
    print(f"  ✓ Retryable result: {result_retryable.status.value}")

    # Test permanent error
    result_permanent = PostingResult(
        status=PostingStatus.PERMANENT_ERROR,
        error_message="Invalid credentials",
    )

    assert result_permanent.is_success() == False
    assert result_permanent.is_retryable() == False
    assert result_permanent.is_permanent_failure() == True
    print(f"  ✓ Permanent error result: {result_permanent.status.value}")

    print(f"✅ Test 5D PASS: Result structure consistent")
    return True

def test_adapter_doesnt_crash_on_failure():
    """Test 5E: Adapter failures don't crash system."""
    from suno.posting.adapters import get_adapter

    adapters_to_test = ["tiktok", "instagram", "youtube", "twitter", "bluesky"]

    for platform in adapters_to_test:
        adapter = get_adapter(platform)

        try:
            # Try to post with invalid credentials (should NOT crash)
            result = adapter.post(
                account_credentials={},  # Invalid/empty
                payload={"caption": "test"},
            )

            # Should return PostingResult, not crash
            assert result is not None, f"{platform} should return PostingResult"
            assert hasattr(result, 'status'), f"{platform} result should have status"
            print(f"  ✓ {platform.upper()}: Handled invalid creds gracefully")

        except Exception as e:
            print(f"  ✗ {platform.upper()}: {e}")
            return False

    print(f"✅ Test 5E PASS: No adapter crashes on failure")
    return True

if __name__ == "__main__":
    print("\n" + "="*60)
    print("GATE 5: PLATFORM ADAPTER EXECUTION")
    print("="*60)

    try:
        success_1 = test_adapter_interface()
        success_2 = test_adapter_payload_validation()
        success_3 = test_adapter_error_classification()
        success_4 = test_adapter_result_structure()
        success_5 = test_adapter_doesnt_crash_on_failure()

        if all([success_1, success_2, success_3, success_4, success_5]):
            print("\n" + "="*60)
            print("GATE 5: ✅ PASS")
            print("="*60)
            print("""
✅ All 5 platform adapters available and working
✅ Payload preparation correct for each platform
✅ Error classification (retryable vs permanent) correct
✅ Result structure consistent across all adapters
✅ Adapter failures handled gracefully (no crashes)
✅ System resilient to bad credentials/API errors
            """)
        else:
            print("\n" + "="*60)
            print("GATE 5: ❌ FAIL")
            print("="*60)

    except Exception as e:
        print(f"\n❌ GATE 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
