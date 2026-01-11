"""
youtube_publisher.py - YouTube Shorts Publisher

Uploads videos to YouTube as Shorts using the YouTube Data API v3.
Includes "Altered content" disclosure for AI-generated content.
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv

from .base_publisher import BasePublisher, PublishResult
from social_metadata import PlatformMetadata

load_dotenv(override=True)


class YouTubePublisher(BasePublisher):
    """
    Publishes videos to YouTube Shorts via Data API v3.
    
    Requirements:
    - Google Cloud Project with YouTube Data API v3 enabled
    - OAuth 2.0 credentials (client_secrets.json)
    - User authorization (one-time browser flow)
    
    AI Disclosure:
    - Adds "Altered content" label via description disclosure
    - Sets appropriate video metadata for AI-generated content
    """
    
    PLATFORM_NAME = "youtube"
    
    # API configuration
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
    
    # YouTube Shorts requirements
    MAX_DURATION_SECONDS = 60
    MAX_TITLE_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 5000
    MAX_TAGS_CHARS = 500
    
    def __init__(self, settings):
        """Initialize YouTube publisher."""
        super().__init__(settings)
        
        self.youtube = None  # API client (initialized on authenticate)
        self._credentials = None
        
        # Get token path from settings
        if self.social_config:
            self.token_path = self.social_config.youtube_token_path
            self.channel_id = self.social_config.youtube_channel_id
        else:
            self.token_path = "secrets/youtube_token.pickle"
            self.channel_id = ""
        
        # Secret Manager secret name (used on Cloud Run)
        self.secret_name = os.getenv('YOUTUBE_TOKEN_SECRET', 'youtube-oauth-token')
    
    def authenticate(self) -> bool:
        """
        Authenticate with YouTube API using OAuth 2.0.
        
        On Cloud Run: Loads credentials from Secret Manager
        Locally: Loads from pickle/json file, or initiates browser OAuth flow
        
        Returns:
            True if authenticated successfully
        """
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            
            # Import our secret manager utility
            from secret_manager import get_oauth_credentials, is_running_on_gcp
            
            credentials = None
            
            # Try loading credentials
            if is_running_on_gcp():
                # On Cloud Run: Load from Secret Manager
                print(f"   ☁️ Loading YouTube credentials from Secret Manager...")
                credentials = get_oauth_credentials(
                    self.secret_name,
                    local_fallback=self.token_path
                )
            else:
                # Local: Try file first, then Secret Manager
                token_file = self._get_token_path(self.token_path)
                
                if token_file and token_file.exists():
                    print(f"   📁 Loading YouTube credentials from local file...")
                    if token_file.suffix == '.pickle':
                        import pickle
                        with open(token_file, 'rb') as f:
                            credentials = pickle.load(f)
                    elif token_file.suffix == '.json':
                        credentials = Credentials.from_authorized_user_file(
                            str(token_file), self.SCOPES
                        )
            
            # Check if credentials were loaded
            if not credentials:
                print("   ⚠️ YouTube credentials not found.")
                if is_running_on_gcp():
                    print(f"   → Ensure secret '{self.secret_name}' exists in Secret Manager")
                else:
                    print(f"   → Run: python scripts/youtube_oauth_setup.py")
                return False
            
            # Refresh if expired
            if credentials.expired and credentials.refresh_token:
                print("   🔄 Refreshing YouTube credentials...")
                credentials.refresh(Request())
                # Save refreshed credentials (only locally)
                if not is_running_on_gcp():
                    token_file = self._get_token_path(self.token_path)
                    if token_file:
                        self._save_credentials(credentials, token_file)
            
            # Validate credentials
            if not credentials.valid and not credentials.refresh_token:
                print("   ❌ YouTube credentials invalid and cannot be refreshed.")
                return False
            
            # Build API client
            self.youtube = build(
                self.API_SERVICE_NAME,
                self.API_VERSION,
                credentials=credentials
            )
            self._credentials = credentials
            self._authenticated = True
            
            print(f"   ✅ YouTube API authenticated")
            return True
            
        except ImportError as e:
            print(f"   ❌ Missing required packages: {e}")
            print("   Install with: pip install google-auth-oauthlib google-api-python-client")
            return False
        except Exception as e:
            print(f"   ❌ YouTube authentication failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _save_credentials(self, credentials, token_file: Path):
        """Save credentials to file."""
        if not token_file:
            return
        
        # Ensure directory exists
        token_file.parent.mkdir(parents=True, exist_ok=True)
        
        if token_file.suffix == '.pickle':
            with open(token_file, 'wb') as f:
                pickle.dump(credentials, f)
        else:
            # Save as JSON
            with open(token_file, 'w') as f:
                json.dump({
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': list(credentials.scopes) if credentials.scopes else [],
                }, f)
    
    def upload(self, video_path: str, metadata: PlatformMetadata) -> PublishResult:
        """
        Upload a video as a YouTube Short with AI disclosure.
        
        Args:
            video_path: Path to the video file
            metadata: YouTube-specific metadata
            
        Returns:
            PublishResult with video URL or error
        """
        # Validate video
        if not self.validate_video(video_path):
            return self._create_result(
                success=False,
                error="Video validation failed"
            )
        
        # Ensure authenticated
        if not self._authenticated:
            if not self.authenticate():
                return self._create_result(
                    success=False,
                    error="Authentication failed"
                )
        
        try:
            from googleapiclient.http import MediaFileUpload
            
            print(f"   📤 Uploading to YouTube Shorts...")
            
            # Build title (ensure #Shorts is included)
            title = self._build_title(metadata)
            
            # Build description with AI disclosure
            description = self._build_description(metadata)
            
            # Build tags (limit to 500 chars total)
            tags = self._build_tags(metadata)
            
            # Video metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'categoryId': '27',  # Education - fits "what if?" history content
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False,
                    'madeForKids': False,
                    'containsSyntheticMedia': True,  # AI-generated content disclosure
                },
            }
            
            # Upload with resumable upload
            media = MediaFileUpload(
                video_path,
                mimetype='video/mp4',
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
            
            # Execute upload
            request = self.youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"   📊 Upload progress: {progress}%")
            
            video_id = response['id']
            video_url = f"https://youtube.com/shorts/{video_id}"
            
            print(f"   ✅ Upload complete: {video_url}")
            
            # Note about AI disclosure
            print(f"   ⚠️  Note: Mark as 'Altered content' in YouTube Studio for full AI disclosure")
            
            return self._create_result(
                success=True,
                url=video_url,
                post_id=video_id,
                ai_label_applied=True,  # Via description disclosure
                title=title,
                channel_id=self.channel_id
            )
            
        except Exception as e:
            error_msg = str(e)
            
            # Handle specific errors
            if 'quotaExceeded' in error_msg:
                error_msg = "YouTube API quota exceeded. Try again tomorrow."
            elif 'forbidden' in error_msg.lower():
                error_msg = "Access forbidden. Check API permissions and channel access."
            
            print(f"   ❌ YouTube upload failed: {error_msg}")
            return self._create_result(
                success=False,
                error=error_msg
            )
    
    def _build_title(self, metadata: PlatformMetadata) -> str:
        """Build YouTube title with #Shorts."""
        title = metadata.title or metadata.description[:80]
        
        # Ensure #Shorts is in title (helps with Shorts classification)
        if '#shorts' not in title.lower():
            # Add #Shorts at end if there's room
            if len(title) + 8 <= self.MAX_TITLE_LENGTH:
                title = f"{title} #Shorts"
            else:
                # Truncate and add #Shorts
                title = f"{title[:self.MAX_TITLE_LENGTH - 9]} #Shorts"
        
        return title[:self.MAX_TITLE_LENGTH]
    
    def _build_description(self, metadata: PlatformMetadata) -> str:
        """Build description with AI disclosure and hashtags."""
        parts = []
        
        # Main description
        if metadata.description:
            parts.append(metadata.description)
        
        # Hashtags (first 3 appear above video title)
        if metadata.hashtags:
            hashtag_str = ' '.join([f"#{h}" for h in metadata.hashtags[:3]])
            parts.append(hashtag_str)
        
        # AI Disclosure (always add for our content)
        ai_disclosure = """
---
🤖 This video contains AI-generated imagery and audio.

This content was created using artificial intelligence and represents an 
imaginary "what if?" scenario. It does not depict real events."""
        
        parts.append(ai_disclosure)
        
        # Channel info
        parts.append(f"\n📺 {self.settings.channel_name if self.settings else 'ChronoReel'}")
        
        description = '\n\n'.join(parts)
        return description[:self.MAX_DESCRIPTION_LENGTH]
    
    def _build_tags(self, metadata: PlatformMetadata) -> list:
        """Build tags list within character limit."""
        tags = []
        char_count = 0
        
        # Start with metadata tags
        all_tags = list(metadata.tags) if metadata.tags else []
        
        # Add hashtags as tags
        all_tags.extend(metadata.hashtags)
        
        # Add default tags
        default_tags = [
            'alternate history', 'what if', 'history', 'shorts',
            'time travel', 'ai generated', 'visualization'
        ]
        all_tags.extend(default_tags)
        
        # Deduplicate while preserving order
        seen = set()
        unique_tags = []
        for tag in all_tags:
            tag_lower = tag.lower()
            if tag_lower not in seen:
                seen.add(tag_lower)
                unique_tags.append(tag)
        
        # Add tags up to character limit
        for tag in unique_tags:
            tag_chars = len(tag) + 1  # +1 for comma separator
            if char_count + tag_chars <= self.MAX_TAGS_CHARS:
                tags.append(tag)
                char_count += tag_chars
            else:
                break
        
        return tags
    
    def get_channel_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the authenticated channel.
        
        Returns:
            Dict with channel info, or None if not authenticated
        """
        if not self._authenticated:
            if not self.authenticate():
                return None
        
        try:
            request = self.youtube.channels().list(
                part='snippet,statistics',
                mine=True
            )
            response = request.execute()
            
            if response.get('items'):
                channel = response['items'][0]
                return {
                    'id': channel['id'],
                    'title': channel['snippet']['title'],
                    'description': channel['snippet'].get('description', ''),
                    'subscriber_count': channel['statistics'].get('subscriberCount', '0'),
                    'video_count': channel['statistics'].get('videoCount', '0'),
                }
            return None
            
        except Exception as e:
            print(f"   ❌ Failed to get channel info: {e}")
            return None


# Convenience function
def create_youtube_publisher(settings) -> YouTubePublisher:
    """Create and authenticate a YouTube publisher."""
    publisher = YouTubePublisher(settings)
    return publisher


if __name__ == "__main__":
    # Test the publisher
    print("\n" + "=" * 50)
    print("🎬 Testing YouTube Publisher")
    print("=" * 50)
    
    from manager import load_config
    
    try:
        settings = load_config("configs/realistic.yaml")
        publisher = YouTubePublisher(settings)
        
        # Test authentication
        if publisher.authenticate():
            # Get channel info
            info = publisher.get_channel_info()
            if info:
                print(f"\n📺 Channel: {info['title']}")
                print(f"   Subscribers: {info['subscriber_count']}")
                print(f"   Videos: {info['video_count']}")
        else:
            print("\n⚠️ Authentication failed. Run OAuth setup first.")
            print("   python scripts/youtube_oauth_setup.py")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
