"""
editor.py - Video Assembly & Post-Production

Compiles generated video clips, audio tracks, and text overlays into a final 
short-form video (Reels/TikTok style) using MoviePy.
"""

import os
import textwrap
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from moviepy import (
    VideoFileClip, AudioFileClip, TextClip, 
    CompositeVideoClip, CompositeAudioClip, concatenate_videoclips,
    vfx
)
from moviepy.audio.fx import AudioLoop
from dotenv import load_dotenv

from screenwriter import Scenario
from cinematographer import VideoClip
from sound_engineer import AudioClip
from manager import Settings

# Load environment variables
load_dotenv(override=True)

# Get project root directory
PROJECT_ROOT = Path(__file__).parent


def load_model_config() -> dict:
    """Load model configuration from YAML file."""
    config_path = PROJECT_ROOT / "configs" / "model_config.yaml"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


class Editor:
    """Assembles the final video."""
    
    def __init__(self, output_dir: str, settings: Optional[Settings] = None):
        """
        Initialize the editor.
        
        Args:
            output_dir: Base output directory
            settings: Application settings
        """
        self.output_dir = Path(output_dir)
        self.settings = settings
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Font settings for MoviePy
        # Note: ImageMagick must be installed and configured
        self.font = "Arial"
        self.fontsize_header = 120
        self.fontsize_body = 40
        self.color = "yellow"
        self.stroke_color = "black"
        self.stroke_width = 4
        
        print(f"🎬 Editor initialized")
        print(f"   Output: {self.output_dir}")

    def parse_rich_title(self, title: str) -> List[Tuple[str, str]]:
        """
        Parses title for **emphasis**.
        Returns list of (text, color) tuples.
        """
        parts = []
        # Split by **
        segments = title.split('**')
        for i, segment in enumerate(segments):
            if not segment: continue
            # If index is odd, it was inside **, so emphasize
            color = 'cyan' if i % 2 == 1 else 'white'
            parts.append((segment, color))
        return parts

    def create_header(self, title: str, duration: float) -> CompositeVideoClip:
        """Creates a black header bar with rich text title."""
        header_height = 350
        # Black background
        bg = TextClip(text=" ", size=(1080, header_height), color='black', bg_color='black', font_size=10, font=self.font).with_duration(duration)
        
        # Clean title for simpler rendering (Rich text is hard without Pango)
        clean_title = title.replace('**', '')
        
        text_clip = self.create_text_clip(
            clean_title,
            fontsize=80,
            duration=duration,
            position=('center', 'center'),
            size=(1000, header_height)
        )
        # Note: create_text_clip wrapper uses specific args, need to ensure color/stroke are passed if not default
        # But my create_text_clip uses self.color ("yellow") by default.
        # I want WHITE for header.
        # Let's verify create_text_clip args.
        
        return CompositeVideoClip([bg, text_clip]).with_position(('center', 'top'))

    def create_text_clip(self, text: str, fontsize: int, duration: float, 
                         position: Tuple[str, str] = ('center', 'center'),
                         size: object = None,
                         color: str = None,
                         stroke_color: str = None,
                         stroke_width: int = None) -> TextClip:
        """Create a styled text overlay."""
        
        # Use 'caption' method if size is provided (better for wrapping/blocks)
        if size:
            method = 'caption'
            # Remove manual wrapping if using caption, as ImageMagick handles it
            final_text = text 
        else:
            method = 'label'
            # Manual wrap for label method
            final_text = "\n".join(textwrap.wrap(text, width=30))
        
        text_clip_args = {
            "text": final_text,
            "font_size": fontsize,
            "font": self.font,
            "color": color if color else self.color,
            "stroke_color": stroke_color if stroke_color else self.stroke_color,
            "stroke_width": stroke_width if stroke_width is not None else self.stroke_width,
            "method": method,
            "margin": (40, 40)
        }
        
        # Only pass size if provided (avoid NoneType error in v2)
        if size:
            text_clip_args["size"] = size
            
        return TextClip(**text_clip_args).with_position(position).with_duration(duration)

    def assemble_final_cut(self, scenario: Scenario, video_clips: List[VideoClip], 
                          audio_clips: List[AudioClip]) -> str:
        """
        Assemble the final video using the Ranking Layout.
        """
        print(f"   🎞️ Assembling final cut (Ranking Layout) for: {scenario.premise[:50]}...")
        
        final_clips = []
        
        # Ensure we have matching video and audio
        if len(video_clips) != len(audio_clips):
            print("   ⚠️ Mismatch between video and audio clip counts.")
        
        video_clips.sort(key=lambda x: x.stage)
        audio_clips.sort(key=lambda x: x.stage)
        
        # 1. Prepare Header (Static for whole video)
        # Determine total duration
        total_duration = 0
        stages_data = [] # Store processed pairs
        
        # Pre-process durations to build header
        ordered_clips = []
        for stage_num in [1, 2, 3]:
            v_data = next((v for v in video_clips if v.stage == stage_num), None)
            a_data = next((a for a in audio_clips if a.stage == stage_num), None)
            if v_data and a_data:
                ordered_clips.append((stage_num, v_data, a_data))

        # Check total duration
        temp_durations = []
        for _, v_data, a_data in ordered_clips:
            # We use audio duration as master
            path = a_data.path
            if os.path.exists(path):
                # We need to open it to get duration, done inside loop usually.
                pass

        # 2. Process Each Stage
        for stage_num, v_data, a_data in ordered_clips:
            print(f"      Processing Stage {stage_num}...")
            video = VideoFileClip(v_data.path)
            audio = AudioFileClip(a_data.path)
            
            # Loop/Trim video to match audio
            if audio.duration > video.duration:
                loop_count = int(audio.duration // video.duration) + 1
                video = concatenate_videoclips([video] * loop_count)
            video = video.subclipped(0, audio.duration).with_audio(audio)
            
            # CROP & POSITION VIDEO (Below 350px header)
            # Crop to fit remaining height (1920-350 = 1570)
            # Center crop logic: Keep middle of video
            # Source: 1920h. Target: 1570h. Diff: 350. Crop 175 top, 175 bottom.
            video_cropped = video.cropped(y1=175, y2=1920-175)
            video_positioned = video_cropped.with_position((0, 350))

            # RANKING OVERLAY
            # "1. Year" etc.
            # Define Years
            years = [scenario.stage_1.year, scenario.stage_2.year, scenario.stage_3.year]
            
            ranking_clips = []
            
            # Line 1 (Gold)
            txt_1 = f"1. {years[0]}"
            rank_1 = self.create_text_clip(
                txt_1, 
                fontsize=70, 
                duration=video.duration, 
                position=('left', 'center'), 
                color='#FFD700', 
                stroke_color='black', 
                stroke_width=3
            ).with_position((50, 500)) # Absolute pos on canvas
            ranking_clips.append(rank_1)
            
            # Line 2 (Silver)
            # Show "2." always? User said "2, 3 is empty".
            # So just "2."
            txt_2_num = "2."
            txt_2_yr = years[1]
            if stage_num >= 2:
                txt_2 = f"2. {txt_2_yr}"
                color_2 = '#C0C0C0' # Silver
            else:
                txt_2 = "2."
                color_2 = '#808080' # Dim gray? Or Silver but empty?
                # User said "different colors". 
                # Let's keep the number colored, but text empty?
                # "When Stage 1 playing, display 1. 2024 and 2, 3 is empty"
                # This implies "1." and "2024" are separate? Or just the line content?
                # Assuming "2." is visible but no year.
            
            # Let's render "2." and "Year" separately to handle "empty"
            rank_2_num = self.create_text_clip(
                "2.", 
                70, video.duration, ('left', 'center'), 
                color='#C0C0C0', stroke_color='black', stroke_width=3
            ).with_position((50, 650))
            ranking_clips.append(rank_2_num)
            
            if stage_num >= 2:
                rank_2_yr_clip = self.create_text_clip(
                    txt_2_yr, 
                    70, video.duration, ('left', 'center'), 
                    color='white', stroke_color='black', stroke_width=3
                ).with_position((150, 650))
                ranking_clips.append(rank_2_yr_clip)

            # Line 3 (Bronze)
            txt_3_num = "3."
            txt_3_yr = years[2]
            rank_3_num = self.create_text_clip(
                "3.", 
                70, video.duration, ('left', 'center'), 
                color='#CD7F32', stroke_color='black', stroke_width=3
            ).with_position((50, 800))
            ranking_clips.append(rank_3_num)
            
            if stage_num >= 3:
                rank_3_yr_clip = self.create_text_clip(
                    txt_3_yr, 
                    70, video.duration, ('left', 'center'), 
                    color='white', stroke_color='black', stroke_width=3
                ).with_position((150, 800))
                ranking_clips.append(rank_3_yr_clip)
                
            # Composite stage
            # We need a black background for the whole 1080x1920 canvas first?
            # Or just CompositeVideoClip defaults to transparent/black? Defaults to transparent usually.
            # But the HEADER will provide the top background.
            # What about the gap on sides if cropped?
            # We cropped Y, so X is still 1080.
            
            stage_composite = CompositeVideoClip(
                [video_positioned] + ranking_clips, 
                size=(1080, 1920)
            )
            final_clips.append(stage_composite)
            
        # Concatenate stages
        print("      Joining clips...")
        full_video = concatenate_videoclips(final_clips)
        
        # Add Header (Static Overlay)
        clean_title = scenario.title.replace('**', '').upper()
        # Ensure title fits? We'll rely on create_header
        
        header_clip = self.create_header(clean_title, full_video.duration)
        
        # Final Composite
        final_video = CompositeVideoClip([full_video, header_clip], size=(1080, 1920))
        
        # Output logic
        scenario_dir = self.output_dir / scenario.id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        output_path = scenario_dir / "final_cut.mp4"
        
        print(f"      Rendering to {output_path.name}...")
        final_video.write_videofile(
            str(output_path),
            codec='libx264',
            audio_codec='aac',
            fps=24,
            preset='medium',
            threads=4,
            logger=None
        )
        
        print(f"   ✅ Final cut saved: {output_path}")
        return str(output_path)


def assemble_video(scenario: Scenario, video_clips: List[VideoClip], 
                  audio_clips: List[AudioClip], output_dir: str) -> str:
    """Convenience function to assemble video."""
    editor = Editor(output_dir)
    return editor.assemble_final_cut(scenario, video_clips, audio_clips)
