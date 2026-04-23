import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from world import WorldState
from renderer import Renderer


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Civilization Sandbox")
    clock = pygame.time.Clock()

    world = WorldState()
    renderer = Renderer(screen, world)

    running = True
    while running:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
        renderer.handle_input(events)
        renderer.draw()
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
