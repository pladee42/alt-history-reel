#!/usr/bin/env python3
"""
test_meta_publisher.py - Integration Tests for Meta Publisher

Tests the Instagram and Facebook Reels upload functionality.
Run with: python tests/test_meta_publisher.py --quick

Note: These tests require valid OAuth credentials.
Instagram uploads require a public video URL.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from publishers.meta_publisher import MetaPublisher
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
    """Create a Meta publisher instance."""
    if settings is None:
        pytest.skip("Config not found")
    return MetaPublisher(settings)


@pytest.fixture
def test_metadata():
    """Create test metadata for uploads."""
    return PlatformMetadata(
        platform='instagram',
        description='🧪 TEST upload - What if history changed? This is an automated test.',
        hashtags=['test', 'alternatehistory', 'whatif', 'ai', 'fyp'],
    )


# ============================================
# UNIT TESTS (No API calls)
# ============================================

class TestMetaPublisherUnit:
    """Unit tests that don't require API access."""
    
    def test_initialization(self, publisher):
        """Test publisher initializes correctly."""
        assert publisher.PLATFORM_NAME == "meta"
        assert publisher._page_token is None  # Not authenticated yet
        assert publisher.token_path is not None
    
    def test_build_instagram_caption(self, publisher, test_metadata):
        """Test Instagram caption building."""
        caption = publisher._build_instagram_caption(test_metadata)
        
        assert test_metadata.description in caption
        assert '#test' in caption
        assert 'AI' in caption  # AI disclosure
    
    def test_build_facebook_description(self, publisher, test_metadata):
        """Test Facebook description building."""
        desc = publisher._build_facebook_description(test_metadata)
        
        assert test_metadata.description in desc
        assert 'AI' in desc  # AI disclosure
    
    def test_caption_limit(self, publisher):
        """Test caption is truncated to Instagram limit."""
        long_description = "A" * 3000
        metadata = PlatformMetadata(
            platform='instagram',
            description=long_description,
            hashtags=['test']
        )
        caption = publisher._build_instagram_caption(metadata)
        assert len(caption) <= 2200


# ============================================
# INTEGRATION TESTS (Require API access)
# ============================================

@pytest.mark.integration
class TestMetaPublisherIntegration:
    """Integration tests that make real API calls."""
    
    def test_authentication(self, publisher):
        """Test OAuth authentication works."""
        result = publisher.authenticate()
        
        if not result:
            pytest.skip("Meta credentials not configured")
        
        assert publisher._authenticated is True
        assert publisher._page_token is not None
    
    def test_get_account_info(self, publisher):
        """Test fetching account information."""
        if not publisher.authenticate():
            pytest.skip("Meta credentials not configured")
        
        info = publisher.get_account_info()
        
        if info:
            print(f"\n📸 Account Info: {info}")


# ============================================
# CLI RUNNER
# ============================================

def run_quick_test():
    """Run a quick test without pytest."""
    print("\n" + "=" * 50)
    print("📸 Meta Publisher Quick Test")
    print("=" * 50)
    
    try:
        settings = load_config(str(PROJECT_ROOT / "configs" / "realistic.yaml"))
        publisher = MetaPublisher(settings)
        
        print(f"\n📁 Token path: {publisher.token_path}")
        print(f"🔐 Secret name: {publisher.secret_name}")
        
        # Test authentication
        print("\n🔑 Testing authentication...")
        if publisher.authenticate():
            print("   ✅ Authentication successful!")
            
            # Get account info
            info = publisher.get_account_info()
            if info:
                if 'instagram' in info:
                    ig = info['instagram']
                    print(f"\n📸 Instagram: @{ig.get('username', 'N/A')}")
                    print(f"   Followers: {ig.get('followers_count', 0)}")
                    print(f"   Media count: {ig.get('media_count', 0)}")
                if 'facebook_page' in info:
                    fb = info['facebook_page']
                    print(f"\n📄 Facebook Page: {fb.get('name', 'N/A')}")
                    print(f"   Followers: {fb.get('followers_count', 0)}")
        else:
            print("   ❌ Authentication failed")
            print("   → Run: python scripts/meta_oauth_setup.py")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


