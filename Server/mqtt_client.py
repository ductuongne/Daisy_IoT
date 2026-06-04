from __future__ import annotations

import json
import time
from collections import deque
from copy import deepcopy
from threading import Lock

import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883
CMD_TOPIC = "esp32/lenh"
STATUS_TOPIC = "esp32/trangthai"

_state_lock = Lock()
_events_lock = Lock()
_started = False
_connected = False
_last_message_ts = 0.0
_max_events = 50
_events = deque(maxlen=_max_events)

latest_status = {
    "alert": False,
    "online": False,
    "last_seen": None,
    "connection": "disconnected",
}

client = mqtt.Client()


def _push_event(kind: str, detail: str, payload=None) -> None:
    item = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "detail": detail,
        "payload": payload,
    }
    with _events_lock:
        _events.appendleft(item)


def _mark_online(online: bool) -> None:
    with _state_lock:
        latest_status["online"] = online
        latest_status["connection"] = "connected" if online else "disconnected"
        if online:
            latest_status["last_seen"] = time.strftime("%Y-%m-%d %H:%M:%S")


def on_connect(client, userdata, flags, rc):
    global _connected
    _connected = rc == 0
    if _connected:
        client.subscribe(STATUS_TOPIC)
        _mark_online(True)
        _push_event("system", "MQTT connected")
    else:
        _mark_online(False)
        _push_event("error", f"MQTT connect failed rc={rc}")


def on_disconnect(client, userdata, rc):
    global _connected
    _connected = False
    _mark_online(False)
    _push_event("system", f"MQTT disconnected rc={rc}")


def on_message(client, userdata, msg):
    global _last_message_ts
    payload = msg.payload.decode(errors="replace")
    _last_message_ts = time.time()
    _mark_online(True)

    if payload == "PIR_ALERT":
        with _state_lock:
            latest_status["alert"] = True
            latest_status["last_event"] = "PIR_ALERT"
        _push_event("alert", "Motion detected (PIR_ALERT)")
        return

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        _push_event("raw", payload)
        return

    if not isinstance(data, dict):
        _push_event("raw", payload)
        return

    with _state_lock:
        latest_status.update(data)
        latest_status["alert"] = bool(data.get("alert", latest_status.get("alert", False)))
        latest_status["last_seen"] = time.strftime("%Y-%m-%d %H:%M:%S")
        latest_status["connection"] = "connected"
        latest_status["online"] = True

    _push_event("status", "Status updated", data)


def start():
    global _started
    if _started:
        return
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    _started = True


def send_command(cmd: str) -> bool:
    if not cmd:
        return False
    result = client.publish(CMD_TOPIC, cmd)
    _push_event("command", f"Sent command: {cmd}", {"command": cmd, "mid": result.mid})
    return result.rc == mqtt.MQTT_ERR_SUCCESS


def is_connected() -> bool:
    return _connected


def get_events():
    with _events_lock:
        return list(_events)


def get_snapshot():
    with _state_lock:
        snapshot = deepcopy(latest_status)
    snapshot.setdefault("alert", False)
    snapshot.setdefault("online", _connected)
    snapshot.setdefault("last_seen", None)
    snapshot["connection"] = "connected" if _connected else "disconnected"
    snapshot["server_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    snapshot["events"] = get_events()
    return snapshot