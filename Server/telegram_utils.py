import os
import time
import threading
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


# ==========================================
# TELEGRAM BOT CONTROL LOGIC (POLLING LOOP)
# ==========================================
last_control_message_id = None

def make_control_panel_payload(chat_id, message_id=None):
    # Import inside functions to avoid circular import issues
    from mqtt_client import get_status
    
    status = get_status()
    online = status.get("online", False)
    
    if online:
        conn_str = "🟢 Trực tuyến"
        cam_str = "🟢 BẬT" if status.get("stream") == 1 else "🔴 TẮT"
        coi_kc_str = "🔊 ĐANG HÚ" if status.get("coi_kc") == 1 else "🔴 TẮT"
        coi_td_str = "🟢 BẬT" if status.get("coi_td") == 1 else "🔴 TẮT"
        pir_str = "🟢 BẬT" if status.get("pir_on") == 1 else "🔴 TẮT"
    else:
        conn_str = "🔴 Ngoại tuyến"
        cam_str = "⚪ Không rõ"
        coi_kc_str = "⚪ Không rõ"
        coi_td_str = "⚪ Không rõ"
        pir_str = "⚪ Không rõ"
        
    text = (
        f"🔔 <b>BẢNG ĐIỀU KHIỂN THIẾT BỊ DAISY IoT</b> 🔔\n\n"
        f"🌐 <b>Trạng thái kết nối</b>: {conn_str}\n"
        f"🎥 <b>Trạng thái Camera</b>: {cam_str}\n"
        f"🚨 <b>Còi báo khẩn cấp</b>: {coi_kc_str}\n"
        f"🔊 <b>Còi báo tự động</b>: {coi_td_str}\n"
        f"🧭 <b>Cảm biến PIR</b>: {pir_str}\n\n"
        f"👉 <i>Nhấp vào các nút bên dưới để bật/tắt thiết bị hoặc đồng bộ trạng thái.</i>"
    )
    
    # Generate inline keyboard
    keyboard = []
    if online:
        btn_cam = {"text": f"🎥 Camera ({'TẮT' if status.get('stream') == 1 else 'BẬT'})", "callback_data": "toggle_camera"}
        btn_kc = {"text": f"🚨 Còi khẩn ({'TẮT' if status.get('coi_kc') == 1 else 'BẬT'})", "callback_data": "toggle_emergency"}
        btn_td = {"text": f"🔊 Còi tự động ({'TẮT' if status.get('coi_td') == 1 else 'BẬT'})", "callback_data": "toggle_auto"}
        btn_pir = {"text": f"🧭 Cảm biến PIR ({'TẮT' if status.get('pir_on') == 1 else 'BẬT'})", "callback_data": "toggle_pir"}
        keyboard.append([btn_cam])
        keyboard.append([btn_kc])
        keyboard.append([btn_td])
        keyboard.append([btn_pir])
        
    # Always show refresh button
    btn_refresh = {"text": "🔄 Đồng bộ trạng thái", "callback_data": "refresh_status"}
    keyboard.append([btn_refresh])
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": keyboard}
    }
    
    if message_id:
        payload["message_id"] = message_id
        
    return payload


def send_control_panel(chat_id):
    global last_control_message_id
    payload = make_control_panel_payload(chat_id)
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        res_data = r.json()
        if res_data.get("ok"):
            last_control_message_id = res_data["result"]["message_id"]
            print("Telegram: Control panel sent and message ID stored:", last_control_message_id)
    except Exception as e:
        print("Failed to send control panel:", e)


def sync_telegram_control_panel():
    global last_control_message_id
    if not last_control_message_id or not TOKEN or not RAW_CHAT_ID:
        return
    
    payload = make_control_panel_payload(RAW_CHAT_ID, last_control_message_id)
    url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
    try:
        # Edit the message in place. Ignore exceptions (e.g. if content is identical)
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass


