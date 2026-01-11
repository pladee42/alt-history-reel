#!/usr/bin/env python3
"""
test_youtube_publisher.py - Integration Tests for YouTube Publisher

Tests the YouTube upload functionality with real API calls.
Run with: python -m pytest tests/test_youtube_publisher.py -v

Note: These tests require valid OAuth credentials and will make real API calls.
Use --run-integration flag to execute integration tests.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from publishers.youtube_publisher import YouTubePublisher
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
    """Create a YouTube publisher instance."""
    if settings is None:
        pytest.skip("Config not found")
    return YouTubePublisher(settings)


@pytest.fixture
def test_metadata():
    """Create test metadata for uploads."""
    return PlatformMetadata(
        platform='youtube',
        title='Test Upload - What If History Changed? #Shorts',
        description='🧪 This is a TEST upload to verify YouTube API integration.',
        hashtags=['test', 'shorts', 'alternatehistory'],
        tags=['test upload', 'api test', 'alternate history']
    )


@pytest.fixture
def test_video_path():
    """Get path to a test video if available."""
    # Look for any final_cut.mp4 in output directory
    output_dir = PROJECT_ROOT / "output"
    if output_dir.exists():
        for scenario_dir in sorted(output_dir.iterdir(), reverse=True):
            final_cut = scenario_dir / "final_cut.mp4"
            if final_cut.exists():
                return str(final_cut)
    
    # Fallback to test fixtures
    test_fixture = PROJECT_ROOT / "output" / "test_fixtures" / "video_1.mp4"
    if test_fixture.exists():
        return str(test_fixture)
    
    return None


# ============================================
# UNIT TESTS (No API calls)
# ============================================

class TestYouTubePublisherUnit:
    """Unit tests that don't require API access."""
    
    def test_initialization(self, publisher):
        """Test publisher initializes correctly."""
        assert publisher.PLATFORM_NAME == "youtube"
        assert publisher.youtube is None  # Not authenticated yet
        assert publisher.token_path is not None
    
    def test_build_title_adds_shorts(self, publisher, test_metadata):
        """Test that #Shorts is added to title."""
        # Test with title that doesn't have #Shorts
        metadata = PlatformMetadata(
            platform='youtube',
            title='Test Video Title',
            description='Test'
        )
        title = publisher._build_title(metadata)
        assert '#Shorts' in title or '#shorts' in title.lower()
    
    def test_build_title_respects_max_length(self, publisher):
        """Test title is truncated to max length."""
        long_title = "A" * 150  # Longer than 100 chars
        metadata = PlatformMetadata(
            platform='youtube',
            title=long_title,
            description='Test'
        )
        title = publisher._build_title(metadata)
        assert len(title) <= publisher.MAX_TITLE_LENGTH
    
    def test_build_description_includes_ai_disclosure(self, publisher, test_metadata):
        """Test AI disclosure is included in description."""
        description = publisher._build_description(test_metadata)
        assert 'AI-generated' in description or 'AI' in description
    
    def test_build_tags_respects_limit(self, publisher):
        """Test tags stay within character limit."""
        # Create metadata with many tags
        metadata = PlatformMetadata(
            platform='youtube',
            title='Test',
            description='Test',
            tags=['very_long_tag_' + str(i) for i in range(50)]
        )
        tags = publisher._build_tags(metadata)
        
        # Calculate total chars
        total_chars = sum(len(tag) + 1 for tag in tags)
        assert total_chars <= publisher.MAX_TAGS_CHARS + len(tags)  # Allow for separators
    
    def test_validate_video_rejects_missing_file(self, publisher):
        """Test validation fails for missing files."""
        result = publisher.validate_video("/nonexistent/path/video.mp4")
        assert result is False
    
    def test_create_result_sets_platform(self, publisher):
        """Test PublishResult has correct platform."""
        result = publisher._create_result(
            success=True,
            url="https://youtube.com/shorts/abc123"
        )
        assert result.platform == "youtube"
        assert result.success is True


