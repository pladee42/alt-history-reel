"""
social_metadata.py - Viral Metadata Generator

Uses Gemini to generate platform-specific metadata optimized for 
maximum reach and engagement on Instagram, Facebook, TikTok, and YouTube.
"""

import os
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import google.genai as genai
from dotenv import load_dotenv

from screenwriter import Scenario
from manager import load_prompt, Settings

load_dotenv(override=True)


@dataclass
class PlatformMetadata:
    """Platform-specific metadata for viral optimization."""
    platform: str
    description: str
    hashtags: List[str] = field(default_factory=list)
    
    # YouTube-specific
    title: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    # Universal
    ai_disclosure: bool = True  # Always True for AI-generated content
    
    def get_hashtag_string(self, prefix: str = "#") -> str:
        """Return hashtags as a formatted string."""
        return " ".join([f"{prefix}{h}" for h in self.hashtags])
    
    def get_caption(self, include_hashtags: bool = True) -> str:
        """Return full caption with description and optional hashtags."""
        if include_hashtags and self.hashtags:
            return f"{self.description}\n\n{self.get_hashtag_string()}"
        return self.description


@dataclass 
class SocialMetadataBundle:
    """Container for all platform metadata."""
    instagram: Optional[PlatformMetadata] = None
    facebook: Optional[PlatformMetadata] = None
    tiktok: Optional[PlatformMetadata] = None
    youtube: Optional[PlatformMetadata] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        result = {}
        for platform in ['instagram', 'facebook', 'tiktok', 'youtube']:
            meta = getattr(self, platform)
            if meta:
                result[platform] = {
                    'description': meta.description,
                    'hashtags': meta.hashtags,
                    'title': meta.title,
                    'tags': meta.tags,
                }
        return result
    
    def get(self, platform: str) -> Optional[PlatformMetadata]:
        """Get metadata for a specific platform."""
        return getattr(self, platform, None)


class SocialMetadataGenerator:
    """Generates viral-optimized metadata for each platform using Gemini."""
    
    # Platform configuration constants
    PLATFORM_CONFIGS = {
        'instagram': {
            'max_description': 2200,
            'max_hashtags': 30,
            'ideal_hashtags': 12,
            'ai_disclosure_method': 'ai_info_label',
        },
        'facebook': {
            'max_description': 63206,
            'max_hashtags': 30,
            'ideal_hashtags': 5,
            'ai_disclosure_method': 'ai_info_label',
        },
        'tiktok': {
            'max_description': 4000,
            'max_hashtags': 5,
            'ideal_hashtags': 5,
            'ai_disclosure_method': 'ai_generated_content_label',
        },
        'youtube': {
            'max_description': 5000,
            'max_title': 100,
            'max_tags_chars': 500,
            'ideal_hashtags': 3,
            'ai_disclosure_method': 'altered_content_setting',
        },
    }
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize with optional settings."""
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        self.client = genai.Client(api_key=self.api_key)
        self.settings = settings
        self.model_name = settings.gemini_model if settings else "gemini-2.0-flash"
        
        # Load prompts
        try:
            self.system_prompt = load_prompt("social_metadata")
            self.user_prompt_template = load_prompt("social_metadata_user")
        except FileNotFoundError as e:
            print(f"⚠️ Prompt file not found: {e}")
            self.system_prompt = self._get_default_system_prompt()
            self.user_prompt_template = self._get_default_user_prompt()
    
    def generate(self, scenario: Scenario, channel_name: str = "ChronoReel") -> SocialMetadataBundle:
        """
        Generate optimized metadata for all platforms.
        
        Args:
            scenario: The video scenario
            channel_name: Channel name for context
            
        Returns:
            SocialMetadataBundle with metadata for each platform
        """
        print(f"📱 Generating social metadata for: {scenario.title}...")
        
        # Build user prompt with scenario details
        user_prompt = self.user_prompt_template.format(
            title=scenario.title,
            premise=scenario.premise,
            location_name=scenario.location_name,
            stage_1_label=scenario.stage_1.label,
            stage_1_description=scenario.stage_1.description,
            stage_2_label=scenario.stage_2.label,
            stage_2_description=scenario.stage_2.description,
            stage_3_label=scenario.stage_3.label,
            stage_3_description=scenario.stage_3.description,
            channel_name=channel_name,
        )
        
        # Generate with Gemini
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config={
                    'response_mime_type': 'application/json',
                    'system_instruction': self.system_prompt,
                    'temperature': 0.8,  # Slightly creative
                }
            )
            
            # Parse response
            data = self._parse_response(response)
            bundle = self._build_bundle(data)
            
            print(f"   ✅ Generated metadata for {len([p for p in [bundle.instagram, bundle.facebook, bundle.tiktok, bundle.youtube] if p])} platforms")
            return bundle
            
        except Exception as e:
            print(f"   ❌ Metadata generation failed: {e}")
            import traceback
            traceback.print_exc()
            # Return fallback metadata
            return self._generate_fallback(scenario)
    
    def _parse_response(self, response) -> Dict:
        """Parse Gemini response as JSON."""
        # Try parsed first
        if response.parsed:
            return response.parsed if isinstance(response.parsed, dict) else {}
        
        # Fallback to text parsing
        if response.text:
            text = response.text.strip()
            # Clean markdown code blocks
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text.rsplit("\n", 1)[0]
            text = text.strip()
            return json.loads(text)
        
        return {}
    
    def _build_bundle(self, data: Dict) -> SocialMetadataBundle:
        """Build SocialMetadataBundle from parsed JSON."""
        bundle = SocialMetadataBundle()
        
        # Instagram
        if 'instagram' in data:
            ig = data['instagram']
            bundle.instagram = PlatformMetadata(
                platform='instagram',
                description=ig.get('description', ''),
                hashtags=self._clean_hashtags(ig.get('hashtags', [])),
            )
        
        # Facebook
        if 'facebook' in data:
            fb = data['facebook']
            bundle.facebook = PlatformMetadata(
                platform='facebook',
                description=fb.get('description', ''),
                hashtags=self._clean_hashtags(fb.get('hashtags', [])),
            )
        
        # TikTok
        if 'tiktok' in data:
            tt = data['tiktok']
            bundle.tiktok = PlatformMetadata(
                platform='tiktok',
                description=tt.get('description', ''),
                hashtags=self._clean_hashtags(tt.get('hashtags', []))[:5],  # Max 5
            )
        
        # YouTube
        if 'youtube' in data:
            yt = data['youtube']
            bundle.youtube = PlatformMetadata(
                platform='youtube',
                title=yt.get('title', '')[:100],  # Max 100 chars
                description=yt.get('description', ''),
                hashtags=self._clean_hashtags(yt.get('hashtags', []))[:3],
                tags=yt.get('tags', []),
            )
        
        return bundle
    
    def _clean_hashtags(self, hashtags: List) -> List[str]:
        """Clean hashtags - remove # prefix, lowercase, remove spaces."""
        cleaned = []
        for h in hashtags:
            if isinstance(h, str):
                h = h.strip().lstrip('#').lower().replace(' ', '')
                if h and h not in cleaned:
                    cleaned.append(h)
        return cleaned
    
    def _generate_fallback(self, scenario: Scenario) -> SocialMetadataBundle:
        """Generate basic fallback metadata if API fails."""
        print("   ⚠️ Using fallback metadata generation...")
        
        base_description = f"What if {scenario.premise}? 🌍✨ Watch this journey through time!"
        base_hashtags = ['alternatehistory', 'whatif', 'timetravel', 'history', 'viral']
        
        return SocialMetadataBundle(
            instagram=PlatformMetadata(
                platform='instagram',
                description=f"{base_description}\n\n📍 {scenario.location_name}",
                hashtags=base_hashtags + ['reels', 'explore', 'fyp', 'historylovers', 'mindblown'],
            ),
            facebook=PlatformMetadata(
                platform='facebook',
                description=f"🤔 {base_description}\n\nWhat do you think would happen?",
                hashtags=base_hashtags[:5],
            ),
            tiktok=PlatformMetadata(
                platform='tiktok',
                description=f"bro what if this actually happened 😳 {scenario.premise[:50]}...",
                hashtags=['fyp', 'viral', 'alternatehistory', 'whatif', 'mindblowing'],
            ),
            youtube=PlatformMetadata(
                platform='youtube',
                title=f"What If {scenario.premise[:60]}? #Shorts",
                description=f"{base_description}\n\n🤖 Created with AI-generated imagery and audio.",
                hashtags=['alternatehistory', 'whatif', 'shorts'],
                tags=['alternate history', 'what if', 'time travel', 'history', 'visualization'],
            ),
        )
    
    def _get_default_system_prompt(self) -> str:
        """Fallback system prompt if file not found."""
        return """You are a viral social media expert. Generate platform-specific 
metadata for short-form video content. Output valid JSON with keys: 
instagram, facebook, tiktok, youtube. Each should have description and hashtags.
YouTube should also have title and tags."""
    
    def _get_default_user_prompt(self) -> str:
        """Fallback user prompt if file not found."""
        return """Generate metadata for this video:
Title: {title}
Premise: {premise}
Location: {location_name}
Channel: {channel_name}
Stages: {stage_1_label}, {stage_2_label}, {stage_3_label}"""


