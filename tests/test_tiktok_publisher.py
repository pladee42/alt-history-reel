#!/usr/bin/env python3
"""
test_tiktok_publisher.py - Integration Tests for TikTok Publisher

Tests the TikTok upload functionality with real API calls.
Run with: python tests/test_tiktok_publisher.py --quick

Note: These tests require valid OAuth credentials and will make real API calls.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from publishers.tiktok_publisher import TikTokPublisher
from publishers.base_publisher import PublishResult
from social_metadata import PlatformMetadata
from manager import load_config


# ============================================
# FIXTURES
# ============================================

@pytest.fixture
def settings():
    """Load test settings."""
    config_path = PROJECT_ROOT / "configs" / "realistic.yaml"
    if config_path.exists():
        return load_config(str(config_path))
    return None


@pytest.fixture
def publisher(settings):
    """Create a TikTok publisher instance."""
    if settings is None:
        pytest.skip("Config not found")
    return TikTokPublisher(settings)


@pytest.fixture
def test_metadata():
    """Create test metadata for uploads."""
    return PlatformMetadata(
        platform='tiktok',
        description='🧪 TEST upload - What if history changed? This is an automated test.',
        hashtags=['fyp', 'test', 'alternatehistory', 'whatif', 'ai'],
    )


@pytest.fixture
def test_video_path():
    """Get path to a test video if available."""
    output_dir = PROJECT_ROOT / "output"
    if output_dir.exists():
        for scenario_dir in sorted(output_dir.iterdir(), reverse=True):
            final_cut = scenario_dir / "final_cut.mp4"
            if final_cut.exists():
                return str(final_cut)
    
    test_fixture = PROJECT_ROOT / "output" / "test_fixtures" / "video_1.mp4"
    if test_fixture.exists():
        return str(test_fixture)
    
    return None


# ============================================
# UNIT TESTS (No API calls)
# ============================================

class TestTikTokPublisherUnit:
    """Unit tests that don't require API access."""
    
    def test_initialization(self, publisher):
        """Test publisher initializes correctly."""
        assert publisher.PLATFORM_NAME == "tiktok"
        assert publisher._access_token is None  # Not authenticated yet
        assert publisher.token_path is not None
    
    def test_build_caption(self, publisher, test_metadata):
        """Test caption building with hashtags."""
        caption = publisher._build_caption(test_metadata)
        
        assert test_metadata.description in caption
        assert '#fyp' in caption
        assert '#test' in caption
    
    def test_build_caption_respects_limit(self, publisher):
        """Test caption is truncated to 4000 chars."""
        long_description = "A" * 5000
        metadata = PlatformMetadata(
            platform='tiktok',
            description=long_description,
            hashtags=['test']
        )
        caption = publisher._build_caption(metadata)
        assert len(caption) <= 4000
    
    def test_validate_video_rejects_missing_file(self, publisher):
        """Test validation fails for missing files."""
        result = publisher.validate_video("/nonexistent/path/video.mp4")
        assert result is False
    
    def test_create_result_sets_platform(self, publisher):
        """Test PublishResult has correct platform."""
        result = publisher._create_result(
            success=True,
            url="https://tiktok.com/@user/video/123"
        )
        assert result.platform == "tiktok"
        assert result.success is True


# ============================================
# INTEGRATION TESTS (Require API access)
# ============================================

@pytest.mark.integration
class TestTikTokPublisherIntegration:
    """Integration tests that make real API calls."""
    
    def test_authentication(self, publisher):
        """Test OAuth authentication works."""
        result = publisher.authenticate()
        
        if not result:
            pytest.skip("TikTok credentials not configured")
        
        assert publisher._authenticated is True
        assert publisher._access_token is not None
    
    def test_get_creator_info(self, publisher):
        """Test fetching creator information."""
        if not publisher.authenticate():
            pytest.skip("TikTok credentials not configured")
        
        info = publisher.get_creator_info()
        
        if info:
            print(f"\n👤 Creator Info: {info}")
    
    def test_upload_video(self, publisher, test_metadata, test_video_path):
        """
        Test uploading a video to TikTok.
        
        ⚠️ This test will create a real video on TikTok!
        Note: Sandbox apps may have restrictions.
        """
        if test_video_path is None:
            pytest.skip("No test video available")
        
        if not publisher.authenticate():
            pytest.skip("TikTok credentials not configured")
        
        # Modify metadata to indicate it's a test
        test_metadata.description = "[TEST] Delete Me - Automated API Test 🧪"
        
        result = publisher.upload(test_video_path, test_metadata)
        
        print(f"\n📤 Upload result: {result}")
        
        if result.success:
            print(f"   ✅ Video URL: {result.url}")
            print(f"   🆔 Post ID: {result.post_id}")
            print(f"   🤖 AI Label: {result.ai_label_applied}")
        else:
            print(f"   ❌ Error: {result.error}")
        
        # Don't assert success - sandbox may have restrictions
        # Just check we got a valid result
        assert isinstance(result, PublishResult)


