
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

sys.path.append(str(Path(__file__).parent.parent))

from prompt_improver import PromptImprover
from screenwriter import Scenario, StageData

@dataclass
class MockStyle:
    name: str = "Realistic"
    image_suffix: str = "photorealistic, 8k"

@dataclass
class MockSettings:
    gemini_model: str = "gemini-2.0-flash"
    style: MockStyle = MockStyle()

class TestPromptImprover(unittest.TestCase):
    def setUp(self):
        self.settings = MockSettings()
        self.scenario = Scenario(
            id="test_id",
            title="What if Rome Never Fell?",
            premise="Rome continues to rule.",
            location_name="Colosseum",
            location_prompt="Ancient arena",
            stage_1=StageData(year="2024", label="Eternal Rome", description="Modern tech mixed with Roman architecture", mood="Grand"),
            stage_2=StageData(year="2025", label="Stage 2", description="Desc 2", mood="Mood 2"),
            stage_3=StageData(year="2026", label="Stage 3", description="Desc 3", mood="Mood 3"),
        )

    @patch('prompt_improver.genai')
    @patch('prompt_improver.os.getenv')
    def test_improve_scenario(self, mock_getenv, mock_genai):
        mock_getenv.return_value = "fake_key"
        
        # Mock client and response
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.parsed = {
            "image_prompt": "Improved Image Prompt",
            "audio_prompt": "Improved Audio Prompt"
        }
        mock_client.models.generate_content.return_value = mock_response

        improver = PromptImprover(self.settings)
        improved_scenario = improver.improve_scenario(self.scenario)

        # check if stage 1 was updated
        self.assertEqual(improved_scenario.stage_1.image_prompt, "Improved Image Prompt")
        self.assertEqual(improved_scenario.stage_1.audio_prompt, "Improved Audio Prompt")
        
        # Verify call arguments
        args = mock_client.models.generate_content.call_args
        # We can inspect args if needed, but the effect is verified.
        print("✅ Prompt Improver updated stage data correctly.")

if __name__ == '__main__':
    unittest.main()
