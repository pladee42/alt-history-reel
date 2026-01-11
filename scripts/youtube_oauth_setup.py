#!/usr/bin/env python3
"""
youtube_oauth_setup.py - YouTube OAuth 2.0 Setup Script

This script performs the one-time OAuth flow to authorize the application
to upload videos to your YouTube channel.

Prerequisites:
1. Create a Google Cloud Project at https://console.cloud.google.com
2. Enable the YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop App type)
4. Download the client_secret.json file

Usage:
    python scripts/youtube_oauth_setup.py

This will:
1. Open a browser for you to authorize the app
2. Save the access/refresh tokens to secrets/youtube_token.pickle
3. Display channel info to confirm it's working
"""

import os
import pickle
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)


# Configuration
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
CLIENT_SECRETS_FILE = PROJECT_ROOT / "secrets" / "youtube_client_secret.json"
TOKEN_FILE = PROJECT_ROOT / "secrets" / "youtube_token.pickle"


def main():
    print("\n" + "=" * 60)
    print("🎬 YouTube OAuth 2.0 Setup")
    print("=" * 60)
    
    # Check for required packages
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("\n❌ Missing required packages!")
        print("Install with:")
        print("  pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)
    
    # Check for client secrets file
    if not CLIENT_SECRETS_FILE.exists():
        print(f"\n❌ Client secrets file not found: {CLIENT_SECRETS_FILE}")
        print("\nTo fix this:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth 2.0 Client ID (Desktop App type)")
        print("3. Download the JSON file")
        print(f"4. Save it as: {CLIENT_SECRETS_FILE}")
        sys.exit(1)
    
    # Ensure secrets directory exists
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 Client secrets: {CLIENT_SECRETS_FILE}")
    print(f"📁 Token file: {TOKEN_FILE}")
    
    # Check for existing token
    if TOKEN_FILE.exists():
        print("\n⚠️ Existing token found. Do you want to re-authenticate?")
        response = input("   Type 'yes' to continue, or press Enter to exit: ").strip().lower()
        if response != 'yes':
            print("   Exiting without changes.")
            sys.exit(0)
    
    # Run OAuth flow
    print("\n🔐 Starting OAuth flow...")
    print("   A browser window will open for you to authorize the app.")
    print("   Sign in with the Google account that owns your YouTube channel.")
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRETS_FILE),
            SCOPES
        )
        
        # Run local server for OAuth callback
        credentials = flow.run_local_server(
            port=8080,
            prompt='consent',  # Always show consent screen
            access_type='offline'  # Get refresh token
        )
        
        # Save credentials
        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(credentials, f)
        
        print(f"\n✅ Token saved to: {TOKEN_FILE}")
        
        # Verify by getting channel info
        print("\n🔍 Verifying authentication...")
        youtube = build('youtube', 'v3', credentials=credentials)
        
        request = youtube.channels().list(
            part='snippet,statistics',
            mine=True
        )
        response = request.execute()
        
        if response.get('items'):
            channel = response['items'][0]
            print("\n" + "=" * 60)
            print("✅ SUCCESS! Connected to YouTube channel:")
            print("=" * 60)
            print(f"📺 Channel: {channel['snippet']['title']}")
            print(f"🆔 ID: {channel['id']}")
            print(f"👥 Subscribers: {channel['statistics'].get('subscriberCount', 'N/A')}")
            print(f"🎬 Videos: {channel['statistics'].get('videoCount', 'N/A')}")
            print("=" * 60)
            
            # Update config reminder
            print("\n📝 Next steps:")
            print(f"1. Update configs/realistic.yaml with your channel ID:")
            print(f"   youtube_channel_id: \"{channel['id']}\"")
            print(f"2. Set youtube_enabled: true")
            print(f"3. Run the pipeline to test video upload!")
            
        else:
            print("\n⚠️ Authentication successful but no channel found.")
            print("   Make sure this Google account has a YouTube channel.")
            
    except Exception as e:
        print(f"\n❌ OAuth flow failed: {e}")
        
        if 'redirect_uri_mismatch' in str(e).lower():
            print("\n🔧 Fix: Add http://localhost:8080/ to Authorized redirect URIs")
            print("   in your Google Cloud OAuth client settings.")
        
        sys.exit(1)
    
    print("\n✨ Setup complete!")


if __name__ == "__main__":
    main()