# ============================================
# INTEGRATION TESTS (Require API access)
# ============================================

@pytest.mark.integration
class TestYouTubePublisherIntegration:
    """Integration tests that make real API calls."""
    
    def test_authentication(self, publisher):
        """Test OAuth authentication works."""
        result = publisher.authenticate()
        
        if not result:
            pytest.skip("YouTube credentials not configured")
        
        assert publisher._authenticated is True
        assert publisher.youtube is not None
    
    def test_get_channel_info(self, publisher):
        """Test fetching channel information."""
        if not publisher.authenticate():
            pytest.skip("YouTube credentials not configured")
        
        info = publisher.get_channel_info()
        
        assert info is not None
        assert 'id' in info
        assert 'title' in info
        print(f"\n📺 Channel: {info['title']}")
        print(f"   ID: {info['id']}")
    
    def test_upload_private_video(self, publisher, test_metadata, test_video_path):
        """
        Test uploading a video as private.
        
        ⚠️ This test will create a real (private) video on YouTube!
        You should delete it manually after testing.
        """
        if test_video_path is None:
            pytest.skip("No test video available")
        
        if not publisher.authenticate():
            pytest.skip("YouTube credentials not configured")
        
        # Modify metadata to indicate it's a test
        test_metadata.title = "[TEST] Delete Me - API Test #Shorts"
        test_metadata.description = "🧪 Automated test upload. Safe to delete."
        
        # For safety, we'll use private upload directly
        from googleapiclient.http import MediaFileUpload
        
        body = {
            'snippet': {
                'title': publisher._build_title(test_metadata),
                'description': publisher._build_description(test_metadata),
                'tags': publisher._build_tags(test_metadata),
                'categoryId': '27',
            },
            'status': {
                'privacyStatus': 'private',  # Always private for tests
                'selfDeclaredMadeForKids': False,
                'containsSyntheticMedia': True,
            },
        }
        
        media = MediaFileUpload(
            test_video_path,
            mimetype='video/mp4',
            resumable=True
        )
        
        request = publisher.youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
        
        video_id = response['id']
        video_url = f"https://youtube.com/shorts/{video_id}"
        
        print(f"\n✅ Test upload successful!")
        print(f"   Video ID: {video_id}")
        print(f"   URL: {video_url}")
        print(f"   ⚠️ Remember to delete this test video!")
        
        assert video_id is not None
        assert len(video_id) > 0


# ============================================
# CLI RUNNER
# ============================================

def run_quick_test():
    """Run a quick test without pytest."""
    print("\n" + "=" * 50)
    print("🎬 YouTube Publisher Quick Test")
    print("=" * 50)
    
    try:
        settings = load_config(str(PROJECT_ROOT / "configs" / "realistic.yaml"))
        publisher = YouTubePublisher(settings)
        
        print(f"\n📁 Token path: {publisher.token_path}")
        print(f"🔐 Secret name: {publisher.secret_name}")
        
        # Test authentication
        print("\n🔑 Testing authentication...")
        if publisher.authenticate():
            print("   ✅ Authentication successful!")
            
            # Get channel info
            info = publisher.get_channel_info()
            if info:
                print(f"\n📺 Connected to channel: {info['title']}")
                print(f"   Subscribers: {info['subscriber_count']}")
        else:
            print("   ❌ Authentication failed")
            print("   → Run: python scripts/youtube_oauth_setup.py")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="YouTube Publisher Tests")
    parser.add_argument("--quick", action="store_true", help="Run quick test without pytest")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    args = parser.parse_args()
    
    if args.quick:
        run_quick_test()
    elif args.integration:
        pytest.main([__file__, "-v", "-m", "integration"])
    else:
        # Run unit tests only by default
        pytest.main([__file__, "-v", "-m", "not integration"])
