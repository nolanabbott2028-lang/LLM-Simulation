"""
App entry — web dashboard is the default (no Pygame window).

  python3 main.py

Legacy Pygame desktop client (separate map window):

  python3 main.py --pygame
  # or:  PYGAME=1 python3 main.py

Optional flags (same as default: web only). Scripts may use
`WEB_ONLY=1` or `python3 main.py --web` to be explicit; `--web` is stripped
from `sys.argv` for compatibility.
"""
import os
import sys
import threading
import time

from config import DASHBOARD_HOST, DASHBOARD_PORT, MAP_IMAGE_PATH, SCREEN_HEIGHT, SCREEN_WIDTH, FPS
from map_context import import_map_to_terrain, try_load_map
from world import WorldState
from bootstrap import spawn_adam_eve_if_empty
from sim_loop import run_sim_loop, autonomous_tick, _bubble_tick


def _want_pygame_desktop() -> bool:
    if os.environ.get("PYGAME", "").lower() in ("1", "true", "yes"):
        return True
    if "--pygame" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--pygame"]
        return True
    return False


def _strip_web_argv() -> None:
    if "--web" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--web"]


def run_web_dashboard() -> None:
    """Full sim + HTTP dashboard only — no Pygame window."""
    world = WorldState()
    if try_load_map(MAP_IMAGE_PATH):
        import_map_to_terrain(world)
    spawn_adam_eve_if_empty(world)

    sim_thread = threading.Thread(target=run_sim_loop, args=(world,), daemon=True)
    sim_thread.start()

    if os.environ.get("DISABLE_DASHBOARD") == "1":
        print("DISABLE_DASHBOARD=1: no browser server.")
    else:
        try:
            from dashboard_server import start_dashboard_background

            if start_dashboard_background(world) is None:
                print("[dashboard] Could not start browser UI.")
            else:
                print(f"Web dashboard: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}/")
        except Exception as exc:
            print(f"[dashboard] Could not start browser UI: {exc}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped.")


def run_pygame() -> None:
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Civilization Sandbox")
    clock = pygame.time.Clock()

    world = WorldState()
    if try_load_map(MAP_IMAGE_PATH):
        import_map_to_terrain(world)
    spawn_adam_eve_if_empty(world)

    from renderer import Renderer

    renderer = Renderer(screen, world)

    sim_thread = threading.Thread(target=run_sim_loop, args=(world,), daemon=True)
    sim_thread.start()

    if os.environ.get("DISABLE_DASHBOARD") != "1":
        try:
            from dashboard_server import start_dashboard_background

            start_dashboard_background(world)
            print(f"Web dashboard: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}/")
        except Exception as exc:
            print(f"[dashboard] Could not start browser UI: {exc}")

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
        renderer.handle_input(events)
        if world.sim_running and not world.paused:
            autonomous_tick(world, dt)
            _bubble_tick(world, dt)
        renderer.draw()
        pygame.display.flip()

    pygame.quit()


def main() -> None:
    if _want_pygame_desktop():
        try:
            run_pygame()
        except ImportError as e:
            print(
                "Pygame is not available. Install it (e.g. pip install pygame) or run without it:\n"
                "  python3 main.py"
            )
            raise e
        return
    _strip_web_argv()
    run_web_dashboard()


if __name__ == "__main__":
    main()
