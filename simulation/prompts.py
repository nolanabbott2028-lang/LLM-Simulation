"""Layered prompts + strict JSON action schema for LLM decisions."""
from __future__ import annotations

import json
from typing import Any

from simulation.memory_system import compress_memory_lines

SYSTEM_RULES = """You are a real person in a living world among others.
You must behave realistically based on needs, traits, memory, and environment.

Rules:
- You MUST choose exactly one action per turn.
- You MUST NOT invent new facts beyond what you are told.
- You MUST only use information provided in the input.
- You MUST respond in valid JSON only.
- Survival and long-term self-interest matter.
- Social relationships influence decisions.
- If information is missing or ambiguous, choose "observe".
- Never assume hidden resources or people exist.
- Keep "intent" under 20 words. Do not explain abstract mechanics."""

DEVELOPER_RULES = """The world is grid-based with resources, agents, and rules.

Available actions (exactly one):
move, gather, craft, trade, talk, rest, observe

- craft: combine inventory materials into tools, comfort items, or a building. Use target.type "recipe"
  and target.id set to a recipe id listed under CRAFTING.recipes (only if your inventory satisfies inputs,
  or prefer ids in CRAFTING.ready_now).

Output MUST match this schema:
{
  "thought": "(optional) one short internal note, not executed",
  "action": "move|gather|craft|trade|talk|rest|observe",
  "target": {
    "type": "agent|resource|location|recipe|self",
    "id": null,
    "x": null,
    "y": null
  },
  "quantity": null,
  "intent": "short why"
}

All quantities are integers where applicable. Targets must exist in perception when required.
Your intent should be consistent with YOUR BELIEFS and memory — do not invent new belief labels."""


def priority_signals(hunger: float, energy: float, safety: float) -> str:
    lines = []
    if hunger > 70:
        lines.append("- hunger > 70 → urgent survival (seek food)")
    if energy < 20:
        lines.append("- energy < 20 → rest strongly preferred")
    if safety < 25:
        lines.append("- safety low → avoid conflict, seek safety or observe")
    if not lines:
        lines.append("- needs are moderate; balance goals")
    return "\n".join(lines)


def build_prompt(agent: Any, perception: dict[str, Any]) -> str:
    mem_lines = compress_memory_lines(getattr(agent, "memory", []) or [])
    traits = getattr(agent, "traits", {}) or {}
    traits_s = json.dumps(traits, indent=2)
    inv = getattr(agent, "inventory", None)
    if inv is None:
        inv = {}
    thirst = float(getattr(agent, "thirst", 50))
    laws = perception.get("laws") or []
    nearby_agents = perception.get("nearby_agents") or []
    resources = perception.get("resources") or []
    crafting = perception.get("crafting") or {}

    hunger = float(getattr(agent, "hunger", 50))
    energy = float(getattr(agent, "energy", 50))
    safety = float(getattr(agent, "safety", 50))

    pri = priority_signals(hunger, energy, safety)
    mem_block = "\n".join(mem_lines)

    return f"""SYSTEM:
{SYSTEM_RULES}

DEVELOPER:
{DEVELOPER_RULES}

PRIORITY SIGNALS:
{pri}

AGENT STATE:
ID: {getattr(agent, 'id', '?')} | name: {getattr(agent, 'name', '?')}

TRAITS:
{traits_s}

NEEDS:
- hunger: {hunger:.0f}
- thirst: {thirst:.0f}
- energy: {energy:.0f}
- safety: {safety:.0f}

LOCATION (world x,y):
{getattr(agent, 'position', (0, 0))}

INVENTORY:
{json.dumps(inv, indent=2)}

MEMORY (behavioral):
{mem_block}

NEARBY ENTITIES:
- agents: {json.dumps(nearby_agents, indent=2)}
- resources: {json.dumps(resources, indent=2)}

CRAFTING (recipe ids and materials; prefer ready_now when urgent):
{json.dumps(crafting, indent=2)}

CURRENT LAWS:
{json.dumps(laws, indent=2)}

FACTION STATUS (do not invent; use only if listed):
{json.dumps(perception.get('faction_status') or {}, indent=2)}

YOUR BELIEFS (how you explain good or bad fortune — numeric, do not invent new axes):
{perception.get('beliefs_prompt') or '—'}

ONE-LINE STORY YOU TELL YOURSELF (compressed from experience, not new facts):
{perception.get('beliefs_summary_line') or '—'}

AVAILABLE ACTIONS:
move, gather, craft, trade, talk, rest, observe

OUTPUT FORMAT (JSON only, no markdown):
{{
  "thought": "",
  "action": "",
  "target": {{ "type": "", "id": null, "x": null, "y": null }},
  "quantity": null,
  "intent": ""
}}
For craft, example target: {{ "type": "recipe", "id": "stone_axe", "x": null, "y": null }}
"""


def parse_structured_response(text: str) -> dict[str, Any]:
    """Extract JSON object from model output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"action": "observe", "target": {"type": "self"}, "intent": "parse failed; observing"}
