from flask import Flask, render_template, redirect, jsonify, send_from_directory
from mqtt_client import *
import os

from pir_capture import DATA_DIR, IMAGES_DIR, VIDEOS_DIR, get_all_records

app = Flask(__name__)

ESP_IP = os.getenv("ESP_IP")
start()


@app.route("/")
def home():
    return render_template(
        "index.html",
        stream_url=f"http://{ESP_IP}:80"
    )


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/api/history")
def api_history():
    return jsonify(get_all_records())


@app.route("/data/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


@app.route("/data/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEOS_DIR, filename)


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
