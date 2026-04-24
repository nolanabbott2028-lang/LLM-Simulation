"""Browser dashboard: prefer FastAPI+WebSocket; fall back to stdlib HTTP (no pip)."""
from __future__ import annotations

import threading
from typing import Any


def start_dashboard_background(world: Any, host: str | None = None, port: int | None = None) -> Any:
    from config import DASHBOARD_HOST, DASHBOARD_PORT

    host = host or DASHBOARD_HOST
    port = port or DASHBOARD_PORT

    try:
        import uvicorn
        from dashboard_app import create_app

        app = create_app(world)

        def runner() -> None:
            uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)

        t = threading.Thread(target=runner, name="dashboard-uvicorn", daemon=True)
        t.start()
        print(f"[dashboard] FastAPI + WebSocket: http://{host}:{port}/")
        return t
    except ImportError:
        pass
    except Exception as exc:
        print(f"[dashboard] uvicorn path failed ({exc}); trying stdlib HTTP…")

    try:
        from dashboard_stdlib import start_stdlib_dashboard

        start_stdlib_dashboard(world, host, port)
        print(
            f"[dashboard] stdlib HTTP (no FastAPI): http://{host}:{port}/ — "
            "live polling; pip install fastapi uvicorn for WebSocket."
        )
        return True
    except Exception as exc:
        print(
            "[dashboard] Could not start browser UI. "
            "If pip is broken (pyexpat), stdlib server should still work — error:",
            exc,
        )
        return None
