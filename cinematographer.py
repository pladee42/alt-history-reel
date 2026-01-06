"""
cinematographer.py - Video Generation

Animates static keyframes into video clips using Fal.ai image-to-video models.
"""

import os
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

import yaml
import fal_client
import requests
from dotenv import load_dotenv

from screenwriter import Scenario
from art_department import Keyframe

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


@dataclass
class VideoClip:
    """A single video clip generated from a keyframe."""
    stage: int
    path: str
    duration: float


class Cinematographer:
    """Generates video clips from keyframes using Fal.ai."""
    
    def __init__(self, output_dir: str):
        """
        Initialize with output directory.
        
        Args:
            output_dir: Base output directory for videos
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load model configuration
        self.config = load_model_config()
        video_config = self.config.get("fal_video", {})
        
        # Get model name from config
        self.video_model = video_config.get("model", "fal-ai/minimax/hailuo-2.3/pro/image-to-video")
        self.video_duration = video_config.get("duration", 5.0)
        
        # Verify FAL_KEY exists
        fal_key = os.getenv("FAL_KEY")
        if not fal_key:
            raise ValueError("FAL_KEY not found in environment")
        
        print(f"🎬 Cinematographer initialized")
        print(f"   Model: {self.video_model}")
        print(f"   Output: {self.output_dir}")
    
    def _upload_image_to_fal(self, image_path: str) -> str:
        """
        Upload a local image to Fal.ai and get a URL.
        
        Args:
            image_path: Local path to the image
            
        Returns:
            URL of the uploaded image
        """
        url = fal_client.upload_file(image_path)
        return url
    
    def animate_keyframe(self, keyframe: Keyframe, scenario: Scenario, 
                         motion_prompt: Optional[str] = None) -> VideoClip:
        """
        Animate a single keyframe into a video clip.
        
        Args:
            keyframe: The keyframe to animate
            scenario: The scenario for context
            motion_prompt: Optional motion description (defaults to stage mood)
            
        Returns:
            VideoClip with path to the generated video
        """
        stage = getattr(scenario, f"stage_{keyframe.stage}")
        
        # Build motion prompt from stage mood if not provided
        if not motion_prompt:
            motion_prompt = f"slow gentle motion, atmospheric, {stage.mood}"
        
        print(f"   🎥 Animating keyframe {keyframe.stage}...")
        
        # Upload the keyframe image to get a URL
        image_url = self._upload_image_to_fal(keyframe.path)
        
        # Call Fal.ai image-to-video
        try:
            result = fal_client.subscribe(
                self.video_model,
                arguments={
                    "image_url": image_url,
                    "prompt": motion_prompt,
                    "aspect_ratio": "9:16",
                },
            )
            
            # Get video URL from result
            video_url = result.get("video", {}).get("url")
            if not video_url:
                # Try alternative response structure
                video_url = result.get("video_url") or result.get("url")
            
            if not video_url:
                raise ValueError(f"No video URL in response: {result}")
            
            # Download and save the video
            video_path = Path(keyframe.path).parent / f"video_{keyframe.stage}.mp4"
            
            response = requests.get(video_url)
            with open(video_path, 'wb') as f:
                f.write(response.content)
            
            print(f"      ✅ Saved: {video_path.name}")
            
            return VideoClip(
                stage=keyframe.stage,
                path=str(video_path),
                duration=self.video_duration
            )
            
        except Exception as e:
            print(f"      ❌ Error: {e}")
            raise
    
    def animate_all_keyframes(self, keyframes: List[Keyframe], 
                              scenario: Scenario) -> List[VideoClip]:
        """
        Animate all keyframes into video clips.
        
        Args:
            keyframes: List of keyframes to animate
            scenario: The scenario for context
            
        Returns:
            List of VideoClip objects
        """
        print(f"\n🎬 Animating {len(keyframes)} keyframes for: {scenario.premise[:50]}...")
        
        video_clips = []
        for keyframe in keyframes:
            clip = self.animate_keyframe(keyframe, scenario)
            video_clips.append(clip)
            time.sleep(1)  # Brief pause between API calls
        
        print(f"\n✅ Generated {len(video_clips)} video clips")
        return video_clips


def animate_keyframes(keyframes: List[Keyframe], scenario: Scenario, 
                      output_dir: str) -> List[VideoClip]:
    """Convenience function to animate keyframes."""
    cinematographer = Cinematographer(output_dir)
    return cinematographer.animate_all_keyframes(keyframes, scenario)


if __name__ == "__main__":
    # Quick test
    print("Cinematographer module loaded successfully")
    config = load_model_config()
    print(f"Video model: {config.get('fal_video', {}).get('model', 'default')}")
