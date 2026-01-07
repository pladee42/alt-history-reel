"""
test_editor.py - Test script for Editor module

Verifies video assembly using existing media files.
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List

# Add parent directory to path to allow importing modules
sys.path.append(str(Path(__file__).parent.parent))

# Mock classes to match main.py expectation
@dataclass
class Stage:
    year: str
    label: str
    description: str

@dataclass
class Scenario:
    id: str
    premise: str
    title: str
    stage_1: Stage
    stage_2: Stage
    stage_3: Stage

@dataclass
class VideoClip:
    stage: int
    path: str
    duration: float = 5.0

@dataclass
class AudioClip:
    stage: int
    path: str
    duration: float = 5.0
    mood: str = "test"

# Import Editor
try:
    from editor import assemble_video
    print("✅ Imported assemble_video")
except ImportError as e:
    print(f"❌ Failed to import editor: {e}")
    exit(1)

def run_test():
    # Setup test data using found files
    # UPDATE THIS PATH based on 'find' result
    base_dir = Path("output/test_fixtures") 
    
    if not base_dir.exists():
        print(f"❌ Test directory not found: {base_dir}")
        print("Run tests/create_test_media.py first.")
        return

    print(f"📂 Using media from: {base_dir}")

    # Mock Scenario
    scenario = Scenario(
        id="test_assembly_001",
        premise="What if the test script worked perfectly?",
        title="What if **Test Script** Worked??",
        stage_1=Stage(year="2024", label="The Beginning", description="A peaceful start to the test run."),
        stage_2=Stage(year="2025", label="The Conflict", description="Things get complicated in the middle."),
        stage_3=Stage(year="2030", label="The Resolution", description="A happy ending for the code.")
    )

    # Create Clips
    video_clips = []
    audio_clips = []

    for i in range(1, 4):
        v_path = base_dir / f"video_{i}.mp4"
        a_path = base_dir / f"audio_{i}.mp3"
        
        if v_path.exists():
            video_clips.append(VideoClip(stage=i, path=str(v_path)))
            print(f"   Found video: {v_path.name}")
        else:
            print(f"   ⚠️ Missing video: {v_path.name}")
            
        if a_path.exists():
            audio_clips.append(AudioClip(stage=i, path=str(a_path)))
            print(f"   Found audio: {a_path.name}")
        else:
            print(f"   ⚠️ Missing audio: {a_path.name}")

    if len(video_clips) < 3 or len(audio_clips) < 3:
        print("❌ Not enough media files to test.")
        return

    # Run Assembly
    print("\n🎬 Starting assembly test...")
    try:
        output_path = assemble_video(scenario, video_clips, audio_clips, "output")
        print(f"\n✅ Test Complete! Video saved to: {output_path}")
        
        # Verify file exists
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"   File size: {size_mb:.2f} MB")
        else:
            print("   ❌ Output file reported but not found on disk.")
            
    except Exception as e:
        print(f"\n❌ Assembly Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
