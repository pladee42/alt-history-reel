"""
test_social_metadata.py - Tests for Social Metadata Generator

Tests the SocialMetadataGenerator with mock scenarios.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

# Import the modules under test
from social_metadata import (
    SocialMetadataGenerator,
    SocialMetadataBundle,
    PlatformMetadata,
    generate_social_metadata,
)
from screenwriter import Scenario, StageData


@pytest.fixture
def mock_scenario():
    """Create a mock scenario for testing."""
    return Scenario(
        id="test_scenario_001",
        title="What if **dinosaurs** survived?",
        premise="an asteroid missed Earth 66 million years ago",
        location_name="New York City",
        location_prompt="Modern New York City skyline",
        stage_1=StageData(
            year="66 Million BC",
            label="Earth, 66 Million BC",
            description="Dinosaurs roaming a prehistoric Earth",
            mood="dramatic, ancient"
        ),
        stage_2=StageData(
            year="1000 AD",
            label="Earth, 1000 AD",
            description="Intelligent dinosaur civilization developing",
            mood="mysterious, evolving"
        ),
        stage_3=StageData(
            year="2025 AD",
            label="Earth, 2025 AD",
            description="Modern dinosaur-human hybrid society",
            mood="futuristic, surreal"
        ),
    )


class TestPlatformMetadata:
    """Tests for PlatformMetadata dataclass."""
    
    def test_get_hashtag_string(self):
        """Test hashtag string generation."""
        meta = PlatformMetadata(
            platform="instagram",
            description="Test description",
            hashtags=["test", "viral", "trending"]
        )
        
        result = meta.get_hashtag_string()
        assert result == "#test #viral #trending"
    
    def test_get_hashtag_string_custom_prefix(self):
        """Test hashtag string with custom prefix."""
        meta = PlatformMetadata(
            platform="instagram",
            description="Test",
            hashtags=["test"]
        )
        
        result = meta.get_hashtag_string(prefix="")
        assert result == "test"
    
    def test_get_caption_with_hashtags(self):
        """Test caption generation with hashtags."""
        meta = PlatformMetadata(
            platform="instagram",
            description="Check this out!",
            hashtags=["viral", "trending"]
        )
        
        result = meta.get_caption(include_hashtags=True)
        assert "Check this out!" in result
        assert "#viral" in result
        assert "#trending" in result
    
    def test_get_caption_without_hashtags(self):
        """Test caption generation without hashtags."""
        meta = PlatformMetadata(
            platform="instagram",
            description="Check this out!",
            hashtags=["viral"]
        )
        
        result = meta.get_caption(include_hashtags=False)
        assert result == "Check this out!"
        assert "#viral" not in result


class TestSocialMetadataBundle:
    """Tests for SocialMetadataBundle container."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        bundle = SocialMetadataBundle(
            instagram=PlatformMetadata(
                platform="instagram",
                description="IG desc",
                hashtags=["ig1", "ig2"]
            ),
            youtube=PlatformMetadata(
                platform="youtube",
                description="YT desc",
                hashtags=["yt1"],
                title="Test Title",
                tags=["tag1", "tag2"]
            ),
        )
        
        result = bundle.to_dict()
        
        assert "instagram" in result
        assert result["instagram"]["description"] == "IG desc"
        assert result["instagram"]["hashtags"] == ["ig1", "ig2"]
        
        assert "youtube" in result
        assert result["youtube"]["title"] == "Test Title"
        assert result["youtube"]["tags"] == ["tag1", "tag2"]
    
    def test_get_platform(self):
        """Test getting specific platform metadata."""
        bundle = SocialMetadataBundle(
            tiktok=PlatformMetadata(
                platform="tiktok",
                description="TT desc",
                hashtags=["fyp"]
            )
        )
        
        assert bundle.get("tiktok").description == "TT desc"
        assert bundle.get("instagram") is None


class TestSocialMetadataGenerator:
    """Tests for SocialMetadataGenerator class."""
    
    def test_clean_hashtags(self):
        """Test hashtag cleaning."""
        generator = SocialMetadataGenerator.__new__(SocialMetadataGenerator)
        generator.api_key = "test"
        
        # Test various input formats
        hashtags = ["#Test", "VIRAL", "  spaces  ", "#duplicate", "duplicate"]
        result = generator._clean_hashtags(hashtags)
        
        assert "test" in result
        assert "viral" in result
        assert "spaces" in result
        # Should deduplicate
        assert result.count("duplicate") == 1
    
    def test_generate_fallback(self, mock_scenario):
        """Test fallback metadata generation."""
        generator = SocialMetadataGenerator.__new__(SocialMetadataGenerator)
        generator.api_key = "test"
        
        bundle = generator._generate_fallback(mock_scenario)
        
        # All platforms should have metadata
        assert bundle.instagram is not None
        assert bundle.facebook is not None
        assert bundle.tiktok is not None
        assert bundle.youtube is not None
        
        # Check basic content
        assert "asteroid" in bundle.instagram.description.lower() or "dinosaur" in bundle.instagram.description.lower()
        assert "fyp" in bundle.tiktok.hashtags
        assert "#Shorts" in bundle.youtube.title
    
    @patch('social_metadata.genai.Client')
    def test_generate_with_mock_api(self, mock_client_class, mock_scenario):
        """Test generation with mocked Gemini API."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = json.dumps({
            "instagram": {
                "description": "IG test description",
                "hashtags": ["test", "viral"]
            },
            "facebook": {
                "description": "FB test description",
                "hashtags": ["test"]
            },
            "tiktok": {
                "description": "TT test description",
                "hashtags": ["fyp", "test"]
            },
            "youtube": {
                "title": "Test Title #Shorts",
                "description": "YT test description",
                "hashtags": ["shorts"],
                "tags": ["test tag"]
            }
        })
        
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Create generator with mocked prompts
        with patch('social_metadata.load_prompt', return_value="test prompt"):
            generator = SocialMetadataGenerator()
            bundle = generator.generate(mock_scenario)
        
        # Verify results
        assert bundle.instagram.description == "IG test description"
        assert bundle.youtube.title == "Test Title #Shorts"
        assert "fyp" in bundle.tiktok.hashtags


class TestIntegration:
    """Integration tests (require API key)."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("os").getenv("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set"
    )
    def test_real_generation(self, mock_scenario):
        """Test real generation (requires API key)."""
        bundle = generate_social_metadata(mock_scenario)
        
        # All platforms should have metadata
        assert bundle.instagram is not None
        assert bundle.facebook is not None
        assert bundle.tiktok is not None
        assert bundle.youtube is not None
        
        # Instagram
        assert len(bundle.instagram.description) > 0
        assert len(bundle.instagram.hashtags) >= 5
        
        # YouTube
        assert len(bundle.youtube.title) <= 100
        assert "#" in bundle.youtube.title.lower() or "shorts" in bundle.youtube.title.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