def run_instagram_upload_test(video_url: str):
    """Run an Instagram Reel upload test."""
    print("\n" + "=" * 50)
    print("📸 Instagram Reel Upload Test")
    print("=" * 50)
    
    if not video_url:
        print("❌ Video URL required for Instagram upload")
        print("   Usage: python tests/test_meta_publisher.py --instagram --video-url https://...")
        return
    
    try:
        settings = load_config(str(PROJECT_ROOT / "configs" / "realistic.yaml"))
        publisher = MetaPublisher(settings)
        
        # Authenticate
        print("\n🔑 Authenticating...")
        if not publisher.authenticate():
            print("❌ Authentication failed!")
            return
        
        print(f"   ✅ Authenticated")
        
        # Create metadata
        metadata = PlatformMetadata(
            platform='instagram',
            description='🧪 [TEST] What if history took a different path? AI-generated alternative history.',
            hashtags=['test', 'alternatehistory', 'whatif', 'ai', 'fyp'],
        )
        
        print(f"\n📹 Video URL: {video_url}")
        
        # Upload
        print("\n📤 Uploading to Instagram...")
        result = publisher.upload_instagram_reel(video_url, metadata)
        
        print("\n" + "=" * 50)
        if result.success:
            print("✅ UPLOAD SUCCESSFUL!")
            print("=" * 50)
            print(f"🔗 URL: {result.url}")
            print(f"🆔 Post ID: {result.post_id}")
        else:
            print("❌ UPLOAD FAILED")
            print("=" * 50)
            print(f"Error: {result.error}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


def run_facebook_upload_test():
    """Run a Facebook Page Reel upload test."""
    print("\n" + "=" * 50)
    print("📄 Facebook Page Reel Upload Test")
    print("=" * 50)
    
    try:
        settings = load_config(str(PROJECT_ROOT / "configs" / "realistic.yaml"))
        publisher = MetaPublisher(settings)
        
        # Authenticate
        print("\n🔑 Authenticating...")
        if not publisher.authenticate():
            print("❌ Authentication failed!")
            return
        
        print(f"   ✅ Authenticated")
        
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
        
        # Create metadata
        metadata = PlatformMetadata(
            platform='facebook',
            description='🧪 [TEST] What if history took a different path? AI-generated alternative history.',
            hashtags=['test', 'alternatehistory', 'whatif', 'ai'],
        )
        
        # Upload
        print("\n📤 Uploading to Facebook...")
        result = publisher.upload_facebook_reel(video_path, metadata)
        
        print("\n" + "=" * 50)
        if result.success:
            print("✅ UPLOAD SUCCESSFUL!")
            print("=" * 50)
            print(f"🔗 URL: {result.url}")
            print(f"🆔 Post ID: {result.post_id}")
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
    
    parser = argparse.ArgumentParser(description="Meta Publisher Tests")
    parser.add_argument("--quick", action="store_true", help="Run quick authentication test")
    parser.add_argument("--instagram", action="store_true", help="Test Instagram Reel upload")
    parser.add_argument("--facebook", action="store_true", help="Test Facebook Page Reel upload")
    parser.add_argument("--video-url", type=str, help="Public video URL for Instagram upload")
    parser.add_argument("--integration", action="store_true", help="Run pytest integration tests")
    args = parser.parse_args()
    
    if args.quick:
        run_quick_test()
    elif args.instagram:
        run_instagram_upload_test(args.video_url)
    elif args.facebook:
        run_facebook_upload_test()
    elif args.integration:
        pytest.main([__file__, "-v", "-m", "integration"])
    else:
        # Default: run quick test
        run_quick_test()
