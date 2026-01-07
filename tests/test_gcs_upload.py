"""
Test script for GCS upload via GCSDistributor.
Uses an existing video file to test upload without running the full pipeline.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

from manager import init_settings
from distributor import GCSDistributor

def test_gcs_upload(scenario_id: str = None):
    """Test GCS upload with an existing video file."""
    
    # 1. Load Settings
    config_path = PROJECT_ROOT / "configs" / "realistic.yaml"
    settings = init_settings(str(config_path))
    
    print(f"📋 Settings Loaded")
    print(f"   GCS Bucket: {settings.gcs_bucket or '(not configured)'}")
    print(f"   Drive Folder ID: {settings.drive_folder_id or '(not configured)'}")
    
    if not settings.gcs_bucket:
        print("\n❌ GCS bucket not configured in configs/realistic.yaml")
        print("   Add: gcs_bucket: \"your-bucket-name\"")
        return
    
    # 2. Find a video file to upload
    output_dir = Path(settings.output_dir)
    
    if scenario_id:
        video_path = output_dir / scenario_id / "final_cut.mp4"
    else:
        # Find the first available final_cut.mp4
        video_path = None
        for scenario_dir in output_dir.iterdir():
            if scenario_dir.is_dir():
                candidate = scenario_dir / "final_cut.mp4"
                if candidate.exists():
                    video_path = candidate
                    scenario_id = scenario_dir.name
                    break
    
    if not video_path or not video_path.exists():
        print(f"❌ No video file found to test with.")
        print(f"   Looking in: {output_dir}")
        return
    
    print(f"   Video File: {video_path}")
    print(f"   File Size: {video_path.stat().st_size / (1024*1024):.2f} MB")
    
    # 3. Attempt Upload
    print(f"\n🚀 Attempting GCS Upload...")
    
    try:
        distributor = GCSDistributor(settings.gcs_bucket)
        
        # Upload with scenario ID as filename
        public_url = distributor.upload_video(
            str(video_path),
            title=f"TEST_{scenario_id}.mp4",
            description="Test upload from test_gcs_upload.py"
        )
        
        if public_url:
            print(f"\n✅ SUCCESS! Video uploaded to GCS.")
            print(f"   Public URL: {public_url}")
            print(f"\n📱 Open this URL on your phone to verify playback!")
        else:
            print(f"\n⚠️ Upload returned None (check error messages above)")
            
    except Exception as e:
        print(f"\n❌ EXCEPTION during upload:")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {e}")
        
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test GCS upload")
    parser.add_argument("--scenario", type=str, default=None, 
                        help="Scenario ID to use (optional, will auto-detect)")
    args = parser.parse_args()
    
    test_gcs_upload(args.scenario)
