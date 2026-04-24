"""FastAPI app: static dashboard + snapshot API + WebSocket stream (same process as pygame)."""
from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    try:
        import eval_type_backport  # noqa: F401 — PEP 604 hints on Python 3.9
    except ImportError:
        pass

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from simulation.replay_buffer import replay_clear, replay_get, replay_meta
from simulation.map_http import (
    map_cities_bbox,
    map_fog,
    map_provinces_bbox,
    map_regions_bbox,
    map_terrain,
    map_towns_bbox,
)
from simulation.state_snapshot import get_agent_focus, get_world_snapshot

WEB_DIR = Path(__file__).resolve().parent / "web"


def create_app(world) -> FastAPI:
    app = FastAPI(title="Civilization Sandbox Dashboard")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/snapshot")
    async def api_snapshot():
        return get_world_snapshot(world)

    @app.get("/api/map/terrain")
    async def api_map_terrain(
        lod: int = Query(0, ge=0, le=6),
        tx: int = Query(0, ge=0),
        ty: int = Query(0, ge=0),
    ):
        return map_terrain(world, lod, tx, ty)

    @app.get("/api/map/regions")
    async def api_map_regions(
        min_x: float | None = Query(None),
        min_y: float | None = Query(None),
        max_x: float | None = Query(None),
        max_y: float | None = Query(None),
    ):
        return map_regions_bbox(world, min_x, min_y, max_x, max_y)

    @app.get("/api/map/provinces")
    async def api_map_provinces(
        min_x: float | None = Query(None),
        min_y: float | None = Query(None),
        max_x: float | None = Query(None),
        max_y: float | None = Query(None),
    ):
        return map_provinces_bbox(world, min_x, min_y, max_x, max_y)

    @app.get("/api/map/cities")
    async def api_map_cities(
        min_x: float | None = Query(None),
        min_y: float | None = Query(None),
        max_x: float | None = Query(None),
        max_y: float | None = Query(None),
    ):
        return map_cities_bbox(world, min_x, min_y, max_x, max_y)

    @app.get("/api/map/towns")
    async def api_map_towns(
        min_x: float | None = Query(None),
        min_y: float | None = Query(None),
        max_x: float | None = Query(None),
        max_y: float | None = Query(None),
    ):
        return map_towns_bbox(world, min_x, min_y, max_x, max_y)

    @app.get("/api/map/fog")
    async def api_map_fog():
        return map_fog(world)

    @app.get("/api/agent/{agent_id}")
    async def api_agent(agent_id: str):
        data = get_agent_focus(world, agent_id)
        if data is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        return data

    @app.post("/api/sim/speed")
    async def api_speed(request: Request):
        try:
            body: dict[str, Any] = await request.json()
        except Exception:
            body = {}
        v = int(body.get("speed", 1))
        v = max(1, min(100, v))
        with world.lock:
            world.speed = v
        return {"speed": world.speed}

    @app.post("/api/sim/pause")
    async def api_pause(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        with world.lock:
            if body.get("toggle"):
                world.paused = not world.paused
            else:
                world.paused = bool(body.get("paused", True))
        return {"paused": world.paused}

    @app.post("/api/sim/run")
    async def api_run(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        running = bool(body.get("running", True))
        with world.lock:
            world.sim_running = running
            if running:
                world.paused = False
        return {"sim_running": world.sim_running}

    async def _read_founders_and_spawn(request: Request) -> dict[str, Any]:
        from bootstrap import spawn_adam_eve_near
        from config import TILE_SIZE, WORLD_TILES_H, WORLD_TILES_W

        try:
            body = await request.json()
        except Exception:
            body = {}
        cx = (WORLD_TILES_W * TILE_SIZE) / 2
        cy = (WORLD_TILES_H * TILE_SIZE) / 2
        try:
            wx = float(body.get("x", cx))
            wy = float(body.get("y", cy))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="invalid coordinates")
        ok, msg = spawn_adam_eve_near(world, wx, wy)
        return {"ok": ok, "message": msg}

    @app.post("/api/founders")
    async def api_founders(request: Request):
        return await _read_founders_and_spawn(request)

    @app.post("/api/world/founders")
    async def api_founders_world(request: Request):
        return await _read_founders_and_spawn(request)

    @app.get("/api/replay/meta")
    async def api_replay_meta():
        return replay_meta()

    @app.get("/api/replay/frame")
    async def api_replay_frame(i: int = Query(0, ge=0)):
        fr = replay_get(i)
        if fr is None:
            raise HTTPException(status_code=404, detail="no frame at index")
        return fr

    @app.post("/api/replay/clear")
    async def api_replay_clear():
        replay_clear()
        return {"ok": True, **replay_meta()}

    @app.post("/api/bookmark")
    async def api_bookmark(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        yr, day = body.get("year"), body.get("day")
        with world.lock:
            if yr is not None and day is not None:
                world.dashboard_bookmark = {
                    "year": int(yr),
                    "day": int(day),
                    "summary": (body.get("summary") or "")[:200],
                    "event_index": body.get("event_index"),
                }
            else:
                world.dashboard_bookmark = None
        return {"bookmark": getattr(world, "dashboard_bookmark", None)}

    @app.post("/api/event")
    async def api_event(request: Request):
        """Macro hooks for the dashboard — lightweight timeline / world nudges."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        kind = (body.get("type") or "").lower()
        from simulation.timeline_engine import TimelineEngine

        tl = TimelineEngine(world)
        if kind == "famine":
            with world.lock:
                for s in world.sims.values():
                    if s.alive:
                        s.hunger = max(5.0, s.hunger - 25.0)
            tl.log("crisis", "Hard season: hunger bites across the land.", {})
            return {"ok": True}
        if kind == "war_drums":
            tl.log("macro", "Whispers speak of gathering storms between bands.", {})
            return {"ok": True}
        if kind == "leader_shift":
            tl.log("macro", "Voices rise — leadership questioned in the camps.", {})
            return {"ok": True}
        tl.log("unknown", body.get("note", "An event was marked."), {})
        return {"ok": True}

    @app.websocket("/ws")
    async def ws_snap(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                snap = get_world_snapshot(world)
                await websocket.send_json(snap)
                await asyncio.sleep(0.45)
        except Exception:
            pass

    if WEB_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(WEB_DIR)), name="assets")

        @app.get("/")
        async def root():
            index = WEB_DIR / "index.html"
            if index.exists():
                return FileResponse(index)
            return {"detail": "Missing web/index.html"}

    return app
