import json
from pathlib import Path
from datetime import datetime, timedelta

import cv2
import numpy as np
import requests


BASE_DIR = Path.cwd()
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
VIDEOS_DIR = DATA_DIR / "videos"
INFO_FILE = DATA_DIR / "information.json"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

records = []

for i in range(3):

    timestamp = datetime.now() - timedelta(minutes=i * 15)

    ts_str = timestamp.strftime("%Y%m%d_%H%M%S")

    image_name = f"{ts_str}.jpg"
    video_name = f"{ts_str}.mp4"

    image_path = IMAGES_DIR / image_name
    video_path = VIDEOS_DIR / video_name

    # --------------------------------------------------
    # Download placeholder image
    # --------------------------------------------------

    image_url = (
        f"https://picsum.photos/640/480?random={i}"
    )

    r = requests.get(image_url, timeout=10)

    with open(image_path, "wb") as f:
        f.write(r.content)

    # --------------------------------------------------
    # Create fake video
    # --------------------------------------------------

    width = 640
    height = 480
    fps = 20

    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height)
    )

    for frame_num in range(100):

        frame = np.zeros(
            (height, width, 3),
            dtype=np.uint8
        )

        cv2.putText(
            frame,
            f"PIR EVENT #{i + 1}",
            (50, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (255, 255, 255),
            3
        )

        cv2.putText(
            frame,
            timestamp.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            (50, 220),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"Frame {frame_num}",
            (50, 320),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        writer.write(frame)

    writer.release()

    records.append(
        {
            "id": i + 1,
            "timestamp": timestamp.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "event": "PIR_ALERT",
            "image": f"images/{image_name}",
            "video": f"videos/{video_name}"
        }
    )

with open(INFO_FILE, "w", encoding="utf-8") as f:
    json.dump(
        records,
        f,
        indent=4,
        ensure_ascii=False
    )

print("Created:")
print(f"  {len(records)} records")
print(f"  {IMAGES_DIR}")
print(f"  {VIDEOS_DIR}")
print(f"  {INFO_FILE}")