"""Server-side ring buffer of JSON snapshots for dashboard replay (stdlib or FastAPI)."""
from __future__ import annotations

import json
from collections import deque
from typing import Any

_MAX_FRAMES = 500
_buffer: deque[dict[str, Any]] = deque(maxlen=_MAX_FRAMES)


def replay_append(snap: dict[str, Any]) -> None:
    try:
        _buffer.append(json.loads(json.dumps(snap)))
    except Exception:
        pass


def replay_clear() -> None:
    _buffer.clear()


def replay_meta() -> dict[str, Any]:
    return {"count": len(_buffer), "max": _MAX_FRAMES}


def replay_get(index: int) -> dict[str, Any] | None:
    n = len(_buffer)
    if n == 0 or index < 0 or index >= n:
        return None
    return list(_buffer)[index]


def replay_latest_index() -> int:
    return max(0, len(_buffer) - 1)
