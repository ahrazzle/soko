#!/usr/bin/env python3
"""Replay trilogy routes in the pinned original PuzzleScript builds.

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
import signal
import math

SOURCE_URL = "https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban_III_The_Bard_and_The_Druid.html"
HTML_SHA256 = "380d343ad35a8f8caf6863341172a7771d0d28ced2824a7a3085990614562105"
SCRIPT_SHA256 = "f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0"
SOURCES = {
    1: ("https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban.html", "9811b0538cc7dd73cb7ef271d8f5ff5d4395329a7b87c6cf18c94d7a126bf311", "81a1d27115fc40c04f27bb39d0ef12ebffbea513e3fe9f550b5173bb683728a3"),
    2: ("https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban_II_Monsters.html", "a91a1e38706a1bf70a3d1d612a89370b1f5f7c86eefbe86e13a0e2288415f14e", "1f8b35dbd51d33552c0d394ec0dbc76cd6e8be6db253eedb267d3912ed1a9738"),
    3: (SOURCE_URL, HTML_SHA256, SCRIPT_SHA256),
}
MAX_KEYS = 10_000


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_input(room: int, route: str, part: int = 3) -> None:
    if type(part) is not int or part not in SOURCES:
        raise ValueError("part must be 1, 2, or 3")
    if type(room) is not int or not 1 <= room <= 22:
        raise ValueError("room must be an integer from 1 through 22")
    if not isinstance(route, str) or len(route) > MAX_KEYS or any(k not in "UDLRA" for k in route):
        raise ValueError("route must contain at most 10000 uppercase U/D/L/R/A keys")


def checked_html(path: Path, part: int = 3) -> bytes:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCES[part][1]:
        raise ValueError("Original HTML checksum mismatch; preserve the file and review upstream changes")
    return raw


def get_html(html: Path | None = None, cache_dir: Path | None = None, part: int = 3) -> bytes:
    if html is not None:
        return checked_html(Path(html), part)
    cache_dir = Path(cache_dir) if cache_dir is not None else Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "soko-original"
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / (SOURCES[part][1] + ".html")
    if destination.exists():
        return checked_html(destination, part)
    # Retain inherited proxy and CA configuration. Never disable TLS validation.
    with tempfile.TemporaryDirectory(prefix="download-", dir=cache_dir) as temporary:
        downloaded = Path(temporary) / "part3.html"
        subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                        "--max-time", "60", "--output", str(downloaded), SOURCES[part][0]], check=True, timeout=65)
        raw = checked_html(downloaded, part)
        # Another process may have populated the cache while downloading.
        if destination.exists():
            return checked_html(destination, part)
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
    const objectIds = Object.fromEntries(Object.entries(state.objects).map(([name, obj]) => [name, obj.id]));
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
            object_count: state.objectCount, stride: STRIDE_OBJ, source_code: sourceCode, object_ids: objectIds,
            final_objects: Array.from(level.objects), glyphs: state.glyphDict,
            initial_objects: initial, frames, first_win: firstWin, first_death: firstDeath,
            restarts, again_limit_hit: againLimitHit};
}"""


def accepted(result: dict, route_length: int) -> bool:
    return (type(result.get("first_win")) is int
            and result["first_win"] == route_length
            and result.get("first_death") is None
            and result.get("restarts") == 0
            and result.get("again_limit_hit") is False)


