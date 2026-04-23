import threading
import time
import json
import ollama
from config import OLLAMA_MODEL, SIM_TICK_SECONDS, PILLAR_NAMES
from world import WorldState
from entities.sim import Sim, Bubble
import uuid


BUBBLE_DURATION = 6.0
MEMORY_LIMIT = 20
NEARBY_RADIUS = 5 * 32


def _nearby_context(sim: Sim, world: WorldState) -> str:
    lines = []
    for other in world.sims.values():
        if other.id != sim.id and other.alive:
            dist = ((other.position[0] - sim.position[0])**2 +
                    (other.position[1] - sim.position[1])**2) ** 0.5
            if dist < NEARBY_RADIUS:
                lines.append(f"  - {other.name} (distance {int(dist)}px, role: {other.role or 'none'})")
    for res in world.resources.values():
        if not res.depleted:
            dist = ((res.position[0] - sim.position[0])**2 +
                    (res.position[1] - sim.position[1])**2) ** 0.5
            if dist < NEARBY_RADIUS:
                lines.append(f"  - {res.object_type} at ({int(res.position[0])}, {int(res.position[1])}), qty {res.quantity}")
    for struct in world.structures.values():
        dist = ((struct.position[0] - sim.position[0])**2 +
                (struct.position[1] - sim.position[1])**2) ** 0.5
        if dist < NEARBY_RADIUS:
            lines.append(f"  - {struct.name} (structure) nearby")
    return "\n".join(lines) if lines else "  Nothing nearby."


def _relationship_summary(sim: Sim, world: WorldState) -> str:
    lines = []
    for other_id, rel in sim.relationships.items():
        other = world.sims.get(other_id)
        if other:
            lines.append(f"  - {other.name}: trust={rel.get('trust',0)}, bond={rel.get('bond',0)}, romantic={rel.get('romantic',0)}")
    return "\n".join(lines) if lines else "  No relationships yet."


def _build_prompt(sim: Sim, world: WorldState) -> str:
    memories = "\n".join(f"  - {m}" for m in sim.memory[-5:]) or "  None yet."
    nearby = _nearby_context(sim, world)
    rels = _relationship_summary(sim, world)
    pillar_summary = ", ".join(f"{k}: {int(v)}" for k, v in world.pillars.items())
    techs = ", ".join(world.technologies) if world.technologies else "none"

    return f"""You are {sim.name}, age {int(sim.age)}.
Health: {int(sim.health)}/100. Hunger: {int(sim.hunger)}/100. Energy: {int(sim.energy)}/100.
Your role: {sim.role or "none yet"}.
Your memories:
{memories}
Nearby (within sight):
{nearby}
Your relationships:
{rels}
Current era: {world.current_era()}. Known technologies: {techs}.
Civilization progress: {pillar_summary}.

What do you think, say, and do right now?
Respond ONLY as valid JSON with these exact keys:
{{
  "thought": "your inner thought (one sentence)",
  "speech": "what you say aloud, or empty string if silent",
  "action": "move|gather|build|talk|eat|sleep|reproduce|govern|trade|teach|attack|pray|invent|explore",
  "target": "name/id of target or null",
  "detail": "brief extra info"
}}"""


