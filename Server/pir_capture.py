import json
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
VIDEOS_DIR = DATA_DIR / "videos"
INFO_FILE = DATA_DIR / "information.json"

_lock = threading.Lock()
_cooldown_lock = threading.Lock()
_last_capture = 0.0
COOLDOWN_SEC = 6
VIDEO_DURATION_SEC = 5


def _ensure_dirs():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    if not INFO_FILE.exists():
        INFO_FILE.write_text("[]", encoding="utf-8")


def _read_records():
    with open(INFO_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_all_records():
    _ensure_dirs()
    with _lock:
        return _read_records()


def _save_record(record):
    with _lock:
        records = _read_records()
        records.insert(0, record)
        with open(INFO_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)


def capture_screenshot(stream_base_url, image_path):
    url = f"{stream_base_url.rstrip('/')}/capture"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    image_path.write_bytes(resp.content)


def capture_video(stream_base_url, video_path, duration=VIDEO_DURATION_SEC):
    stream_url = f"{stream_base_url.rstrip('/')}/stream"
    cap = cv2.VideoCapture(stream_url)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open stream: {stream_url}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 10

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))

    start = time.time()
    while time.time() - start < duration:
        ret, frame = cap.read()
        if not ret:
            break
        writer.write(frame)

    writer.release()
    cap.release()


def _do_capture(stream_base_url):
    _ensure_dirs()
    ts = datetime.now()
    stamp = ts.strftime("%Y%m%d_%H%M%S")
    image_name = f"pir_{stamp}.jpg"
    video_name = f"pir_{stamp}.mp4"
    image_path = IMAGES_DIR / image_name
    video_path = VIDEOS_DIR / video_name

    try:
        capture_screenshot(stream_base_url, image_path)
        capture_video(stream_base_url, video_path)

        record = {
            "id": stamp,
            "time": ts.isoformat(),
            "message": "PIR_ALERT",
            "stream_url": stream_base_url,
            "image_url": f"/data/images/{image_name}",
            "video_url": f"/data/videos/{video_name}",
            "image": f"data/images/{image_name}",
            "video": f"data/videos/{video_name}",
        }
        _save_record(record)
        print(f"PIR capture saved: {stamp}")
    except Exception as e:
        print(f"PIR capture failed: {e}")


def handle_pir_detection(stream_base_url):
    global _last_capture

    with _cooldown_lock:
        now = time.time()
        if now - _last_capture < COOLDOWN_SEC:
            return
        _last_capture = now

    threading.Thread(
        target=_do_capture,
        args=(stream_base_url,),
        daemon=True,
    ).start()
