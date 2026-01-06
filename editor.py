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
    CompositeVideoClip, CompositeAudioClip, concatenate_videoclips
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

    def create_text_clip(self, text: str, fontsize: int, duration: float, 
                         position: Tuple[str, str] = ('center', 'center')) -> TextClip:
        """Create a styled text overlay."""
        # Wrap text to fit vertical video width (approx 30 chars for 720px width)
        wrapped_text = "\n".join(textwrap.wrap(text, width=30))
        
        return TextClip(
            text=wrapped_text,
            font_size=fontsize,
            font=self.font,
            color=self.color,
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            method='label'
        ).with_position(position).with_duration(duration)

    def assemble_final_cut(self, scenario: Scenario, video_clips: List[VideoClip], 
                          audio_clips: List[AudioClip]) -> str:
        """
        Assemble all elements into the final video.
        
        Args:
            scenario: The scenario data (for text overlay)
            video_clips: List of generated video clips
            audio_clips: List of generated audio clips
            
        Returns:
            Path to the final video file
        """
        print(f"   🎞️ Assembling final cut for: {scenario.premise[:50]}...")
        
        final_clips = []
        
        # Ensure we have matching video and audio
        if len(video_clips) != len(audio_clips):
            print("   ⚠️ Mismatch between video and audio clip counts. Checking stages...")
        
        # Sort by stage just in case
        video_clips.sort(key=lambda x: x.stage)
        audio_clips.sort(key=lambda x: x.stage)
        
        # Process each stage
        for i, video_data in enumerate(video_clips):
            stage_num = video_data.stage
            
            # Load video file
            print(f"      Processing Stage {stage_num}...")
            video = VideoFileClip(video_data.path)
            
            # Find matching audio (if any)
            audio_data = next((a for a in audio_clips if a.stage == stage_num), None)
            if audio_data:
                audio = AudioFileClip(audio_data.path)
                
                # Loop audio if shorter than video, or trim if longer
                if audio.duration < video.duration:
                    audio = audio.with_effects([AudioLoop(duration=video.duration)])
                else:
                    audio = audio.subclipped(0, video.duration)
                
                video = video.with_audio(audio)
            
            # Get stage description for text overlay
            stage_info = getattr(scenario, f"stage_{stage_num}")
            
            # Create text overlays
            # 1. Year (Top)
            label_text = str(stage_info.year)
            text_top = self.create_text_clip(
                label_text, 
                self.fontsize_header, 
                video.duration, 
                ('center', 100)  # Top position
            )
            
            # 2. Description (Bottom) - Show only for first 3 seconds of clip
            # Determine text based on stage
            if stage_num == 1:
                desc_text = "Wait for it..."
            elif stage_num == 2:
                desc_text = "The Turning Point"
            else:
                desc_text = "The New Reality"
                
            text_bottom = self.create_text_clip(
                desc_text,
                self.fontsize_body,
                3.0,  # Duration
                ('center', 'bottom')
            ).with_start(0.5) # Slight delay
            
            # Composite stage clip
            stage_composite = CompositeVideoClip([video, text_top, text_bottom])
            final_clips.append(stage_composite)
            
        # Concatenate all stages
        print("      Joining clips...")
        final_video = concatenate_videoclips(final_clips)
        
        # Add premise title overlay at the very beginning (first 3s)
        print("      Adding titles...")
        # (This is simplified; a real editor might add a dedicated title card)
        
        # Output path
        scenario_dir = self.output_dir / scenario.id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        output_path = scenario_dir / "final_cut.mp4"
        
        # Write final file
        print(f"      Rendering to {output_path.name}...")
        final_video.write_videofile(
            str(output_path),
            codec='libx264',
            audio_codec='aac',
            fps=24,
            preset='medium',
            threads=4,
            logger=None  # Suppress MoviePy bar to standard output
        )
        
        print(f"   ✅ Final cut saved: {output_path}")
        return str(output_path)


def assemble_video(scenario: Scenario, video_clips: List[VideoClip], 
                  audio_clips: List[AudioClip], output_dir: str) -> str:
    """Convenience function to assemble video."""
    editor = Editor(output_dir)
    return editor.assemble_final_cut(scenario, video_clips, audio_clips)
