#!/usr/bin/env python3
"""Publish selected wb-mqtt-dali controls as Home Assistant MQTT Discovery."""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover - gives an actionable controller error
    mqtt = None

LOG = logging.getLogger("wb-dali-ha")
ROOT = "/devices/"
DALI_DEVICE_RE = re.compile(r"^wb-dali_[^/]+_bus_[0-9]+_[0-9]+$")


def read_config(path):
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    data.setdefault("mqtt", {})
    data["mqtt"].setdefault("host", "127.0.0.1")
    data["mqtt"].setdefault("port", 1883)
    data["mqtt"].setdefault("discovery_prefix", "homeassistant")
    data.setdefault("devices", {})
    return data


def device_items(config):
    """Return (device_id, settings) for both legacy and current config formats."""
    devices = config.get("devices", {})
    if isinstance(devices, dict):
        return list(devices.items())
    return [
        (item.get("id"), item)
        for item in devices
        if isinstance(item, dict) and item.get("id")
    ]


def wb_topic(device, control, command=False):
    suffix = "/on" if command else ""
    return f"{ROOT}{device}/controls/{control}{suffix}"


def discovery_topic(prefix, component, uid):
    return f"{prefix}/{component}/{uid}/config"


def is_physical_dali_device(device, controls):
    """Exclude the wb-dali root, broadcast objects and non-ballast topics."""
    return bool(DALI_DEVICE_RE.match(device)) and {
        "actual_level", "wanted_level"
    }.issubset(controls)


def configured_dali_devices(path="/etc/wb-mqtt-dali.conf"):
    """Read current DALI MQTT IDs from wb-mqtt-dali configuration if present."""
    try:
        with open(path, encoding="utf-8") as stream:
            text = stream.read()
        ids = set(re.findall(r"wb-dali_[^\"'\\s]+_bus_[0-9]+_[0-9]+", text))
        return ids
    except (OSError, UnicodeError):
        return set()


def collect_live_dali_devices(client, wait_seconds=5):
    """Collect physical DALI devices, filtering stale MQTT retained topics."""
    found = {}

    def on_message(_client, _userdata, message):
        parts = message.topic.split("/")
        if len(parts) != 5 or parts[1] != "devices" or parts[3] != "controls":
            return
        device, control = parts[2], parts[4]
        found.setdefault(device, set()).add(control)

    client.message_callback_add("/devices/+/controls/#", on_message)
    client.subscribe("/devices/+/controls/#", qos=1)
    time.sleep(wait_seconds)
    configured = configured_dali_devices()
    candidates = {
        device: controls
        for device, controls in found.items()
        if is_physical_dali_device(device, controls)
    }
    if configured:
        candidates = {device: controls for device, controls in candidates.items() if device in configured}
    return candidates


def clear_owned_discovery(client, prefix):
    """Remove retained Discovery configs previously created by this package."""
    topics = []

    def on_message(_client, _userdata, message):
        parts = message.topic.split("/")
        if len(parts) == 4 and parts[0] == prefix and parts[3] == "config":
            object_id = parts[2]
            payload = message.payload.decode("utf-8", errors="ignore")
            if (
                "wb_dali_" in object_id
                or object_id.startswith("wb-dali")
                or "wb-dali" in payload
                or "wb_dali" in payload
            ):
                topics.append(message.topic)

    client.message_callback_add(f"{prefix}/+/+/config", on_message)
    client.subscribe(f"{prefix}/+/+/config", qos=1)
    time.sleep(1)
    for topic in topics:
        client.publish(topic, "", qos=1, retain=True)
        LOG.info("removed stale discovery topic %s", topic)


def device_block(device, name):
    return {
        "identifiers": [device],
        "name": name or device,
        "manufacturer": "Wiren Board",
        "model": "DALI"
    }


def friendly_device_name(device):
    match = DALI_DEVICE_RE.match(device)
    if not match:
        return device
    gateway, bus, address = device.split("_")[1], device.split("_bus_")[1].split("_")[0], device.rsplit("_", 1)[1]
    return f"DALI {gateway} — шина {bus}, адрес {address}"


