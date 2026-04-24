# Civilization Sandbox — Design Spec
**Date:** 2026-04-23

---

## Overview

A Python/Pygame sandbox simulation where two AI-powered beings ("sims") start from nothing and evolve a civilization autonomously. The simulation is driven by a local Ollama LLM. The player can build the world before starting, observe the sims in real time, and review civilizational history through a Civilization Book. The player may intervene at will but is not required to.

---

## Architecture

**Single Python process, three layers:**

1. **World State** (`world.py`) — central dataclass holding all beings, structures, terrain tiles, placed objects, civilization metrics, and the Civilization Book log. All mutations go through here.
2. **Sim Loop** (`sim_loop.py`) — background thread. Ticks every ~3 seconds. For each being: assembles a context prompt, fires an Ollama call, parses the JSON response, applies the resulting action to world state.
3. **Pygame Renderer** (`renderer.py`) — main thread, 60fps. Reads world state (thread-safe via a lock), draws terrain, objects, beings, bubbles, UI panels, timeline, and camera. Handles all input.

**Entry point:** `main.py` — initializes world state, starts the renderer, conditionally starts the sim loop after world-building is complete.

---

## Modes

### World Builder Mode (pre-sim)

The game starts here. Two sequential phases:

**Phase 1 — Terrain Paint**
- Left toolbar with brush types: Grass, Forest, Water, Mountain, Desert, Snow
- Adjustable brush size (1–5 tiles)
- Flood-fill tool for large areas
- Default map is all grass

**Phase 2 — Object Placement**
- Switch via toolbar button after terrain is complete
- Drag-and-drop placeable objects: Berry Bush, Stone Deposit, Tree, River Source, Animal Spawn, Hut, Shrine, Farm Plot
- Objects sit on top of terrain tiles and become discoverable resources

**Starting the sim:**
- Press "Begin Civilization" button
- Player clicks a location on the map to spawn the two starting sims (Adam and Eve, or named by the player)
- World Builder Mode is locked; Sim Loop starts

---

### Simulation Mode

Once started, the sim runs autonomously. The player can:
- Pan the camera freely (WASD or arrow keys)
- Zoom in/out (scroll wheel)
- Click a sim to inspect their full profile (memory, relationships, stats)
- Press `B` to open/close the Civilization Book
- Press `P` to pause/resume the sim loop
- Place new objects mid-sim (optional god-mode intervention)

---

## Camera & Rendering

- **Free-roam 2D camera** — infinite scroll, follows no sim by default
- **Tile-based world** — each tile is 32x32px, world defaults to 100x100 tiles (expandable)
- **Zoom levels** — 3 levels: overview (0.5x), normal (1x), close-up (2x)
- **Layer order:** terrain → objects/structures → beings → bubbles → UI panels → timeline

---

## Timeline (top bar)

A persistent horizontal bar at the top of the screen showing:

- **Current day/year** (simulation time, e.g. "Year 1, Day 14")
- **Era label** — auto-advances as Technology pillar grows: Stone Age → Bronze Age → Iron Age → Classical → Medieval → Renaissance → Industrial → Modern
- **Milestone markers** — small icons on the timeline showing when major events occurred (first fire, first birth, first law, etc.). Hover to see event name.
- **Playback speed control** — 1x / 2x / 4x sim speed buttons on the right side of the bar

---

## Beings (Sims)

Each sim is a dataclass with:

| Field | Description |
|---|---|
| `name` | String, set at spawn |
| `position` | (x, y) float coordinates |
| `age` | Increments each sim-day |
| `health` | 0–100 |
| `hunger` | 0–100 (decreases over time, must eat) |
| `energy` | 0–100 (rest to restore) |
| `role` | Evolves naturally: None → Hunter / Gatherer / Builder / Leader / Merchant / Priest / Soldier / Teacher |
| `relationships` | Dict of `{sim_id: {trust, bond, romantic}}` |
| `memory` | List of last 20 significant events (strings) |
| `speech_bubble` | Current speech text + fade timer |
| `thought_bubble` | Current thought text + fade timer |
| `inventory` | Dict of held resources |
| `skills` | Dict of skill levels (farming, building, combat, teaching, etc.) |

**Reproduction:** When two sims have a romantic bond ≥ 70, both health ≥ 60, and both hunger ≥ 40, the LLM may choose the `reproduce` action. A child sim spawns with inherited traits (averaged skills, combined memory summary as "upbringing"). Child grows to adult over 10 sim-days.

**Death:** Sims die if health reaches 0 (starvation, conflict, old age). A death entry is written to the Civilization Book.

---

## LLM Decision Loop

Every tick (~3 seconds real time), each sim gets an Ollama prompt:

```
You are [Name], age [X]. 
Health: [X]/100. Hunger: [X]/100. Energy: [X]/100.
Your role: [role or "none yet"].
Your memories: [last 5 memories as bullet points].
Nearby (within sight): [list of visible beings, resources, structures].
Your relationships: [summary of known sims and bond levels].
Current civilization era: [era]. Available knowledge: [list of unlocked techs].
Civilization stats: [10 pillar scores as brief list].

What do you think, say, and do right now?
Respond ONLY as JSON:
{
  "thought": "...",
  "speech": "...",
  "action": "move|gather|build|talk|eat|sleep|reproduce|govern|trade|teach|attack|pray|invent|explore",
  "target": "sim_id | object_id | position | null",
  "detail": "optional extra info about the action"
}
```

The sim loop parses this response and applies the action to world state. Invalid JSON triggers a retry (max 2).