def _apply_action(sim: Sim, response: dict, world: WorldState):
    action = response.get("action", "move")
    detail = response.get("detail", "")

    sim.hunger = max(0, sim.hunger - 2)
    sim.energy = max(0, sim.energy - 1)
    if sim.hunger == 0:
        sim.health = max(0, sim.health - 5)
    if sim.health <= 0:
        sim.alive = False
        world.add_book_entry("People", f"Death of {sim.name}",
            f"{sim.name} passed away at age {int(sim.age)} in {world.current_era()}.")
        return

    sim.age += 1 / 365

    if action in ("move", "explore"):
        import random
        from config import WORLD_TILES_W, WORLD_TILES_H, TILE_SIZE
        world_w = WORLD_TILES_W * TILE_SIZE
        world_h = WORLD_TILES_H * TILE_SIZE
        dx = random.uniform(-2, 2) * 32
        dy = random.uniform(-2, 2) * 32
        new_x = max(0.0, min(world_w - TILE_SIZE, sim.position[0] + dx))
        new_y = max(0.0, min(world_h - TILE_SIZE, sim.position[1] + dy))
        sim.position = (new_x, new_y)

    elif action == "gather":
        for res in world.resources.values():
            if not res.depleted:
                dist = ((res.position[0] - sim.position[0])**2 +
                        (res.position[1] - sim.position[1])**2) ** 0.5
                if dist < 64:
                    item = res.object_type
                    sim.inventory[item] = sim.inventory.get(item, 0) + 1
                    res.quantity -= 1
                    if res.quantity <= 0:
                        res.depleted = True
                    sim.memory.append(f"Gathered {item}")
                    world.raise_pillar("Food Supply", 0.5)
                    break

    elif action == "eat":
        food_items = ["berry_bush", "animal_spawn", "farm_plot"]
        for item in food_items:
            if sim.inventory.get(item, 0) > 0:
                sim.inventory[item] -= 1
                sim.hunger = min(100, sim.hunger + 30)
                sim.memory.append("Ate food, felt better")
                break

    elif action == "sleep":
        sim.energy = min(100, sim.energy + 20)
        sim.memory.append("Rested and regained energy")

    elif action == "talk":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < 96:
                    rel = sim.relationships.setdefault(other.id, {"trust": 0, "bond": 0, "romantic": 0})
                    rel["trust"] = min(100, rel["trust"] + 2)
                    rel["bond"] = min(100, rel["bond"] + 1)
                    other.memory.append(f"{sim.name} said: {response.get('speech', '')[:80]}")
                    world.raise_pillar("Language", 0.5)
                    break

    elif action == "build":
        from entities.structure import Structure
        struct_name = detail or "Shelter"
        struct = Structure(
            id=str(uuid.uuid4())[:8],
            name=struct_name,
            position=(sim.position[0] + 16, sim.position[1] + 16),
            structure_type=struct_name.lower(),
            built_by=sim.id,
        )
        world.add_structure(struct)
        world.raise_pillar("Infrastructure", 2)
        sim.memory.append(f"Built {struct_name}")
        _check_milestone(world, "first_build", "History",
            f"First Structure: {struct_name}",
            f"{sim.name} built the first {struct_name}, marking a step toward permanent settlement.")

    elif action == "reproduce":
        partner = None
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                rel = sim.relationships.get(other.id, {})
                if rel.get("romantic", 0) >= 70 and sim.health >= 60 and sim.hunger >= 40:
                    partner = other
                    break
        if partner:
            child_name = detail or f"Child{len(world.sims) + 1}"
            child = Sim(
                id=str(uuid.uuid4())[:8],
                name=child_name,
                position=sim.position,
                age=0,
                skills={k: (v + partner.skills.get(k, 0)) / 2
                        for k, v in sim.skills.items()},
            )
            world.add_sim(child)
            world.raise_pillar("Social Structure", 3)
            world.add_book_entry("People", f"Birth of {child_name}",
                f"{sim.name} and {partner.name} welcomed {child_name} into the world.")

    elif action == "govern":
        law = detail or "All must share food"
        world.laws.append({"law": law, "by": sim.name, "year": world.sim_year, "day": world.sim_day})
        world.raise_pillar("Government", 5)
        sim.role = "Leader"
        sim.memory.append(f"Declared law: {law}")
        _check_milestone(world, "first_law", "Laws",
            f"First Law: {law}",
            f"{sim.name} declared the first law: '{law}'. Order had begun.")

    elif action == "trade":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < 96:
                    world.raise_pillar("Economy", 3)
                    rel = sim.relationships.setdefault(other.id, {"trust": 0, "bond": 0, "romantic": 0})
                    rel["trust"] = min(100, rel["trust"] + 5)
                    sim.memory.append(f"Traded with {other.name}")
                    _check_milestone(world, "first_trade", "History",
                        "First Trade",
                        f"{sim.name} and {other.name} exchanged goods for the first time, laying the seeds of an economy.")
                    break

    elif action == "teach":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < 96:
                    skill = detail or "survival"
                    other.skills[skill] = other.skills.get(skill, 0) + 1
                    world.raise_pillar("Education", 2)
                    sim.memory.append(f"Taught {other.name} about {skill}")
                    break

    elif action == "attack":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < 64:
                    other.health = max(0, other.health - 10)
                    world.raise_pillar("Military", 2)
                    sim.memory.append(f"Attacked {other.name}")
                    break

    elif action == "pray":
        world.raise_pillar("Culture & Religion", 3)
        sim.memory.append("Prayed and felt a sense of meaning")
        _check_milestone(world, "first_prayer", "Culture",
            "First Prayer",
            f"{sim.name} knelt and offered words to the unknown — the first stirring of faith.")

    elif action == "invent":
        tech = detail or "stone tool"
        if tech not in world.technologies:
            world.technologies.append(tech)
            world.raise_pillar("Technology", 5)
            sim.memory.append(f"Invented: {tech}")
            _check_milestone(world, f"invent_{tech}", "Technology",
                f"Invention: {tech}",
                f"{sim.name} conceived of {tech} — a leap forward in the story of their people.")

    if len(sim.memory) > MEMORY_LIMIT:
        sim.memory = sim.memory[-MEMORY_LIMIT:]

    for other_id, rel in sim.relationships.items():
        if rel.get("bond", 0) >= 50:
            rel["romantic"] = min(100, rel.get("romantic", 0) + 1)


