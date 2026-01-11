"""
tiktok_publisher.py - TikTok Video Publisher

Uploads videos to TikTok using the Content Posting API.
Includes AI-generated content disclosure via the ai_generated parameter.
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv

from .base_publisher import BasePublisher, PublishResult
from social_metadata import PlatformMetadata

load_dotenv(override=True)


class TikTokPublisher(BasePublisher):
    """
    Publishes videos to TikTok via Content Posting API.
    
    Requirements:
    - TikTok for Developers app with Content Posting API enabled
    - OAuth 2.0 authorization with video.publish scope
    - App must be audited by TikTok for public posts (otherwise private only)
    
    AI Disclosure:
    - Uses ai_generated=true parameter for "AI-generated content" label
    """
    
    PLATFORM_NAME = "tiktok"
    
    # API endpoints
    API_BASE = "https://open.tiktokapis.com/v2"
    TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
    
    # Scopes required
    SCOPES = ["video.publish", "video.upload"]
    
    # Video requirements
    MAX_DURATION_SECONDS = 60  # For Shorts-style content
    MAX_FILE_SIZE_MB = 287  # ~4GB total but we limit for Shorts
    SUPPORTED_FORMATS = ['.mp4', '.mov', '.webm']
    
    def __init__(self, settings):
        """Initialize TikTok publisher."""
        super().__init__(settings)
        
        self._access_token = None
        self._refresh_token = None
        self._open_id = None
        
        # Get config from settings
        if self.social_config:
            self.token_path = self.social_config.tiktok_token_path
            self.open_id = self.social_config.tiktok_open_id
        else:
            self.token_path = "secrets/tiktok_token.json"
            self.open_id = ""
        
        # Secret Manager secret name (for Cloud Run)
        self.secret_name = os.getenv('TIKTOK_TOKEN_SECRET', 'tiktok-oauth-token')
        
        # Client credentials (from environment)
        self.client_key = os.getenv('TIKTOK_CLIENT_KEY', '')
        self.client_secret = os.getenv('TIKTOK_CLIENT_SECRET', '')
    
    def authenticate(self) -> bool:
        """
        Load TikTok OAuth credentials.
        
        On Cloud Run: Loads from Secret Manager
        Locally: Loads from JSON file
        
        Returns:
            True if credentials loaded successfully
        """
        try:
            from secret_manager import get_secret, is_running_on_gcp
            
            token_data = None
            
            # Try loading credentials
            if is_running_on_gcp():
                print(f"   ☁️ Loading TikTok credentials from Secret Manager...")
                token_data = get_secret(
                    self.secret_name,
                    local_fallback=self.token_path,
                    as_json=True
                )
            else:
                # Load from local file
                token_file = self._get_token_path(self.token_path)
                if token_file and token_file.exists():
                    print(f"   📁 Loading TikTok credentials from local file...")
                    with open(token_file, 'r') as f:
                        token_data = json.load(f)
            
            if not token_data:
                print("   ⚠️ TikTok credentials not found.")
                if is_running_on_gcp():
                    print(f"   → Ensure secret '{self.secret_name}' exists in Secret Manager")
                else:
                    print(f"   → Run: python scripts/tiktok_oauth_setup.py")
                return False
            
            # Extract tokens
            self._access_token = token_data.get('access_token')
            self._refresh_token = token_data.get('refresh_token')
            self._open_id = token_data.get('open_id') or self.open_id
            
            if not self._access_token:
                print("   ❌ No access token found in credentials.")
                return False
            
            # Check if token needs refresh
            expires_at = token_data.get('expires_at', 0)
            if expires_at and time.time() > expires_at - 300:  # 5 min buffer
                print("   🔄 Refreshing TikTok access token...")
                if not self._refresh_access_token():
                    return False
            
            self._authenticated = True
            print(f"   ✅ TikTok API authenticated")
            return True
            
        except Exception as e:
            print(f"   ❌ TikTok authentication failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token."""
        if not self._refresh_token or not self.client_key or not self.client_secret:
            print("   ❌ Cannot refresh: missing refresh token or client credentials")
            return False
        
        try:
            response = requests.post(
                self.TOKEN_URL,
                data={
                    'client_key': self.client_key,
                    'client_secret': self.client_secret,
                    'grant_type': 'refresh_token',
                    'refresh_token': self._refresh_token,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code != 200:
                print(f"   ❌ Token refresh failed: {response.text}")
                return False
            
            data = response.json()
            if 'access_token' not in data:
                print(f"   ❌ No access token in refresh response")
                return False
            
            self._access_token = data['access_token']
            self._refresh_token = data.get('refresh_token', self._refresh_token)
            self._open_id = data.get('open_id', self._open_id)
            
            # Save updated tokens locally (not on Cloud Run)
            from secret_manager import is_running_on_gcp
            if not is_running_on_gcp():
                self._save_tokens(data)
            
            return True
            
        except Exception as e:
            print(f"   ❌ Token refresh error: {e}")
            return False
    
    def _save_tokens(self, token_data: Dict):
        """Save tokens to local file."""
        token_file = self._get_token_path(self.token_path)
        if token_file:
            token_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Add expiry time
            expires_in = token_data.get('expires_in', 86400)
            token_data['expires_at'] = time.time() + expires_in
            
            with open(token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
    
    def upload(self, video_path: str, metadata: PlatformMetadata, privacy: str = 'public') -> PublishResult:
        """
        Upload a video to TikTok with AI disclosure.
        
        Uses FILE_UPLOAD method for direct upload.
        
        Args:
            video_path: Path to the video file
            metadata: TikTok-specific metadata
            privacy: Privacy level - 'public', 'private', or 'friends'
            
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
            privacy_display = 'PRIVATE' if privacy == 'private' else 'PUBLIC'
            print(f"   📤 Uploading to TikTok ({privacy_display})...")
            
            # Step 1: Initialize upload
            init_response = self._init_upload(video_path, metadata, privacy)
            if not init_response:
                return self._create_result(
                    success=False,
                    error="Failed to initialize upload"
                )
            
            publish_id = init_response.get('publish_id')
            upload_url = init_response.get('upload_url')
            
            if not upload_url:
                return self._create_result(
                    success=False,
                    error="No upload URL received"
                )
            
            # Step 2: Upload video file
            print(f"   📊 Uploading video file...")
            if not self._upload_video_file(upload_url, video_path):
                return self._create_result(
                    success=False,
                    error="Video file upload failed"
                )
            
            # Step 3: Check publish status
            print(f"   ⏳ Processing video...")
            status_result = self._check_publish_status(publish_id)
            
            if status_result.get('status') == 'PUBLISH_COMPLETE':
                video_id = status_result.get('video_id', publish_id)
                video_url = f"https://www.tiktok.com/@{self._open_id}/video/{video_id}"
                
                print(f"   ✅ Upload complete: {video_url}")
                
                return self._create_result(
                    success=True,
                    url=video_url,
                    post_id=video_id,
                    ai_label_applied=True,
                    publish_id=publish_id
                )
            else:
                error = status_result.get('error', 'Unknown publish error')
                return self._create_result(
                    success=False,
                    error=f"Publish failed: {error}"
                )
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ TikTok upload failed: {error_msg}")
            return self._create_result(
                success=False,
                error=error_msg
            )
    
    def _init_upload(self, video_path: str, metadata: PlatformMetadata, privacy: str = 'public') -> Optional[Dict]:
        """Initialize direct upload to TikTok.
        
        Args:
            video_path: Path to video file
            metadata: Platform metadata
            privacy: 'public', 'private', or 'friends'
        """
        
        # Get file size
        file_size = Path(video_path).stat().st_size
        
        # Build caption with hashtags
        caption = self._build_caption(metadata)
        
        # Map privacy levels
        privacy_map = {
            'public': 'PUBLIC_TO_EVERYONE',
            'private': 'SELF_ONLY',
            'friends': 'MUTUAL_FOLLOW_FRIENDS',
        }
        privacy_level = privacy_map.get(privacy.lower(), 'PUBLIC_TO_EVERYONE')
        
        # Prepare request body
        body = {
            'post_info': {
                'title': caption,
                'privacy_level': privacy_level,
                'disable_duet': False,
                'disable_comment': False,
                'disable_stitch': False,
                'video_cover_timestamp_ms': 1000,  # Cover from 1 second
            },
            'source_info': {
                'source': 'FILE_UPLOAD',
                'video_size': file_size,
                'chunk_size': file_size,  # Single chunk for small files
                'total_chunk_count': 1,
            },
            # AI-generated content disclosure
            'ai_generated': True,
        }
        
        try:
            response = requests.post(
                f"{self.API_BASE}/post/publish/video/init/",
                headers={
                    'Authorization': f'Bearer {self._access_token}',
                    'Content-Type': 'application/json; charset=UTF-8',
                },
                json=body
            )
            
            if response.status_code != 200:
                print(f"   ❌ Init upload failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
            
            data = response.json()
            
            if data.get('error', {}).get('code') != 'ok':
                error = data.get('error', {})
                print(f"   ❌ Init error: {error.get('message', 'Unknown error')}")
                return None
            
            return data.get('data', {})
            
        except Exception as e:
            print(f"   ❌ Init upload exception: {e}")
            return None
    
    def _upload_video_file(self, upload_url: str, video_path: str) -> bool:
        """Upload video file to TikTok's upload URL."""
        try:
            file_size = Path(video_path).stat().st_size
            
            with open(video_path, 'rb') as f:
                response = requests.put(
                    upload_url,
                    data=f,
                    headers={
                        'Content-Type': 'video/mp4',
                        'Content-Length': str(file_size),
                        'Content-Range': f'bytes 0-{file_size-1}/{file_size}',
                    }
                )
            
            if response.status_code in [200, 201]:
                return True
            else:
                print(f"   ❌ Upload failed: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"   ❌ File upload exception: {e}")
            return False
    
    def _check_publish_status(self, publish_id: str, max_attempts: int = 30) -> Dict:
        """Check the status of a video publish operation."""
        
        for attempt in range(max_attempts):
            try:
                response = requests.post(
                    f"{self.API_BASE}/post/publish/status/fetch/",
                    headers={
                        'Authorization': f'Bearer {self._access_token}',
                        'Content-Type': 'application/json',
                    },
                    json={'publish_id': publish_id}
                )
                
                if response.status_code != 200:
                    continue
                
                data = response.json()
                status = data.get('data', {}).get('status')
                
                if status == 'PUBLISH_COMPLETE':
                    return {
                        'status': 'PUBLISH_COMPLETE',
                        'video_id': data.get('data', {}).get('video_id')
                    }
                elif status == 'FAILED':
                    return {
                        'status': 'FAILED',
                        'error': data.get('data', {}).get('fail_reason', 'Unknown')
                    }
                
                # Still processing, wait and retry
                time.sleep(2)
                
            except Exception as e:
                print(f"   ⚠️ Status check error: {e}")
                time.sleep(2)
        
        return {'status': 'TIMEOUT', 'error': 'Publish status check timed out'}
    
    def _build_caption(self, metadata: PlatformMetadata) -> str:
        """Build TikTok caption with hashtags."""
        parts = []
        
        # Main description
        if metadata.description:
            parts.append(metadata.description)
        
        # Hashtags
        if metadata.hashtags:
            hashtag_str = ' '.join([f"#{h}" for h in metadata.hashtags[:5]])
            parts.append(hashtag_str)
        
        caption = '\n'.join(parts)
        
        # TikTok caption limit is 4000 chars
        return caption[:4000]
    
    def get_creator_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the authenticated creator."""
        if not self._authenticated:
            if not self.authenticate():
                return None
        
        try:
            response = requests.post(
                f"{self.API_BASE}/post/publish/creator_info/query/",
                headers={
                    'Authorization': f'Bearer {self._access_token}',
                    'Content-Type': 'application/json',
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {})
            
            return None
            
        except Exception as e:
            print(f"   ❌ Failed to get creator info: {e}")
            return None


# Convenience function
def create_tiktok_publisher(settings) -> TikTokPublisher:
    """Create a TikTok publisher."""
    return TikTokPublisher(settings)


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("🎵 Testing TikTok Publisher")
    print("=" * 50)
    
    from manager import load_config
    
    try:
        settings = load_config("configs/realistic.yaml")
        publisher = TikTokPublisher(settings)
        
        print(f"\n📁 Token path: {publisher.token_path}")
        print(f"🔐 Secret name: {publisher.secret_name}")
        
        # Test authentication
        if publisher.authenticate():
            # Get creator info
            info = publisher.get_creator_info()
            if info:
                print(f"\n👤 Creator: {info}")
        else:
            print("\n⚠️ Authentication failed. Run OAuth setup first.")
            print("   python scripts/tiktok_oauth_setup.py")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
