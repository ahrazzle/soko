#!/usr/bin/env python3
"""Replay a route in a pinned original trilogy PuzzleScript build."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

# Support running this script directly from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from soko_mcp.original import (HTML_SHA256, SOURCE_URL, SOURCES, accepted, checked_html,
                               digest, get_html, local_page, replay, validate_input)


def check(room: int, route: str, *, html: Path | None = None, cache_dir: Path | None = None,
          chromium: str | None = None, include_frames: bool = False, timeout_sec: float = 30) -> dict:
    """Compatibility wrapper for the original Part III checker."""
    return replay(3, room, route, html=html, cache_dir=cache_dir,
                  chromium=chromium, include_frames=include_frames, timeout_sec=timeout_sec)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--room", type=int, required=True, help="Room number, 1..22")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--route")
    inputs.add_argument("--instance", type=Path, help="JSON with part=3 and route; its grid is not used")
    parser.add_argument("--html", type=Path, help="Previously downloaded original HTML, checked against the pinned hash")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--chromium", help="Executable name/path; defaults to SOKO_CHROMIUM, system Chromium, then Playwright's browser")
    parser.add_argument("--frames", action="store_true", help="Include full raw frame states rather than only their digest")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        route = args.route
        if args.instance:
            instance = json.loads(args.instance.read_text())
            if not isinstance(instance, dict) or instance.get("part") != args.part:
                raise ValueError("instance part differs from --part")
            if instance.get("room_id") not in (None, f"{('I', 'II', 'III')[args.part-1]}-{args.room}"):
                raise ValueError("instance room_id differs from --room")
            route = instance["route"]
        if args.part == 3:
            result = check(args.room, route, html=args.html, cache_dir=args.cache_dir,
                           chromium=args.chromium, include_frames=args.frames)
        else:
            result = replay(args.part, args.room, route, html=args.html, cache_dir=args.cache_dir,
                            chromium=args.chromium, include_frames=args.frames)
    except Exception as exc:
        # Preserve a failed attempt, including browser failures. Never leave an
        # earlier successful certificate at the requested output path.
        result = {
            "schema_version": 1, "evidence_level": "original_build_replay_attempt",
            "room": args.room, "valid_winning_route": False, "status": "CHECK_FAILED",
            "error_type": type(exc).__name__, "diagnostic": str(exc),
            "expected_html_sha256": SOURCES[args.part][1], "public_submission": False,
        }
        print(f"Original-engine check failed: {exc}", file=sys.stderr)
        exit_code = 2
    else:
        exit_code = 0 if result["valid_winning_route"] else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("room", "route_len", "first_win", "first_death", "valid_winning_route", "status") if key in result}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
