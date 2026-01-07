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
from manager import load_prompt


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
            
            # Load and format user prompt
            user_template = load_prompt("prompt_improver_user")
            prompt = user_template.format(
                label=stage.label,
                year=stage.year,
                description=stage.description,
                mood=stage.mood
            )
            # Format system instruction with current context
            formatted_system = system_instruction.format(
                location=scenario.location_name,
                style_name=self.settings.style.name,
                style_suffix=self.settings.style.image_suffix,
                description=stage.description,
                mood=stage.mood
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
                
                # Update the stage data
                if result:
                    # Handle both dict (from json.loads) and object (from parsed)
                    if isinstance(result, dict):
                        stage.image_prompt = result.get("image_prompt", "")
                        stage.audio_prompt = result.get("audio_prompt", "")
                    else:
                        # Assume it's a SimpleNamespace or similar object from genai
                        stage.image_prompt = getattr(result, "image_prompt", "")
                        stage.audio_prompt = getattr(result, "audio_prompt", "")
                    
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
