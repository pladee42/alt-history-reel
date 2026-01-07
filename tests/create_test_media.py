from moviepy import *
import numpy as np
import os
from pathlib import Path
from pathlib import Path

def make_test_media(output_dir="output/test_fixtures"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating test media in {output_path}...")
    
    # 3 Stages
    for i in range(1, 4):
        # 5s Blue Video
        v_name = f"video_{i}.mp4"
        v_path = output_path / v_name
        
        print(f"  Generating {v_name} (5s)...")
        clip = ColorClip(size=(1080, 1920), color=(0, 0, 255), duration=5.0)
        clip.write_videofile(str(v_path), fps=24, logger=None)

        # 5s Audio (Tone)
        a_name = f"audio_{i}.mp3"
        a_path = output_path / a_name
        
        print(f"  Generating {a_name} (5s)...")
        from moviepy.audio.AudioClip import AudioClip
        
        def sine_tone(t):
            return np.array([np.sin(440 * 2 * np.pi * t), np.sin(440 * 2 * np.pi * t)]).T

        audioclip = AudioClip(sine_tone, duration=2.0, fps=44100)
        audioclip.write_audiofile(str(a_path), fps=44100, logger=None)

    print("Done!")

if __name__ == "__main__":
    make_test_media()
