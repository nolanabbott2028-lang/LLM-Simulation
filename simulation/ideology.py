"""Emergent ideology: belief vectors drift from outcomes; factions aggregate without fixed labels."""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from entities.sim import Sim
    from simulation.factions import Faction
    from world import WorldState

BELIEF_KEYS = (
    "cooperation_good",
    "authority_good",
    "trade_good",
    "violence_justified",
    "outgroup_danger",
)


def default_beliefs() -> dict[str, float]:
    return {k: 0.0 for k in BELIEF_KEYS}


def ensure_beliefs(sim: "Sim") -> dict[str, float]:
    b = getattr(sim, "beliefs", None)
    if not isinstance(b, dict):
        sim.beliefs = default_beliefs()
        return sim.beliefs
    for k in BELIEF_KEYS:
        if k not in b:
            b[k] = 0.0
    return b


def clamp_beliefs(b: dict[str, float]) -> None:
    for k in BELIEF_KEYS:
        b[k] = max(-100.0, min(100.0, float(b.get(k, 0))))


def _leader_mult(world: "WorldState", sim: "Sim") -> float:
    fm = getattr(world, "faction_manager", None)
    if not fm:
        return 1.0
    fid = fm.sim_faction.get(sim.id)
    if not fid or fid not in fm.factions:
        return 1.0
    fac = fm.factions[fid]
    lead = fac.leader
    if lead == sim.id:
        return 1.15
    ch = float(getattr(fac, "leader_charisma", 1.0))
    return 1.0 + 0.05 * (ch - 1.0)


def _apply_delta(sim: "Sim", deltas: dict[str, float], world: "WorldState | None" = None) -> None:
    b = ensure_beliefs(sim)
    mult = _leader_mult(world, sim) if world else 1.0
    for k, dv in deltas.items():
        if k not in BELIEF_KEYS:
            continue
        b[k] += float(dv) * mult
    clamp_beliefs(b)


def on_trade_success(sim: "Sim", partner: "Sim", world: "WorldState") -> None:
    _apply_delta(sim, {"trade_good": 2.0, "cooperation_good": 1.0}, world)


def on_betrayal(sim: "Sim", world: "WorldState") -> None:
    _apply_delta(sim, {"outgroup_danger": 5.0, "cooperation_good": -3.0}, world)


def on_faction_mutual_aid(actor: "Sim", world: "WorldState") -> None:
    _apply_delta(actor, {"authority_good": 3.0, "cooperation_good": 1.5}, world)


def on_starvation_pressure(sim: "Sim", world: "WorldState") -> None:
    _apply_delta(sim, {"violence_justified": 2.0, "trade_good": -0.5}, world)


def on_authority_event(sim: "Sim", world: "WorldState") -> None:
    _apply_delta(sim, {"authority_good": 2.0}, world)


def on_gather_success(sim: "Sim", world: "WorldState") -> None:
    _apply_delta(sim, {"cooperation_good": 0.5}, world)


def on_attack_as_aggressor(sim: "Sim", world: "WorldState") -> None:
    _apply_delta(sim, {"violence_justified": 1.0}, world)


def on_attack_as_victim(sim: "Sim", attacker: "Sim", world: "WorldState") -> None:
    rel = sim.relationships.get(attacker.id, {})
    trust = float(rel.get("trust", rel.get("bond", 0)) / 2)
    if trust > 25:
        on_betrayal(sim, world)
    else:
        _apply_delta(sim, {"outgroup_danger": 3.0}, world)


def on_law_declaration(sim: "Sim", world: "WorldState") -> None:
    _apply_delta(sim, {"authority_good": 3.0, "cooperation_good": 1.0}, world)


def on_public_punishment(sim: "Sim", world: "WorldState") -> None:
    _apply_delta(sim, {"authority_good": -2.0, "violence_justified": 1.0}, world)


