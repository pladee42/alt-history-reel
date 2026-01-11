"""
base_publisher.py - Abstract Base Class for Publishers

Defines the common interface and shared functionality for all
platform-specific publishers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path

from social_metadata import PlatformMetadata


@dataclass
class PublishResult:
    """Result of a social media publish operation."""
    platform: str  # "instagram", "facebook", "tiktok", "youtube"
    success: bool
    url: Optional[str] = None
    post_id: Optional[str] = None
    error: Optional[str] = None
    ai_label_applied: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        if self.success:
            return f"✅ {self.platform.capitalize()}: {self.url}"
        else:
            return f"❌ {self.platform.capitalize()}: {self.error}"


class BasePublisher(ABC):
    """
    Abstract base class for social media publishers.
    
    All platform-specific publishers should inherit from this class
    and implement the required abstract methods.
    """
    
    PLATFORM_NAME: str = "base"
    
    def __init__(self, settings):
        """
        Initialize the publisher.
        
        Args:
            settings: Application settings object with social config
        """
        self.settings = settings
        self.social_config = settings.social if settings else None
        self._authenticated = False
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the platform API.
        
        Returns:
            True if authentication successful, False otherwise
        """
        pass
    
    @abstractmethod
    def upload(self, video_path: str, metadata: PlatformMetadata) -> PublishResult:
        """
        Upload a video to the platform.
        
        Args:
            video_path: Path to the video file
            metadata: Platform-specific metadata for the video
            
        Returns:
            PublishResult with success/failure status and URL
        """
        pass
    
    def validate_video(self, video_path: str) -> bool:
        """
        Validate that the video file exists and meets basic requirements.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            True if video is valid, False otherwise
        """
        path = Path(video_path)
        
        if not path.exists():
            print(f"   ❌ Video file not found: {video_path}")
            return False
        
        if not path.suffix.lower() in ['.mp4', '.mov']:
            print(f"   ❌ Invalid video format: {path.suffix}")
            return False
        
        # Check file size (max 256MB for most platforms)
        max_size_mb = 256
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            print(f"   ❌ Video too large: {file_size_mb:.1f}MB (max {max_size_mb}MB)")
            return False
        
        return True
    
    def _get_token_path(self, token_file: str) -> Optional[Path]:
        """
        Get the absolute path to a token file.
        
        Args:
            token_file: Relative path to token file
            
        Returns:
            Absolute Path object, or None if not found
        """
        if not token_file:
            return None
        
        # Check if absolute path
        path = Path(token_file)
        if path.is_absolute() and path.exists():
            return path
        
        # Check relative to project root
        if self.settings and self.settings.config_path:
            project_root = Path(self.settings.config_path).parent.parent
            relative_path = project_root / token_file
            if relative_path.exists():
                return relative_path
        
        return None
    
    def _create_result(
        self,
        success: bool,
        url: Optional[str] = None,
        post_id: Optional[str] = None,
        error: Optional[str] = None,
        ai_label_applied: bool = False,
        **kwargs
    ) -> PublishResult:
        """Create a PublishResult with platform name auto-filled."""
        return PublishResult(
            platform=self.PLATFORM_NAME,
            success=success,
            url=url,
            post_id=post_id,
            error=error,
            ai_label_applied=ai_label_applied,
            metadata=kwargs
        )
