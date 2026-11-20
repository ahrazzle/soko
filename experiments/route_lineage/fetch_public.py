#!/usr/bin/env python3
"""Download every public record route for some Frontier rooms.

Uses the same endpoints as experiments/long_shortcut (splice):
/api/rooms/<part>/<room> lists the records, /api/replay/<id> gives the keys.
Writes a JSON list of {room, id, len, handle, at, keys} for lineage.py.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

BASE = "https://soko.banteg.xyz/api"


def get(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": "soko-route-lineage"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rooms", nargs="*", default=["III-14", "III-20", "III-21"])
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    out = []
    for room in args.rooms:
        part = room.split("-")[0].count("I")
        num = int(room.split("-")[1])
        for rec in get(f"rooms/{part}/{num}")["records"]:
            keys = get(f"replay/{rec['id']}")["keys"]
            if len(keys) != rec["length"]:
                raise SystemExit(f"{room} record {rec['id']}: replay has {len(keys)} keys, list says {rec['length']}")
            out.append({"room": room, "id": rec["id"], "len": rec["length"], "handle": rec["handle"], "at": rec["at"], "keys": keys})
            time.sleep(0.3)
    args.output.write_text(json.dumps(out, indent=1) + "\n")
    print(f"{len(out)} routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
