"""
main.py - ChronoReel Entry Point

Orchestrates the Alternative History video generation pipeline.
Run with: python main.py --style realistic
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers.manager import parse_args, init_settings, print_settings, resolve_config_path


def backup_to_gcs(settings, scenario_id: str, step_name: str = ""):
    """
    Backup current scenario folder to GCS after each major step.
    This enables recovery if the pipeline fails mid-way.
    """
    if not settings.gcs_bucket:
        return  # No GCS configured
    
    try:
        from pathlib import Path
        from utils.distributor import GCSDistributor
        
        scenario_folder = Path(settings.output_dir) / scenario_id
        if not scenario_folder.exists():
            return
        
        distributor = GCSDistributor(settings.gcs_bucket)
        print(f"   ☁️ Backing up assets to GCS ({step_name})...")
        distributor.upload_folder(str(scenario_folder), scenario_id)
    except Exception as e:
        print(f"   ⚠️ GCS backup failed (non-fatal): {e}")


def run_phase_1(settings, dry_run: bool = False):
    """Phase 1: Config verification (already complete if we got here)."""
    print("✅ Phase 1: Configuration loaded and verified")
    return True


def run_phase_2(settings, dry_run: bool = False):
    """Phase 2: Generate scenario and static keyframes with Vision Gate."""
    print("🎨 Phase 2: Generating scenario and static keyframes...")
    
    if dry_run:
        print("   [DRY RUN] Would generate scenario with Gemini")
        print("   [DRY RUN] Would store in Google Sheets")
        print("   [DRY RUN] Would generate 3 keyframes with Fal.ai")
        print("   [DRY RUN] Would verify with Gemini Vision Gate")
        return True
    
    from agents.screenwriter import generate_scenario
    from utils.archivist import Archivist
    from agents.art_department import ArtDepartment
    from agents.prompt_improver import PromptImprover
    
    # Initialize archivist early for duplicate checking
    archivist = Archivist(settings.google_sheet_id)
    
    # Get existing premises to avoid duplicates
    existing_scenarios = archivist.get_all_scenarios()
    existing_premises = [s.premise for s in existing_scenarios]
    print(f"   📚 Found {len(existing_premises)} existing scenarios to avoid")
    
    # Step 1: Generate a new scenario (with duplicate retry)
    print("\n📝 Step 1: Generating scenario...")
    scenario = None
    max_scenario_tries = 5
    
    for attempt in range(1, max_scenario_tries + 1):
        scenario = generate_scenario(avoid_premises=existing_premises)
        
        # Step 2: Try to store in Google Sheets (with duplicate check)
        print(f"\n📊 Step 2: Storing in Google Sheets (attempt {attempt}/{max_scenario_tries})...")
        
        if archivist.store_scenario(scenario):
            break  # Success!
        else:
            print("   🔄 Duplicate found, generating new scenario...")
            existing_premises.append(scenario.premise)  # Add to avoid list
            scenario = None
            if attempt == max_scenario_tries:
                print(f"   ❌ Failed to generate unique scenario after {max_scenario_tries} attempts")
                return False
    
    # Step 2.5: Improve prompts (Quality Enhancement)
    try:
        improver = PromptImprover(settings)
        scenario = improver.improve_scenario(scenario)
        # Save improved data (Title, Prompts) to Sheet
        archivist.update_full_scenario(scenario)
    except Exception as e:
        print(f"   ⚠️ Prompt Improver failed (skipping): {e}")

    # Step 3: Generate keyframes with Vision Gate
    print("\n🖼️ Step 3: Generating keyframes...")
    art = ArtDepartment(settings)
    keyframes = art.generate_with_retries(scenario, max_retries=settings.image_retries)
    
    if not keyframes:
        print("   ❌ Failed to generate consistent keyframes")
        archivist.update_status(scenario.id, "FAILED")
        return False
    
    # Update status
    archivist.update_status(scenario.id, "IMAGES_DONE")
    
    # Backup images to GCS
    backup_to_gcs(settings, scenario.id, "images")
    
    # Store keyframes info for Phase 3
    settings._current_scenario = scenario
    settings._current_keyframes = keyframes
    
    print("\n✅ Phase 2 complete!")
    return True


def run_phase_3(settings, dry_run: bool = False):
    """Phase 3: Animate keyframes into video clips."""
    print("🎬 Phase 3: Animating keyframes...")
    
    if dry_run:
        print("   [DRY RUN] Would animate with Fal.ai (Cinematographer)")
        print("   [DRY RUN] Would generate audio with Fal.ai (Sound Engineer)")
        return True
    
    # Retrieve context from Phase 2
    scenario = getattr(settings, '_current_scenario', None)
    keyframes = getattr(settings, '_current_keyframes', None)
    
    if not scenario or not keyframes:
        print("   ❌ Context missing (Phase 2 did not run or failed). Cannot run Phase 3 standalone yet.")
        return False
        
    from agents.cinematographer import animate_keyframes
    from agents.sound_engineer import generate_audio
    from utils.archivist import Archivist
    
    output_dir = settings.output_dir
    
    # Step 1: Animate Keyframes (Image-to-Video)
    print("\n🎥 Step 1: Generating video clips...")
    try:
        video_clips = animate_keyframes(keyframes, scenario, output_dir)
    except Exception as e:
        print(f"   ❌ Animation failed: {e}")
        return False
        
    # Step 2: Generate Audio (Sound Effects)
    print("\n🔊 Step 2: Generating sound effects...")
    try:
        audio_clips = generate_audio(scenario, output_dir)
    except Exception as e:
        print(f"   ❌ Audio generation failed: {e}")
        return False
        
    # Store results for Phase 4
    settings._current_video_clips = video_clips
    settings._current_audio_clips = audio_clips
    
    # Update status
    archivist = Archivist(settings.google_sheet_id)
    archivist.update_status(scenario.id, "ANIMATION_DONE")
    
    # Backup videos and audio to GCS
    backup_to_gcs(settings, scenario.id, "videos+audio")
    
    print("\n✅ Phase 3 complete!")
    return True


def run_phase_4(settings, dry_run: bool = False):
    """Phase 4: Assemble and distribute final video."""
    print("📦 Phase 4: Assembling final video...")
    
    if dry_run:
        print("   [DRY RUN] Would stitch clips with MoviePy")
        print("   [DRY RUN] Would upload to Google Drive")
        return True
    
    # Retrieve context from Phase 3
    scenario = getattr(settings, '_current_scenario', None)
    video_clips = getattr(settings, '_current_video_clips', None)
    audio_clips = getattr(settings, '_current_audio_clips', None)
    
    if not scenario or not video_clips:
        print("   ⚠️  Context missing. Attempting to resume from latest findings...")
        from utils.archivist import Archivist
        archivist = Archivist(settings.google_sheet_id)
        
        # Find latest ANIMATION_DONE scenario
        all_scenarios = archivist.get_all_scenarios()
        resume_scenario = None
        for s in reversed(all_scenarios):
             if s.status == "ANIMATION_DONE":
                 resume_scenario = s
                 break
        
        if resume_scenario:
            print(f"      ✅ Found resumable scenario: {resume_scenario.id}")
            scenario = resume_scenario
            
            # Reconstruct clips
            # Assumes standard naming convention from previous phases
            scenario_dir = settings.output_dir  # Base output dir
            # Note: sound_engineer makes a subdir for audio, cinematographer puts directly in output?
            # Let's check logic:
            # Cinematographer: `video_path = Path(keyframe.path).parent / f"video_{keyframe.stage}.mp4"`
            # Keyframes are typically in output_dir directly?
            # SoundEngineer: `scenario_dir = self.output_dir / scenario_id` -> `audio_{stage}.mp3`
            
            # Re-building VideoClips (assuming they are in output_dir, checking file existence)
            from agents.cinematographer import VideoClip
            from agents.sound_engineer import AudioClip
            
            video_clips = []
            audio_clips = []
            
            for stage in [1, 2, 3]:
                # Video
                v_path = os.path.join(settings.output_dir, scenario.id, f"video_{stage}.mp4")
                if os.path.exists(v_path):
                    video_clips.append(VideoClip(stage=stage, path=v_path, duration=5.0))
                
                # Audio
                a_path = os.path.join(settings.output_dir, scenario.id, f"audio_{stage}.mp3")
                if os.path.exists(a_path):
                     # Retrieve mood from scenario data
                     stage_data = getattr(scenario, f"stage_{stage}")
                     mood = stage_data.mood
                     audio_clips.append(AudioClip(stage=stage, path=a_path, duration=5.0, mood=mood))
            
            if len(video_clips) < 3:
                 print("   ❌ Missing some video files for resume. Cannot proceed.")
                 return False
            
            if len(audio_clips) < 3:
                 print("   ⚠️  Missing separate audio files. Assuming embedded audio in videos.")
                 
            print(f"      ✅ Loaded {len(video_clips)} videos and {len(audio_clips)} audios")
            
        else:
            print("   ❌ No resumable scenario found (Status=ANIMATION_DONE). Run Phase 3 first.")
            return False
        
    from utils.editor import assemble_video
    from utils.archivist import Archivist
    from utils.distributor import Distributor, GCSDistributor
    
    output_dir = settings.output_dir
    
    try:
        final_video_path = assemble_video(scenario, video_clips, audio_clips, output_dir)
        
        # Upload to cloud storage (prefer GCS, fallback to Drive)
        video_url = None
        
        if settings.gcs_bucket:
            # Use GCS (recommended for GCP deployment)
            print(f"   📤 Uploading to GCS bucket: {settings.gcs_bucket}")
            distributor = GCSDistributor(settings.gcs_bucket)
            video_url = distributor.upload_video(
                final_video_path, 
                title=f"{scenario.id}.mp4",
                description=scenario.premise
            )
            
            # Also upload the assets folder for debugging
            from pathlib import Path
            scenario_folder = Path(output_dir) / scenario.id
            print(f"   🔍 Checking scenario folder: {scenario_folder}")
            if scenario_folder.exists():
                print(f"   📁 Found {len(list(scenario_folder.iterdir()))} files in folder")
                distributor.upload_folder(str(scenario_folder), scenario.id)
            else:
                print(f"   ⚠️ Scenario folder not found: {scenario_folder}")
        elif settings.drive_folder_id and settings.drive_folder_id != "YOUR_DRIVE_FOLDER_ID":
            # Fallback to Drive (legacy)
            print(f"   📤 Uploading to Google Drive...")
            distributor = Distributor(settings.drive_folder_id)
            video_url = distributor.upload_video(
                final_video_path, 
                title=f"{scenario.id}.mp4",
                description=scenario.premise
            )
        else:
            print("   ⚠️ No storage configured. Skipping upload.")
            video_url = ""
        
        # Update status
        archivist = Archivist(settings.google_sheet_id)
        archivist.update_status(scenario.id, "COMPLETED", video_url=video_url or "")
        
        # Update cost in Google Sheets
        try:
            from utils.cost_tracker import cost_tracker
            scenario_cost = cost_tracker.get_scenario_total(scenario.id)
            if scenario_cost > 0:
                archivist.update_cost(scenario.id, scenario_cost)
        except ImportError:
            pass
        
        # Set video URL on scenario object for later use
        scenario.video_url = video_url
        settings._current_final_video = final_video_path
        
        print(f"\n✅ Phase 4 complete! Final video: {final_video_path}")
        if video_url:
            print(f"   ☁️  Video URL: {video_url}")
            
        return True
        
    except Exception as e:
        print(f"   ❌ Assembly/Distribution failed: {e}")
        return False


def main():
    """Main entry point for ChronoReel."""
    print("\n" + "🎬 " * 20)
    print("     C H R O N O R E E L")
    print("     Alternative History Engine")
    print("🎬 " * 20)
    
    # Parse args and load config
    args = parse_args()
    config_path = resolve_config_path(args)
    
    try:
        settings = init_settings(config_path)
        print_settings(settings, verbose=args.verbose)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ Configuration Error: {e}")
        sys.exit(1)
    
    # Track timing
    start_time = datetime.now()
    
    # Determine which phases to run
    max_phase = args.phase if args.phase else 4
    
    # Run phases
    phases = [
        (1, run_phase_1),
        (2, run_phase_2),
        (3, run_phase_3),
        (4, run_phase_4),
    ]
    
    for phase_num, phase_fn in phases:
        if phase_num > max_phase:
            break
            
        success = phase_fn(settings, dry_run=args.dry_run)
        if not success and not args.dry_run:
            print(f"\n❌ Pipeline stopped at Phase {phase_num}")
            break
    
    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 50)
    print("📊 Run Summary")
    print("=" * 50)
    print(f"⏱️  Duration: {elapsed:.2f}s")
    print(f"📺 Channel:  {settings.channel_name}")
    
    if args.dry_run:
        print("🔍 Mode:     DRY RUN (no API calls)")
    else:
        # Print cost tracking summary
        try:
            from utils.cost_tracker import cost_tracker
            cost_tracker.print_summary()
        except ImportError:
            pass  # Cost tracking not available
    
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
