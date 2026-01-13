
import os
import sys
import yaml
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from helpers.manager import init_settings, get_settings
from utils.archivist import Archivist
from agents.sound_engineer import generate_audio
from agents.cinematographer import VideoClip
from utils.editor import Editor
from moviepy import VideoFileClip

def resume_run(scenario_id: str):
    print(f"🔄 Resuming run for: {scenario_id}")
    
    # 1. Initialize Settings
    config_path = PROJECT_ROOT / "configs" / "realistic.yaml" # Defaulting to realistic
    settings = init_settings(str(config_path))
    
    # 2. Retrieve Scenario from Sheet
    print(f"📊 Fetching scenario data from Google Sheet...")
    archivist = Archivist(settings.google_sheet_id)
    all_scenarios = archivist.get_all_scenarios()
    
    target_scenario = None
    for s in all_scenarios:
        if s.id == scenario_id:
            target_scenario = s
            break
            
    if not target_scenario:
        print(f"❌ Scenario {scenario_id} not found in Google Sheet.")
        return
        
    print(f"✅ Loaded Scenario: {target_scenario.premise}")
    
    # 3. Verify Existing Video Clips
    scenario_dir = Path(settings.output_dir) / scenario_id
    if not scenario_dir.exists():
        print(f"❌ Scenario directory not found: {scenario_dir}")
        return
        
    video_clips = []
    for stage_num in [1, 2, 3]:
        video_path = scenario_dir / f"video_{stage_num}.mp4"
        if not video_path.exists():
            print(f"❌ Missing video clip: {video_path}")
            return
            
        # Get duration
        try:
            with VideoFileClip(str(video_path)) as clip:
                duration = clip.duration
        except Exception as e:
            print(f"⚠️ Could not read duration for {video_path}: {e}")
            duration = 5.0 # Default fallback
            
        video_clips.append(VideoClip(
            stage=stage_num,
            path=str(video_path),
            duration=duration
        ))
        
    print(f"✅ Verified {len(video_clips)} video clips")
    
    # 4. Generate Audio (Phase 4 - Retry)
    print("\n🔊 Step 2: Generating sound effects (Retry)...")
    try:
        # Note: generate_audio expects scenario, output_dir
        audio_clips = generate_audio(target_scenario, str(settings.output_dir))
    except Exception as e:
        print(f"❌ Audio generation failed again: {e}")
        return

    # 5. Assemble Final Cut (Phase 5)
    print("\n🎬 Step 3: Assembling final cut...")
    editor = Editor(str(settings.output_dir))
    final_video = editor.assemble_final_cut(target_scenario, video_clips, audio_clips)
    
    if final_video:
        print(f"\n✅ Video Assembly Complete: {final_video}")
        
        # 6. Update Status
        archivist.update_status(scenario_id, "DONE", video_url=final_video)
        print("📝 Updated status in Google Sheet to DONE")
    else:
        print("\n❌ Video Assembly Failed")

if __name__ == "__main__":
    SCENARIO_ID = "scenario_20260107_171147"
    resume_run(SCENARIO_ID)
