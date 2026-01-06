
try:
    import moviepy
    print(f"MoviePy version: {moviepy.__version__}")
except:
    print("MoviePy not installed/found")

try:
    from moviepy.editor import VideoFileClip
    print("Import from moviepy.editor: SUCCESS")
except ImportError as e:
    print(f"Import from moviepy.editor: FAILED ({e})")

try:
    from moviepy import VideoFileClip
    print("Import from moviepy: SUCCESS")
except ImportError as e:
    print(f"Import from moviepy: FAILED ({e})")
