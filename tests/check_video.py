
from moviepy import VideoFileClip
import sys
import os

try:
    path = "output/test_assembly_001/final_cut.mp4"
    if not os.path.exists(path):
        print(f"File not found at {path}")
        sys.exit(1)
        
    print(f"Inspecting {path}...")
    clip = VideoFileClip(path)
    print(f"Duration: {clip.duration}")
    print(f"Size: {clip.size}")
    if clip.audio:
        print(f"Audio Duration: {clip.audio.duration}")
    else:
        print("No Audio Track Found")
    clip.close()
    print("Video seems valid.")
except Exception as e:
    print(f"FAILED to load video: {e}")
    sys.exit(1)
