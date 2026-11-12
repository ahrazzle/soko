#!/usr/bin/env python3
"""Replay Part III routes in the pinned original PuzzleScript build.

The upstream HTML is fetched into an external cache, never vendored here.
Requires optional Playwright and Chromium; importing this module does not.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

SOURCE_URL = "https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban_III_The_Bard_and_The_Druid.html"
HTML_SHA256 = "380d343ad35a8f8caf6863341172a7771d0d28ced2824a7a3085990614562105"
SCRIPT_SHA256 = "f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0"
MAX_KEYS = 10_000


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_input(room: int, route: str) -> None:
    if type(room) is not int or not 1 <= room <= 22:
        raise ValueError("room must be an integer from 1 through 22 (Part III)")
    if not isinstance(route, str) or len(route) > MAX_KEYS or any(k not in "UDLRA" for k in route):
        raise ValueError("route must contain at most 10000 uppercase U/D/L/R/A keys")


def checked_html(path: Path) -> bytes:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != HTML_SHA256:
        raise ValueError("Original HTML checksum mismatch; preserve the file and review upstream changes")
    return raw


def get_html(html: Path | None = None, cache_dir: Path | None = None) -> bytes:
    if html is not None:
        return checked_html(html)
    cache_dir = cache_dir or Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "soko-original"
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / (HTML_SHA256 + ".html")
    if destination.exists():
        return checked_html(destination)
    # Retain inherited proxy and CA configuration. Never disable TLS validation.
    with tempfile.TemporaryDirectory(prefix="download-", dir=cache_dir) as temporary:
        downloaded = Path(temporary) / "part3.html"
        subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                        "--max-time", "60", "--output", str(downloaded), SOURCE_URL], check=True, timeout=65)
        raw = checked_html(downloaded)
        # Another process may have populated the cache while downloading.
        if destination.exists():
            return checked_html(destination)
        downloaded.replace(destination)
        return raw


def chromium_path(explicit: str | None = None) -> str | None:
    selected = explicit or os.environ.get("SOKO_CHROMIUM")
    if selected:
        found = shutil.which(selected)
        if found is None:
            raise ValueError("Requested Chromium executable was not found")
        return found
    return shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")


@contextmanager
def local_page(raw: bytes):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/part3.html":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/part3.html"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


# Instrumentation observes the original functions; transitions and win rules are
# executed unchanged. The pinned build is self-contained and needs no remote JS.
REPLAY_JS = r"""({room, route}) => {
    const rooms = state.levels.map((x, i) => ({x, i})).filter(({x}) => x.width && x.height);
    const entry = rooms[room - 1];
    if (!entry) throw Error('Unknown room');
    unitTesting = false; muted = 1; winning = false;
    loadLevelFromState(state, entry.i, 'soko-original-replay-v2');
    const initial = Array.from(level.objects);
    let restarts = 0;
    const oldRestart = DoRestart;
    DoRestart = function(...args) { restarts++; return oldRestart(...args); };
    const corpseId = state.objects.corpse?.id;
    function corpse() {
        if (corpseId === undefined) return false;
        for (let i = 0; i < level.n_tiles; i++)
            if (level.objects[i * STRIDE_OBJ + (corpseId >> 5)] & (1 << (corpseId & 31))) return true;
        return false;
    }
    const frames = [];
    let firstWin = null, firstDeath = null, againLimitHit = false;
    const keys = {U: 0, L: 1, D: 2, R: 3, A: 4};
    try {
        for (let i = 0; i < route.length; i++) {
            processInput(keys[route[i]]);
            let againSteps = 0;
            while (againing && !winning && againSteps < 100) {
                processInput(-1); againSteps++;
            }
            if (againing && !winning) againLimitHit = true;
            const dead = corpse() || restarts > 0;
            frames.push({step: i + 1, key: route[i], winning, dead, restarts,
                         objects: Array.from(level.objects)});
            if (dead) { firstDeath = i + 1; break; }
            if (winning) { firstWin = i + 1; break; }
            if (againLimitHit) break;
        }
    } finally { DoRestart = oldRestart; }
    return {room, compiled_level_index: entry.i, width: entry.x.width, height: entry.x.height,
            object_count: state.objectCount, stride: STRIDE_OBJ, source_code: sourceCode,
            initial_objects: initial, frames, first_win: firstWin, first_death: firstDeath,
            restarts, again_limit_hit: againLimitHit};
}"""


def accepted(result: dict, route_length: int) -> bool:
    return (type(result.get("first_win")) is int
            and result["first_win"] == route_length
            and result.get("first_death") is None
            and result.get("restarts") == 0
            and result.get("again_limit_hit") is False)


def check(room: int, route: str, *, html: Path | None = None, cache_dir: Path | None = None,
          chromium: str | None = None, include_frames: bool = False) -> dict:
    validate_input(room, route)
    raw = get_html(html, cache_dir)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Install the optional playwright package and Chromium; see experiments/original_engine/README.md") from exc
    with local_page(raw) as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=chromium_path(chromium), headless=True)
        try:
            context = browser.new_context(service_workers="block")
            blocked = []

            def route_request(request):
                if request.request.url == url:
                    request.continue_()
                else:
                    blocked.append(request.request.url)
                    request.abort()

            context.route("**/*", route_request)
            page = context.new_page()
            page.goto(url, wait_until="load", timeout=30_000)
            result = page.evaluate(REPLAY_JS, {"room": room, "route": route})
            browser_version = browser.version
        finally:
            browser.close()
    source = result.pop("source_code")
    if hashlib.sha256(source.encode()).hexdigest() != SCRIPT_SHA256:
        raise ValueError("Compiled PuzzleScript source checksum mismatch")
    frames = result.pop("frames")
    result.update({
        "schema_version": 1, "evidence_level": "original_build_replay",
        "source_url": SOURCE_URL, "html_sha256": HTML_SHA256,
        "puzzlescript_source_sha256": SCRIPT_SHA256,
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "browser_version": browser_version, "checked_at": datetime.now(timezone.utc).isoformat(),
        "route": route, "route_len": len(route), "route_sha256": hashlib.sha256(route.encode()).hexdigest(),
        "instance_sha256": digest({"html_sha256": HTML_SHA256, "part": 3, "room": room,
                                   "width": result["width"], "height": result["height"],
                                   "stride": result["stride"], "initial_objects": result["initial_objects"]}),
        "trajectory_sha256": digest(frames), "steps_executed": len(frames),
        "valid_winning_route": accepted(result, len(route)),
        "blocked_resource_requests": len(blocked),
        "public_submission": False, "formal_proof_checked": False,
    })
    if include_frames:
        result["frames"] = frames
    result["certificate_sha256"] = digest(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--room", type=int, required=True, help="Part III room number, 1..22")
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
            if not isinstance(instance, dict) or instance.get("part") != 3:
                raise ValueError("instance must specify part=3")
            if instance.get("room_id") not in (None, f"III-{args.room}"):
                raise ValueError("instance room_id differs from --room")
            route = instance["route"]
        result = check(args.room, route, html=args.html, cache_dir=args.cache_dir,
                       chromium=args.chromium, include_frames=args.frames)
    except Exception as exc:
        # Preserve a failed attempt, including browser failures. Never leave an
        # earlier successful certificate at the requested output path.
        result = {
            "schema_version": 1, "evidence_level": "original_build_replay_attempt",
            "room": args.room, "valid_winning_route": False, "status": "CHECK_FAILED",
            "error_type": type(exc).__name__, "diagnostic": str(exc),
            "expected_html_sha256": HTML_SHA256, "public_submission": False,
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
