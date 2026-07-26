#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo sh uninstall.sh" >&2
    exit 1
fi

systemctl disable --now wb-dali-ha.service 2>/dev/null || true
apt-get remove -y wb-dali-ha
echo "Configuration was kept in /etc/wb-dali-ha.json"
