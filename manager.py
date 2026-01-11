"""
manager.py - Configuration Manager for ChronoReel

Handles CLI argument parsing and YAML config loading.
Exposes a Settings dataclass to all other modules.
"""

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, Optional

import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = PROJECT_ROOT / "prompts" / f"{name}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding='utf-8').strip()
    raise FileNotFoundError(f"Prompt file not found: {prompt_path}")


@dataclass
class StyleConfig:
    """Visual style configuration."""
    name: str
    image_suffix: str
    video_prompt: str


@dataclass
class SocialConfig:
    """Social media publishing configuration."""
    enabled: bool = False
    
    # Platform toggles
    instagram_enabled: bool = False
    facebook_enabled: bool = False
    tiktok_enabled: bool = False
    youtube_enabled: bool = False
    
    # Token paths
    meta_token_path: str = "secrets/meta_token.json"
    tiktok_token_path: str = "secrets/tiktok_token.json"
    youtube_token_path: str = "secrets/youtube_token.json"
    
    # Account IDs
    instagram_account_id: str = ""
    facebook_page_id: str = ""
    tiktok_open_id: str = ""
    youtube_channel_id: str = ""
    
    # Behavior
    publish_delay_seconds: int = 60
    retry_on_failure: bool = True
    max_retries: int = 3
    
    def get_enabled_platforms(self) -> list:
        """Return list of enabled platform names."""
        platforms = []
        if self.instagram_enabled:
            platforms.append('instagram')
        if self.facebook_enabled:
            platforms.append('facebook')
        if self.tiktok_enabled:
            platforms.append('tiktok')
        if self.youtube_enabled:
            platforms.append('youtube')
        return platforms


