"""Normalize and update relationship edges (trust, fear, familiarity, bond, romantic)."""


def ensure_edge(rel: dict) -> dict:
    """Ensure all keys exist for faction / social logic."""
    if "trust" not in rel:
        rel["trust"] = rel.get("bond", 0) // 2
    rel.setdefault("fear", 0)
    rel.setdefault("familiarity", 0)
    rel.setdefault("bond", rel.get("trust", 0))
    rel.setdefault("romantic", 0)
    return rel


def on_trade_success(rel: dict, delta_trust: int = 5) -> None:
    ensure_edge(rel)
    rel["trust"] = max(-100, min(100, rel["trust"] + delta_trust))
    rel["familiarity"] = min(100, rel["familiarity"] + 3)


def on_attack(rel_victim_to_attacker: dict, rel_attacker_to_victim: dict) -> None:
    """Victim fears attacker more; attacker loses trust from victim's perspective."""
    ensure_edge(rel_victim_to_attacker)
    ensure_edge(rel_attacker_to_victim)
    rel_victim_to_attacker["fear"] = min(100, rel_victim_to_attacker["fear"] + 15)
    rel_victim_to_attacker["trust"] = max(-100, rel_victim_to_attacker["trust"] - 20)
    rel_attacker_to_victim["trust"] = max(-100, rel_attacker_to_victim["trust"] - 25)


def mutual_trust_cluster(sims_relations: dict[str, dict], member_ids: list[str]) -> float:
    """Average pairwise trust among members who have edges."""
    if len(member_ids) < 2:
        return 0.0
    pairs = 0
    total = 0.0
    for i, a in enumerate(member_ids):
        for b in member_ids[i + 1 :]:
            ra = sims_relations.get(a, {}).get(b)
            rb = sims_relations.get(b, {}).get(a)
            if ra is None or rb is None:
                continue
            ta = ensure_edge(dict(ra))["trust"]
            tb = ensure_edge(dict(rb))["trust"]
            total += (ta + tb) / 2
            pairs += 1
    return total / pairs if pairs else 0.0