**Critical prompt rule:** Sims are never told they are in a simulation, that they are AI, or that a player is watching. All prompts are written in second-person present tense as if the sim is a real living person in a real world. No meta-references to "the game", "the simulation", "your programming", or "the player" may appear anywhere in a prompt. This applies to milestone Civilization Book prompts as well — entries are written as in-world historical records, not observer notes.

**Milestone detection:** After each action is applied, a lightweight check determines if it's a first-ever event. If so, a second short Ollama call generates a Civilization Book entry in narrative prose.

---

## Actions Reference

| Action | Effect |
|---|---|
| `move` | Updates position toward target |
| `gather` | Extracts resource from nearby object, adds to inventory |
| `build` | Consumes inventory resources to place a structure |
| `talk` | Sets speech bubble; nearby sims "hear" it and it enters their memory |
| `eat` | Consumes food from inventory, restores hunger |
| `sleep` | Restores energy over several ticks |
| `reproduce` | Spawns child sim (if conditions met) |
| `govern` | Creates a law entry in world state; raises Government pillar |
| `trade` | Transfers inventory items between two sims; raises Economy pillar |
| `teach` | Transfers a skill level to a nearby sim; raises Education pillar |
| `attack` | Reduces target health; raises Military pillar |
| `pray` | Raises Culture/Religion pillar; may spawn a shrine if one doesn't exist |
| `invent` | Creates a new named technology entry; raises Technology pillar |
| `explore` | Moves to an undiscovered area; may reveal new resources |

---

## The 10 Civilization Pillars

Each pillar is a score from 0–100 stored in world state. Scores rise when relevant actions occur. They are displayed as a side panel (press `C` to toggle) and fed into each sim's LLM prompt so they know what's possible in their era.

| # | Pillar | Key Triggers |
|---|---|---|
| 1 | Government | `govern` actions, laws declared, leaders elected |
| 2 | Economy | `trade` actions, currency invented |
| 3 | Language | Stories told, written symbols placed, books created |
| 4 | Social Structure | Roles assigned, hierarchy formed, population grows |
| 5 | Culture & Religion | `pray`, rituals, shrines built, art created |
| 6 | Technology | `invent` actions, new tools/structures built |
| 7 | Infrastructure | Roads, buildings, water systems constructed |
| 8 | Food Supply | Farms planted, food stockpiled, animals domesticated |
| 9 | Education | `teach` actions, schools built |
| 10 | Military | Weapons crafted, conflicts, defense structures built |

**Era progression** is gated by the Technology pillar score:
- 0–10: Stone Age
- 11–25: Bronze Age
- 26–40: Iron Age
- 41–55: Classical Age
- 56–70: Medieval
- 71–85: Renaissance / Industrial
- 86–100: Modern

---

## The Civilization Book

Toggled with `B`. A scrollable in-game panel with tab navigation:

| Tab | Contents |
|---|---|
| History | Chronological major events |
| Technology | Inventions and discoveries |
| Laws | All laws passed by governing sims |
| People | Births, deaths, notable sims |
| Culture | Religions, traditions, art events |

Each entry is auto-generated by a short Ollama call when a milestone fires, written in narrative prose, timestamped with the sim day/year.

Example entry:
> **Year 1, Day 4 — The Discovery of Fire**
> *Adam gathered dry wood from the forest to the east and struck two stones together until sparks flew. As warmth pushed back the cold night, Eve watched in silence. Neither had words for what they had found — but both knew the world had changed.*

---

## UI Layout Summary

```
┌─────────────────────────────────────────────────────┐
│  TIMELINE: Year 1, Day 3 | Stone Age    [1x][2x][4x]│
├──────┬──────────────────────────────────────────────┤
│      │                                              │
│TOOL  │           WORLD CANVAS (free-roam)           │
│BAR   │     beings, terrain, structures, bubbles     │
│(WB   │                                              │
│mode) │                                              │
│      │                                              │
├──────┴──────────────────────────────────────────────┤
│  [B] Book  [C] Pillars  [P] Pause  [ESC] Menu       │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Library |
|---|---|
| Rendering & input | `pygame` |
| LLM inference | `ollama` Python client (local Ollama server) |
| Concurrency | `threading` + `threading.Lock` for world state |
| Data structures | Python `dataclasses` |
| Persistence (save/load) | `json` serialization of world state |

**Ollama model:** Default `llama3` or `mistral` — configurable in `config.py`.

---

## File Structure

```
StudioMCP/
├── main.py               # Entry point
├── config.py             # Model name, tick rate, world size, etc.
├── world.py              # WorldState dataclass, all mutations
├── sim_loop.py           # Background thread, LLM calls, action dispatch
├── renderer.py           # Pygame render loop, camera, input
├── world_builder.py      # Terrain paint + object placement logic
├── ui/
│   ├── timeline.py       # Top timeline bar
│   ├── book.py           # Civilization Book panel
│   ├── pillars.py        # Pillar scores side panel
│   ├── bubbles.py        # Speech/thought bubble rendering
│   └── inspector.py      # Sim profile inspector on click
├── entities/
│   ├── sim.py            # Sim dataclass
│   ├── structure.py      # Structure dataclass
│   └── resource.py       # Resource/object dataclass
└── docs/
    └── superpowers/specs/
        └── 2026-04-23-civilization-sandbox-design.md
```

---

## Out of Scope (v1)

- Multiplayer
- Procedural world generation (player builds it manually)
- Modding/plugin system
- Sound/music
