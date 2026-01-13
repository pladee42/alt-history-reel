
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load Env (for Drive, Sheets API)
load_dotenv(override=True)

from helpers.manager import init_settings
from utils.archivist import Archivist
from utils.editor import Editor
from agents.sound_engineer import AudioClip
from agents.cinematographer import VideoClip
from moviepy import VideoFileClip

def test_editor(scenario_id: str):
    print(f"🔄 Testing Editor for: {scenario_id}")
    
    # 1. Config
    config_path = PROJECT_ROOT / "configs" / "realistic.yaml"
    settings = init_settings(str(config_path))
    scenario_dir = Path(settings.output_dir) / scenario_id
    
    if not scenario_dir.exists():
        print(f"❌ Scenario directory not found: {scenario_dir}")
        return

    # 2. Get Scenario Data
    print(f"📊 Fetching scenario data from Google Sheet...")
    archivist = Archivist(settings.google_sheet_id)
    all_scenarios = archivist.get_all_scenarios()
    scenario = next((s for s in all_scenarios if s.id == scenario_id), None)
    
    if not scenario:
        print(f"❌ Scenario ID {scenario_id} not found in Sheet.")
        return

    print(f"✅ Loaded Scenario Data: {scenario.title}")
    print(f"✅ Loaded Scenario Data: {scenario.title}")


    # 3. Load Video Clips
    video_clips = []
    print("   Checking video files...")
    for i in [1, 2, 3]:
        v_path = scenario_dir / f"video_{i}.mp4"
        if not v_path.exists():
            print(f"   ❌ Missing: {v_path.name}")
            return
        
        # Get duration
        try:
            with VideoFileClip(str(v_path)) as clip:
                dur = clip.duration
        except Exception:
            dur = 5.0
            
        video_clips.append(VideoClip(stage=i, path=str(v_path), duration=dur))

    # 4. Load Audio Clips
    audio_clips = []
    print("   Checking audio files...")
    for i in [1, 2, 3]:
        a_path = scenario_dir / f"audio_{i}.mp3"
        if not a_path.exists():
            print(f"   ⚠️ Missing: {a_path.name} (Will skip audio for this stage)")
        else:
            audio_clips.append(AudioClip(stage=i, path=str(a_path), duration=5.0, mood="Test Mood"))

    # 5. Run Editor
    print(f"\n🎬 Assembling Final Cut...")
    editor = Editor(str(settings.output_dir))
    try:
        final_path = editor.assemble_final_cut(scenario, video_clips, audio_clips)
        
        if final_path:
            print(f"\n✅ SUCCESS! Final video saved at:")
            print(f"{final_path}")
            
            # Auto-open on Mac
            import subprocess
            subprocess.call(["open", final_path])
        else:
            print(f"\n❌ Editor returned None.")
    except Exception as e:
        print(f"\n❌ Editor Crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Editor on existing scenario.")
    parser.add_argument("scenario_id", type=str, help="Scenario ID (e.g. scenario_20260107_...)")
    args = parser.parse_args()
    
    test_editor(args.scenario_id)
