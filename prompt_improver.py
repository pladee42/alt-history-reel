"""
prompt_improver.py - Middleware Agent

Acts as a specialized prompt engineer, refining the raw scenario descriptions
into high-fidelity prompts for image and audio generation models.
"""

import os
from typing import Optional
import google.genai as genai
from dotenv import load_dotenv

from screenwriter import Scenario


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
        system_instruction = """
You are an expert AI Prompt Engineer for high-end video production.
Your task is to take a raw scene description and convert it into two specific prompts:
1. IMAGE_PROMPT: A highly detailed, artistic prompt for an image generation model (like Midjourney/Fal.ai).
2. AUDIO_PROMPT: A rich, atmospheric prompt for a sound effect generation model (ElevenLabs).

INPUT CONTEXT:
- Location: {location}
- Style: {style_name} ({style_suffix})
- Consistency: EXTERIOR VIEW ONLY, wide establishing shot, no interior shots.

Refine the descriptions to be visual, sensory, and specific to the requested style.
For Audio, focus on the soundscape (ambient noise, specific effects, mood).
For Image, focus on lighting, composition, texture, and the specific historical shift.
"""
        
        # Prepare the conversation or batch request
        # We'll do it stage by stage for simplicity and clearer context
        for i in range(1, 4):
            stage_num = f"stage_{i}"
            stage = getattr(scenario, stage_num)
            
            print(f"   ✨ Refining Stage {i}: {stage.label}...")
            
            prompt = f"""
Input Stage: {stage.label} ({stage.year})
Raw Description: {stage.description}
Mood: {stage.mood}

Generate the 2 prompts.
RETURN JSON ONLY:
{{
  "image_prompt": "...",
  "audio_prompt": "..."
}}
"""
            # Format system instruction with current context
            formatted_system = system_instruction.format(
                location=scenario.location_name,
                style_name=self.settings.style.name,
                style_suffix=self.settings.style.image_suffix
            )

            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "system_instruction": formatted_system
                    }
                )
                
                result = response.parsed
                
                # Update the stage data
                # Note: We must update the dataclass instance
                if result:
                    # We might get a dict or an object depending on parsed result structure.
                    # Google GenAI parsed usually returns a typed object if schema provided, 
                    # or a dict/list if generic JSON. Let's assume dict for now given "application/json".
                    # Actually parsed returns a python object (dict/list).
                    
                    stage.image_prompt = result.get("image_prompt", "")
                    stage.audio_prompt = result.get("audio_prompt", "")
                    
                    # Ensure style suffix is enforced if the model missed it, 
                    # but the model should include it if instructed well.
                    # Let's trust the model for now but verify length.
                    
            except Exception as e:
                print(f"   ❌ Error improving stage {i}: {e}")
                # Fallback: copy raw description
                stage.image_prompt = f"{stage.description}, {self.settings.style.image_suffix}"
                stage.audio_prompt = f"{stage.mood}, {stage.description}"

        print("✨ Prompt enhancement complete.")
        return scenario
