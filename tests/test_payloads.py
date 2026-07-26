import json
from pathlib import Path

from wb_dali_ha import payloads


config = json.loads(Path("config/wb-dali-ha.example.json").read_text())
settings = config["devices"][0]
items = payloads("wb-dali_23_bus_1_1", settings, "homeassistant")
bodies = [body for _, body in items]

assert any("/light/" in topic for topic, _ in items)
assert any("controls/wanted_level/on" in body.get("command_topic", "") for body in bodies)
assert any("controls/off/on" in body.get("command_topic", "") for body in bodies)
assert any("controls/actual_level" in body.get("state_topic", "") for body in bodies)
print("wb-dali-ha tests: OK")