@dataclass
class Settings:
    """Configuration settings loaded from YAML config file."""
    
    # Core identifiers
    channel_name: str
    google_sheet_id: str
    
    # Visual style (controls how content looks, not what it's about)
    style: StyleConfig
    
    # Storage options (gcs_bucket preferred, drive_folder_id is legacy)
    gcs_bucket: str = ""
    drive_folder_id: str = ""
    
    # Audio mood keywords
    audio_mood: str = "cinematic, atmospheric"
    
    # Model settings
    gemini_model: str = "gemini-3-flash-preview"
    
    # Generation settings
    image_retries: int = 3
    
    # Social media publishing
    social: Optional['SocialConfig'] = None
    
    # Runtime paths (set after initialization)
    config_path: str = ""
    output_dir: str = ""
    
    def __post_init__(self):
        """Set up runtime paths based on config location."""
        if self.config_path:
            project_root = os.path.dirname(os.path.dirname(self.config_path))
            self.output_dir = os.path.join(project_root, "output")
            os.makedirs(self.output_dir, exist_ok=True)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ChronoReel - Alternative History Video Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --style realistic
  python main.py --style vintage --dry-run
        """
    )
    
    parser.add_argument(
        "--style", "-s",
        default="realistic",
        help="Style config to use (looks for configs/<style>.yaml)"
    )
    
    parser.add_argument(
        "--config", "-c",
        help="Direct path to config file (overrides --style)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making API calls (for testing)"
    )
    
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3, 4],
        help="Run only up to a specific phase (for incremental testing)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def load_config(config_path: str) -> Settings:
    """
    Load and validate YAML configuration file.
    
    Args:
        config_path: Path to the YAML config file
        
    Returns:
        Settings dataclass with all configuration values
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If required fields are missing
    """
    # Resolve to absolute path
    config_path = os.path.abspath(config_path)
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    
    if not config_data:
        raise ValueError(f"Config file is empty: {config_path}")
    
    # Required fields
    required_fields = ['channel_name', 'google_sheet_id', 'style']
    
    missing = [f for f in required_fields if f not in config_data]
    if missing:
        raise ValueError(f"Missing required config fields: {', '.join(missing)}")
    
    # Parse style
    style_data = config_data['style']
    style = StyleConfig(
        name=style_data['name'],
        image_suffix=style_data['image_suffix'],
        video_prompt=style_data['video_prompt']
    )
    
    # Clean Gemini config
    gemini_config = config_data.get('gemini', {})
    gemini_model = gemini_config.get('model', 'gemini-3-flash-preview')
    
    # Parse social config (optional)
    social_data = config_data.get('social', {})
    social = SocialConfig(
        enabled=social_data.get('enabled', False),
        instagram_enabled=social_data.get('instagram_enabled', False),
        facebook_enabled=social_data.get('facebook_enabled', False),
        tiktok_enabled=social_data.get('tiktok_enabled', False),
        youtube_enabled=social_data.get('youtube_enabled', False),
        meta_token_path=social_data.get('meta_token_path', 'secrets/meta_token.json'),
        tiktok_token_path=social_data.get('tiktok_token_path', 'secrets/tiktok_token.json'),
        youtube_token_path=social_data.get('youtube_token_path', 'secrets/youtube_token.json'),
        instagram_account_id=social_data.get('instagram_account_id', ''),
        facebook_page_id=social_data.get('facebook_page_id', ''),
        tiktok_open_id=social_data.get('tiktok_open_id', ''),
        youtube_channel_id=social_data.get('youtube_channel_id', ''),
        publish_delay_seconds=social_data.get('publish_delay_seconds', 60),
        retry_on_failure=social_data.get('retry_on_failure', True),
        max_retries=social_data.get('max_retries', 3),
    )
    
    # Create Settings object
    settings = Settings(
        channel_name=config_data['channel_name'],
        google_sheet_id=config_data['google_sheet_id'],
        style=style,
        gcs_bucket=config_data.get('gcs_bucket', ''),
        drive_folder_id=config_data.get('drive_folder_id', ''),
        gemini_model=gemini_model,
        audio_mood=config_data.get('audio_mood', 'cinematic, atmospheric'),
        image_retries=config_data.get('image_retries', 3),
        social=social,
        config_path=config_path
    )
    
    return settings


def resolve_config_path(args: argparse.Namespace) -> str:
    """Resolve config path from args."""
    if args.config:
        return args.config
    
    # Look for configs/<style>.yaml relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "configs", f"{args.style}.yaml")


def print_settings(settings: Settings, verbose: bool = False) -> None:
    """Print loaded settings for verification."""
    print("\n" + "=" * 50)
    print("🎬 ChronoReel Configuration Loaded")
    print("=" * 50)
    print(f"📺 Channel:  {settings.channel_name}")
    print(f"📁 Output:   {settings.output_dir}")
    print(f"🎨 Style:    {settings.style.name}")
    print(f"🔊 Mood:     {settings.audio_mood}")
    print(f"🔄 Retries:  {settings.image_retries}")
    
    # Social publishing status
    if settings.social and settings.social.enabled:
        platforms = settings.social.get_enabled_platforms()
        print(f"📱 Social:   {', '.join(platforms) if platforms else 'No platforms enabled'}")
    else:
        print(f"📱 Social:   Disabled")
    
    if verbose:
        print(f"\n📷 Image Suffix: {settings.style.image_suffix}")
        print(f"🎥 Video Prompt: {settings.style.video_prompt}")
    
    print("=" * 50 + "\n")


# Module-level singleton for easy import
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    if _settings is None:
        raise RuntimeError("Settings not initialized. Call init_settings() first.")
    return _settings


def init_settings(config_path: str) -> Settings:
    """Initialize global settings from config file."""
    global _settings
    _settings = load_config(config_path)
    return _settings


if __name__ == "__main__":
    # Test the config loader
    args = parse_args()
    config_path = resolve_config_path(args)
    settings = load_config(config_path)
    print_settings(settings, verbose=args.verbose)
    print("✅ Config loaded successfully!")
