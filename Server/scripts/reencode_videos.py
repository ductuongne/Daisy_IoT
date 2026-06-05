"""Re-encode existing data/videos/*.mp4 to H.264 for browser playback."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video_utils import encode_for_browser

VIDEOS_DIR = Path(__file__).resolve().parent.parent / "data" / "videos"

for path in sorted(VIDEOS_DIR.glob("*.mp4")):
    print(f"Encoding {path.name}...")
    if encode_for_browser(path):
        print(f"  OK: {path.name}")
    else:
        print(f"  FAILED: {path.name}")