def _check_milestone(world: WorldState, key: str, tab: str, title: str, body: str):
    if key not in world.milestones:
        world.milestones.add(key)
        world.add_book_entry(tab, title, body)


def _tick(world: WorldState):
    with world.lock:
        sim_ids = list(world.sims.keys())

    for sim_id in sim_ids:
        with world.lock:
            sim = world.sims.get(sim_id)
            if sim is None or not sim.alive:
                continue
            prompt = _build_prompt(sim, world)

        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
        except Exception:
            try:
                retry_prompt = prompt + "\n\nREMINDER: respond ONLY with raw JSON, no markdown."
                response = ollama.chat(
                    model=OLLAMA_MODEL,
                    messages=[{"role": "user", "content": retry_prompt}],
                )
                raw = response["message"]["content"].strip()
                data = json.loads(raw)
            except Exception:
                continue

        with world.lock:
            sim = world.sims.get(sim_id)
            if sim is None:
                continue
            thought = data.get("thought", "")
            speech = data.get("speech", "")
            if thought:
                sim.thought_bubble = Bubble(text=thought[:120], timer=BUBBLE_DURATION)
            if speech:
                sim.speech_bubble = Bubble(text=speech[:120], timer=BUBBLE_DURATION)
            _apply_action(sim, data, world)

    world.advance_time()


def _bubble_tick(world: WorldState, dt: float):
    with world.lock:
        for sim in world.sims.values():
            if sim.thought_bubble:
                sim.thought_bubble.timer -= dt
                if sim.thought_bubble.timer <= 0:
                    sim.thought_bubble = None
            if sim.speech_bubble:
                sim.speech_bubble.timer -= dt
                if sim.speech_bubble.timer <= 0:
                    sim.speech_bubble = None


def run_sim_loop(world: WorldState):
    while True:
        if not world.sim_running or world.paused:
            time.sleep(0.1)
            continue
        tick_interval = SIM_TICK_SECONDS / world.speed
        _tick(world)
        time.sleep(tick_interval)