def aggregate_beliefs(world: "WorldState", member_ids: set[str]) -> dict[str, float]:
    if not member_ids:
        return default_beliefs()
    acc = default_beliefs()
    n = 0
    for sid in member_ids:
        s = world.sims.get(sid)
        if not s:
            continue
        b = ensure_beliefs(s)
        for k in BELIEF_KEYS:
            acc[k] += b[k]
        n += 1
    if n == 0:
        return default_beliefs()
    for k in BELIEF_KEYS:
        acc[k] /= n
    return acc


def belief_variance_score(world: "WorldState", member_ids: set[str]) -> float:
    """Mean sum of squared deviation from faction mean belief vector."""
    ids = [i for i in member_ids if i in world.sims]
    if len(ids) < 2:
        return 0.0
    mean = aggregate_beliefs(world, set(ids))
    total = 0.0
    for sid in ids:
        b = ensure_beliefs(world.sims[sid])
        for k in BELIEF_KEYS:
            d = b[k] - mean[k]
            total += d * d
    return total / len(ids)


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in BELIEF_KEYS)
    na = math.sqrt(sum(a.get(k, 0) ** 2 for k in BELIEF_KEYS))
    nb = math.sqrt(sum(b.get(k, 0) ** 2 for k in BELIEF_KEYS))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


def ideology_distance_factions(world: "WorldState", fa: set[str], fb: set[str]) -> float:
    va = aggregate_beliefs(world, fa)
    vb = aggregate_beliefs(world, fb)
    return math.sqrt(sum((va[k] - vb[k]) ** 2 for k in BELIEF_KEYS))


def beliefs_prompt_block(sim: "Sim") -> str:
    b = ensure_beliefs(sim)
    lines = [f"- {k}: {int(round(b[k]))}" for k in BELIEF_KEYS]
    return "\n".join(lines)


def compressed_belief_summary(sim: "Sim") -> str:
    """Single line narrative compression from belief vector — not free-form invention."""
    b = ensure_beliefs(sim)
    parts = []
    if b["cooperation_good"] > 35:
        parts.append("working with others tends to help")
    elif b["cooperation_good"] < -35:
        parts.append("counting on others has gone badly")
    if b["trade_good"] > 35:
        parts.append("exchange beats wasting strength")
    if b["outgroup_danger"] > 45:
        parts.append("strangers feel risky")
    if b["violence_justified"] > 45:
        parts.append("force seems necessary when lean")
    if b["authority_good"] > 35:
        parts.append("order from above keeps peace")
    if not parts:
        parts.append("still weighing how the world works")
    return "; ".join(parts)


def inherit_beliefs_parent(parent: "Sim", noise: float = 8.0) -> dict[str, float]:
    base = dict(ensure_beliefs(parent))
    out = default_beliefs()
    for k in BELIEF_KEYS:
        out[k] = base[k] + random.uniform(-noise, noise)
    clamp_beliefs(out)
    return out


def blend_child_beliefs(p1: "Sim", p2: "Sim") -> dict[str, float]:
    a = ensure_beliefs(p1)
    b = ensure_beliefs(p2)
    out = default_beliefs()
    for k in BELIEF_KEYS:
        out[k] = (a[k] + b[k]) / 2.0 + random.uniform(-5.0, 5.0)
    clamp_beliefs(out)
    return out


def accepts_aggressive_actions(sim: "Sim") -> bool:
    return ensure_beliefs(sim)["violence_justified"] > 50


def prefers_trade(sim: "Sim") -> bool:
    return ensure_beliefs(sim)["trade_good"] > 25


def avoids_outsiders(sim: "Sim") -> bool:
    return ensure_beliefs(sim)["outgroup_danger"] > 40


def faction_narrative_line(world: "WorldState", fac: "Faction") -> str:
    agg = aggregate_beliefs(world, fac.members)
    lines = []
    if agg["cooperation_good"] > 25 and agg["authority_good"] > 15:
        lines.append("We survived because we stayed united.")
    if agg["outgroup_danger"] > 35:
        lines.append("Outsiders have brought harm.")
    if agg["trade_good"] > 25:
        lines.append("Prosperity came through exchange.")
    if agg["violence_justified"] > 35:
        lines.append("Strength answers hunger and fear.")
    if not lines:
        lines.append("Our story is still being argued.")
    return " ".join(lines)
