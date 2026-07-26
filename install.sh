#!/bin/sh
set -eu

REPO="${WB_DALI_HA_REPO:-skibinskiy/wb-dali-ha}"
API="https://api.github.com/repos/${REPO}/releases/latest"
TMP_DIR="$(mktemp -d /tmp/wb-dali-ha.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo sh install.sh" >&2
    exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 1; }
command -v dpkg >/dev/null 2>&1 || { echo "dpkg is required" >&2; exit 1; }

ASSET_URL="$(curl -fsSL "$API" | sed -n 's/.*"browser_download_url": "\([^"]*wb-dali-ha_[^"]*\.deb\)".*/\1/p' | head -n 1)"
if [ -z "$ASSET_URL" ]; then
    echo "No wb-dali-ha .deb asset found in the latest release of $REPO" >&2
    exit 1
fi

echo "Downloading $ASSET_URL"
curl -fsSL "$ASSET_URL" -o "$TMP_DIR/wb-dali-ha.deb"
dpkg -i "$TMP_DIR/wb-dali-ha.deb" || true
apt-get install -f -y
systemctl enable --now wb-dali-ha.service
echo "wb-dali-ha installed successfully"
