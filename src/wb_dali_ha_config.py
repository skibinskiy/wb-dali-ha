#!/usr/bin/env python3
"""JSON passthrough used by wb-mqtt-confed for the DALI HA config file."""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-json", action="store_true")
    parser.add_argument("--to-json", action="store_true")
    args = parser.parse_args()
    value = json.load(sys.stdin) if args.from_json else json.load(open("/etc/wb-dali-ha.json", encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("configuration must be a JSON object")
    json.dump(value, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
