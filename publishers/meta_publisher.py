"""
meta_publisher.py - Meta (Instagram & Facebook) Publisher

Publishes Reels to Instagram Business accounts and Facebook Pages
using the Instagram Graph API and Facebook Graph API.
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from dotenv import load_dotenv

from .base_publisher import BasePublisher, PublishResult
from social_metadata import PlatformMetadata

load_dotenv(override=True)


class MetaPublisher(BasePublisher):
    """
    Publishes Reels to Instagram and Facebook Pages via Graph API.
    
    Requirements:
    - Meta Developer app with Instagram Graph API enabled
    - Instagram Business/Creator account linked to a Facebook Page
    - OAuth authorization with instagram_content_publish permission
    
    AI Disclosure:
    - Instagram: Add disclosure via description text (no API parameter)
    - Users should also use Instagram's "Add AI label" toggle in the app
    """
    
    PLATFORM_NAME = "meta"
    
    # API configuration
    GRAPH_API_VERSION = "v24.0"  # Latest as of Oct 2025
    GRAPH_API_URL = "https://graph.facebook.com/{version}"
    
    # Video requirements
    MAX_DURATION_SECONDS = 90  # Instagram Reels max
    MAX_FILE_SIZE_MB = 100
    SUPPORTED_FORMATS = ['.mp4', '.mov']
    
    def __init__(self, settings):
        """Initialize Meta publisher."""
        super().__init__(settings)
        
        self._user_token = None
        self._page_token = None
        self._page_id = None
        self._instagram_account_id = None
        
        # Get config from settings
        if self.social_config:
            self.token_path = self.social_config.meta_token_path
            self._instagram_account_id = self.social_config.instagram_account_id
            self._page_id = self.social_config.facebook_page_id
        else:
            self.token_path = "secrets/meta_token.json"
        
        # Secret Manager secret name (for Cloud Run)
        self.secret_name = os.getenv('META_TOKEN_SECRET', 'meta-oauth-token')
    
    def authenticate(self) -> bool:
        """
        Load Meta OAuth credentials.
        
        Returns:
            True if credentials loaded successfully
        """
        try:
            from secret_manager import get_secret, is_running_on_gcp
            
            token_data = None
            
            # Try loading credentials
            if is_running_on_gcp():
                print(f"   ☁️ Loading Meta credentials from Secret Manager...")
                token_data = get_secret(
                    self.secret_name,
                    local_fallback=self.token_path,
                    as_json=True
                )
            else:
                # Load from local file
                token_file = self._get_token_path(self.token_path)
                if token_file and token_file.exists():
                    print(f"   📁 Loading Meta credentials from local file...")
                    with open(token_file, 'r') as f:
                        token_data = json.load(f)
            
            if not token_data:
                print("   ⚠️ Meta credentials not found.")
                print(f"   → Run: python scripts/meta_oauth_setup.py")
                return False
            
            # Extract tokens and IDs
            self._user_token = token_data.get('user_access_token')
            self._page_token = token_data.get('page_access_token')
            self._page_id = token_data.get('page_id') or self._page_id
            self._instagram_account_id = token_data.get('instagram_account_id') or self._instagram_account_id
            
            if not self._page_token:
                print("   ❌ No page access token found.")
                return False
            
            # Check token expiry
            expires_at = token_data.get('expires_at', 0)
            if expires_at and time.time() > expires_at - 86400:  # 1 day buffer
                days_left = int((expires_at - time.time()) / 86400)
                print(f"   ⚠️ Token expires in {days_left} days. Consider refreshing.")
            
            self._authenticated = True
            print(f"   ✅ Meta API authenticated")
            
            if self._instagram_account_id:
                print(f"   📸 Instagram Account: {self._instagram_account_id}")
            if self._page_id:
                print(f"   📄 Facebook Page: {self._page_id}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Meta authentication failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def upload_instagram_reel(self, video_url: str, metadata: PlatformMetadata) -> PublishResult:
        """
        Upload a Reel to Instagram.
        
        Note: Video must be on a publicly accessible URL.
        
        Args:
            video_url: Public URL of the video file
            metadata: Instagram-specific metadata
            
        Returns:
            PublishResult with post URL or error
        """
        if not self._authenticated:
            if not self.authenticate():
                return self._create_result(
                    success=False,
                    error="Authentication failed",
                    platform="instagram"
                )
        
        if not self._instagram_account_id:
            return self._create_result(
                success=False,
                error="No Instagram account configured",
                platform="instagram"
            )
        
        try:
            print(f"   📸 Publishing to Instagram Reels...")
            
            # Build caption with AI disclosure
            caption = self._build_instagram_caption(metadata)
            
            # Step 1: Create media container
            container_id = self._create_instagram_container(video_url, caption)
            if not container_id:
                return self._create_result(
                    success=False,
                    error="Failed to create media container",
                    platform="instagram"
                )
            
            print(f"   📦 Container created: {container_id}")
            
            # Step 2: Wait for processing
            print(f"   ⏳ Waiting for video processing...")
            if not self._wait_for_instagram_container(container_id):
                return self._create_result(
                    success=False,
                    error="Video processing failed or timed out",
                    platform="instagram"
                )
            
            # Step 3: Publish the container
            print(f"   📤 Publishing Reel...")
            media_id = self._publish_instagram_container(container_id)
            if not media_id:
                return self._create_result(
                    success=False,
                    error="Failed to publish Reel",
                    platform="instagram"
                )
            
            # Get permalink
            permalink = self._get_instagram_permalink(media_id)
            
            print(f"   ✅ Instagram Reel published: {permalink or media_id}")
            
            return self._create_result(
                success=True,
                url=permalink,
                post_id=media_id,
                ai_label_applied=True,  # Via caption disclosure
                platform="instagram"
            )
            
        except Exception as e:
            print(f"   ❌ Instagram upload failed: {e}")
            return self._create_result(
                success=False,
                error=str(e),
                platform="instagram"
            )
    
    def upload_facebook_reel(self, video_path: str, metadata: PlatformMetadata) -> PublishResult:
        """
        Upload a Reel to Facebook Page.
        
        Args:
            video_path: Path to the video file (will be uploaded directly)
            metadata: Facebook-specific metadata
            
        Returns:
            PublishResult with post URL or error
        """
        if not self._authenticated:
            if not self.authenticate():
                return self._create_result(
                    success=False,
                    error="Authentication failed",
                    platform="facebook"
                )
        
        if not self._page_id:
            return self._create_result(
                success=False,
                error="No Facebook Page configured",
                platform="facebook"
            )
        
        try:
            print(f"   📄 Publishing to Facebook Page Reels...")
            
            # Build description
            description = self._build_facebook_description(metadata)
            
            # Step 1: Initialize upload
            video_id, upload_url = self._init_facebook_reel_upload()
            if not video_id or not upload_url:
                return self._create_result(
                    success=False,
                    error="Failed to initialize upload",
                    platform="facebook"
                )
            
            print(f"   📦 Upload initialized: {video_id}")
            
            # Step 2: Upload video
            print(f"   📤 Uploading video...")
            if not self._upload_facebook_video(upload_url, video_path):
                return self._create_result(
                    success=False,
                    error="Video upload failed",
                    platform="facebook"
                )
            
            # Step 3: Publish the Reel
            print(f"   🚀 Publishing Reel...")
            success = self._publish_facebook_reel(video_id, description)
            if not success:
                return self._create_result(
                    success=False,
                    error="Failed to publish Reel",
                    platform="facebook"
                )
            
            post_url = f"https://www.facebook.com/reel/{video_id}"
            print(f"   ✅ Facebook Reel published: {post_url}")
            
            return self._create_result(
                success=True,
                url=post_url,
                post_id=video_id,
                ai_label_applied=True,
                platform="facebook"
            )
            
        except Exception as e:
            print(f"   ❌ Facebook upload failed: {e}")
            return self._create_result(
                success=False,
                error=str(e),
                platform="facebook"
            )
    
    def upload(self, video_path: str, metadata: PlatformMetadata, 
               platform: str = 'instagram', video_url: str = None) -> PublishResult:
        """
        Upload to specified Meta platform.
        
        Args:
            video_path: Path to the video file
            metadata: Platform-specific metadata
            platform: 'instagram' or 'facebook'
            video_url: Public URL of video (required for Instagram)
        """
        if platform == 'instagram':
            if not video_url:
                return self._create_result(
                    success=False,
                    error="Instagram requires a public video URL",
                    platform="instagram"
                )
            return self.upload_instagram_reel(video_url, metadata)
        elif platform == 'facebook':
            return self.upload_facebook_reel(video_path, metadata)
        else:
            return self._create_result(
                success=False,
                error=f"Unknown platform: {platform}"
            )
    
    # ==========================================
    # Instagram Helper Methods
    # ==========================================
    
    def _create_instagram_container(self, video_url: str, caption: str) -> Optional[str]:
        """Create Instagram media container for Reel."""
        url = f"{self.GRAPH_API_URL.format(version=self.GRAPH_API_VERSION)}/{self._instagram_account_id}/media"
        
        response = requests.post(url, data={
            'access_token': self._page_token,
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
        })
        
        if response.status_code != 200:
            print(f"   ❌ Container creation failed: {response.text}")
            return None
        
        return response.json().get('id')
    
    def _wait_for_instagram_container(self, container_id: str, max_wait: int = 300) -> bool:
        """Wait for Instagram container to finish processing."""
        url = f"{self.GRAPH_API_URL.format(version=self.GRAPH_API_VERSION)}/{container_id}"
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            response = requests.get(url, params={
                'access_token': self._page_token,
                'fields': 'status_code,status',
            })
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status_code')
                
                if status == 'FINISHED':
                    return True
                elif status == 'ERROR':
                    print(f"   ❌ Processing error: {data.get('status')}")
                    return False
            
            time.sleep(5)
        
        return False
    
    def _publish_instagram_container(self, container_id: str) -> Optional[str]:
        """Publish Instagram container."""
        url = f"{self.GRAPH_API_URL.format(version=self.GRAPH_API_VERSION)}/{self._instagram_account_id}/media_publish"
        
        response = requests.post(url, data={
            'access_token': self._page_token,
            'creation_id': container_id,
        })
        
        if response.status_code != 200:
            print(f"   ❌ Publish failed: {response.text}")
            return None
        
        return response.json().get('id')
    
    def _get_instagram_permalink(self, media_id: str) -> Optional[str]:
        """Get permalink for Instagram media."""
        url = f"{self.GRAPH_API_URL.format(version=self.GRAPH_API_VERSION)}/{media_id}"
        
        response = requests.get(url, params={
            'access_token': self._page_token,
            'fields': 'permalink',
        })
        
        if response.status_code == 200:
            return response.json().get('permalink')
        return None
    
    def _build_instagram_caption(self, metadata: PlatformMetadata) -> str:
        """Build Instagram caption with AI disclosure."""
        parts = []
        
        if metadata.description:
            parts.append(metadata.description)
        
        # Add hashtags
        if metadata.hashtags:
            hashtag_str = ' '.join([f"#{h}" for h in metadata.hashtags[:30]])
            parts.append(hashtag_str)
        
        # AI disclosure
        parts.append("\n🤖 This content was created using AI")
        
        caption = '\n\n'.join(parts)
        return caption[:2200]  # Instagram caption limit
    
    # ==========================================
    # Facebook Helper Methods
    # ==========================================
    
    def _init_facebook_reel_upload(self) -> Tuple[Optional[str], Optional[str]]:
        """Initialize Facebook Reel upload session."""
        url = f"{self.GRAPH_API_URL.format(version=self.GRAPH_API_VERSION)}/{self._page_id}/video_reels"
        
        response = requests.post(url, data={
            'access_token': self._page_token,
            'upload_phase': 'start',
        })
        
        if response.status_code != 200:
            print(f"   ❌ Init failed: {response.text}")
            return None, None
        
        data = response.json()
        return data.get('video_id'), data.get('upload_url')
    
    def _upload_facebook_video(self, upload_url: str, video_path: str) -> bool:
        """Upload video to Facebook's upload URL."""
        file_size = Path(video_path).stat().st_size
        
        # Facebook uses rupload.facebook.com for uploads
        with open(video_path, 'rb') as f:
            response = requests.post(
                upload_url,
                data=f,
                headers={
                    'Authorization': f'OAuth {self._page_token}',
                    'offset': '0',
                    'file_size': str(file_size),
                }
            )
        
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"   ❌ Upload failed: {response.status_code} - {response.text}")
            return False
    
    def _publish_facebook_reel(self, video_id: str, description: str) -> bool:
        """Publish Facebook Reel."""
        url = f"{self.GRAPH_API_URL.format(version=self.GRAPH_API_VERSION)}/{self._page_id}/video_reels"
        
        response = requests.post(url, data={
            'access_token': self._page_token,
            'upload_phase': 'finish',
            'video_id': video_id,
            'video_state': 'PUBLISHED',
            'description': description,
        })
        
        if response.status_code != 200:
            print(f"   ❌ Publish failed: {response.text}")
            return False
        
        return response.json().get('success', False)
    
    def _build_facebook_description(self, metadata: PlatformMetadata) -> str:
        """Build Facebook description with AI disclosure."""
        parts = []
        
        if metadata.description:
            parts.append(metadata.description)
        
        # Hashtags
        if metadata.hashtags:
            hashtag_str = ' '.join([f"#{h}" for h in metadata.hashtags[:10]])
            parts.append(hashtag_str)
        
        # AI disclosure
        parts.append("\n🤖 This content was created using AI")
        
        return '\n\n'.join(parts)
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get information about connected accounts."""
        if not self._authenticated:
            if not self.authenticate():
                return None
        
        info = {}
        
        # Get Instagram info
        if self._instagram_account_id:
            url = f"{self.GRAPH_API_URL.format(version=self.GRAPH_API_VERSION)}/{self._instagram_account_id}"
            response = requests.get(url, params={
                'access_token': self._page_token,
                'fields': 'id,username,name,followers_count,media_count',
            })
            if response.status_code == 200:
                info['instagram'] = response.json()
        
        # Get Page info
        if self._page_id:
            url = f"{self.GRAPH_API_URL.format(version=self.GRAPH_API_VERSION)}/{self._page_id}"
            response = requests.get(url, params={
                'access_token': self._page_token,
                'fields': 'id,name,followers_count',
            })
            if response.status_code == 200:
                info['facebook_page'] = response.json()
        
        return info


# Convenience function
def create_meta_publisher(settings) -> MetaPublisher:
    """Create a Meta publisher."""
    return MetaPublisher(settings)


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("📸 Testing Meta Publisher")
    print("=" * 50)
    
    from manager import load_config
    
    try:
        settings = load_config("configs/realistic.yaml")
        publisher = MetaPublisher(settings)
        
        print(f"\n📁 Token path: {publisher.token_path}")
        print(f"🔐 Secret name: {publisher.secret_name}")
        
        # Test authentication
        if publisher.authenticate():
            # Get account info
            info = publisher.get_account_info()
            if info:
                if 'instagram' in info:
                    ig = info['instagram']
                    print(f"\n📸 Instagram: @{ig.get('username', 'N/A')}")
                    print(f"   Followers: {ig.get('followers_count', 0)}")
                if 'facebook_page' in info:
                    fb = info['facebook_page']
                    print(f"\n📄 Facebook Page: {fb.get('name', 'N/A')}")
        else:
            print("\n⚠️ Authentication failed. Run OAuth setup first.")
            print("   python scripts/meta_oauth_setup.py")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
