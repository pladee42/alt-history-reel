
import fal_client
import os
from dotenv import load_dotenv

load_dotenv()

def test_elevenlabs():
    model = "fal-ai/elevenlabs/sound-effects/v2"
    prompt = "A cinematic explosion with debris falling"
    
    print(f"Testing {model} with 'text' parameter...")
    
    try:
        result = fal_client.subscribe(
            model,
            arguments={
                "text": prompt,
                "duration_seconds": 5.0
            }
        )
        print("Success!")
        print(result)
    except Exception as e:
        print(f"Failed with 'text': {e}")
        
        print("\nRetrying with 'prompt' parameter to confirm error...")
        try:
            result = fal_client.subscribe(
                model,
                arguments={
                    "prompt": prompt,
                    "duration": 5.0
                }
            )
            print("Success with 'prompt'?")
            print(result)
        except Exception as e2:
            print(f"Failed with 'prompt': {e2}")

if __name__ == "__main__":
    test_elevenlabs()
