"""Behavioral memory compression — short bullets, not raw dumps."""


def compress_memory_lines(memory: list[str], max_lines: int = 6) -> list[str]:
    """Turn recent memory strings into concise behavioral summaries."""
    if not memory:
        return ["(no recent behavioral memory)"]
    tail = memory[-max_lines * 2 :]
    out = []
    for line in tail[-max_lines:]:
        s = line.strip()
        if len(s) > 90:
            s = s[:87] + "…"
        out.append(f"- {s}")
    return out if out else ["(nothing notable)"]
