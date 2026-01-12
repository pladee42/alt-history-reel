#!/usr/bin/env python3
"""
meta_oauth_setup.py - Meta/Instagram/Facebook OAuth 2.0 Setup Script

This script performs the OAuth flow to authorize the application
to publish Reels to Instagram Business and Facebook Pages.

Prerequisites:
1. Create a Meta Developer app at https://developers.facebook.com
2. Add Instagram Graph API and Facebook Login products
3. Create secrets/meta_client_secret.json with your credentials
4. Have an Instagram Business/Creator account linked to a Facebook Page

Usage:
    python scripts/meta_oauth_setup.py

This will:
1. Open a browser for you to authorize the app
2. Exchange the code for access tokens
3. Get long-lived token and Page access token
4. Save tokens to secrets/meta_token.json
"""

import os
import sys
import json
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, urlencode
from pathlib import Path

import requests
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(override=True)

# Configuration
CLIENT_SECRETS_FILE = PROJECT_ROOT / "secrets" / "meta_client_secret.json"
TOKEN_FILE = PROJECT_ROOT / "secrets" / "meta_token.json"

# Meta OAuth endpoints
GRAPH_API_VERSION = "v24.0"  # Latest as of Oct 2025
AUTH_URL = "https://www.facebook.com/{version}/dialog/oauth"
TOKEN_URL = "https://graph.facebook.com/{version}/oauth/access_token"
GRAPH_API_URL = "https://graph.facebook.com/{version}"

# Required scopes for Instagram Reels and Facebook Page Reels
SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "business_management",
]

# Default redirect
DEFAULT_REDIRECT_URI = "http://localhost:8082/"


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
                <head><title>Meta OAuth Success</title></head>
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
                <head><title>Meta OAuth Error</title></head>
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


def exchange_code_for_token(code: str, app_id: str, app_secret: str, redirect_uri: str) -> dict:
    """Exchange authorization code for short-lived access token."""
    url = TOKEN_URL.format(version=GRAPH_API_VERSION)
    
    response = requests.get(url, params={
        'client_id': app_id,
        'client_secret': app_secret,
        'redirect_uri': redirect_uri,
        'code': code,
    })
    
    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.text}")
    
    return response.json()


def get_long_lived_token(short_token: str, app_id: str, app_secret: str) -> dict:
    """Exchange short-lived token for long-lived token (60 days)."""
    url = TOKEN_URL.format(version=GRAPH_API_VERSION)
    
    response = requests.get(url, params={
        'grant_type': 'fb_exchange_token',
        'client_id': app_id,
        'client_secret': app_secret,
        'fb_exchange_token': short_token,
    })
    
    if response.status_code != 200:
        raise Exception(f"Long-lived token exchange failed: {response.text}")
    
    return response.json()


def get_user_pages(access_token: str) -> list:
    """Get list of Facebook Pages the user manages."""
    url = f"{GRAPH_API_URL.format(version=GRAPH_API_VERSION)}/me/accounts"
    
    response = requests.get(url, params={
        'access_token': access_token,
        'fields': 'id,name,access_token,instagram_business_account',
    })
    
    if response.status_code != 200:
        raise Exception(f"Failed to get pages: {response.text}")
    
    return response.json().get('data', [])


def get_instagram_account(page_id: str, page_token: str) -> dict:
    """Get Instagram Business Account connected to a Page."""
    url = f"{GRAPH_API_URL.format(version=GRAPH_API_VERSION)}/{page_id}"
    
    response = requests.get(url, params={
        'access_token': page_token,
        'fields': 'instagram_business_account{id,username,name,profile_picture_url}',
    })
    
    if response.status_code != 200:
        return None
    
    data = response.json()
    return data.get('instagram_business_account')


