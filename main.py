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
    """Phase 2: Generate static keyframes with Vision Gate."""
    print("🎨 Phase 2: Generating static keyframes...")
    
    if dry_run:
        print("   [DRY RUN] Would generate 3 keyframes with Flux")
        print("   [DRY RUN] Would verify with Gemini Vision Gate")
        return True
    
    # TODO: Implement in next phase
    # from screenwriter import generate_script
    # from art_department import generate_keyframes, verify_consistency
    
    print("   ⚠️ Phase 2 not yet implemented")
    return False


def run_phase_3(settings, dry_run: bool = False):
    """Phase 3: Animate keyframes into video clips."""
    print("🎬 Phase 3: Animating keyframes...")
    
    if dry_run:
        print("   [DRY RUN] Would animate with Luma Dream Machine")
        print("   [DRY RUN] Would generate audio with ElevenLabs")
        return True
    
    # TODO: Implement later
    # from cinematographer import animate_keyframes
    # from sound_engineer import generate_audio
    
    print("   ⚠️ Phase 3 not yet implemented")
    return False


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
