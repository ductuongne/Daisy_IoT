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
    except Exception as e:
        print("MQTT parsing error:", e)

# Use v2 client to match requirements of paho-mqtt 2.0+
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

client.on_connect = on_connect
client.on_message = on_message

def start():
    try:
        # Use connect_async to prevent blocking Flask startup when the broker is offline
        client.connect_async(BROKER, PORT, 60)
        client.loop_start()
        print(f"MQTT loop started, connecting to broker {BROKER}:{PORT}...")
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