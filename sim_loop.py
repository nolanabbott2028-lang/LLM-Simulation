from __future__ import annotations

import random
import threading
import time
import json
import sys
from config import OLLAMA_MODEL, SIM_TICK_SECONDS, OLLAMA_WARN_INTERVAL_SEC
from world import WorldState
from entities.sim import Sim, Bubble
from ollama_client import ollama_chat
from map_context import environment_paragraph, in_water, adjacent_to_water, terrain_at_world
from language import bump_language, stage_label
from simulation.ideology import (
    blend_child_beliefs,
    on_attack_as_aggressor,
    on_attack_as_victim,
    on_faction_mutual_aid,
    on_gather_success,
    on_law_declaration,
    on_starvation_pressure,
    on_trade_success as belief_trade,
    avoids_outsiders,
    prefers_trade,
    ensure_beliefs,
)
from simulation.prompts import build_prompt
from simulation.world_engine import get_world_engine
from simulation.materials import gather_yields_for_node
from simulation.crafting import RECIPES, suggested_recipe_ids, try_craft
from simulation.relationships import on_attack as rel_on_attack, on_trade_success as rel_trade_success
from simulation.war_system import GRIEVANCE_ATTACK
import uuid

INTERACT_RADIUS = 120


_SYSTEM_PROMPT = (
    "You are simulating the inner life of a real person in a real world. "
    "This person has no concept of video games, artificial intelligence, experiments, or watching observers. "
    "Never use words like: simulation, game, AI, player, prompt, or model. "
    "The environment description is what they actually perceive. "
    "Respond only with the requested JSON, no other text before or after it."
)


BUBBLE_DURATION = 6.0
MEMORY_LIMIT = 20
NEARBY_RADIUS = 5 * 32

# Each sim stores a target position they walk toward between LLM ticks
# This dict maps sim_id -> (target_x, target_y)
_sim_targets: dict = {}
_last_ollama_warn_time: float = 0.0


def _is_connection_error(err: BaseException) -> bool:
    def _one(e: BaseException | None) -> bool:
        if e is None:
            return False
        name = type(e).__name__
        if "Connect" in name or "Connection" in name:
            return True
        if name in ("ConnectTimeout", "PoolTimeout"):
            return True
        s = str(e).lower()
        if "refused" in s or "errno 61" in s or "unreachable" in s or "name or service not known" in s:
            return True
        if "connection" in s and any(x in s for x in ("error", "failed", "refused", "reset", "aborted")):
            return True
        if "all connection attempts failed" in s:
            return True
        return False

    if _one(err):
        return True
    cause = getattr(err, "__cause__", None)
    if _one(cause if isinstance(cause, BaseException) else None):
        return True
    ctx = getattr(err, "__context__", None)
    if _one(ctx if isinstance(ctx, BaseException) else None):
        return True
    return False


def _maybe_warn_ollama_unavailable() -> None:
    global _last_ollama_warn_time
    now = time.time()
    if now - _last_ollama_warn_time < OLLAMA_WARN_INTERVAL_SEC:
        return
    _last_ollama_warn_time = now
    print(
        "[sim_loop] Ollama server not reachable (install https://ollama.com, start the Ollama app, "
        "or run `ollama serve`). Sims use built-in behavior until the server is up.",
        file=sys.stderr,
    )


def _gather_multiplier(sim: Sim) -> float:
    m = 1.0
    if sim.inventory.get("stone_axe", 0) >= 1:
        m += 0.55
    if sim.inventory.get("wooden_hammer", 0) >= 1:
        m += 0.3
    return m


