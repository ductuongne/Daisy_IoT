import json
import os
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

def on_connect(client, userdata, flags, rc):
    print("MQTT Connected")
    client.subscribe(STATUS_TOPIC)

def on_message(client, userdata, msg):
    global latest_status

    payload = msg.payload.decode()

    print("MQTT:", payload)

    if payload == "PIR_ALERT":
        latest_status["alert"] = True
        stream_url = f"http://{ESP_IP}:80"
        handle_pir_detection(stream_url)
        return

    try:
        latest_status = json.loads(payload)
    except:
        pass

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

def start():
    client.loop_start()

def send_command(cmd):
    client.publish(CMD_TOPIC, cmd)