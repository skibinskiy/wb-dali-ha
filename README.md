# wb-dali-ha

MQTT Discovery bridge for Wiren Board `wb-mqtt-dali` devices.

The service reads DALI devices and controls from MQTT, keeps a user-selected
configuration in JSON, and publishes Home Assistant MQTT Discovery payloads.
It supports one light entity per DALI ballast plus optional entities for the
individual DALI controls.

## Configuration

The default file is `/etc/wb-dali-ha.json`. A development example is available
at `config/wb-dali-ha.example.json`.

Command topics use the Wiren Board `/on` suffix. Brightness is expressed in
the DALI driver's 0..100 range.

## Local run

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install paho-mqtt
python3 src/wb_dali_ha.py --config config/wb-dali-ha.example.json --once
```

`--once` discovers retained MQTT channels and publishes discovery once. The
normal service subscribes continuously and republishes discovery when a
selected device or control changes.

## Package

The Debian package is deliberately small: it installs the Python service,
configuration schema, and a systemd unit. Build it on a Debian/Ubuntu host
with `dpkg-buildpackage -us -uc` and install the resulting `.deb` on the
controller. The controller must have `python3-paho-mqtt` available from its
APT repositories.

The WebUI schema is a safe editor for the selected devices and controls.
The service's `--discover` command can be used to generate a starting config
from the currently retained WB MQTT topics.

When the WebUI page is opened, the configurator reads the retained DALI MQTT
topics again. Removed or re-addressed DALI devices are therefore replaced by
their current MQTT identifiers. Each device is shown as a separate form item;
its controls are selected with checkboxes and only selected controls are
published to Home Assistant Discovery.

Discovery deliberately ignores retained-only MQTT topics. This prevents old
addresses and service objects such as `wb-dali`, `broadcast`, and group topics
from becoming Home Assistant devices after a DALI re-addressing operation.
On service restart, retained Discovery records owned by this package are
removed before the current configuration is published.

## Installation for users

After a GitHub release exists, users install the latest package on a Wiren
Board controller with:

```sh
curl -fsSL https://raw.githubusercontent.com/skibinskiy/wb-dali-ha/main/install.sh | sudo sh
```

The installer downloads the `.deb` asset from the latest GitHub Release,
installs dependencies, and starts `wb-dali-ha.service`. It does not modify the
existing DALI configuration. After installation, open the Wiren Board WebUI
configuration page and select the controls to expose in Home Assistant.

## Fast local installation during development

Before publishing a release, install the current source directly from a Mac:

```sh
./install-direct.sh
```

The script copies only the service and schema files to the controller. It does
not replace `/etc/wb-dali-ha.json`, so selected controls are preserved.

## Publishing a release

Create a public GitHub repository, copy this directory into it, then push a
version tag:

```sh
git add .
git commit -m "Initial wb-dali-ha release"
git push origin main
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions builds `wb-dali-ha_<version>_all.deb` and attaches it to the
Release. The installer uses that asset for every supported Wiren Board
controller because the package contains Python code and is architecture
independent.
