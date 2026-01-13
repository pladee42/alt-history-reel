"""
prompt_improver.py - Middleware Agent

Acts as a specialized prompt engineer, refining the raw scenario descriptions
into high-fidelity prompts for image and audio generation models.
"""

import os
from typing import Optional
import google.genai as genai
from dotenv import load_dotenv

from agents.screenwriter import Scenario
from helpers.manager import load_prompt


load_dotenv()


class PromptImprover:
    """Refines scenario descriptions into high-quality generation prompts."""

    def __init__(self, settings):
        self.settings = settings
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = settings.gemini_model

    def improve_scenario(self, scenario: Scenario) -> Scenario:
        """
        Process the entire scenario and populate improved prompts for each stage.
        """
        print(f"✨ Enhancing prompts for: {scenario.title}...")

        # Construct the system instruction
        # Construct the system instruction
        system_instruction = load_prompt("prompt_improver")
        
        # Prepare the conversation or batch request
        # We'll do it stage by stage for simplicity and clearer context
        for i in range(1, 4):
            stage_num = f"stage_{i}"
            stage = getattr(scenario, stage_num)
            
            print(f"   ✨ Refining Stage {i}: {stage.label}...")
            
            try:
                # Format system instruction (User might have custom placeholders)
                # We provide all available context just in case
                sys_formatted = system_instruction.format(
                    location=scenario.location_name,
                    style_name=self.settings.style.name,
                    style_suffix=self.settings.style.image_suffix,
                    description=stage.description,
                    mood=stage.mood
                )

                # ------------------------------------------------------------------
                # STEP 1: Generate Visual Prompt (Image)
                # ------------------------------------------------------------------
                print(f"      🎨 Generating Image Prompt...")
                template_img = load_prompt("improver_image_user")
                prompt_img = template_img.format(
                    label=stage.label,
                    year=stage.year,
                    description=stage.description,
                    mood=stage.mood,
                    style_name=self.settings.style.name,
                    style_suffix=self.settings.style.image_suffix
                )
                
                response_img = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt_img,
                    config={
                        "response_mime_type": "application/json",
                        "system_instruction": sys_formatted
                    }
                )
                
                result_img = self._parse_json_response(response_img)
                if result_img:
                    if isinstance(result_img, dict):
                        stage.image_prompt = result_img.get("image_prompt", "")
                    else:
                        stage.image_prompt = getattr(result_img, "image_prompt", "")
                else:
                    print(f"      ❌ Image prompt generation failed for stage {i}. Falling back.")
                    stage.image_prompt = f"{stage.description}, {self.settings.style.image_suffix}"
                
                # ------------------------------------------------------------------
                # STEP 2: Generate Audio Prompt (Based on Image Prompt)
                # ------------------------------------------------------------------
                if stage.image_prompt: # Only try if image prompt was successfully generated or fell back
                    print(f"      🔊 Generating Audio Prompt (from Image)...")
                    template_audio = load_prompt("improver_audio_user")
                    prompt_audio = template_audio.format(
                        label=stage.label,
                        year=stage.year,
                        image_prompt=stage.image_prompt,
                        mood=stage.mood
                    )
                    
                    response_audio = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt_audio,
                        config={
                            "response_mime_type": "application/json",
                            "system_instruction": sys_formatted
                        }
                    )
                    
                    result_audio = self._parse_json_response(response_audio)
                    if result_audio:
                        if isinstance(result_audio, dict):
                            stage.audio_prompt = result_audio.get("audio_prompt", "")
                        else:
                            stage.audio_prompt = getattr(result_audio, "audio_prompt", "")
                    else:
                        print(f"      ❌ Audio prompt generation failed for stage {i}. Falling back.")
                        stage.audio_prompt = f"{stage.mood}, {stage.description}"
                else:
                    print(f"      ⚠️ Skipping audio prompt generation for stage {i} due to missing image prompt.")
                    stage.audio_prompt = f"{stage.mood}, {stage.description}" # Fallback for audio if image failed
                    
            except Exception as e:
                print(f"   ❌ Error improving stage {i}: {e}")
                import traceback
                traceback.print_exc()
                # Fallback: copy raw description
                stage.image_prompt = f"{stage.description}, {self.settings.style.image_suffix}"
                stage.audio_prompt = f"{stage.mood}, {stage.description}"

        print("✨ Prompt enhancement complete.")
        return scenario

    def _parse_json_response(self, response):
        """
        Helper to parse JSON response with fallback.
        """
        result = response.parsed
        
        # Fallback if parsed is None but text exists
        if not result and response.text:
            try:
                text = response.text.strip()
                # Clean markdown code blocks
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    if text.endswith("```"):
                        text = text.rsplit("\n", 1)[0]
                text = text.strip()
                import json
                result = json.loads(text)
            except Exception as e:
                print(f"   ❌ JSON Parsing failed: {e}")
                print(f"DEBUG Response Text: {response.text}")
        
        return result
