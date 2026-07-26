import json
from pathlib import Path

from wb_dali_ha import configured_dali_devices, is_physical_dali_device, payloads


config = json.loads(Path("config/wb-dali-ha.example.json").read_text())
settings = config["devices"][0]
items = payloads("wb-dali_23_bus_1_1", settings, "homeassistant")
bodies = [body for _, body in items]

assert any("/light/" in topic for topic, _ in items)
assert any("controls/wanted_level/on" in body.get("command_topic", "") for body in bodies)
assert any(body.get("unique_id", "").endswith("_light") for body in bodies)
assert any("/light/wb_dali_23_bus_1_1_light/config" in topic for topic, _ in items)
assert not any(body.get("schema") == "json" for body in bodies)
assert any("controls/actual_level" in body.get("brightness_state_topic", "") for body in bodies)
assert not any("brightness raw" in body.get("name", "") for body in bodies)
assert not any(body.get("name", "").endswith(" Off") for body in bodies)
assert is_physical_dali_device("wb-dali_23_bus_1_2", {"actual_level", "wanted_level"})
assert not is_physical_dali_device("wb-dali", {"actual_level", "wanted_level"})
assert not is_physical_dali_device("wb-dali_23_bus_1_broadcast", {"actual_level", "wanted_level"})
assert configured_dali_devices("/path/that/does/not/exist") == set()
print("wb-dali-ha tests: OK")