def _heuristic_action(sim: Sim, world: WorldState) -> dict:
    """When Ollama is offline, drive survival + rich social / language behaviour."""
    def out(thought: str, speech: str, action: str, detail: str = "") -> dict:
        return {
            "thought": thought[:120],
            "speech": speech[:120],
            "action": action,
            "target": None,
            "detail": detail,
        }

    with world.lock:
        lp = world.language_progress
    stage = stage_label(lp)

    ensure_beliefs(sim)
    trade_boost = 0.1 if prefers_trade(sim) else 0.0

    if sim.thirst < 40.0 and adjacent_to_water(sim.position[0], sim.position[1], world):
        return out("I need a drink; the water is near.", "", "drink", "")
    if in_water(sim.position[0], sim.position[1], world) and sim.thirst < 70 and random.random() < 0.35:
        return out("The water cools and carries me; I can drink here too.", "", "swim", "")
    if sim.hunger < 40.0:
        for item in ("berries", "meat", "grain", "berry_bush", "animal_spawn", "farm_plot"):
            if sim.inventory.get(item, 0) > 0:
                return out("I must eat while I can.", "", "eat", "")
    if sim.energy < 22.0:
        return out("My limbs are heavy; I must rest.", "", "sleep", "")

    for rid in suggested_recipe_ids(sim, world):
        name = RECIPES[rid].name
        return out(f"I work materials into {name.lower()}.", "", "craft", rid)

    partner = None
    best_d = 1e9
    for other in world.sims.values():
        if other.id == sim.id or not other.alive:
            continue
        dist = (
            (other.position[0] - sim.position[0]) ** 2
            + (other.position[1] - sim.position[1]) ** 2
        ) ** 0.5
        if dist < INTERACT_RADIUS and dist < best_d:
            best_d = dist
            partner = other

    if partner is not None:
        rel = sim.relationships.get(partner.id, {})
        bond = rel.get("bond", 0)
        trust = rel.get("trust", 0)
        r = random.random()

        if avoids_outsiders(sim) and trust < 18 and random.random() < 0.35:
            return out("I keep my distance until I know them.", "", random.choice(("explore", "move")), "")

        if bond >= 35 and trust >= 25 and r < 0.22:
            skill = random.choice(("survival", "paths", "water", "stones", "kinship", "seasons"))
            return out(
                f"I try to put into words what {partner.name} should remember.",
                f"Listen: the {skill} we spoke of — carry it.",
                "teach",
                skill,
            )
        if r < 0.38:
            lines = [
                (f"The old way says we name this place together.", f"{partner.name}, walk with me while we still have light."),
                (f"Our people are learning how to speak of what matters.", f"I keep your name like a stone in my hand, {partner.name}."),
                (f"In {stage}, every word costs breath.", f"{partner.name} — the water, the wood, the watch: we share the names."),
                (f"A cry is not enough when the heart has a reason.", f"{partner.name}, I ask you by your own name to hear me."),
            ]
            if lp < 15:
                lines.append((f"We have only sounds and hands yet.", f"{partner.name}. You. Me. Here."))
            thought, speech = random.choice(lines)
            if lp > 55 and random.random() < 0.15:
                return out(thought, speech.replace("speak", "bind")[:120], "recite", "")
            return out(thought, speech, "talk", "")
        if r < 0.52 + trade_boost and bond >= 15:
            return out(
                "We have little, but we can trade words and goods.",
                f"Take this share, {partner.name}; I ask fair return.",
                "trade",
                "",
            )
        if r < 0.58 and lp > 40 and bond >= 40:
            return out(
                "The band needs a line everyone can repeat.",
                "Let no one take what all must eat.",
                "govern",
                "Share food in hunger",
            )
        if r < 0.62 and lp > 65:
            return out(
                "Some things must stay when the speaker is gone.",
                "Notches for days, marks for hands that owe.",
                "invent",
                "clay tally and mark",
            )
        if r < 0.68:
            return out(
                "I lift my voice to what I do not see.",
                "Guard us, you who hear the quiet.",
                "pray",
                "",
            )

    if sim.hunger < 55.0 or random.random() < 0.42:
        return out("I search the land for something useful.", "", "gather", "")

    return out("I go further to see what the day offers.", "", random.choice(("explore", "move")), "")


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
    place = environment_paragraph(sim.position[0], sim.position[1], world)
    uft = terrain_at_world(sim.position[0], sim.position[1], world)
    with world.lock:
        lp = world.language_progress
    lang_stage = stage_label(lp)

    return f"""You are {sim.name}, age {int(sim.age)}.
Health: {int(sim.health)}/100. Hunger: {int(sim.hunger)}/100. Thirst: {int(sim.thirst)}/100. Energy: {int(sim.energy)}/100.
Your role: {sim.role or "none yet"}.
Your ease with the shared tongue (personal): {int(sim.language_fluency)}/100.
How speech grows among your people: about {int(lp)}/100 — now at \"{lang_stage}\".
What you perceive right now:
{place}
Terrain underfoot: {uft}
Your memories:
{memories}
Others and resources (within sight):
{nearby}
Your relationships:
{rels}
The age of the world: {world.current_era()}. Known technologies: {techs}.
How your people are advancing: {pillar_summary}

Talking, teaching, trading, ruling aloud, prayer with words, and inventions of marks or lists all deepen language.
If you are at water: when thirsty, drinking is natural; when not thirsty, you might still wade, swim, or rest by the water.

What do you think, say, and do right now?
Respond ONLY as valid JSON with these exact keys:
{{
  "thought": "your inner thought (one sentence)",
  "speech": "what you say aloud, or empty string if silent",
  "action": "move|gather|build|craft|talk|recite|eat|drink|swim|sleep|reproduce|govern|trade|teach|attack|pray|invent|explore",
  "target": "name or id, or null",
  "detail": "brief extra — craft: recipe id (stone_axe, cottage, bedroll, …); invent: writing/tally/symbol/mark"
}}"""


