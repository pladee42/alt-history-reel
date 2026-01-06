
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import dataclasses

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent))

from sound_engineer import SoundEngineer
from screenwriter import Scenario, StageData

def test_prompt_construction():
    with patch('sound_engineer.fal_client') as mock_fal, \
         patch('sound_engineer.requests') as mock_requests, \
         patch('builtins.open', new_callable=MagicMock):
        
        mock_fal.subscribe.return_value = {"audio": {"url": "http://test/audio.mp3"}}
        mock_requests.get.return_value.content = b"fake_audio_data"
        
        # Setup
        # Create a dummy config via the load_model_config mock if needed, 
        # or just instantiate Sound Engineer and inject config manually if possible.
        # But SoundEngineer loads config in __init__. We might need to mock yaml.safe_load or ignore config load.
        
        with patch('sound_engineer.load_model_config') as mock_config:
            mock_config.return_value = {
                "fal_audio": {
                    "model": "fal-ai/elevenlabs/sound-effects/v2",
                    "duration": 5.0,
                    "prompt_influence": 0.7
                }
            }
            
            engineer = SoundEngineer("tests/output")
            
            # Test generate_sfx directly
            engineer.generate_sfx(
                mood_prompt="Spooky mood",
                stage_num=1,
                scenario_id="test_scen",
                duration=None,
                stage_description="A dark forest with fog"
            )
            
            # Verify arguments passed to fal_client
            call_args = mock_fal.subscribe.call_args
            print(f"Call args: {call_args}")
            
            args_dict = call_args[1]['arguments']
            
            assert args_dict['text'] == "Spooky mood. Context: A dark forest with fog"
            assert args_dict['duration_seconds'] == 5.0
            assert args_dict['prompt_influence'] == 0.7
            
            print("✅ TEST PASSED: arguments match expectation")

if __name__ == "__main__":
    test_prompt_construction()
