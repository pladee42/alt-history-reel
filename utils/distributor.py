"""
distributor.py - Video Distribution

Handles uploading the final video to Google Drive.
"""

import os
from pathlib import Path
from typing import Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class Distributor:
    """Manages video distribution to Google Drive."""
    
    def __init__(self, folder_id: str, credentials_path: Optional[str] = None):
        """
        Initialize Google Drive service.
        
        Args:
            folder_id: ID of the Google Drive folder to upload to
            credentials_path: Path to service account JSON
        """
        self.folder_id = folder_id
        
        # Get credentials path (check Cloud Run path first, then default)
        creds_path = credentials_path or os.getenv("GCP_SA_KEY_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_path:
            raise ValueError("No credentials path found (GCP_SA_KEY_PATH or GOOGLE_APPLICATION_CREDENTIALS)")
        
        # Authenticate
        self.credentials = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        self.service = build('drive', 'v3', credentials=self.credentials)
        
        print(f"🚀 Distributor initialized (Folder ID: {folder_id})")
    
    def upload_video(self, file_path: str, title: str, description: str = "") -> str:
        """
        Upload a video file to Google Drive.
        
        Args:
            file_path: Local path to the video file
            title: Title for the file in Drive
            description: Description/metadata
            
        Returns:
            Review URL (webViewLink) of the uploaded file
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")
        
        print(f"   📤 Uploading to Drive: {title}...")
        
        file_metadata = {
            'name': title,
            'parents': [self.folder_id],
            'description': description
        }
        
        media = MediaFileUpload(
            file_path,
            mimetype='video/mp4',
            resumable=True
        )
        
        try:
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            link = file.get('webViewLink')
            print(f"   ✅ Upload complete: {link}")
            return link
            
        except Exception as e:
            # Check for specific quota error
            error_str = str(e)
            if "storageQuotaExceeded" in error_str:
                print(f"   ⚠️  Drive Upload Skipped: Storage Quota Exceeded.")
                print(f"       (Service Accounts have 0GB quota. Use a Shared Drive or OAuth user credentials.)")
                print(f"       Video is saved locally: {file_path}")
                return None
            else:
                print(f"   ❌ Upload failed: {e}")
                print(f"       Video is saved locally: {file_path}")
                return None


class GCSDistributor:
    """Manages video distribution to Google Cloud Storage."""
    
    def __init__(self, bucket_name: str, credentials_path: Optional[str] = None):
        """
        Initialize GCS client.
        
        Args:
            bucket_name: Name of the GCS bucket
            credentials_path: Path to service account JSON (optional, uses ADC if not provided)
        """
        from google.cloud import storage
        
        self.bucket_name = bucket_name
        
        # Get credentials path (check Cloud Run path first, then default)
        creds_path = credentials_path or os.getenv("GCP_SA_KEY_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if creds_path and os.path.exists(creds_path):
            self.client = storage.Client.from_service_account_json(creds_path)
        else:
            # Use Application Default Credentials (ADC)
            self.client = storage.Client()
        
        self.bucket = self.client.bucket(bucket_name)
        
        print(f"🚀 GCS Distributor initialized (Bucket: {bucket_name})")
    
    def upload_video(self, file_path: str, title: str, description: str = "") -> Optional[str]:
        """
        Upload a video file to GCS.
        
        Args:
            file_path: Local path to the video file
            title: Filename in GCS (e.g., "scenario_xxx.mp4")
            description: Not used for GCS but kept for API compatibility
            
        Returns:
            Public URL of the uploaded file, or None on failure
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")
        
        print(f"   📤 Uploading to GCS: {title}...")
        
        try:
            blob = self.bucket.blob(title)
            blob.upload_from_filename(file_path, content_type='video/mp4')
            
            # For uniform bucket-level access, public access is controlled at bucket level
            # The URL format is: https://storage.googleapis.com/{bucket}/{object}
            public_url = f"https://storage.googleapis.com/{self.bucket_name}/{title}"
            print(f"   ✅ Upload complete: {public_url}")
            return public_url
            
        except Exception as e:
            print(f"   ❌ GCS Upload failed: {e}")
            print(f"       Video is saved locally: {file_path}")
            return None
    
    def upload_folder(self, folder_path: str, scenario_id: str) -> Optional[str]:
        """
        Upload all files in a folder to GCS under assets/{scenario_id}/.
        
        Args:
            folder_path: Local path to the scenario folder
            scenario_id: Unique ID for the scenario (used as GCS prefix)
            
        Returns:
            GCS folder URL, or None on failure
        """
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            print(f"   ⚠️ Folder not found: {folder_path}")
            return None
        
        print(f"   📤 Uploading assets folder to GCS: assets/{scenario_id}/")
        
        uploaded_count = 0
        try:
            # Upload all files in the folder (non-recursive for now)
            for file_path in folder.iterdir():
                if file_path.is_file():
                    # Determine content type
                    suffix = file_path.suffix.lower()
                    content_types = {
                        '.mp4': 'video/mp4',
                        '.mp3': 'audio/mpeg',
                        '.wav': 'audio/wav',
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.json': 'application/json',
                    }
                    content_type = content_types.get(suffix, 'application/octet-stream')
                    
                    # Upload to assets/{scenario_id}/{filename}
                    gcs_path = f"assets/{scenario_id}/{file_path.name}"
                    blob = self.bucket.blob(gcs_path)
                    blob.upload_from_filename(str(file_path), content_type=content_type)
                    uploaded_count += 1
            
            folder_url = f"https://storage.googleapis.com/{self.bucket_name}/assets/{scenario_id}/"
            print(f"   ✅ Uploaded {uploaded_count} files to {folder_url}")
            return folder_url
            
        except Exception as e:
            print(f"   ❌ Folder upload failed: {e}")
            return None


if __name__ == "__main__":
    # Test stub
    print("Distributor module loaded")


class SocialPublisher:
    """Manages publishing to social platforms via serverless-social-uploader."""
    
    def __init__(self, config: dict):
        """
        Initialize SocialPublisher.
        
        Args:
            config: 'publishing' section of the settings
        """
        self.config = config
        self.api_url = os.getenv("SOCIAL_PUBLISHER_API_URL")
        
        if not self.api_url:
            print("   ⚠️  SOCIAL_PUBLISHER_API_URL not set. Publishing disabled.")
        
        # Get template from config, or use default
        self.description_templates = config.get("description_template", ["{title} 🤯"])
        # Ensure it's a list
        if isinstance(self.description_templates, str):
            self.description_templates = [self.description_templates]

    def publish_video(self, video_url: str, scenario: object, dry_run: bool = False) -> bool:
        """
        Publish video to configured platforms.
        
        Args:
            video_url: Public URL of the video
            scenario: Scenario object containing title/metadata
            dry_run: If True, sends dry_run=true to API
            
        Returns:
            True if request accepted/successful, False otherwise
        """
        if not self.config.get("enabled", False):
            return False
            
        if not self.api_url:
            print("   ❌ Publishing failed: API URL missing")
            return False

        import requests
        import random
        
        # 1. Prepare Metadata
        # Remove bold markdown from title if present
        clean_title = scenario.title.replace("**", "").replace("*", "").strip()
        
        # Select a random template
        selected_template = random.choice(self.description_templates)
        
        # Construct final title and description from selected template
        final_description = selected_template.format(title=clean_title)

        # Extract dynamic tags from scenario content (simple keyword matching)
        base_tags = [
            "history", "alternatehistory", "althistory", "whatif",
            "geopolitics", "geography", "mapping", "simulation",
            "documentary", "education", "timeline", "future",
            "shorts", "viral"
        ]
        
        # Keywords to look for in title/location (lowercase for matching)
        keyword_tags = {
            # Countries
            "usa": ["usa", "america", "american", "united states"],
            "russia": ["russia", "russian", "soviet", "ussr", "moscow"],
            "china": ["china", "chinese", "beijing"],
            "japan": ["japan", "japanese", "tokyo"],
            "germany": ["germany", "german", "berlin", "nazi"],
            "uk": ["uk", "britain", "british", "england", "london"],
            "france": ["france", "french", "paris"],
            "india": ["india", "indian"],
            "korea": ["korea", "korean", "pyongyang", "seoul"],
            "mexico": ["mexico", "mexican"],
            "brazil": ["brazil", "brazilian"],
            "italy": ["italy", "italian", "rome"],
            "canada": ["canada", "canadian"],
            "australia": ["australia", "australian"],
            # Topics
            "war": ["war", "invasion", "battle", "military", "army"],
            "ww2": ["ww2", "world war", "wwii", "nazi", "hitler"],
            "coldwar": ["cold war", "soviet", "nuclear"],
            "empire": ["empire", "imperial", "kingdom", "dynasty"],
        }
        
        # Build search text from scenario
        search_text = f"{clean_title} {getattr(scenario, 'location_name', '')} {getattr(scenario, 'premise', '')}".lower()
        
        # Find matching tags
        dynamic_tags = []
        for tag, keywords in keyword_tags.items():
            if any(kw in search_text for kw in keywords):
                dynamic_tags.append(tag)
        
        # Combine base + dynamic (limit to 15 tags for YouTube)
        all_tags = base_tags + dynamic_tags
        all_tags = list(dict.fromkeys(all_tags))[:15]  # Remove duplicates, limit
        
        # Prepare payload
        payload = {
            "channel_id": self.config.get("channel_id"),
            "video_url": video_url,
            "platforms": self.config.get("platforms", []),
            "title": f"{clean_title} 🤯",
            "description": final_description,
            "caption": final_description, # Use same for caption
            "tags": all_tags,
            "ai_generated": True,
            "privacy_status": self.config.get("privacy_status", "private"),
            "category_id": self.config.get("category_id", "27"),
            "share_to_facebook": self.config.get("share_to_facebook", False)
        }
        
        # 2. Send Request
        print(f"\n   🚀 Publishing to Socials ({', '.join(payload['platforms'])})...")
        print(f"      Title: {payload['title']}")
        
        try:
            # Add dry_run query param
            params = {"dry_run": "true"} if dry_run else {}
            
            response = requests.post(
                f"{self.api_url}/publish",
                json=payload,
                params=params,
                timeout=30
            )
            
            if response.status_code in [200, 202]:
                data = response.json()
                print(f"      ✅ Publish request accepted: {data.get('message', 'OK')}")
                return True
            else:
                print(f"      ❌ Publish request failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"      ❌ Publishing error: {e}")
            return False

