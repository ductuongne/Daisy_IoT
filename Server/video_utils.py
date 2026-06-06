import shutil
import subprocess
from pathlib import Path


def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def encode_for_browser(video_path):
    """Re-encode to H.264 (yuv420p) so HTML5 video can play in Chrome/Edge/Firefox."""
    path = Path(video_path)
    if not path.exists():
        return False

    if not ffmpeg_available():
        print("ffmpeg not found — browser may not play this MP4 (needs H.264)")
        return False

    tmp = path.with_suffix(".tmp.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(tmp),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"ffmpeg encode failed: {result.stderr[-500:]}")
        if tmp.exists():
            tmp.unlink()
        return False

    tmp.replace(path)
    return True
