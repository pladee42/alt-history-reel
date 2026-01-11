"""
secret_manager.py - Google Secret Manager Utility

Provides unified access to secrets, supporting both:
- Local file-based secrets (for development)
- Google Secret Manager (for Cloud Run deployment)

Automatically detects environment and loads secrets accordingly.
"""

import os
import pickle
import json
from pathlib import Path
from typing import Optional, Union, Any

from dotenv import load_dotenv

load_dotenv(override=True)


def is_running_on_gcp() -> bool:
    """
    Detect if running on Google Cloud (Cloud Run, Cloud Functions, GCE, etc.)
    
    Returns:
        True if running on GCP, False otherwise
    """
    # Cloud Run sets these environment variables
    gcp_indicators = [
        'K_SERVICE',           # Cloud Run service name
        'K_REVISION',          # Cloud Run revision
        'GOOGLE_CLOUD_PROJECT', # GCP project
        'GCP_PROJECT',         # Alternative GCP project var
        'GCLOUD_PROJECT',      # Another alternative
    ]
    
    return any(os.getenv(var) for var in gcp_indicators)


def get_gcp_project_id() -> Optional[str]:
    """Get the current GCP project ID."""
    # Try environment variables first
    for var in ['GOOGLE_CLOUD_PROJECT', 'GCP_PROJECT', 'GCLOUD_PROJECT']:
        project = os.getenv(var)
        if project:
            return project
    
    # Try metadata server (works on GCP)
    try:
        import requests
        response = requests.get(
            'http://metadata.google.internal/computeMetadata/v1/project/project-id',
            headers={'Metadata-Flavor': 'Google'},
            timeout=1
        )
        if response.status_code == 200:
            return response.text
    except:
        pass
    
    return None


class SecretManager:
    """
    Unified secret access for local and Cloud Run environments.
    
    Usage:
        sm = SecretManager()
        
        # Load a secret (auto-detects environment)
        token = sm.get_secret('youtube-oauth-token')
        
        # Or with explicit fallback to local file
        token = sm.get_secret('youtube-oauth-token', 
                             local_fallback='secrets/youtube_token.pickle')
    """
    
    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize SecretManager.
        
        Args:
            project_id: GCP project ID. Auto-detected if not provided.
        """
        self.project_id = project_id or get_gcp_project_id()
        self._client = None
        self._on_gcp = is_running_on_gcp()
    
    @property
    def client(self):
        """Lazy-load Secret Manager client."""
        if self._client is None and self._on_gcp:
            try:
                from google.cloud import secretmanager
                self._client = secretmanager.SecretManagerServiceClient()
            except ImportError:
                print("⚠️ google-cloud-secret-manager not installed")
                self._client = False  # Mark as unavailable
        return self._client
    
    def get_secret(
        self,
        secret_name: str,
        local_fallback: Optional[str] = None,
        version: str = "latest",
        as_pickle: bool = False,
        as_json: bool = False,
    ) -> Optional[Union[str, bytes, dict, Any]]:
        """
        Get a secret value.
        
        Priority:
        1. If on GCP and Secret Manager available → load from Secret Manager
        2. If local_fallback provided → load from local file
        3. Return None
        
        Args:
            secret_name: Name of the secret in Secret Manager
            local_fallback: Local file path to use as fallback
            version: Secret version (default: "latest")
            as_pickle: If True, unpickle the secret data
            as_json: If True, parse as JSON
            
        Returns:
            Secret value (string, bytes, dict, or unpickled object)
        """
        # Try Secret Manager first (if on GCP)
        if self._on_gcp and self.client and self.project_id:
            try:
                secret_data = self._get_from_secret_manager(secret_name, version)
                if secret_data is not None:
                    return self._parse_secret(secret_data, as_pickle, as_json)
            except Exception as e:
                print(f"⚠️ Secret Manager access failed for '{secret_name}': {e}")
        
        # Try local fallback
        if local_fallback:
            local_data = self._get_from_local_file(local_fallback)
            if local_data is not None:
                return self._parse_secret(local_data, as_pickle, as_json)
        
        return None
    
    def _get_from_secret_manager(self, secret_name: str, version: str) -> Optional[bytes]:
        """Fetch secret from Google Secret Manager."""
        if not self.client or not self.project_id:
            return None
        
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data
        except Exception as e:
            # Secret might not exist
            if 'NOT_FOUND' in str(e):
                print(f"   Secret '{secret_name}' not found in Secret Manager")
            else:
                print(f"   Error accessing secret: {e}")
            return None
    
    def _get_from_local_file(self, file_path: str) -> Optional[bytes]:
        """Load secret from local file."""
        path = Path(file_path)
        
        # Handle relative paths
        if not path.is_absolute():
            # Try relative to project root
            project_root = Path(__file__).parent
            path = project_root / file_path
        
        if not path.exists():
            return None
        
        return path.read_bytes()
    
    def _parse_secret(
        self,
        data: bytes,
        as_pickle: bool,
        as_json: bool
    ) -> Union[str, bytes, dict, Any]:
        """Parse secret data based on requested format."""
        if as_pickle:
            return pickle.loads(data)
        elif as_json:
            return json.loads(data.decode('utf-8'))
        else:
            # Try to decode as string, fall back to bytes
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                return data
    
    def secret_exists(self, secret_name: str) -> bool:
        """Check if a secret exists in Secret Manager."""
        if not self.client or not self.project_id:
            return False
        
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.get_secret(request={"name": name})
            return True
        except:
            return False


# Module-level singleton for convenience
_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """Get the global SecretManager instance."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


def get_secret(
    secret_name: str,
    local_fallback: Optional[str] = None,
    **kwargs
) -> Optional[Union[str, bytes, dict, Any]]:
    """Convenience function to get a secret."""
    return get_secret_manager().get_secret(secret_name, local_fallback, **kwargs)


def get_oauth_credentials(
    secret_name: str,
    local_fallback: Optional[str] = None
):
    """
    Load OAuth credentials from Secret Manager or local file.
    
    Returns:
        google.oauth2.credentials.Credentials object, or None
    """
    data = get_secret(secret_name, local_fallback, as_pickle=True)
    
    if data is None:
        return None
    
    # If it's already a Credentials object (from pickle)
    if hasattr(data, 'token'):
        return data
    
    # If it's a dict (from JSON format)
    if isinstance(data, dict):
        try:
            from google.oauth2.credentials import Credentials
            return Credentials(
                token=data.get('token'),
                refresh_token=data.get('refresh_token'),
                token_uri=data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=data.get('client_id'),
                client_secret=data.get('client_secret'),
                scopes=data.get('scopes'),
            )
        except Exception as e:
            print(f"   ❌ Failed to create credentials from dict: {e}")
            return None
    
    return data


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("🔐 Secret Manager Utility Test")
    print("=" * 50)
    
    print(f"\n📍 Running on GCP: {is_running_on_gcp()}")
    print(f"📁 Project ID: {get_gcp_project_id()}")
    
    sm = SecretManager()
    
    # Test local fallback
    print("\n🧪 Testing local fallback...")
    result = sm.get_secret(
        "test-secret",
        local_fallback="secrets/youtube_token.pickle",
        as_pickle=True
    )
    if result:
        print(f"   ✅ Loaded credentials: {type(result)}")
    else:
        print("   ⚠️ No local token found (this is expected if not set up)")
