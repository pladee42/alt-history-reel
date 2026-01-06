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

from manager import parse_args, init_settings, print_settings, resolve_config_path


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
    
    from screenwriter import generate_scenario
    from archivist import Archivist
    from art_department import ArtDepartment
    
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
        
    from cinematographer import animate_keyframes
    from sound_engineer import generate_audio
    from archivist import Archivist
    
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
    
    print("\n✅ Phase 3 complete!")
    return True


def run_phase_4(settings, dry_run: bool = False):
    """Phase 4: Assemble and distribute final video."""
    print("📦 Phase 4: Assembling final video...")
    
    if dry_run:
        print("   [DRY RUN] Would stitch clips with MoviePy")
        print("   [DRY RUN] Would upload to Google Drive")
        return True
    
    # TODO: Implement later
    # from editor import assemble_video
    # from distributor import upload_to_drive, log_to_sheets
    
    print("   ⚠️ Phase 4 not yet implemented")
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
    
    # TODO: Add cost tracking in Phase 5
    # from cost_tracker import print_cost_summary
    # print_cost_summary()
    
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