def generate_social_metadata(scenario: Scenario, settings: Optional[Settings] = None) -> SocialMetadataBundle:
    """Convenience function to generate social metadata."""
    generator = SocialMetadataGenerator(settings)
    channel_name = settings.channel_name if settings else "ChronoReel"
    return generator.generate(scenario, channel_name)


if __name__ == "__main__":
    # Test with a mock scenario
    from screenwriter import Scenario, StageData
    
    print("\n" + "=" * 50)
    print("📱 Testing Social Metadata Generator")
    print("=" * 50)
    
    # Create mock scenario
    mock_scenario = Scenario(
        id="test_scenario_001",
        title="What if **Rome** never fell?",
        premise="the Roman Empire survived into the modern era",
        location_name="Colosseum, Rome",
        location_prompt="The Roman Colosseum, ancient architecture",
        stage_1=StageData(
            year="476 AD",
            label="Rome, 476 AD",
            description="The final days of the Western Roman Empire",
            mood="tense, dramatic"
        ),
        stage_2=StageData(
            year="1500 AD",
            label="Rome, 1500 AD",
            description="A thriving Roman metropolis with Renaissance influence",
            mood="majestic, hopeful"
        ),
        stage_3=StageData(
            year="2025 AD",
            label="Rome, 2025 AD",
            description="Ultra-modern Roman architecture blending ancient and futuristic",
            mood="awe-inspiring, futuristic"
        ),
    )
    
    # Generate metadata
    bundle = generate_social_metadata(mock_scenario)
    
    # Print results
    print("\n📊 Generated Metadata:\n")
    
    for platform in ['instagram', 'facebook', 'tiktok', 'youtube']:
        meta = bundle.get(platform)
        if meta:
            print(f"{'='*40}")
            print(f"📱 {platform.upper()}")
            print(f"{'='*40}")
            if meta.title:
                print(f"Title: {meta.title}")
            print(f"Description: {meta.description[:200]}...")
            print(f"Hashtags: {meta.get_hashtag_string()}")
            if meta.tags:
                print(f"Tags: {', '.join(meta.tags[:5])}...")
            print()
