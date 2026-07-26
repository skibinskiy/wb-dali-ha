#!/usr/bin/env python3
"""JSON passthrough used by wb-mqtt-confed for the DALI HA config file."""

import argparse
import json
import sys
import time

from wb_dali_ha import collect_live_dali_devices, connect, device_items


DEFAULT_CONTROLS = {"wanted_level", "actual_level", "on_and_step_up", "off", "error_status"}


def refresh_devices(config):
    """Replace stale IDs with the currently retained wb-mqtt-dali devices."""
    probe_config = dict(config)
    probe_config["mqtt"] = dict(config.get("mqtt", {}))
    probe_config["mqtt"]["client_id"] = "wb-dali-ha-config"
    client = connect(probe_config)
    found = collect_live_dali_devices(client)
    client.loop_stop()
    client.disconnect()

    old = dict(device_items(config))
    devices = []
    for device, controls in sorted(found.items()):
        if not device.startswith("wb-dali"):
            continue
        previous = old.get(device, {})
        previous_controls = previous.get("controls", {})
        devices.append({
            "id": device,
            "name": previous.get("name") or device,
            "light": previous.get("light", True),
            "controls": {
                control: previous_controls.get(control, control in DEFAULT_CONTROLS)
                for control in sorted(controls)
            }
        })
    result = dict(config)
    result["devices"] = devices
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-json", action="store_true")
    parser.add_argument("--to-json", action="store_true")
    args = parser.parse_args()
    input_text = sys.stdin.read()
    value = json.loads(input_text) if input_text.strip() else json.load(open("/etc/wb-dali-ha.json", encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("configuration must be a JSON object")
    if args.to_json:
        value = refresh_devices(value)
    json.dump(value, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
