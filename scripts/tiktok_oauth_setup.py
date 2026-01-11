#!/usr/bin/env python3
"""
tiktok_oauth_setup.py - TikTok OAuth 2.0 Setup Script

This script performs the OAuth flow to authorize the application
to upload videos to your TikTok account.

Prerequisites:
1. Create a TikTok for Developers app at https://developers.tiktok.com
2. Add the "Content Posting API" product to your app
3. Enable "Direct Post" in the Content Posting API settings
4. Create secrets/tiktok_client_secret.json with your credentials

Usage:
    python scripts/tiktok_oauth_setup.py

This will:
1. Open a browser for you to authorize the app
2. Save the access/refresh tokens to secrets/tiktok_token.json
"""

import os
import sys
import json
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pathlib import Path

import requests
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(override=True)

# Configuration
CLIENT_SECRETS_FILE = PROJECT_ROOT / "secrets" / "tiktok_client_secret.json"
TOKEN_FILE = PROJECT_ROOT / "secrets" / "tiktok_token.json"
SCOPES = "video.upload,video.publish"

# TikTok OAuth endpoints
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

# Default redirect - will be overridden from client_secret.json
DEFAULT_REDIRECT_URI = "http://localhost:8081/"


class OAuthHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""
    
    authorization_code = None
    
    def do_GET(self):
        """Handle GET request from OAuth callback."""
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        
        if 'code' in query:
            OAuthHandler.authorization_code = query['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>TikTok OAuth Success</title></head>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1>&#10003; Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
            """)
        elif 'error' in query:
            error = query.get('error', ['Unknown'])[0]
            error_desc = query.get('error_description', ['No description'])[0]
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"""
                <html>
                <head><title>TikTok OAuth Error</title></head>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1>&#10007; Authorization Failed</h1>
                    <p>Error: {error}</p>
                    <p>{error_desc}</p>
                </body>
                </html>
            """.encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"OK")
    
    def log_message(self, format, *args):
        """Suppress logging."""
        pass


def load_client_secrets() -> dict:
    """Load client credentials from JSON file."""
    if not CLIENT_SECRETS_FILE.exists():
        return None
    
    with open(CLIENT_SECRETS_FILE, 'r') as f:
        return json.load(f)


def exchange_code_for_token(code: str, client_key: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange authorization code for access token."""
    response = requests.post(
        TOKEN_URL,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'client_key': client_key,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.text}")
    
    return response.json()


def main():
    print("\n" + "=" * 60)
    print("🎵 TikTok OAuth 2.0 Setup")
    print("=" * 60)
    
    # Load client secrets
    secrets = load_client_secrets()
    
    if not secrets:
        print(f"\n❌ Client secrets file not found: {CLIENT_SECRETS_FILE}")
        print("\nCreate this file with the following format:")
        print("""
{
    "client_key": "your_client_key",
    "client_secret": "your_client_secret",
    "redirect_uri": "https://your-ngrok-url.ngrok.io/"
}
        """)
        print("Get these from: https://developers.tiktok.com/apps")
        sys.exit(1)
    
    client_key = secrets.get('client_key')
    client_secret = secrets.get('client_secret')
    redirect_uri = secrets.get('redirect_uri', DEFAULT_REDIRECT_URI)
    
    if not client_key or not client_secret:
        print("\n❌ Missing client_key or client_secret in secrets file!")
        sys.exit(1)
    
    print(f"\n📁 Client secrets: {CLIENT_SECRETS_FILE}")
    print(f"📁 Token will be saved to: {TOKEN_FILE}")
    print(f"🔑 Client Key: {client_key[:8]}...")
    print(f"🔗 Redirect URI: {redirect_uri}")
    
    # Check for existing token
    if TOKEN_FILE.exists():
        print("\n⚠️ Existing token found. Do you want to re-authenticate?")
        response = input("   Type 'yes' to continue, or press Enter to exit: ").strip().lower()
        if response != 'yes':
            print("   Exiting without changes.")
            sys.exit(0)
    
    # Ensure secrets directory exists
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate state for CSRF protection
    import secrets as secrets_module
    state = secrets_module.token_urlsafe(16)
    
    # Build authorization URL
    auth_url = (
        f"{AUTH_URL}?"
        f"client_key={client_key}&"
        f"scope={SCOPES}&"
        f"response_type=code&"
        f"redirect_uri={redirect_uri}&"
        f"state={state}"
    )
    
    print("\n🔐 Starting OAuth flow...")
    print("   A browser window will open for you to authorize the app.")
    print("   Sign in with your TikTok account.")
    
    # Determine if using localhost or external URL
    is_localhost = 'localhost' in redirect_uri or '127.0.0.1' in redirect_uri
    
    if is_localhost:
        # Parse port from redirect URI
        from urllib.parse import urlparse as url_parse
        parsed = url_parse(redirect_uri)
        port = parsed.port or 8081
        
        # Start local server for callback
        server = HTTPServer(('localhost', port), OAuthHandler)
        
        # Open browser
        webbrowser.open(auth_url)
        
        print(f"\n⏳ Waiting for authorization on port {port}...")
        
        # Wait for callback
        while OAuthHandler.authorization_code is None:
            server.handle_request()
        
        code = OAuthHandler.authorization_code
    else:
        # External redirect - user needs to paste the code manually
        print(f"\n🌐 Open this URL in your browser:")
        print(f"   {auth_url}")
        print("\n   After authorization, you'll be redirected.")
        print("   Copy the 'code' parameter from the URL and paste it below.")
        print("\n   Example URL: https://yoursite.com/callback?code=ABC123&state=xyz")
        
        code = input("\n📋 Paste the authorization code: ").strip()
        
        if not code:
            print("❌ No code provided!")
            sys.exit(1)
    
    print(f"   ✅ Authorization code received")
    
    # Exchange code for token
    print("\n🔄 Exchanging code for access token...")
    
    try:
        token_data = exchange_code_for_token(code, client_key, client_secret, redirect_uri)
        
        if 'access_token' not in token_data:
            error = token_data.get('error', 'Unknown error')
            error_desc = token_data.get('error_description', '')
            print(f"❌ No access token in response: {error} - {error_desc}")
            sys.exit(1)
        
        # Add expiry timestamp
        expires_in = token_data.get('expires_in', 86400)
        token_data['expires_at'] = time.time() + expires_in
        
        # Save token
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        print(f"\n✅ Token saved to: {TOKEN_FILE}")
        
        # Display info
        print("\n" + "=" * 60)
        print("✅ SUCCESS! TikTok OAuth complete")
        print("=" * 60)
        print(f"🆔 Open ID: {token_data.get('open_id', 'N/A')}")
        print(f"⏰ Token expires in: {expires_in // 3600} hours")
        print(f"🔄 Refresh token: {'Yes' if token_data.get('refresh_token') else 'No'}")
        
        # Update config reminder
        print("\n📝 Next steps:")
        print(f"1. Update configs/realistic.yaml with:")
        print(f"   tiktok_open_id: \"{token_data.get('open_id', '')}\"")
        print(f"   tiktok_enabled: true")
        print(f"2. For Cloud Run, upload token to Secret Manager:")
        print(f"   gcloud secrets create tiktok-oauth-token --data-file={TOKEN_FILE}")
        
    except Exception as e:
        print(f"\n❌ Token exchange failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n✨ Setup complete!")


if __name__ == "__main__":
    main()
