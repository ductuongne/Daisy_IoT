import json
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883

CMD_TOPIC = "esp32/lenh"
STATUS_TOPIC = "esp32/trangthai"

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