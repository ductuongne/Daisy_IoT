from flask import Flask, render_template, redirect, jsonify
from mqtt_client import start, send_command, get_snapshot, get_events, is_connected
import os

app = Flask(__name__)

ESP_IP = os.getenv("ESP_IP", "192.168.1.50")
COMMANDS = {
    "COIKC_ON": "Bật còi khẩn cấp",
    "COIKC_OFF": "Tắt còi khẩn cấp",
    "COI_ON": "Bật còi tự động",
    "COI_OFF": "Tắt còi tự động",
    "CAMBIEN_ON": "Bật cảm biến PIR",
    "CAMBIEN_OFF": "Tắt cảm biến PIR",
    "CAMERA_ON": "Bật camera",
    "CAMERA_OFF": "Tắt camera",
    "RESET": "Khởi động lại ESP",
    "TRANG_THAI": "Lấy trạng thái",
}

# Start MQTT loop once.
start()

@app.route("/")
def home():
    return render_template(
        "index.html",
        stream_url=f"http://{ESP_IP}:80",
        commands=COMMANDS,
        initial_state=get_snapshot(),
        broker_connected=is_connected(),
    )

@app.route("/status")
def status():
    return jsonify(get_snapshot())

@app.route("/events")
def events():
    return jsonify(get_events())

@app.route("/cmd/<command>")
def command(command):
    if command in COMMANDS:
        send_command(command)
    return redirect("/")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False,
    )
