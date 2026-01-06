
from moviepy import TextClip
import inspect

print("TextClip init args:")
sig = inspect.signature(TextClip.__init__)
for name, param in sig.parameters.items():
    print(f" - {name}")