def main():
    print("\n" + "=" * 60)
    print("📸 Meta/Instagram OAuth 2.0 Setup")
    print("=" * 60)
    
    # Load client secrets
    secrets = load_client_secrets()
    
    if not secrets:
        print(f"\n❌ Client secrets file not found: {CLIENT_SECRETS_FILE}")
        print("\nCreate this file with the following format:")
        print("""
{
    "app_id": "your_app_id",
    "app_secret": "your_app_secret",
    "redirect_uri": "http://localhost:8082/"
}
        """)
        print("Get these from: https://developers.facebook.com/apps")
        sys.exit(1)
    
    app_id = secrets.get('app_id')
    app_secret = secrets.get('app_secret')
    redirect_uri = secrets.get('redirect_uri', DEFAULT_REDIRECT_URI)
    
    if not app_id or not app_secret:
        print("\n❌ Missing app_id or app_secret in secrets file!")
        sys.exit(1)
    
    print(f"\n📁 Client secrets: {CLIENT_SECRETS_FILE}")
    print(f"📁 Token will be saved to: {TOKEN_FILE}")
    print(f"🔑 App ID: {app_id}")
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
    
    # Build authorization URL
    scope_str = ','.join(SCOPES)
    
    auth_params = {
        'client_id': app_id,
        'redirect_uri': redirect_uri,
        'scope': scope_str,
        'response_type': 'code',
        'state': 'timeline_b_auth',
    }
    
    auth_url = f"{AUTH_URL.format(version=GRAPH_API_VERSION)}?{urlencode(auth_params)}"
    
    print("\n🔐 Starting OAuth flow...")
    print("   A browser window will open for you to authorize the app.")
    print("   Log in with your Facebook account and grant permissions.")
    
    # Determine if using localhost
    is_localhost = 'localhost' in redirect_uri or '127.0.0.1' in redirect_uri
    
    if is_localhost:
        # Parse port from redirect URI
        parsed = urlparse(redirect_uri)
        port = parsed.port or 8082
        
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
        print("\n   After authorization, copy the 'code' parameter from the redirect URL.")
        
        code = input("\n📋 Paste the authorization code: ").strip()
        
        if not code:
            print("❌ No code provided!")
            sys.exit(1)
    
    print(f"   ✅ Authorization code received")
    
    # Exchange code for short-lived token
    print("\n🔄 Exchanging code for access token...")
    
    try:
        # Get short-lived token
        token_data = exchange_code_for_token(code, app_id, app_secret, redirect_uri)
        short_token = token_data.get('access_token')
        
        if not short_token:
            print(f"❌ No access token in response: {token_data}")
            sys.exit(1)
        
        print("   ✅ Short-lived token received")
        
        # Exchange for long-lived token
        print("\n🔄 Getting long-lived token (60 days)...")
        long_token_data = get_long_lived_token(short_token, app_id, app_secret)
        long_token = long_token_data.get('access_token')
        expires_in = long_token_data.get('expires_in', 5184000)  # Default 60 days
        
        print(f"   ✅ Long-lived token received (expires in {expires_in // 86400} days)")
        
        # Get user's Pages
        print("\n📄 Fetching your Facebook Pages...")
        pages = get_user_pages(long_token)
        
        if not pages:
            print("   ⚠️ No Facebook Pages found!")
            print("   Make sure you have admin access to at least one Page.")
        else:
            print(f"   Found {len(pages)} Page(s):")
            for i, page in enumerate(pages):
                print(f"   {i+1}. {page['name']} (ID: {page['id']})")
                
                # Check for connected Instagram
                ig_account = page.get('instagram_business_account')
                if ig_account:
                    print(f"      └── Instagram: {ig_account.get('id', 'N/A')}")
        
        # Let user select a page if multiple
        selected_page = None
        if len(pages) == 1:
            selected_page = pages[0]
        elif len(pages) > 1:
            print("\n📝 Select a Page to use (enter number):")
            try:
                choice = int(input("   > ").strip()) - 1
                if 0 <= choice < len(pages):
                    selected_page = pages[choice]
            except:
                selected_page = pages[0]
        
        # Get Instagram account details
        instagram_account = None
        if selected_page:
            ig_data = get_instagram_account(selected_page['id'], selected_page['access_token'])
            if ig_data:
                instagram_account = ig_data
                print(f"\n📸 Instagram Business Account:")
                print(f"   ID: {ig_data.get('id')}")
                print(f"   Username: @{ig_data.get('username', 'N/A')}")
        
        # Prepare token data to save
        save_data = {
            'user_access_token': long_token,
            'expires_at': time.time() + expires_in,
            'expires_in': expires_in,
            'pages': pages,
        }
        
        if selected_page:
            save_data['page_id'] = selected_page['id']
            save_data['page_name'] = selected_page['name']
            save_data['page_access_token'] = selected_page['access_token']
        
        if instagram_account:
            save_data['instagram_account_id'] = instagram_account.get('id')
            save_data['instagram_username'] = instagram_account.get('username')
        
        # Save token
        with open(TOKEN_FILE, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"\n✅ Token saved to: {TOKEN_FILE}")
        
        # Display summary
        print("\n" + "=" * 60)
        print("✅ SUCCESS! Meta OAuth complete")
        print("=" * 60)
        
        if selected_page:
            print(f"📄 Facebook Page: {selected_page['name']}")
            print(f"   Page ID: {selected_page['id']}")
        
        if instagram_account:
            print(f"📸 Instagram: @{instagram_account.get('username', 'N/A')}")
            print(f"   Account ID: {instagram_account.get('id')}")
        
        print(f"⏰ Token expires: {expires_in // 86400} days")
        
        # Config update reminder
        print("\n📝 Next steps:")
        print("1. Update configs/realistic.yaml with:")
        if selected_page:
            print(f"   facebook_page_id: \"{selected_page['id']}\"")
        if instagram_account:
            print(f"   instagram_account_id: \"{instagram_account.get('id')}\"")
        print("2. For Cloud Run, upload token to Secret Manager:")
        print(f"   gcloud secrets create meta-oauth-token --data-file={TOKEN_FILE}")
        
    except Exception as e:
        print(f"\n❌ OAuth failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n✨ Setup complete!")


if __name__ == "__main__":
    main()
