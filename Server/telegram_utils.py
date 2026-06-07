import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("TELEBOT_TOKEN")
RAW_CHAT_ID = os.getenv("ADMIN_BOT_ID")

# Clean Token and Chat ID
if TOKEN:
    TOKEN = TOKEN.strip('"').strip("'")
if RAW_CHAT_ID:
    # Clean brackets like [5159544554] or quotes
    RAW_CHAT_ID = RAW_CHAT_ID.strip('"').strip("'").strip('[]').strip()

def send_telegram_alert(message, photo_path=None, video_path=None):
    if not TOKEN or not RAW_CHAT_ID:
        print("Telegram configuration is missing in .env (TELEBOT_TOKEN or ADMIN_BOT_ID).")
        return False

    print(f"Sending Telegram alert to Chat ID: {RAW_CHAT_ID}...")

    # 1. Send the text notification message
    url_msg = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": RAW_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url_msg, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to send Telegram text message: {e}")

    # 2. Send the captured photo if it exists
    if photo_path and Path(photo_path).exists():
        url_photo = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        try:
            with open(photo_path, "rb") as f:
                r = requests.post(
                    url_photo,
                    data={"chat_id": RAW_CHAT_ID, "caption": "📸 Hình ảnh phát hiện chuyển động"},
                    files={"photo": f},
                    timeout=15
                )
                r.raise_for_status()
            print("Telegram: Photo sent successfully.")
        except Exception as e:
            print(f"Failed to send Telegram photo: {e}")

    # 3. Send the captured video if it exists
    if video_path and Path(video_path).exists():
        url_video = f"https://api.telegram.org/bot{TOKEN}/sendVideo"
        try:
            with open(video_path, "rb") as f:
                r = requests.post(
                    url_video,
                    data={"chat_id": RAW_CHAT_ID, "caption": "🎥 Video ghi hình 5 giây"},
                    files={"video": f},
                    timeout=30
                )
                r.raise_for_status()
            print("Telegram: Video sent successfully.")
        except Exception as e:
            print(f"Failed to send Telegram video: {e}")

    return True