def handle_callback(chat_id, message_id, cb_data, cb_id):
    global last_control_message_id
    last_control_message_id = message_id

    from mqtt_client import get_status, send_command
    
    status = get_status()
    online = status.get("online", False)
    
    if not online and cb_data != "refresh_status":
        # Cannot control if offline
        try:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", json={
                "callback_query_id": cb_id,
                "text": "⚠️ Lỗi: Thiết bị đang ngoại tuyến!",
                "show_alert": False
            }, timeout=5)
        except Exception:
            pass
        payload = make_control_panel_payload(chat_id, message_id)
        url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print("Failed to edit offline message:", e)
        return

    # Process commands and determine the popup text
    alert_text = "Đã gửi lệnh đồng bộ trạng thái 🔄"
    if cb_data == "toggle_camera":
        is_on = (status.get("stream") == 1)
        alert_text = "Đã tắt Camera 🎥" if is_on else "Đã bật Camera 🎥"
        cmd = "CAMERA_OFF" if is_on else "CAMERA_ON"
        send_command(cmd)
    elif cb_data == "toggle_emergency":
        is_on = (status.get("coi_kc") == 1)
        alert_text = "Đã tắt Còi khẩn cấp 🚨" if is_on else "Đã hú Còi khẩn cấp 🚨"
        cmd = "COIKC_OFF" if is_on else "COIKC_ON"
        send_command(cmd)
    elif cb_data == "toggle_auto":
        is_on = (status.get("coi_td") == 1)
        alert_text = "Đã tắt Còi tự động 🔊" if is_on else "Đã bật Còi tự động 🔊"
        cmd = "COI_OFF" if is_on else "COI_ON"
        send_command(cmd)
    elif cb_data == "toggle_pir":
        is_on = (status.get("pir_on") == 1)
        alert_text = "Đã tắt Cảm biến PIR 🧭" if is_on else "Đã bật Cảm biến PIR 🧭"
        cmd = "CAMBIEN_OFF" if is_on else "CAMBIEN_ON"
        send_command(cmd)
    elif cb_data == "refresh_status":
        send_command("TRANG_THAI")

    # Acknowledge the callback query with the custom popup message
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", json={
            "callback_query_id": cb_id,
            "text": alert_text,
            "show_alert": False
        }, timeout=5)
    except Exception as e:
        print("Failed to answer callback query:", e)


def start_telegram_bot_loop():
    if not TOKEN or not RAW_CHAT_ID:
        print("Telegram BOT token or admin ID is missing. Bot listener will not start.")
        return

    print("Telegram: Starting Bot listener loop...")
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            params = {"offset": offset, "timeout": 30}
            r = requests.get(url, params=params, timeout=35)
            if r.status_code != 200:
                time.sleep(5)
                continue
            
            data = r.json()
            if not data.get("ok"):
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                
                # Check text message command
                if "message" in update:
                    msg = update["message"]
                    chat_id = str(msg["chat"]["id"])
                    
                    # Security check: only allow the configured admin ID
                    if chat_id != RAW_CHAT_ID:
                        print(f"Unauthorized chat attempt from Chat ID: {chat_id}")
                        continue
                        
                    text = msg.get("text", "").strip()
                    if text in ["/start", "/control", "/menu"]:
                        send_control_panel(chat_id)

                # Check callback query (button clicks)
                elif "callback_query" in update:
                    cb = update["callback_query"]
                    chat_id = str(cb["message"]["chat"]["id"])
                    
                    if chat_id != RAW_CHAT_ID:
                        continue
                        
                    cb_id = cb["id"]
                    cb_data = cb.get("data")
                    message_id = cb["message"]["message_id"]
                    
                    handle_callback(chat_id, message_id, cb_data, cb_id)
                    
        except Exception as e:
            print("Error in Telegram Bot listener loop:", e)
            time.sleep(5)


def start_bot_thread():
    if not TOKEN or not RAW_CHAT_ID:
        print("Telegram BOT token or admin ID is missing. Bot thread not started.")
        return
    
    # Start bot listener thread
    t = threading.Thread(target=start_telegram_bot_loop, daemon=True)
    t.start()
    print("Telegram: Bot listener thread started successfully.")
