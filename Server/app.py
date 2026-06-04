from flask import Flask, render_template, redirect, jsonify
from mqtt_client import *
import os

app = Flask(__name__)

ESP_IP= os.getenv("ESP_IP")
start()

@app.route("/")
def home():
    return render_template(
        "index.html",
        stream_url=f"http://{ESP_IP}:80"
    )

@app.route("/status")
def status():
    return jsonify(latest_status)

@app.route("/cmd/<command>")
def command(command):

    valid = [
        "COIKC_ON",
        "COIKC_OFF",
        "COI_ON",
        "COI_OFF",
        "CAMBIEN_ON",
        "CAMBIEN_OFF",
        "CAMERA_ON",
        "CAMERA_OFF",
        "RESET",
        "TRANG_THAI"
    ]

    if command in valid:
        send_command(command)

    return redirect("/")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )