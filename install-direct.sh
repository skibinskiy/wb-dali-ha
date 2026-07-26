#!/bin/sh
set -eu

CONTROLLER="${WB_DALI_HA_CONTROLLER:-root@192.168.31.243}"
REMOTE_DIR="/usr/lib/wb-dali-ha"
SCHEMA_DIR="/usr/share/wb-mqtt-confed/schemas"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

echo "Installing wb-dali-ha directly to ${CONTROLLER}"

ssh "$CONTROLLER" "mkdir -p '$REMOTE_DIR' '$SCHEMA_DIR'"
scp "$SCRIPT_DIR/src/wb_dali_ha.py" "$CONTROLLER:$REMOTE_DIR/wb_dali_ha.py"
scp "$SCRIPT_DIR/src/wb_dali_ha_config.py" "$CONTROLLER:$REMOTE_DIR/wb_dali_ha_config.py"
scp "$SCRIPT_DIR/config/wb-dali-ha.schema.json" "$CONTROLLER:$SCHEMA_DIR/wb-dali-ha.schema.json"

ssh "$CONTROLLER" "chmod 755 '$REMOTE_DIR/wb_dali_ha.py' '$REMOTE_DIR/wb_dali_ha_config.py' && apt-get update && apt-get install -y python3-paho-mqtt && systemctl daemon-reload && systemctl restart wb-dali-ha.service"

echo "Installed. Check with: ssh $CONTROLLER systemctl status wb-dali-ha.service"
