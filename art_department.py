"""
art_department.py - Image Generation with Vision Gate

Uses Fal.ai (Nano Banana/Flux) to generate keyframes for each stage.
Verifies consistency using Gemini Vision before proceeding.
"""

import os
import json
import time
import base64
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

import yaml
import fal_client
from google import genai
from PIL import Image
import requests
from dotenv import load_dotenv

from screenwriter import Scenario
from manager import Settings, StyleConfig, load_prompt

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
class Keyframe:
    """A single keyframe image."""
    stage: int
    path: str
    prompt: str


class ArtDepartment:
    """Generates and verifies keyframe images."""
    
    def __init__(self, settings: Settings):
        """
        Initialize with settings.
        
        Args:
            settings: Application settings with style config
        """
        self.settings = settings
        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load model configuration
        self.config = load_model_config()
        fal_config = self.config.get("fal", {})
        
        # Get model names from config
        self.txt2img_model = fal_config.get("text_to_image", {}).get("model", "fal-ai/flux/schnell")
        self.txt2img_steps = fal_config.get("text_to_image", {}).get("num_inference_steps", 4)
        
        self.img2img_model = fal_config.get("image_to_image", {}).get("model", "fal-ai/flux/dev/image-to-image")
        self.img2img_strength = fal_config.get("image_to_image", {}).get("strength", 0.65)
        self.img2img_steps = fal_config.get("image_to_image", {}).get("num_inference_steps", 28)
        
        img_size = fal_config.get("image_size", {})
        self.img_width = img_size.get("width", 720)
        self.img_height = img_size.get("height", 1280)
        
        # Fal.ai client uses FAL_KEY from environment
        fal_key = os.getenv("FAL_KEY")
        if not fal_key:
            raise ValueError("FAL_KEY not found in environment")
        
        # Gemini Vision Gate using new Client API
        gemini_config = self.config.get("gemini", {})
        self.vision_model_name = gemini_config.get("model", "gemini-2.0-flash")
        self.vision_gate_enabled = gemini_config.get("vision_gate", {}).get("enabled", True)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        self.genai_client = genai.Client(api_key=api_key)
        
        # Load Vision Gate prompt
        try:
            self.vision_prompt_template = load_prompt("vision_gate")
        except FileNotFoundError:
            self.vision_prompt_template = self._get_default_vision_prompt()
        
        print(f"🎨 Art Department initialized")
        print(f"   Style: {settings.style.name}")
        print(f"   Models: {self.txt2img_model} / {self.img2img_model}")
        print(f"   Output: {self.output_dir}")
    
    def _get_default_vision_prompt(self) -> str:
        """Fallback prompt if file not found."""
        return """Verify these 3 images show the same location "{location_name}" consistently.
Reply PASS if consistent, FAIL if not."""
    
    def build_image_prompt(self, scenario: Scenario, stage_num: int) -> str:
        """
        Build a complete image prompt for a stage.
        
        Args:
            scenario: The scenario data
            stage_num: Stage number (1, 2, or 3)
            
        Returns:
            Complete prompt with style suffix
        """
        stage = getattr(scenario, f"stage_{stage_num}")
        
        # Use improved prompt if available (from Prompt Improver)
        if stage.image_prompt:
            return stage.image_prompt
            
        # CRITICAL: Enforce consistent exterior viewpoint
        # The location prompt + "exterior view" ensures we stay outside
        consistency_clause = (
            "EXTERIOR VIEW ONLY, same camera angle as previous frames, "
            "wide establishing shot, consistent architecture, same viewpoint, "
            "NO interior shots, outdoor scene"
        )
        
        # Combine location + stage description + consistency + style
        prompt_parts = [
            f"Exterior view of {scenario.location_name}",
            scenario.location_prompt,
            stage.description,
            consistency_clause,
            self.settings.style.image_suffix,
        ]
        
        return ", ".join(prompt_parts)
    
    def generate_keyframe(self, prompt: str, stage_num: int, scenario_id: str, 
                          reference_image_url: str = None) -> str:
        """
        Generate a single keyframe image using Fal.ai.
        
        Args:
            prompt: The image prompt
            stage_num: Stage number for filename
            scenario_id: Scenario ID for folder organization
            reference_image_url: Optional reference image URL for img2img (stages 2-3)
            
        Returns:
            Path to the saved image
        """
        print(f"   🖼️ Generating keyframe {stage_num}{'(img2img)' if reference_image_url else ''}...")
        
        # Create scenario folder
        scenario_dir = self.output_dir / scenario_id
        scenario_dir.mkdir(exist_ok=True)
        
        if reference_image_url:
            # Use image-to-image for stages 2-3 to maintain consistency
            # Different models use different parameter names
            if "nano-banana" in self.img2img_model:
                # nano-banana/edit uses image_urls (plural, as list)
                img2img_args = {
                    "prompt": prompt,
                    "image_urls": [reference_image_url],
                    "num_inference_steps": self.img2img_steps,
                    "num_images": 1,
                }
            else:
                # flux/dev/image-to-image and others use image_url + strength
                img2img_args = {
                    "prompt": prompt,
                    "image_url": reference_image_url,
                    "strength": self.img2img_strength,
                    "image_size": {
                        "width": self.img_width,
                        "height": self.img_height
                    },
                    "num_inference_steps": self.img2img_steps,
                    "num_images": 1,
                }
            
            result = fal_client.subscribe(
                self.img2img_model,
                arguments=img2img_args,
            )
        else:
            # Text-to-image for stage 1
            if "nano-banana" in self.txt2img_model:
                txt2img_args = {
                    "prompt": prompt,
                    "aspect_ratio": "9:16",
                    "num_inference_steps": self.txt2img_steps,
                    "num_images": 1,
                }
            else:
                txt2img_args = {
                    "prompt": prompt,
                    "image_size": {
                        "width": self.img_width,
                        "height": self.img_height
                    },
                    "num_inference_steps": self.txt2img_steps,
                    "num_images": 1,
                }
                
            result = fal_client.subscribe(
                self.txt2img_model,  # From model_config.yaml
                arguments=txt2img_args,
            )
        
        # Log cost
        try:
            from cost_tracker import log_image_generation
            log_image_generation(
                self.img2img_model if reference_image else self.txt2img_model,
                scenario.id,
                stage=stage_num
            )
        except ImportError:
            pass
        
        # Download and save the image
        image_url = result["images"][0]["url"]
        image_path = scenario_dir / f"frame_{stage_num}.png"
        
        response = requests.get(image_url)
        with open(image_path, 'wb') as f:
            f.write(response.content)
        
        print(f"      ✅ Saved: {image_path.name}")
        return str(image_path), image_url  # Return URL too for chaining
    
    def generate_all_keyframes(self, scenario: Scenario) -> List[Keyframe]:
        """
        Generate all 3 keyframes for a scenario.
        Uses text-to-image for stage 1, then image-to-image for stages 2-3.
        
        Args:
            scenario: The scenario data
            
        Returns:
            List of Keyframe objects
        """
        print(f"\n🎨 Generating keyframes for: {scenario.premise[:50]}...")
        
        keyframes = []
        reference_url = None  # Will be set after stage 1
        
        for stage_num in [1, 2, 3]:
            prompt = self.build_image_prompt(scenario, stage_num)
            path, url = self.generate_keyframe(prompt, stage_num, scenario.id, reference_url)
            
            # Use stage 1's URL as reference for stages 2-3
            if stage_num == 1:
                reference_url = url
            
            keyframes.append(Keyframe(
                stage=stage_num,
                path=path,
                prompt=prompt
            ))
        
        return keyframes
    
    def verify_consistency(self, keyframes: List[Keyframe], scenario: Scenario) -> Tuple[bool, str]:
        """
        Use Gemini Vision to verify keyframe consistency.
        
        Args:
            keyframes: List of keyframes to verify
            scenario: The scenario for context
            
        Returns:
            Tuple of (passed: bool, feedback: str)
        """
        print("\n🔍 Vision Gate: Verifying consistency...")
        
        # Load images
        images = []
        for kf in keyframes:
            img = Image.open(kf.path)
            images.append(img)
        
        # Build verification prompt from external file
        verification_prompt = self.vision_prompt_template.format(
            location_name=scenario.location_name
        )
        
        # Send to Gemini Vision using new Client API
        # PIL.Image objects are automatically converted in the new SDK
        response = self.genai_client.models.generate_content(
            model=self.vision_model_name,
            contents=[verification_prompt] + images
        )
        feedback = response.text.strip()
        
        passed = feedback.upper().startswith("PASS")
        
        if passed:
            print("   ✅ Vision Gate: PASSED")
        else:
            print("   ❌ Vision Gate: FAILED")
            print(f"   Feedback: {feedback[:200]}...")
        
        return passed, feedback
    
    def generate_with_retries(self, scenario: Scenario, max_retries: int = 3) -> Optional[List[Keyframe]]:
        """
        Generate keyframes with Vision Gate verification and retries.
        
        Args:
            scenario: The scenario data
            max_retries: Maximum retry attempts
            
        Returns:
            List of verified keyframes, or None if all retries failed
        """
        for attempt in range(1, max_retries + 1):
            print(f"\n🎬 Attempt {attempt}/{max_retries}")
            
            # Generate keyframes
            keyframes = self.generate_all_keyframes(scenario)
            
            # Skip Vision Gate if disabled
            if not self.vision_gate_enabled:
                print("\n⏭️  Vision Gate: DISABLED (skipping verification)")
                return keyframes
            
            # Verify consistency
            passed, feedback = self.verify_consistency(keyframes, scenario)
            
            if passed:
                return keyframes
            
            if attempt < max_retries:
                print(f"   🔄 Retrying...")
                time.sleep(2)  # Brief pause before retry
        
        print(f"\n❌ Failed to generate consistent keyframes after {max_retries} attempts")
        return None


if __name__ == "__main__":
    import yaml
    from manager import load_config, resolve_config_path, parse_args
    from screenwriter import generate_scenario
    
    print("\n" + "=" * 50)
    print("🎨 Testing Art Department")
    print("=" * 50)
    
    # Load config
    args = parse_args()
    config_path = resolve_config_path(args)
    settings = load_config(config_path)
    
    # Generate a test scenario
    scenario = generate_scenario()
    
    # Initialize art department
    art = ArtDepartment(settings)
    
    # Generate keyframes with Vision Gate
    keyframes = art.generate_with_retries(scenario, max_retries=settings.image_retries)
    
    if keyframes:
        print("\n✅ Successfully generated and verified keyframes!")
        for kf in keyframes:
            print(f"   Frame {kf.stage}: {kf.path}")
    else:
        print("\n❌ Failed to generate consistent keyframes")