def apply_sim_action(sim: Sim, response: dict, world: WorldState):
    action = response.get("action", "move")
    detail = response.get("detail", "")

    sim.hunger = max(0, sim.hunger - 2)
    sim.energy = max(0, sim.energy - 1)

    cal_day = world.sim_year * 366 + world.sim_day
    if sim.hunger < 17:
        if getattr(sim, "_belief_starve_cycle", -1) != cal_day:
            on_starvation_pressure(sim, world)
            sim._belief_starve_cycle = cal_day

    if sim.hunger == 0:
        sim.health = max(0, sim.health - 5)
    if sim.thirst == 0:
        sim.health = max(0, sim.health - 3)
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
        # Set a new wander target; actual movement happens in autonomous_tick each frame
        spread = random.uniform(64, 256)
        angle = random.uniform(0, 6.2832)
        import math
        tx = max(0.0, min(world_w - TILE_SIZE, sim.position[0] + math.cos(angle) * spread))
        ty = max(0.0, min(world_h - TILE_SIZE, sim.position[1] + math.sin(angle) * spread))
        _sim_targets[sim.id] = (tx, ty)

    elif action == "gather":
        if in_water(sim.position[0], sim.position[1], world):
            sim.memory.append("Could not forage while deep in the water")
        else:
            px, py = sim.position[0], sim.position[1]
            nearby: list[tuple[float, object]] = []
            for res in world.resources.values():
                if res.depleted:
                    continue
                dist = ((res.position[0] - px) ** 2 + (res.position[1] - py) ** 2) ** 0.5
                if dist < 64:
                    nearby.append((dist, res))
            nearby.sort(key=lambda x: x[0])
            prefer = (response.get("detail") or "").strip()
            chosen = None
            if prefer:
                for _, res in nearby:
                    if res.id == prefer:
                        chosen = res
                        break
            if chosen is None and nearby:
                chosen = nearby[0][1]
            if chosen is not None:
                if not gather_yields_for_node(chosen.object_type):
                    sim.memory.append("Nothing useful to take here")
                else:
                    mult = _gather_multiplier(sim)
                    parts = []
                    for mat, base_amt in gather_yields_for_node(chosen.object_type):
                        if base_amt >= 1.0:
                            n = int(max(1, round(float(base_amt) * mult)))
                        else:
                            n = 1 if random.random() < min(1.0, float(base_amt) * mult) else 0
                        if n:
                            sim.inventory[mat] = sim.inventory.get(mat, 0) + n
                            parts.append(f"{n} {mat}")
                    chosen.quantity -= 1
                    if chosen.quantity <= 0:
                        chosen.depleted = True
                    sim.memory.append("Gathered " + (", ".join(parts) if parts else "nothing"))
                    world.raise_pillar("Food Supply", 0.5)
                    on_gather_success(sim, world)

    elif action == "eat":
        food_items = ["berries", "meat", "grain", "berry_bush", "animal_spawn", "farm_plot"]
        for item in food_items:
            if sim.inventory.get(item, 0) > 0:
                sim.inventory[item] -= 1
                if sim.inventory[item] <= 0:
                    sim.inventory.pop(item, None)
                gain = 34 if item in ("meat", "grain") else 30
                if sim.inventory.get("pottery", 0) >= 1:
                    gain += 4
                sim.hunger = min(100, sim.hunger + gain)
                sim.memory.append("Ate food, felt better")
                break

    elif action == "drink":
        if adjacent_to_water(sim.position[0], sim.position[1], world) or in_water(
            sim.position[0], sim.position[1], world
        ):
            sim.thirst = min(100, sim.thirst + 50)
            sim.memory.append("Drank fresh water")
        else:
            sim.memory.append("Wanted a drink but found no water here")

    elif action == "swim":
        if in_water(sim.position[0], sim.position[1], world) or adjacent_to_water(
            sim.position[0], sim.position[1], world
        ):
            sim.energy = max(0, sim.energy - 8)
            sim.thirst = min(100, sim.thirst + 8)
            sim.memory.append("Swam in the water and felt renewed")
            world.raise_pillar("Culture & Religion", 0.3)
        else:
            sim.memory.append("Sought the water to swim but it was not near enough")

    elif action == "sleep":
        rest = 20
        if sim.inventory.get("bedroll", 0) >= 1:
            rest += 14
        if sim.inventory.get("leather_wrap", 0) >= 1:
            sim.safety = min(100.0, sim.safety + 2.0)
        sim.energy = min(100, sim.energy + rest)
        sim.status = min(100, sim.status + (3 if sim.inventory.get("bedroll", 0) >= 1 else 0))
        sim.memory.append("Rested and regained energy")

    elif action == "craft":
        rid = (detail or "").strip()
        if rid and try_craft(sim, world, rid):
            sim.memory.append(f"Crafted {RECIPES[rid].name}")
            world.raise_pillar("Economy", 2)
        else:
            sim.memory.append("Could not finish what I meant to make")

    elif action in ("talk", "recite"):
        did = False
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < INTERACT_RADIUS:
                    rel = sim.relationships.setdefault(other.id, {"trust": 0, "bond": 0, "romantic": 0})
                    rel["trust"] = min(100, rel["trust"] + 2)
                    rel["bond"] = min(100, rel["bond"] + 2)
                    other.memory.append(f"{sim.name} said: {response.get('speech', '')[:80]}")
                    sim.language_fluency = min(100.0, sim.language_fluency + 0.6)
                    other.language_fluency = min(100.0, other.language_fluency + 0.35)
                    ev = "recite" if action == "recite" else "talk"
                    bump_language(world, ev, sim.name, response.get("speech", ""))
                    did = True
                    break
        if not did:
            sim.memory.append("Called out but no one was close enough to hear")

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
            lf = (sim.language_fluency + partner.language_fluency) / 2
            child = Sim(
                id=str(uuid.uuid4())[:8],
                name=child_name,
                position=sim.position,
                age=0,
                skills={k: (v + partner.skills.get(k, 0)) / 2
                        for k, v in sim.skills.items()},
                language_fluency=lf,
                beliefs=blend_child_beliefs(sim, partner),
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
        bump_language(world, "law", sim.name, law)
        _check_milestone(world, "first_law", "Laws",
            f"First Law: {law}",
            f"{sim.name} declared the first law: '{law}'. Order had begun.")
        on_law_declaration(sim, world)

    elif action == "trade":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < INTERACT_RADIUS:
                    world.raise_pillar("Economy", 3)
                    rel = sim.relationships.setdefault(other.id, {"trust": 0, "bond": 0, "romantic": 0})
                    orel = other.relationships.setdefault(sim.id, {"trust": 0, "bond": 0, "romantic": 0})
                    rel_trade_success(rel)
                    rel_trade_success(orel)
                    rel["bond"] = min(100, rel["bond"] + 1)
                    belief_trade(sim, other, world)
                    fm = world.faction_manager
                    if (
                        fm
                        and fm.sim_faction.get(sim.id)
                        and fm.sim_faction.get(sim.id) == fm.sim_faction.get(other.id)
                    ):
                        on_faction_mutual_aid(sim, world)
                        on_faction_mutual_aid(other, world)
                        fm.record_shared_trade(sim.id, other.id)
                    sim.memory.append(f"Traded with {other.name}")
                    with world.lock:
                        world.trade_flow_events.append(
                            {
                                "from_id": sim.id,
                                "to_id": other.id,
                                "from_name": sim.name,
                                "to_name": other.name,
                                "x1": round(sim.position[0], 1),
                                "y1": round(sim.position[1], 1),
                                "x2": round(other.position[0], 1),
                                "y2": round(other.position[1], 1),
                                "year": world.sim_year,
                                "day": world.sim_day,
                            }
                        )
                    bump_language(world, "trade", sim.name, "")
                    _check_milestone(world, "first_trade", "History",
                        "First Trade",
                        f"{sim.name} and {other.name} exchanged goods for the first time, laying the seeds of an economy.")
                    break

    elif action == "teach":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < INTERACT_RADIUS:
                    skill = detail or "survival"
                    other.skills[skill] = other.skills.get(skill, 0) + 1
                    world.raise_pillar("Education", 2)
                    sim.memory.append(f"Taught {other.name} about {skill}")
                    other.memory.append(f"{sim.name} taught me about {skill}")
                    sim.language_fluency = min(100.0, sim.language_fluency + 0.8)
                    other.language_fluency = min(100.0, other.language_fluency + 1.0)
                    bump_language(world, "teach", sim.name, skill)
                    fm = world.faction_manager
                    if (
                        fm
                        and fm.sim_faction.get(sim.id)
                        and fm.sim_faction.get(sim.id) == fm.sim_faction.get(other.id)
                    ):
                        on_faction_mutual_aid(sim, world)
                        on_faction_mutual_aid(other, world)
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
                    try:
                        eng = get_world_engine(world)
                        eng.government.report_crime(sim, "assault")
                        rv = other.relationships.setdefault(
                            sim.id, {"trust": 0, "bond": 0, "romantic": 0}
                        )
                        ra = sim.relationships.setdefault(
                            other.id, {"trust": 0, "bond": 0, "romantic": 0}
                        )
                        rel_on_attack(rv, ra)
                        on_attack_as_aggressor(sim, world)
                        on_attack_as_victim(other, sim, world)
                        fa = eng.faction_manager.sim_faction.get(sim.id)
                        fb = eng.faction_manager.sim_faction.get(other.id)
                        if fa and fb and fa != fb:
                            eng.war_system.add_grievance(fa, fb, GRIEVANCE_ATTACK)
                    except Exception:
                        pass
                    break

    elif action == "pray":
        world.raise_pillar("Culture & Religion", 3)
        sim.memory.append("Prayed and felt a sense of meaning")
        if (response.get("speech") or "").strip():
            bump_language(world, "pray_speech", sim.name, "")
        _check_milestone(world, "first_prayer", "Culture",
            "First Prayer",
            f"{sim.name} knelt and offered words to the unknown — the first stirring of faith.")

    elif action == "invent":
        tech = detail or "stone tool"
        if tech not in world.technologies:
            world.technologies.append(tech)
            world.raise_pillar("Technology", 5)
            sim.memory.append(f"Invented: {tech}")
            low = (detail or "").lower()
            if any(
                k in low
                for k in (
                    "writ", "script", "symbol", "tally", "mark", "record",
                    "notch", "clay", "tablet", "list", "sign", "count",
                )
            ):
                bump_language(world, "writing", sim.name, tech)
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


def _clean_llm_json(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        content = content.strip()
        if content.startswith("json"):
            content = content[4:].lstrip()
    return content


def _is_structured_sim_response(d: dict) -> bool:
    """New strict schema vs legacy thought/speech/action dict from heuristics or old prompts."""
    if isinstance(d.get("target"), dict):
        return True
    structured_actions = {"move", "gather", "craft", "trade", "talk", "rest", "observe"}
    if d.get("action") in structured_actions and "speech" not in d:
        return True
    return False


def _tick(world: WorldState):
    with world.lock:
        sim_ids = list(world.sims.keys())

    for sim_id in sim_ids:
        with world.lock:
            sim = world.sims.get(sim_id)
            if sim is None or not sim.alive:
                continue
            engine = get_world_engine(world)
            prompt = build_prompt(sim, engine.get_local_state(sim))

        data = None
        first_err: BaseException | None = None
        try:
            response = ollama_chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = _clean_llm_json(response["message"]["content"])
            data = json.loads(raw)
        except Exception as e:
            first_err = e

        if data is None and first_err is not None and not _is_connection_error(first_err):
            try:
                retry_prompt = prompt + "\n\nREMINDER: respond ONLY with raw JSON, no markdown."
                response = ollama_chat(
                    model=OLLAMA_MODEL,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": retry_prompt},
                    ],
                )
                raw = _clean_llm_json(response["message"]["content"])
                data = json.loads(raw)
            except Exception:
                pass

        if data is None:
            if first_err is not None and _is_connection_error(first_err):
                _maybe_warn_ollama_unavailable()
            with world.lock:
                sim_fb = world.sims.get(sim_id)
                if sim_fb is None or not sim_fb.alive:
                    continue
                data = _heuristic_action(sim_fb, world)

        with world.lock:
            sim = world.sims.get(sim_id)
            if sim is None or data is None:
                continue
            if _is_structured_sim_response(data):
                thought_t = (data.get("thought") or data.get("intent") or "")[:120]
                if thought_t:
                    sim.thought_bubble = Bubble(text=thought_t, timer=BUBBLE_DURATION)
                get_world_engine(world).execute_structured_action(sim, data)
            else:
                thought = data.get("thought", "")
                speech = data.get("speech", "")
                if thought:
                    sim.thought_bubble = Bubble(text=thought[:120], timer=BUBBLE_DURATION)
                if speech:
                    sim.speech_bubble = Bubble(text=speech[:120], timer=BUBBLE_DURATION)
                apply_sim_action(sim, data, world)

    # Calendar advances in _run_calendar_loop (wall time) so Ollama latency does not freeze Year/Day.


def autonomous_tick(world: WorldState, dt: float):
    """Called every render frame. Moves sims smoothly toward their targets."""
    import math
    import random
    from config import WORLD_TILES_W, WORLD_TILES_H, TILE_SIZE
    world_w = WORLD_TILES_W * TILE_SIZE
    world_h = WORLD_TILES_H * TILE_SIZE
    base_speed = 60.0  # pixels per second on land

    with world.lock:
        for sim in world.sims.values():
            if not sim.alive:
                continue
            sim.thirst = max(0.0, sim.thirst - 1.2 * dt)
            if sim.thirst < 1.0:
                sim.health = max(0.0, sim.health - 4.0 * dt)
            sim.in_water = in_water(sim.position[0], sim.position[1], world)
            speed = 28.0 if sim.in_water else base_speed

            if sim.id not in _sim_targets:
                spread = random.uniform(64, 200)
                angle = random.uniform(0, 6.2832)
                tx = max(0.0, min(world_w - TILE_SIZE, sim.position[0] + math.cos(angle) * spread))
                ty = max(0.0, min(world_h - TILE_SIZE, sim.position[1] + math.sin(angle) * spread))
                _sim_targets[sim.id] = (tx, ty)

            tx, ty = _sim_targets[sim.id]
            dx = tx - sim.position[0]
            dy = ty - sim.position[1]
            dist = math.sqrt(dx * dx + dy * dy)
            sim.moving = dist >= 4.0
            if dist < 4.0:
                spread = random.uniform(64, 200)
                angle = random.uniform(0, 6.2832)
                ntx = max(0.0, min(world_w - TILE_SIZE, sim.position[0] + math.cos(angle) * spread))
                nty = max(0.0, min(world_h - TILE_SIZE, sim.position[1] + math.sin(angle) * spread))
                _sim_targets[sim.id] = (ntx, nty)
            else:
                step = min(speed * dt, dist)
                nx = sim.position[0] + (dx / dist) * step
                ny = sim.position[1] + (dy / dist) * step
                sim.position = (nx, ny)
                if abs(dx) > 0.5:
                    sim.facing = 1.0 if dx > 0 else -1.0
                sim.walk_cycle = (sim.walk_cycle + 3.5 * dt) % 1.0
            if not sim.moving:
                sim.walk_cycle = 0.0


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


def _run_calendar_loop(world: WorldState) -> None:
    """Advance sim_year/sim_day and subsystems on a wall-clock period from speed, not LLM latency."""
    while True:
        with world.lock:
            if world.sim_running and not world.paused:
                sp = max(1, int(world.speed))
            else:
                sp = 1
        interval = SIM_TICK_SECONDS / sp
        time.sleep(interval)
        with world.lock:
            if not world.sim_running or world.paused:
                continue
            world.advance_time()
            get_world_engine(world).step_subsystems()


def run_sim_loop(world: WorldState):
    cal = threading.Thread(target=_run_calendar_loop, args=(world,), daemon=True, name="sim-calendar")
    cal.start()
    while True:
        if not world.sim_running or world.paused:
            time.sleep(0.1)
            continue
        tick_interval = SIM_TICK_SECONDS / max(1, int(world.speed))
        _tick(world)
        time.sleep(tick_interval)