def payloads(device, settings, prefix):
    name = settings.get("name") or friendly_device_name(device)
    enabled = settings.get("controls", {})
    uid = re.sub(r"[^a-zA-Z0-9_]+", "_", device)
    common = {"device": device_block(device, name)}
    result = []

    if settings.get("light", True) and enabled.get("wanted_level", True):
        light = dict(common)
        light.update({
            "name": name,
            "unique_id": f"{uid}_light",
            "command_topic": wb_topic(device, "wanted_level", True),
            "brightness_state_topic": wb_topic(device, "actual_level"),
            "brightness_command_topic": wb_topic(device, "wanted_level", True),
            "brightness_scale": 100,
            "on_command_type": "brightness",
            "payload_on": "100",
            "payload_off": "0",
            "optimistic": False
        })
        if not enabled.get("wanted_level", True):
            light.pop("brightness_command_topic", None)
            light.pop("brightness_state_topic", None)
        result.append((discovery_topic(prefix, "light", f"{uid}_light"), light))

    control_specs = {
        "on_and_step_up": ("button", "On", "button", "1"),
        "off": ("button", "Off", "button", "1"),
        "step_up": ("button", "Step up", "button", "1"),
        "step_down": ("button", "Step down", "button", "1"),
        "go_to_scene": ("number", "Go to scene", "number", None),
    }
    for control, (component, title, kind, payload) in control_specs.items():
        if settings.get("light", True) and control in {"on_and_step_up", "off"}:
            continue
        if not enabled.get(control, False):
            continue
        entity = dict(common)
        entity.update({
            "name": f"{name} {title}",
            "unique_id": f"{uid}_{control}",
            "command_topic": wb_topic(device, control, True)
        })
        if kind == "button":
            entity["payload_press"] = payload
        else:
            entity.update({"min": 0, "max": 15, "step": 1, "mode": "box"})
        result.append((discovery_topic(prefix, component, f"{uid}_{control}"), entity))

    if not settings.get("light", True) and enabled.get("wanted_level", False):
        result.append((discovery_topic(prefix, "number", f"{uid}_wanted_level"), {
            **common,
            "name": f"{name} brightness raw",
            "unique_id": f"{uid}_wanted_level",
            "state_topic": wb_topic(device, "wanted_level"),
            "command_topic": wb_topic(device, "wanted_level", True),
            "min": 0, "max": 100, "step": 1, "unit_of_measurement": "%"
        }))

    if not settings.get("light", True) and enabled.get("actual_level", False):
        result.append((discovery_topic(prefix, "sensor", f"{uid}_actual_level"), {
            **common,
            "name": f"{name} actual level",
            "unique_id": f"{uid}_actual_level",
            "state_topic": wb_topic(device, "actual_level"),
            "unit_of_measurement": "%",
            "state_class": "measurement"
        }))

    if enabled.get("error_status", False):
        result.append((discovery_topic(prefix, "binary_sensor", f"{uid}_error_status"), {
            **common,
            "name": f"{name} DALI error",
            "unique_id": f"{uid}_error_status",
            "state_topic": wb_topic(device, "error_status"),
            "payload_on": "true",
            "payload_off": "false",
            "device_class": "problem"
        }))
    return result


def publish_all(client, config):
    prefix = config["mqtt"].get("discovery_prefix", "homeassistant").strip("/")
    for device, settings in device_items(config):
        for topic, body in payloads(device, settings, prefix):
            client.publish(topic, json.dumps(body, separators=(",", ":")), qos=1, retain=True)
            LOG.info("published %s", topic)


def discover(client, config):
    found = collect_live_dali_devices(client)
    result = dict(config)
    result["devices"] = []
    for device, controls in sorted(found.items()):
        if not device.startswith("wb-dali"):
            continue
        result["devices"].append({
            "id": device,
            "name": device,
            "light": True,
            "controls": {control: control in {"wanted_level", "actual_level", "on_and_step_up", "off", "error_status"} for control in sorted(controls)}
        })
    return result


def connect(config):
    if mqtt is None:
        raise RuntimeError("Install python3-paho-mqtt before running wb-dali-ha")
    options = config["mqtt"]
    client = mqtt.Client(client_id=options.get("client_id", "wb-dali-ha"))
    if options.get("username"):
        client.username_pw_set(options["username"], options.get("password", ""))
    client.connect(options.get("host", "127.0.0.1"), int(options.get("port", 1883)), 30)
    client.loop_start()
    return client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/wb-dali-ha.json")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--write-config")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = read_config(args.config)
    client = connect(config)
    try:
        if args.discover:
            config = discover(client, config)
            output = args.write_config or args.config
            with open(output, "w", encoding="utf-8") as stream:
                json.dump(config, stream, indent=2, ensure_ascii=False)
            LOG.info("wrote %s", output)
        clear_owned_discovery(client, config["mqtt"].get("discovery_prefix", "homeassistant").strip("/"))
        publish_all(client, config)
        if args.once:
            return 0
        while True:
            time.sleep(60)
            publish_all(client, config)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    sys.exit(main())
