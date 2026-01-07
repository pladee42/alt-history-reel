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
    concatenate_audioclips,
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
        
        # Prepare for Pango Markup (Rich Text)
        try:
            # 1. Convert title to upper
            # 2. Split by **
            # 3. Construct XML-like markup
            pango_title = title.upper()
            parts = pango_title.split('**')
            markup_text = ""
            for i, part in enumerate(parts):
                if not part: continue
                # Escape minimal xml entities just in case
                safe_part = part.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                
                if i % 2 == 1:
                    # Emphasized part (Cyan)
                    markup_text += f"<span foreground='#00FFFF' weight='bold'>{safe_part}</span>"
                else:
                    # Normal part (White)
                    markup_text += safe_part
            
            # Center alignment with Pango requires strict markup
            # usually Pango aligns based on 'pango-view' or wrapping
            # wrapping in <div align='center'> isn't standard pango spec, 
            # but moviepy's text_align argument should handle it if size is provided.
            
            text_clip = TextClip(
                text=markup_text,
                font_size=80,
                font=self.font,
                color='white', # Fallback/Default
                stroke_color='black',
                stroke_width=2,
                method='pango',
                size=(1000, header_height),
                text_align="center"
            ).with_position(('center', 'center')).with_duration(duration)
            
            return CompositeVideoClip([bg, text_clip]).with_position(('center', 'top'))

        except Exception as e:
            print(f"      ⚠️ Pango rich text failed ({e}), falling back to plain text.")
            
            # Fallback to plain caption
            clean_title = title.replace('**', '').upper()
            
            text_clip = TextClip(
                text=clean_title,
                font_size=80,
                font=self.font,
                color='white',
                stroke_color='black',
                stroke_width=2,
                method='caption',
                size=(1000, header_height),
                text_align="center"
            ).with_position(('center', 'center')).with_duration(duration)
            
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
        
        # Sort by stage
        video_clips.sort(key=lambda x: x.stage)
        audio_clips.sort(key=lambda x: x.stage)
        
        # 1. Prepare Data Pairs
        ordered_clips = []
        for stage_num in [1, 2, 3]:
            v_data = next((v for v in video_clips if v.stage == stage_num), None)
            a_data = next((a for a in audio_clips if a.stage == stage_num), None)
            if v_data and a_data:
                ordered_clips.append((stage_num, v_data, a_data))

        # 2. Process Each Stage
        for stage_num, v_data, a_data in ordered_clips:
            print(f"      Processing Stage {stage_num}...")
            video = VideoFileClip(v_data.path)
            audio = AudioFileClip(a_data.path)
            
            print(f"         src_video: {video.duration:.2f}s, src_audio: {audio.duration:.2f}s")
            
            # Determine target duration (Max of both to avoid cutting good footage)
            target_duration = max(video.duration, audio.duration)
            
            # 1. Handle Video (Loop if too short)
            if video.duration < target_duration:
                loop_count = int(target_duration // video.duration) + 1
                video = concatenate_videoclips([video] * loop_count)
            video = video.subclipped(0, target_duration)
            
            # 2. Handle Audio (Loop if too short)
            if audio.duration < target_duration:
                # Use AudioLoop effect for safer looping
                audio = AudioLoop(duration=target_duration).apply(audio)
            
            # Ensure hard limits
            video = video.subclipped(0, target_duration)
            audio = audio.subclipped(0, target_duration)
            
            video = video.with_audio(audio)
            
            # CROP & POSITION VIDEO (Below 350px header)
            # Crop to fit remaining height (1920-350 = 1570)
            video_cropped = video.cropped(y1=175, y2=1920-175)
            video_positioned = video_cropped.with_position((0, 350))

            # RANKING OVERLAY
            labels = [scenario.stage_1.label, scenario.stage_2.label, scenario.stage_3.label]
            ranking_clips = []
            
            # Config
            x_num = 25     # X position for "1." "2." "3."
            x_label = 75   # X position for Label Text
            y_start = 500
            y_gap = 150
            
            colors = ['#FFD700', '#C0C0C0', '#CD7F32'] # Gold, Silver, Bronze
            
            for i in range(3):
                rank_idx = i + 1 # 1, 2, 3
                current_y = y_start + (i * y_gap)
                color = colors[i]
                
                # Number Clip ("1.") - Always visible
                clip_num = self.create_text_clip(
                    f"{rank_idx}.", 
                    70, video.duration, ('left', 'center'), 
                    color=color, stroke_color='black', stroke_width=3
                ).with_position((x_num, current_y))
                ranking_clips.append(clip_num)
                
                # Label Clip (Only if revealed)
                if stage_num >= rank_idx:
                    clip_label = self.create_text_clip(
                        str(labels[i]), 
                        60, video.duration, ('left', 'center'), # Size 60 to fit longer text 
                        color=color, # Label uses Rank Color
                        stroke_color='black', stroke_width=3
                    ).with_position((x_label, current_y))
                    ranking_clips.append(clip_label)
            
            # Composite stage
            stage_composite = CompositeVideoClip(
                [video_positioned] + ranking_clips, 
                size=(1080, 1920)
            ).with_duration(video.duration) # Explicitly set duration
            
            final_clips.append(stage_composite)
            
        # Concatenate stages
        print(f"      Joining {len(final_clips)} clips...")
        full_video = concatenate_videoclips(final_clips)
        print(f"      Total Duration: {full_video.duration:.2f}s")
        
        # Add Header (Static Overlay)
        clean_title = scenario.title.replace('**', '').upper()
        header_clip = self.create_header(clean_title, full_video.duration)
        
        # Final Composite
        final_video = CompositeVideoClip([full_video, header_clip], size=(1080, 1920))
        final_video = final_video.with_duration(full_video.duration)
        
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
