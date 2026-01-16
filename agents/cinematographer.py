"""
cinematographer.py - Video Generation

Animates static keyframes into video clips using Fal.ai or Kie.ai (Seedance).
Supports provider selection via model_config.yaml.
Seedance 1.5 Pro can generate video with native audio.
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

from agents.screenwriter import Scenario
from agents.art_department import Keyframe

# Import Kie.ai client if available
try:
    from utils.kie_client import KieClient
    KIE_AVAILABLE = True
except ImportError:
    KIE_AVAILABLE = False

# Load environment variables
load_dotenv(override=True)

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent


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
    has_audio: bool = False  # True if Seedance generated native audio


class Cinematographer:
    """Generates video clips from keyframes using Fal.ai or Kie.ai (Seedance)."""
    
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
        
        # Check if Kie.ai is enabled
        kie_config = self.config.get("kie", {})
        self.use_kie = kie_config.get("enabled", False) and KIE_AVAILABLE
        
        if self.use_kie:
            # Initialize Kie.ai client for Seedance or Veo3
            kie_key = os.getenv("KIE_AI_KEY")
            if not kie_key:
                print("   ⚠️ KIE_AI_KEY not found, falling back to Fal.ai")
                self.use_kie = False
            else:
                self.kie_client = KieClient()
                kie_video_config = self.config.get("kie_video", {})
                
                # Check provider selection
                self.kie_provider = kie_video_config.get("provider", "seedance")
                
                if self.kie_provider == "veo3":
                    # Veo 3.1 config
                    veo3_config = kie_video_config.get("veo3", {})
                    self.veo3_model = veo3_config.get("model", "veo3_fast")
                    self.veo3_aspect_ratio = veo3_config.get("aspect_ratio", "9:16")
                    self.veo3_enable_translation = veo3_config.get("enable_translation", True)
                    self.generate_audio = True  # Veo3.1 has embedded audio
                else:
                    # Seedance 1.5 Pro config (default)
                    seedance_config = kie_video_config.get("seedance", {})
                    self.kie_model = seedance_config.get("model", "bytedance/seedance-1.5-pro")
                    self.kie_duration = seedance_config.get("duration", 5)
                    self.kie_resolution = seedance_config.get("resolution", "720p")
                    self.kie_aspect_ratio = seedance_config.get("aspect_ratio", "9:16")
                    self.generate_audio = seedance_config.get("generate_audio", True)
        
        # Fal.ai config (fallback or primary)
        if not self.use_kie:
            video_config = self.config.get("fal_video", {})
            self.video_model = video_config.get("model", "fal-ai/minimax/hailuo-2.3/pro/image-to-video")
            self.video_duration = video_config.get("duration", 5.0)
            
            # Verify FAL_KEY exists
            fal_key = os.getenv("FAL_KEY")
            if not fal_key:
                raise ValueError("FAL_KEY not found in environment")
        
        # Determine provider for display
        if self.use_kie:
            if self.kie_provider == "veo3":
                provider = f"Kie.ai Veo3 ({self.veo3_model})"
                audio_note = ""
            else:
                provider = f"Kie.ai Seedance ({self.kie_model})"
                audio_note = " + audio" if self.generate_audio else ""
        else:
            provider = f"Fal.ai ({self.video_model})"
            audio_note = ""
        
        print(f"🎬 Cinematographer initialized")
        print(f"   Provider: {provider}{audio_note}")
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
        
        # 1. Define Motion/Action
        if not motion_prompt:
            motion_prompt = f"slow gentle motion, atmospheric, {stage.mood}"
                
        # Route to appropriate provider
        if self.use_kie:
            if self.kie_provider == "veo3":
                # NOTE: Skip image_prompt prefix for Veo3 to avoid content policy violations
                # The reference image is already passed via imageUrls, so generic motion works fine
                # Original code (commented out):
                # if hasattr(stage, 'image_prompt') and stage.image_prompt and stage.image_prompt not in motion_prompt:
                #     motion_prompt = f"IMPORTANT: Animates the video based on the image {stage.image_prompt}. {motion_prompt}"
                motion_prompt = "Animate the image with realistic sound"
                return self._animate_with_veo3(keyframe, motion_prompt)
            else:
                # Seedance - add image_prompt prefix for better adherence
                if hasattr(stage, 'image_prompt') and stage.image_prompt and stage.image_prompt not in motion_prompt:
                    motion_prompt = f"IMPORTANT: Animates the video based on the image {stage.image_prompt}. {motion_prompt}"
                # Seedance - extract audio prompt if generating audio
                audio_prompt = ""
                if self.generate_audio and hasattr(stage, 'audio_prompt'):
                    audio_prompt = stage.audio_prompt
                return self._animate_with_kie(keyframe, motion_prompt, audio_prompt)
        else:
            # Fal.ai - add image_prompt prefix
            if hasattr(stage, 'image_prompt') and stage.image_prompt and stage.image_prompt not in motion_prompt:
                motion_prompt = f"IMPORTANT: Animates the video based on the image {stage.image_prompt}. {motion_prompt}"
            return self._animate_with_fal(keyframe, motion_prompt)
    
    def _animate_with_kie(self, keyframe: Keyframe, motion_prompt: str, audio_prompt: str = "") -> VideoClip:
        """
        Animate keyframe using Kie.ai Seedance 1.5 Pro.
        
        Args:
            keyframe: The keyframe to animate
            motion_prompt: Motion/action description
            audio_prompt: Optional audio description for native audio generation
            
        Returns:
            VideoClip with path and audio info
        """
        print(f"   🎥 Animating keyframe {keyframe.stage} via Kie.ai Seedance...")
        
        # Combine prompts for Seedance if audio is enabled
        final_prompt = motion_prompt
        if self.generate_audio and audio_prompt:
            final_prompt = f"{motion_prompt}. Audio: {audio_prompt}"
            print(f"      🎵 Including audio prompt: {audio_prompt[:50]}...")
        
        if not keyframe.url:
            raise ValueError(f"Keyframe {keyframe.stage} has no URL. Kie.ai requires image URLs for video generation.")
            
        try:
            result = self.kie_client.generate_video(
                prompt=final_prompt,
                image_url=keyframe.url,
                duration=self.kie_duration,
                resolution=self.kie_resolution,
                aspect_ratio=self.kie_aspect_ratio,
                generate_audio=self.generate_audio
            )
            
            # Download and save the video
            video_path = Path(keyframe.path).parent / f"video_{keyframe.stage}.mp4"
            
            response = requests.get(result.video_url)
            with open(video_path, 'wb') as f:
                f.write(response.content)
            
            # Log cost
            try:
                from utils.cost_tracker import cost_tracker
                scenario_id = video_path.parent.name
                cost_tracker.log_kie_call(
                    model="bytedance/seedance-1.5-pro",
                    scenario_id=scenario_id,
                    operation="image_to_video",
                    metadata={
                        "duration_seconds": self.kie_duration,
                        "has_audio": self.generate_audio
                    }
                )
            except (ImportError, AttributeError):
                pass
            
            audio_note = " (with audio)" if self.generate_audio else ""
            print(f"      ✅ Saved: {video_path.name}{audio_note}")
            
            return VideoClip(
                stage=keyframe.stage,
                path=str(video_path),
                duration=float(self.kie_duration),
                has_audio=self.generate_audio
            )
            
        except Exception as e:
            print(f"      ❌ Error: {e}")
            raise
    
    def _animate_with_veo3(self, keyframe: Keyframe, motion_prompt: str) -> VideoClip:
        """
        Animate keyframe using Kie.ai Veo 3.1.
        
        Args:
            keyframe: The keyframe to animate
            motion_prompt: Motion/action description
            
        Returns:
            VideoClip with path (no audio - Veo3 doesn't support native audio)
        """
        print(f"   🎥 Animating keyframe {keyframe.stage} via Kie.ai Veo3...")
        
        if not keyframe.url:
            raise ValueError(f"Keyframe {keyframe.stage} has no URL. Kie.ai requires image URLs for video generation.")
            
        try:
            result = self.kie_client.generate_video_veo3(
                prompt=motion_prompt,
                image_url=keyframe.url,
                model=self.veo3_model,
                aspect_ratio=self.veo3_aspect_ratio,
                enable_translation=self.veo3_enable_translation
            )
            
            # Download and save the video
            video_path = Path(keyframe.path).parent / f"video_{keyframe.stage}.mp4"
            
            response = requests.get(result.video_url)
            with open(video_path, 'wb') as f:
                f.write(response.content)
            
            # Log cost
            try:
                from utils.cost_tracker import cost_tracker
                scenario_id = video_path.parent.name
                cost_tracker.log_kie_call(
                    model=f"veo3-{self.veo3_model}",
                    scenario_id=scenario_id,
                    operation="image_to_video",
                    metadata={
                        "duration_seconds": 8,  # Veo3 default
                        "has_audio": False
                    }
                )
            except (ImportError, AttributeError):
                pass
            
            print(f"      ✅ Saved: {video_path.name}")
            
            return VideoClip(
                stage=keyframe.stage,
                path=str(video_path),
                duration=8.0,  # Veo3 generates ~8s videos
                has_audio=True  # Veo3.1 embeds audio
            )
            
        except Exception as e:
            print(f"      ❌ Error: {e}")
            raise
    
    def _animate_with_fal(self, keyframe: Keyframe, motion_prompt: str) -> VideoClip:
        """
        Animate keyframe using Fal.ai.
        
        Args:
            keyframe: The keyframe to animate
            motion_prompt: Motion/action description
            
        Returns:
            VideoClip with path
        """
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
            
            # Log cost
            try:
                from utils.cost_tracker import log_video_generation
                # Extract scenario_id from path (e.g., "output/scenario_xxx/video_1.mp4")
                scenario_id = video_path.parent.name
                log_video_generation(self.video_model, scenario_id, self.video_duration)
            except ImportError:
                pass
            
            print(f"      ✅ Saved: {video_path.name}")
            
            return VideoClip(
                stage=keyframe.stage,
                path=str(video_path),
                duration=self.video_duration,
                has_audio=False
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
