import json
import os
import time
import threading
from dotenv import load_dotenv

import paho.mqtt.client as mqtt

from pir_capture import handle_pir_detection

load_dotenv()

BROKER = os.getenv("BROKER")
raw_port = os.getenv("PORT")
PORT = int(raw_port) if raw_port else 1883

CMD_TOPIC = "esp32/lenh"
STATUS_TOPIC = "esp32/trangthai"

ESP_IP = os.getenv("ESP_IP")

latest_status = {}
last_alert_time = 0.0
last_status_time = 0.0
status_lock = threading.Lock()

print("MQTT PID:", os.getpid())

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("MQTT Connected successfully")
        client.subscribe(STATUS_TOPIC)
    else:
        print(f"MQTT Connection failed with code {reason_code}")

def on_message(client, userdata, msg):
    global last_alert_time, last_status_time

    payload = msg.payload.decode()

    print("MQTT received payload:", payload)

    if payload == "PIR_ALERT":
        last_alert_time = time.time()
        stream_url = f"http://{ESP_IP}:80"
        handle_pir_detection(stream_url)
        return

    try:
        new_status = json.loads(payload)
        required_fields = ["coi_kc", "coi_td", "pir_on", "stream"]
        if all(field in new_status for field in required_fields):
            last_status_time = time.time()
            with status_lock:
                latest_status.clear()
                latest_status.update(new_status)
            print("STATUS UPDATE: ", latest_status)
            
            # Sync Telegram control panel menu reactively
            try:
                from telegram_utils import sync_telegram_control_panel
                import threading
                threading.Thread(target=sync_telegram_control_panel, daemon=True).start()
            except Exception as e:
                print("Failed to trigger Telegram sync:", e)
    except Exception as e:
        print("MQTT parsing error:", e)

# Use v2 client to match requirements of paho-mqtt 2.0+
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

client.on_connect = on_connect
client.on_message = on_message

def check_connection_loop():
    # Wait a bit on startup so we don't spam offline warnings immediately
    time.sleep(10)
    
    # Track the last known state
    is_online = (time.time() - last_status_time < 10.0)
    last_known_state = is_online
    
    while True:
        try:
            time.sleep(2)
            current_online = (time.time() - last_status_time < 10.0)
            
            if current_online != last_known_state:
                last_known_state = current_online
                
                # State changed! Notify Telegram
                from telegram_utils import send_telegram_alert, sync_telegram_control_panel
                
                if not current_online:
                    # Device went offline
                    msg = (
                        "⚠️ <b>CẢNH BÁO MẤT KẾT NỐI</b> ⚠️\n\n"
                        "🔴 Thiết bị ESP32-CAM đã <b>MẤT KẾT NỐI</b> đột ngột!\n"
                        "⏰ Thời gian: " + time.strftime("%H:%M:%S ngày %d/%m/%Y") + "\n\n"
                        "<i>Vui lòng kiểm tra nguồn điện hoặc mạng Wi-Fi của thiết bị.</i>"
                    )
                    send_telegram_alert(msg)
                    sync_telegram_control_panel()
                else:
                    # Device came back online
                    msg = (
                        "✅ <b>THIẾT BỊ ĐÃ KẾT NỐI LẠI</b> ✅\n\n"
                        "🟢 Thiết bị ESP32-CAM đã <b>TRỰC TUYẾN</b> trở lại!\n"
                        "⏰ Thời gian: " + time.strftime("%H:%M:%S ngày %d/%m/%Y")
                    )
                    send_telegram_alert(msg)
                    sync_telegram_control_panel()
                    
        except Exception as e:
            print("Error in connection check loop:", e)


def start():
    try:
        # Use connect_async to prevent blocking Flask startup when the broker is offline
        client.connect_async(BROKER, PORT, 60)
        client.loop_start()
        print(f"MQTT loop started, connecting to broker {BROKER}:{PORT}...")
        
        # Start connection monitor thread
        t = threading.Thread(target=check_connection_loop, daemon=True)
        t.start()
        print("MQTT connection monitor thread started successfully.")
    except Exception as e:
        print(f"Failed to start MQTT connection: {e}")

def get_status():
    global last_status_time
    is_online = (time.time() - last_status_time < 10.0)
    with status_lock:
        status = latest_status.copy()
    status["online"] = is_online
    status["alert"] = (time.time() - last_alert_time < 5.0)
    return status

def send_command(cmd):
    try:
        client.publish(CMD_TOPIC, cmd)
    except Exception as e:
        print(f"Failed to publish command {cmd}: {e}")