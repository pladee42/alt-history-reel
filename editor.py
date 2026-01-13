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
        # Download Arial from GCS in Docker, use local Arial on Mac/Windows
        self.font = self._get_font_path()
        self.fontsize_header = 120
        self.fontsize_body = 40
        self.color = "yellow"
        self.stroke_color = "black"
        self.stroke_width = 4
        
        print(f"🎬 Editor initialized")
        print(f"   Output: {self.output_dir}")
        print(f"   Font: {self.font}")
    
    def _get_font_path(self) -> str:
        """Get the font path, downloading from GCS if needed."""
        import requests
        
        # Local cache path for downloaded font
        cached_font = Path("/tmp/Arial.ttf")
        
        # If running locally (Mac/Windows), Arial should be available by name
        local_arial = Path("/System/Library/Fonts/Supplemental/Arial.ttf")  # Mac path
        if local_arial.exists():
            return str(local_arial)
        
        # Windows path
        windows_arial = Path("C:/Windows/Fonts/arial.ttf")
        if windows_arial.exists():
            return str(windows_arial)
        
        # In Docker: download from GCS if not cached
        if not cached_font.exists():
            print("   📥 Downloading Arial font from GCS...")
            font_url = "https://storage.googleapis.com/timeline-b/ARIAL.TTF"
            response = requests.get(font_url)
            if response.status_code == 200:
                with open(cached_font, 'wb') as f:
                    f.write(response.content)
                print("   ✅ Font downloaded successfully")
            else:
                print(f"   ⚠️ Failed to download font: {response.status_code}")
                # Fallback to Liberation Sans
                return "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        
        return str(cached_font)

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

    def create_pill_title(self, title: str, duration: float) -> CompositeVideoClip:
        """
        Creates a floating pill-shaped title overlay (Instagram/TikTok style).
        Returns a transparent composite with the pill positioned near the top.
        """
        from PIL import Image, ImageDraw
        import numpy as np
        
        # Config
        font_size = 48
        horizontal_padding = 40
        vertical_padding = 20
        text_margin = 10  # Extra margin to prevent text cropping
        pill_y = 300  # Distance from top of video (moved down)
        corner_radius = 30
        bg_opacity = 0.85
        max_pill_width = 1080 - 80  # 40px margin on each side
        
        try:
            # Parse title for **emphasis** markers
            parts_raw = title.split('**')
            word_objs = []  # List of {'text': str, 'color': str}
            space_width = 12  # Approximate space width
            
            for i, part in enumerate(parts_raw):
                if not part:
                    continue
                is_emphasized = (i % 2 == 1)
                curr_color = 'cyan' if is_emphasized else 'white'
                
                # Split into individual words
                words = part.split()
                for w in words:
                    tc = TextClip(
                        text=w,
                        font_size=font_size,
                        font=self.font,
                        color=curr_color,
                        margin=(text_margin, text_margin),  # Prevent text cropping
                    ).with_duration(duration)
                    
                    word_objs.append({
                        'text': w,
                        'color': curr_color,
                        'clip': tc,
                        'width': tc.w,
                        'height': tc.h
                    })
            
            if not word_objs:
                display_title = title.replace('**', '')
                text_clip = TextClip(
                    text=display_title,
                    font_size=font_size,
                    font=self.font,
                    color='white',
                ).with_duration(duration)
                word_objs = [{'clip': text_clip, 'width': text_clip.w, 'height': text_clip.h}]
            
            # Calculate total width and height
            total_width = sum(w['width'] for w in word_objs) + (len(word_objs) - 1) * space_width
            text_height = max(w['height'] for w in word_objs)
            
            # Calculate pill dimensions
            pill_width = total_width + (horizontal_padding * 2)
            pill_height = text_height + (vertical_padding * 2)
            
            # Check if we need line wrapping
            needs_wrap = pill_width > max_pill_width
            
            if needs_wrap:
                # Word wrap with color support - split into lines
                lines = []  # List of {'words': [], 'width': int}
                current_line = []
                current_line_width = 0
                
                for word in word_objs:
                    w_width = word['width']
                    if current_line and (current_line_width + space_width + w_width > max_pill_width - horizontal_padding * 2):
                        lines.append({'words': current_line, 'width': current_line_width})
                        current_line = [word]
                        current_line_width = w_width
                    else:
                        if current_line:
                            current_line_width += space_width
                        current_line.append(word)
                        current_line_width += w_width
                
                if current_line:
                    lines.append({'words': current_line, 'width': current_line_width})
                
                # Calculate pill dimensions for multi-line
                max_line_width = max(line['width'] for line in lines)
                pill_width = max_line_width + (horizontal_padding * 2)
                line_height = text_height
                pill_height = (line_height * len(lines)) + (vertical_padding * 2)
                word_objs = None  # Signal multi-line mode
            else:
                lines = None
            
            # Create pill background using PIL
            pill_img = Image.new('RGBA', (pill_width, pill_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(pill_img)
            
            # Draw rounded rectangle (pill shape)
            bg_color = (0, 0, 0, int(255 * bg_opacity))
            draw.rounded_rectangle(
                [(0, 0), (pill_width - 1, pill_height - 1)],
                radius=corner_radius,
                fill=bg_color
            )
            
            # Convert PIL image to numpy array for MoviePy
            pill_array = np.array(pill_img)
            
            # Create ImageClip from numpy array
            from moviepy import ImageClip
            pill_bg = ImageClip(pill_array, is_mask=False, transparent=True).with_duration(duration)
            
            # Build text clips
            clips = [pill_bg]
            
            if word_objs:
                # Single line - position words inline with colors
                current_x = horizontal_padding
                text_y = vertical_padding - text_margin  # Adjust for margin
                
                for word in word_objs:
                    clip_positioned = word['clip'].with_position((current_x - text_margin, text_y))
                    clips.append(clip_positioned)
                    current_x += word['width'] + space_width
            elif lines:
                # Multi-line mode with colors
                current_y = vertical_padding - text_margin
                for line_data in lines:
                    # Center each line
                    line_width = line_data['width']
                    start_x = (pill_width - line_width) // 2
                    current_x = start_x
                    
                    for word in line_data['words']:
                        clip_positioned = word['clip'].with_position((current_x - text_margin, current_y))
                        clips.append(clip_positioned)
                        current_x += word['width'] + space_width
                    
                    current_y += line_height
            
            # Composite pill background and text
            pill_composite = CompositeVideoClip(
                clips,
                size=(pill_width, pill_height)
            ).with_duration(duration)
            
            # Calculate X position to center pill on screen
            pill_x = (1080 - pill_width) // 2
            
            # Return positioned on full-size transparent canvas
            return pill_composite.with_position((pill_x, pill_y))

        except Exception as e:
            print(f"      ⚠️ Pill title creation failed ({e}), falling back to simple text.")
            import traceback
            traceback.print_exc()
            
            # Fallback: simple text overlay
            display_title = title.replace('**', '')
            text_clip = TextClip(
                text=display_title,
                font_size=font_size,
                font=self.font,
                color='white',
                stroke_color='black',
                stroke_width=2,
                bg_color='black',
                method='caption',
                size=(900, None),
                text_align='center'
            ).with_position(('center', pill_y)).with_duration(duration)
            
            return text_clip

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

    def _resize_to_fill(self, clip, width=1080, height=1920):
        """
        Resizes and center-crops clip to fill target dimensions (Aspect Fill).
        """
        w, h = clip.size
        if w == width and h == height:
            return clip
            
        target_ratio = width / height
        clip_ratio = w / h
        
        # Calculate scale factor to cover the area
        if clip_ratio > target_ratio:
            # Clip is wider (landscape-ish) -> Scale by Height
            scale = height / h
        else:
            # Clip is taller/narrower -> Scale by Width
            scale = width / w
            
        # Resize first
        # Note: using resized() which is safe for v2, fallback logic if needed
        try:
            resized = clip.resized(scale)
        except AttributeError:
            # Fallback for older moviepy
            resized = clip.resize(scale)
            
        # Center Crop
        return resized.cropped(width=width, height=height, x_center=resized.w / 2, y_center=resized.h / 2)


    def assemble_final_cut(self, scenario: Scenario, video_clips: List[VideoClip], 
                          audio_clips: List[AudioClip]) -> str:
        """
        Assemble the final video using the Ranking Layout.
        
        Video flow: [Teaser 1.5s] -> [Phase 1] -> [Phase 2] -> [Phase 3]
        Teaser shows Phase 3 video with all rankings revealed.
        Title overlay appears for first 5 seconds only.
        """
        print(f"   🎞️ Assembling final cut (Ranking Layout) for: {scenario.premise[:50]}...")
        
        # Configurable timing
        teaser_duration = 1.5  # Duration of Phase 3 teaser at start (configurable)
        title_duration = 5.0   # How long title overlay is visible
        
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
            
            # Allow proceeding if we have video, even if audio is missing (embedded audio)
            if v_data:
                ordered_clips.append((stage_num, v_data, a_data))
        
        # Ranking overlay config (shared)
        labels = [scenario.stage_1.label, scenario.stage_2.label, scenario.stage_3.label]
        x_num = 25     # X position for "1." "2." "3."
        x_label = 90   # X position for Label Text
        y_start = 650  # Y position of first ranking
        y_gap = 150
        colors = ['#FFD700', '#C0C0C0', '#CD7F32']  # Gold, Silver, Bronze
        
        # 2. PRE-LOAD all video/audio clips ONCE (memory optimization)
        loaded_clips = {}  # {stage_num: (video, audio, target_duration)}
        for stage_num, v_data, a_data in ordered_clips:
            print(f"      Loading Stage {stage_num}...")
            video = VideoFileClip(v_data.path)
            
            if a_data:
                # External Audio
                audio = AudioFileClip(a_data.path)
                target_duration = max(video.duration, audio.duration)
                
                # Handle Audio (Loop if too short)
                if audio.duration < target_duration:
                    audio = AudioLoop(duration=target_duration).apply(audio)
                audio = audio.subclipped(0, target_duration)
                
                # Handle Video (Loop if too short)
                if video.duration < target_duration:
                    loop_count = int(target_duration // video.duration) + 1
                    video = concatenate_videoclips([video] * loop_count)
                video = video.subclipped(0, target_duration)
                
                video = video.with_audio(audio)
            else:
                # Embedded Audio
                target_duration = video.duration
                print(f"      🎵 Using embedded audio for Stage {stage_num}")
                
            loaded_clips[stage_num] = (video, target_duration)
        
        # 3. Create TEASER clip (reusing Phase 3 video - no double loading!)
        print(f"      Creating Teaser ({teaser_duration}s from Phase 3)...")
        if 3 in loaded_clips:
            stage3_video, _ = loaded_clips[3]
            
            # Extract first N seconds for teaser (subclip reuses existing video in memory)
            teaser_video = stage3_video.subclipped(0, min(teaser_duration, stage3_video.duration))
            teaser_cropped = self._resize_to_fill(teaser_video, 1080, 1920).with_position((0, 0))
            
            # Create ALL rankings visible for teaser
            teaser_ranking_clips = []
            for i in range(3):
                rank_idx = i + 1
                current_y = y_start + (i * y_gap)
                color = colors[i]
                
                # Number Clip
                clip_num = self.create_text_clip(
                    f"{rank_idx}.", 70, teaser_duration, ('left', 'center'),
                    color=color, stroke_color='black', stroke_width=3
                ).with_position((x_num, current_y))
                teaser_ranking_clips.append(clip_num)
                
                # Label Clip (ALL revealed in teaser)
                clip_label = self.create_text_clip(
                    str(labels[i]), 60, teaser_duration, ('left', 'center'),
                    color=color, stroke_color='black', stroke_width=3
                ).with_position((x_label, current_y))
                teaser_ranking_clips.append(clip_label)
            
            teaser_composite = CompositeVideoClip(
                [teaser_cropped] + teaser_ranking_clips,
                size=(1080, 1920)
            ).with_duration(teaser_duration)
            
            final_clips.append(teaser_composite)
            print(f"      ✅ Teaser added: {teaser_duration}s")
        
        # 4. Process Each Stage using pre-loaded clips (normal progression)
        for stage_num, v_data, a_data in ordered_clips:
            print(f"      Compositing Stage {stage_num}...")
            video, target_duration = loaded_clips[stage_num]
            
            # CROP & POSITION VIDEO (Aspect Fill - dynamic resize)
            video_cropped = self._resize_to_fill(video, 1080, 1920)
            video_positioned = video_cropped.with_position((0, 0))

            # RANKING OVERLAY (progressive reveal)
            ranking_clips = []
            
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
        
        # Add Pill Title Overlay - LIMITED DURATION (5 seconds)
        title_clip = self.create_pill_title(scenario.title, title_duration)
        
        # Final Composite
        final_video = CompositeVideoClip([full_video, title_clip], size=(1080, 1920))
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
