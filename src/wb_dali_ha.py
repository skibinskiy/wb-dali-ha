#!/usr/bin/env python3
"""Publish selected wb-mqtt-dali controls as Home Assistant MQTT Discovery."""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover - gives an actionable controller error
    mqtt = None

LOG = logging.getLogger("wb-dali-ha")
ROOT = "/devices/"


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


def device_block(device, name):
    return {
        "identifiers": [device],
        "name": name or device,
        "manufacturer": "Wiren Board",
        "model": "DALI"
    }


def payloads(device, settings, prefix):
    name = settings.get("name") or device
    enabled = settings.get("controls", {})
    uid = device.replace("/", "_")
    common = {"device": device_block(device, name)}
    result = []

    if settings.get("light", True):
        light = dict(common)
        light.update({
            "name": name,
            "unique_id": f"{uid}_light",
            "schema": "json",
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
        result.append((discovery_topic(prefix, "light", uid), light))

    control_specs = {
        "on_and_step_up": ("button", "On", "button", "1"),
        "off": ("button", "Off", "button", "1"),
        "step_up": ("button", "Step up", "button", "1"),
        "step_down": ("button", "Step down", "button", "1"),
        "go_to_scene": ("number", "Go to scene", "number", None),
    }
    for control, (component, title, kind, payload) in control_specs.items():
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

    if enabled.get("wanted_level", False):
        result.append((discovery_topic(prefix, "number", f"{uid}_wanted_level"), {
            **common,
            "name": f"{name} brightness raw",
            "unique_id": f"{uid}_wanted_level",
            "state_topic": wb_topic(device, "wanted_level"),
            "command_topic": wb_topic(device, "wanted_level", True),
            "min": 0, "max": 100, "step": 1, "unit_of_measurement": "%"
        }))

    if enabled.get("actual_level", False):
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
    found = {}

    def on_message(_client, _userdata, message):
        parts = message.topic.split("/")
        if len(parts) == 5 and parts[1] == "devices" and parts[3] == "controls":
            found.setdefault(parts[2], set()).add(parts[4])

    client.message_callback_add("/devices/+/controls/#", on_message)
    client.subscribe("/devices/+/controls/#", qos=1)
    time.sleep(2)
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