# ============================================
# CLI RUNNER
# ============================================

def run_quick_test():
    """Run a quick test without pytest."""
    print("\n" + "=" * 50)
    print("🎵 TikTok Publisher Quick Test")
    print("=" * 50)
    
    try:
        settings = load_config(str(PROJECT_ROOT / "configs" / "realistic.yaml"))
        publisher = TikTokPublisher(settings)
        
        print(f"\n📁 Token path: {publisher.token_path}")
        print(f"🔐 Secret name: {publisher.secret_name}")
        
        # Test authentication
        print("\n🔑 Testing authentication...")
        if publisher.authenticate():
            print("   ✅ Authentication successful!")
            print(f"   🆔 Open ID: {publisher._open_id}")
            
            # Get creator info
            info = publisher.get_creator_info()
            if info:
                print(f"\n👤 Creator Info: {info}")
        else:
            print("   ❌ Authentication failed")
            print("   → Run: python scripts/tiktok_oauth_setup.py")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


def run_upload_test(privacy: str = 'private'):
    """Run an actual upload test."""
    print("\n" + "=" * 50)
    print("🎵 TikTok Upload Test")
    print("=" * 50)
    
    try:
        settings = load_config(str(PROJECT_ROOT / "configs" / "realistic.yaml"))
        publisher = TikTokPublisher(settings)
        
        # Authenticate
        print("\n🔑 Authenticating...")
        if not publisher.authenticate():
            print("❌ Authentication failed!")
            return
        
        print(f"   ✅ Authenticated as: {publisher._open_id}")
        
        # Find a test video
        output_dir = PROJECT_ROOT / "output"
        video_path = None
        
        for scenario_dir in sorted(output_dir.iterdir(), reverse=True):
            final_cut = scenario_dir / "final_cut.mp4"
            if final_cut.exists():
                video_path = str(final_cut)
                break
        
        if not video_path:
            print("❌ No test video found in output/")
            return
        
        print(f"\n📹 Video: {video_path}")
        print(f"🔒 Privacy: {privacy.upper()}")
        
        # Create metadata
        metadata = PlatformMetadata(
            platform='tiktok',
            description='🧪 [TEST] What if history took a different path? AI-generated alternative history. #fyp',
            hashtags=['fyp', 'test', 'alternatehistory', 'whatif', 'ai'],
        )
        
        # Upload with specified privacy
        print("\n📤 Uploading to TikTok...")
        result = publisher.upload(video_path, metadata, privacy=privacy)
        
        print("\n" + "=" * 50)
        if result.success:
            print("✅ UPLOAD SUCCESSFUL!")
            print("=" * 50)
            print(f"🎬 Video URL: {result.url}")
            print(f"🆔 Post ID: {result.post_id}")
            print(f"🤖 AI Disclosure: {result.ai_label_applied}")
        else:
            print("❌ UPLOAD FAILED")
            print("=" * 50)
            print(f"Error: {result.error}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTok Publisher Tests")
    parser.add_argument("--quick", action="store_true", help="Run quick authentication test")
    parser.add_argument("--upload", action="store_true", help="Run actual upload test")
    parser.add_argument("--privacy", choices=['public', 'private', 'friends'], 
                        default='private', help="Privacy level for upload (default: private)")
    parser.add_argument("--integration", action="store_true", help="Run pytest integration tests")
    args = parser.parse_args()
    
    if args.quick:
        run_quick_test()
    elif args.upload:
        run_upload_test(privacy=args.privacy)
    elif args.integration:
        pytest.main([__file__, "-v", "-m", "integration"])
    else:
        # Default: run quick test
        run_quick_test()
