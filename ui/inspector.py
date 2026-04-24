import pygame
from config import TIMELINE_HEIGHT
from entities.sim import Sim
from world import WorldState


PANEL_W = 280
PANEL_X = 10
PANEL_Y_BASE = TIMELINE_HEIGHT + 10


def draw_inspector(screen: pygame.Surface, sim: Sim, world: WorldState,
                   font_sm: pygame.font.Font, font_md: pygame.font.Font):
    lines = [
        f"Name:   {sim.name}",
        f"Age:    {int(sim.age)}",
        f"Health: {int(sim.health)}/100",
        f"Hunger: {int(sim.hunger)}/100",
        f"Thirst: {int(sim.thirst)}/100",
        f"Energy: {int(sim.energy)}/100",
        f"Role:   {sim.role or 'none'}",
        f"Speech (personal): {int(sim.language_fluency)}/100",
        "",
        "Inventory:",
    ]
    for item, qty in sim.inventory.items():
        lines.append(f"  {item}: {qty}")
    lines.append("")
    lines.append("Skills:")
    for skill, level in sim.skills.items():
        lines.append(f"  {skill}: {int(level)}")
    lines.append("")
    lines.append("Relationships:")
    with world.lock:
        for other_id, rel in sim.relationships.items():
            other = world.sims.get(other_id)
            if other:
                lines.append(f"  {other.name}: bond={rel.get('bond',0)} trust={rel.get('trust',0)}")
    lines.append("")
    with world.lock:
        lp = world.language_progress
    lines.append(f"People's speech (shared): {int(lp)}/100")
    lines.append("")
    lines.append("Recent memories:")
    for m in sim.memory[-5:]:
        lines.append(f"  - {m[:40]}")

    line_h = font_sm.get_height() + 2
    panel_h = len(lines) * line_h + 24
    surface = pygame.Surface((PANEL_W, panel_h), pygame.SRCALPHA)
    surface.fill((20, 18, 30, 220))
    screen.blit(surface, (PANEL_X, PANEL_Y_BASE))
    pygame.draw.rect(screen, (80, 100, 160), (PANEL_X, PANEL_Y_BASE, PANEL_W, panel_h), 2, border_radius=6)

    title = font_md.render(f"[ {sim.name} ]", True, (220, 200, 255))
    screen.blit(title, (PANEL_X + PANEL_W // 2 - title.get_width() // 2, PANEL_Y_BASE + 4))

    for i, line in enumerate(lines):
        color = (200, 190, 230) if not line.startswith("  ") else (160, 155, 190)
        lbl = font_sm.render(line, True, color)
        screen.blit(lbl, (PANEL_X + 8, PANEL_Y_BASE + 22 + i * line_h))
