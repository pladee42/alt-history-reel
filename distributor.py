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
        
        # Get credentials path
        creds_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not found")
        
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

if __name__ == "__main__":
    # Test stub
    print("Distributor module loaded")