def _replay(part: int, room: int, route: str, *, html: Path | None = None, cache_dir: Path | None = None,
          chromium: str | None = None, include_frames: bool = False) -> dict:
    validate_input(room, route, part)
    raw = get_html(html, cache_dir, part)
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
    if hashlib.sha256(source.encode()).hexdigest() != SOURCES[part][2]:
        raise ValueError("Compiled PuzzleScript source checksum mismatch")
    frames = result.pop("frames")
    result.update({
        "schema_version": 1, "evidence_level": "original_build_replay",
        "part": part, "source_url": SOURCES[part][0], "html_sha256": SOURCES[part][1],
        "puzzlescript_source_sha256": SOURCES[part][2],
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "browser_version": browser_version, "checked_at": datetime.now(timezone.utc).isoformat(),
        "route": route, "route_len": len(route), "route_sha256": hashlib.sha256(route.encode()).hexdigest(),
        "instance_sha256": digest({"html_sha256": SOURCES[part][1], "part": part, "room": room,
                                   "width": result["width"], "height": result["height"],
                                   "stride": result["stride"], "initial_objects": result["initial_objects"]}),
        "trajectory_sha256": digest(frames), "steps_executed": len(frames),
        "valid_winning_route": accepted(result, len(route)),
        "blocked_resource_requests": len(blocked),
        "public_submission": False, "formal_proof_checked": False,
    })
    result["source_pins"] = {key: result[key] for key in ("html_sha256", "puzzlescript_source_sha256", "checker_sha256", "source_url")}
    # PuzzleScript stores tiles in column-major order. Keep every object,
    # including background, goals, and transient/note objects, per cell.
    ids = result["object_ids"]
    stride, height, width = result["stride"], result["height"], result["width"]
    words = result["final_objects"]
    layers = [[sorted(name for name, oid in ids.items()
                      if words[(x * height + y) * stride + (oid >> 5)] & (1 << (oid & 31)))
               for x in range(width)] for y in range(height)]
    result["final_layers"] = layers
    # Prefer the highest collision-layer glyph; final_layers retains overlaps.
    glyphs = result.pop("glyphs")
    display = {}
    for glyph, object_layers in glyphs.items():
        if len(glyph) == 1:
            for layer, oid in enumerate(object_layers):
                if oid >= 0:
                    display[oid] = (layer, glyph.upper())
    rows = []
    for row in layers:
        rendered = []
        for cell in row:
            candidates = [display[ids[name]] for name in cell if name != "background" and ids[name] in display]
            rendered.append(max(candidates)[1] if candidates else ("?" if any(name != "background" for name in cell) else "."))
        rows.append("".join(rendered))
    result["final_ascii"] = "\n".join(rows)
    if include_frames:
        result["frames"] = frames
    result["certificate_sha256"] = digest(result)
    return result



def capability() -> dict:
    """Report local optional prerequisites without starting a browser or networking."""
    from importlib.util import find_spec
    return {"playwright_installed": find_spec("playwright") is not None,
            "system_chromium": chromium_path() is not None,
            "parts": [1, 2, 3]}


def replay(part: int, room: int, route: str, *, html=None, cache_dir=None,
           chromium=None, include_frames=False, timeout_sec=30) -> dict:
    """Replay an input prefix using the pinned original engine in an isolated worker.

    A nonwinning prefix is a normal observation. A timeout raises TimeoutError.
    """
    validate_input(room, route, part)
    if isinstance(timeout_sec, bool) or not isinstance(timeout_sec, (int, float)) or not math.isfinite(timeout_sec) or timeout_sec <= 0:
        raise ValueError("timeout_sec must be a positive finite number")
    request = dict(part=part, room=room, route=route, html=str(html) if html is not None else None,
                   cache_dir=str(cache_dir) if cache_dir is not None else None,
                   chromium=chromium, include_frames=include_frames)
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(json.dumps(request), timeout=timeout_sec)
    except BaseException as exc:
        # Kill the whole session, including Chromium, even on cancellation.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise TimeoutError(f"Original-engine replay exceeded {timeout_sec} seconds") from exc
        raise
    if process.returncode:
        try:
            error = json.loads(stdout)
        except (ValueError, TypeError):
            raise RuntimeError(f"Original-engine worker failed: {stderr.strip()}")
        kind = {"ValueError": ValueError, "FileNotFoundError": FileNotFoundError}.get(error.get("type"), RuntimeError)
        raise kind(error.get("message", "Original-engine worker failed"))
    return json.loads(stdout)


def _worker():
    try:
        result = _replay(**json.load(sys.stdin))
    except Exception as exc:
        print(json.dumps({"type": type(exc).__name__, "message": str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    raise SystemExit(_worker())
