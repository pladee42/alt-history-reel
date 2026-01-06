"""
sound_engineer.py - Audio Generation

Generates ambient sound effects for video stages using Fal.ai audio models.
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
class AudioClip:
    """A single audio clip generated for a stage."""
    stage: int
    path: str
    duration: float
    mood: str


class SoundEngineer:
    """Generates sound effects using Fal.ai."""
    
    def __init__(self, output_dir: str):
        """
        Initialize with output directory.
        
        Args:
            output_dir: Base output directory for audio files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load model configuration
        self.config = load_model_config()
        audio_config = self.config.get("fal_audio", {})
        
        # Get model and settings from config
        self.audio_model = audio_config.get("model", "fal-ai/cassetteai/sound-effects")
        self.default_duration = audio_config.get("duration", 5.0)
        
        # Verify FAL_KEY exists
        fal_key = os.getenv("FAL_KEY")
        if not fal_key:
            raise ValueError("FAL_KEY not found in environment")
        
        print(f"🔊 Sound Engineer initialized")
        print(f"   Model: {self.audio_model}")
        print(f"   Duration: {self.default_duration}s")
    
    def generate_sfx(self, mood_prompt: str, stage_num: int, 
                     scenario_id: str, duration: Optional[float] = None) -> AudioClip:
        """
        Generate a sound effect for a stage.
        
        Args:
            mood_prompt: Mood/atmosphere keywords for the sound
            stage_num: Stage number for filename
            scenario_id: Scenario ID for folder organization
            duration: Optional duration override
            
        Returns:
            AudioClip with path to the generated audio
        """
        duration = duration or self.default_duration
        
        print(f"   🎵 Generating audio for stage {stage_num}...")
        print(f"      Mood: {mood_prompt[:50]}...")
        
        # Create scenario folder if needed
        scenario_dir = self.output_dir / scenario_id
        scenario_dir.mkdir(exist_ok=True)
        
        try:
            # Prepare arguments based on model arguments
            args = {}
            
            if "elevenlabs" in self.audio_model:
                args["text"] = mood_prompt
                args["duration"] = duration
            else:
                args["prompt"] = mood_prompt
                if "stable-audio" in self.audio_model:
                    args["seconds_total"] = duration
                else:
                    args["duration"] = duration

            # Call Fal.ai sound effects API
            result = fal_client.subscribe(
                self.audio_model,
                arguments=args,
            )
            
            # Get audio URL from result
            audio_url = result.get("audio", {}).get("url")
            if not audio_url:
                # Try stable-audio structure (audio_file)
                audio_url = result.get("audio_file", {}).get("url")
            
            if not audio_url:
                # Try generic structures
                audio_url = result.get("audio_url") or result.get("url")
            
            if not audio_url:
                raise ValueError(f"No audio URL in response: {result}")
            
            # Download and save the audio
            audio_path = scenario_dir / f"audio_{stage_num}.mp3"
            
            response = requests.get(audio_url)
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            
            print(f"      ✅ Saved: {audio_path.name}")
            
            return AudioClip(
                stage=stage_num,
                path=str(audio_path),
                duration=duration,
                mood=mood_prompt
            )
            
        except Exception as e:
            print(f"      ❌ Error: {e}")
            raise
    
    def generate_all_sfx(self, scenario: Scenario) -> List[AudioClip]:
        """
        Generate sound effects for all stages of a scenario.
        
        Args:
            scenario: The scenario with mood data for each stage
            
        Returns:
            List of AudioClip objects
        """
        print(f"\n🔊 Generating audio for: {scenario.premise[:50]}...")
        
        audio_clips = []
        
        for stage_num in [1, 2, 3]:
            stage = getattr(scenario, f"stage_{stage_num}")
            
            # Build mood prompt from stage data
            mood_prompt = f"{stage.mood}, ambient atmosphere, cinematic"
            
            clip = self.generate_sfx(
                mood_prompt=mood_prompt,
                stage_num=stage_num,
                scenario_id=scenario.id
            )
            audio_clips.append(clip)
            time.sleep(1)  # Brief pause between API calls
        
        print(f"\n✅ Generated {len(audio_clips)} audio clips")
        return audio_clips


def generate_audio(scenario: Scenario, output_dir: str) -> List[AudioClip]:
    """Convenience function to generate audio for a scenario."""
    engineer = SoundEngineer(output_dir)
    return engineer.generate_all_sfx(scenario)


if __name__ == "__main__":
    # Quick test
    print("Sound Engineer module loaded successfully")
    config = load_model_config()
    print(f"Audio model: {config.get('fal_audio', {}).get('model', 'default')}")
    print(f"Duration: {config.get('fal_audio', {}).get('duration', 5.0)}s")
