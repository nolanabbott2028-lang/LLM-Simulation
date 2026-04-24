"""stdlib HTTP dashboard — no pip dependencies (FastAPI/uvicorn optional)."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from simulation.map_http import (
    map_cities_bbox,
    map_fog,
    map_provinces_bbox,
    map_regions_bbox,
    map_terrain,
    map_towns_bbox,
)
from config import TILE_SIZE, WORLD_TILES_H, WORLD_TILES_W
from simulation.replay_buffer import replay_clear, replay_get, replay_meta
from simulation.state_snapshot import get_agent_focus, get_world_snapshot

WEB_DIR = Path(__file__).resolve().parent / "web"


def _world_center_xy() -> tuple[float, float]:
    return (WORLD_TILES_W * TILE_SIZE) / 2, (WORLD_TILES_H * TILE_SIZE) / 2


def _qs_float(qs: dict, key: str) -> float | None:
    raw = qs.get(key, [None])[0]
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _qs_int(qs: dict, key: str, default: int = 0) -> int:
    raw = qs.get(key, [str(default)])[0]
    try:
        return int(raw)
    except ValueError:
        return default


class DashboardStdlibHandler(BaseHTTPRequestHandler):
    world: Any = None

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj: Any, status: int = 200) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _static(self, rel: str) -> None:
        path = (WEB_DIR / rel.lstrip("/")).resolve()
        if not str(path).startswith(str(WEB_DIR.resolve())):
            self.send_error(403)
            return
        if not path.is_file():
            self.send_error(404)
            return
        ext = path.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".png": "image/png",
            ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        world = self.world

        if path == "/api/snapshot":
            self._json(get_world_snapshot(world))
            return
        if path == "/api/replay/meta":
            self._json(replay_meta())
            return
        if path.startswith("/api/replay/frame"):
            qs = parse_qs(parsed.query)
            idx = int(qs.get("i", ["0"])[0])
            fr = replay_get(idx)
            if fr is None:
                self._json({"error": "out of range"}, 404)
            else:
                self._json(fr)
            return
        if path.startswith("/api/agent/"):
            aid = unquote(path.split("/api/agent/", 1)[1].strip("/"))
            data = get_agent_focus(world, aid)
            if data is None:
                self._json({"error": "not found"}, 404)
            else:
                self._json(data)
            return
        qs = parse_qs(parsed.query)
        if path == "/api/map/terrain":
            lod = max(0, min(6, _qs_int(qs, "lod", 0)))
            tx = max(0, _qs_int(qs, "tx", 0))
            ty = max(0, _qs_int(qs, "ty", 0))
            self._json(map_terrain(world, lod, tx, ty))
            return
        if path == "/api/map/regions":
            self._json(
                map_regions_bbox(
                    world,
                    _qs_float(qs, "min_x"),
                    _qs_float(qs, "min_y"),
                    _qs_float(qs, "max_x"),
                    _qs_float(qs, "max_y"),
                )
            )
            return
        if path == "/api/map/provinces":
            self._json(
                map_provinces_bbox(
                    world,
                    _qs_float(qs, "min_x"),
                    _qs_float(qs, "min_y"),
                    _qs_float(qs, "max_x"),
                    _qs_float(qs, "max_y"),
                )
            )
            return
        if path == "/api/map/cities":
            self._json(
                map_cities_bbox(
                    world,
                    _qs_float(qs, "min_x"),
                    _qs_float(qs, "min_y"),
                    _qs_float(qs, "max_x"),
                    _qs_float(qs, "max_y"),
                )
            )
            return
        if path == "/api/map/towns":
            self._json(
                map_towns_bbox(
                    world,
                    _qs_float(qs, "min_x"),
                    _qs_float(qs, "min_y"),
                    _qs_float(qs, "max_x"),
                    _qs_float(qs, "max_y"),
                )
            )
            return
        if path == "/api/map/fog":
            self._json(map_fog(world))
            return
        if path == "/" or path == "/index.html":
            self._static("index.html")
            return
        if path.startswith("/assets/"):
            self._static(path[len("/assets/") :])
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        world = self.world
        body = self._read_json_body()

        if path == "/api/sim/speed":
            v = max(1, min(100, int(body.get("speed", 1))))
            with world.lock:
                world.speed = v
            self._json({"speed": world.speed})
            return
        if path == "/api/sim/pause":
            with world.lock:
                if body.get("toggle"):
                    world.paused = not world.paused
                else:
                    world.paused = bool(body.get("paused", True))
            self._json({"paused": world.paused})
            return
        if path == "/api/sim/run":
            running = bool(body.get("running", True))
            with world.lock:
                world.sim_running = running
                if running:
                    world.paused = False
            self._json({"sim_running": world.sim_running})
            return
        if path in ("/api/founders", "/api/world/founders"):
            from bootstrap import spawn_adam_eve_near

            cx, cy = _world_center_xy()
            try:
                wx = float(body.get("x", cx))
                wy = float(body.get("y", cy))
            except (TypeError, ValueError):
                self._json({"ok": False, "error": "invalid coordinates"}, 400)
                return
            ok, msg = spawn_adam_eve_near(world, wx, wy)
            self._json({"ok": ok, "message": msg})
            return
        if path == "/api/bookmark":
            yr = body.get("year")
            day = body.get("day")
            if yr is not None and day is not None:
                with world.lock:
                    world.dashboard_bookmark = {
                        "year": int(yr),
                        "day": int(day),
                        "summary": (body.get("summary") or "")[:200],
                        "event_index": body.get("event_index"),
                    }
            else:
                with world.lock:
                    world.dashboard_bookmark = None
            self._json({"bookmark": getattr(world, "dashboard_bookmark", None)})
            return
        if path == "/api/replay/clear":
            replay_clear()
            self._json({"ok": True, **replay_meta()})
            return
        if path == "/api/event":
            kind = (body.get("type") or "").lower()
            from simulation.timeline_engine import TimelineEngine

            tl = TimelineEngine(world)
            if kind == "famine":
                with world.lock:
                    for s in world.sims.values():
                        if s.alive:
                            s.hunger = max(5.0, s.hunger - 25.0)
                tl.log("crisis", "Hard season: hunger bites across the land.", {})
            elif kind == "war_drums":
                tl.log("macro", "Whispers speak of gathering storms between bands.", {})
            elif kind == "leader_shift":
                tl.log("macro", "Voices rise — leadership questioned in the camps.", {})
            else:
                tl.log("unknown", body.get("note", "An event was marked."), {})
            self._json({"ok": True})
            return

        self.send_error(404)


def start_stdlib_dashboard(world: Any, host: str, port: int) -> ThreadingHTTPServer:
    DashboardStdlibHandler.world = world
    server = ThreadingHTTPServer((host, port), DashboardStdlibHandler)
    server.allow_reuse_address = True
    try:
        server.daemon_threads = True
    except AttributeError:
        pass

    def run() -> None:
        server.serve_forever(poll_interval=0.5)

    threading.Thread(target=run, name="dashboard-stdlib-http", daemon=True).start()
    return server
