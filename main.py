import pygame
import threading
from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from world import WorldState
from renderer import Renderer
from sim_loop import run_sim_loop


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Civilization Sandbox")
    clock = pygame.time.Clock()

    world = WorldState()
    renderer = Renderer(screen, world)

    sim_thread = threading.Thread(target=run_sim_loop, args=(world,), daemon=True)
    sim_thread.start()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
        renderer.handle_input(events)
        renderer.draw()
        from sim_loop import _bubble_tick
        _bubble_tick(world, dt)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
