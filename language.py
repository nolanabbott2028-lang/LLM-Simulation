"""
Civilization language arc: 0–100 progress with book milestones.
Events: talk, teach, recite, law, trade, writing, pray_speech
"""
from world import WorldState

# (threshold, book tab, book title, book body)
LANGUAGE_STAGES: list[tuple[int, str, str, str]] = [
    (
        8,
        "Language",
        "The First Exchanges of Meaning",
        "Before any settled word, people named things by pointing, by the tone of a cry, and by how close they stood. That was the first, fragile bridge between one mind and another.",
    ),
    (
        18,
        "Language",
        "Names That Linger",
        "The same sound began to follow the same face. A place could be 'that hill' in a breath, and a child could be called and answered. The world grew smaller because it could be named.",
    ),
    (
        28,
        "Language",
        "The Tongue of Danger and Need",
        "Short calls carried across clearings: a bird no one ate, a storm line on the water, a stranger's foot. What could be said quickly could save the whole band.",
    ),
    (
        38,
        "Language",
        "Words in the Path of Trade",
        "A handful of goods met a handful of words. 'Yours' and 'mine' did not need a hall to be true in the moment of exchange, and the memory of a fair deal began to outlive the day.",
    ),
    (
        50,
        "Language",
        "Oral Weaving",
        "What one had lived, one could place in the ear of the next. Teaching was no longer only the hand: it was a line of speech that could be tested, retold, and improved.",
    ),
    (
        60,
        "Language",
        "When Speech Binds the Many",
        "The same breath that flattered a spirit could set a law for the body. Oaths and rules lived in the air between people before they ever lived in any mark. Whoever spoke for all learned the weight of every word.",
    ),
    (
        72,
        "Language",
        "The Hand Leaves a Trace",
        "Not every memory had to stay in the skull. A notch, a line in clay, a row of pebbles could carry count and date when the mind tired or the teller was gone. Speech and sign began to work together.",
    ),
    (
        85,
        "Language",
        "The Keeper of the Lineage",
        "What must not vary — kinship, debt, the law of a season — was spoken in a form that could be checked. The slow rise of a fixed wording guarded against forgetting and against lies.",
    ),
    (
        95,
        "Language",
        "A Net of Common Speech",
        "Different voices learned to sound like one people when it mattered: at trial, at harvest, at birth. A shared tongue was no longer a habit only; it was a home you could walk into from any path.",
    ),
    (
        100,
        "Language",
        "The Long Thread of the Tongue",
        "From the first named thing to the last taught verse, the language had outgrown any single life. It had become what the people were to one another: the way they could still meet after the world changed them.",
    ),
]

BUMP: dict[str, float] = {
    "talk": 0.55,
    "teach": 1.0,
    "recite": 0.5,
    "law": 1.35,
    "trade": 0.4,
    "writing": 2.5,
    "pray_speech": 0.35,
}

_STAGE_NAMES: list[tuple[int, str]] = [
    (0, "Cries, signs, and touch"),
    (8, "Cries, signs, and names"),
    (18, "Names for kin and place"),
    (28, "Warnings and calls across clearings"),
    (38, "Barter-words and promise"),
    (50, "Taught line and story"),
    (60, "Oath, law, and prayer in the mouth"),
    (72, "Marks, tallies, and memory outside the head"),
    (85, "List, verse, and fixed phrasing"),
    (95, "A common way of speaking for the people"),
    (100, "A living thread for a living people"),
]


def stage_label(progress: float) -> str:
    name = _STAGE_NAMES[0][1]
    for th, n in _STAGE_NAMES:
        if progress >= th:
            name = n
    return name


def bump_language(world: WorldState, event: str, _actor: str, _extra: str = "") -> None:
    base = BUMP.get(event, 0.2)
    with world.lock:
        old = world.language_progress
        world.language_progress = min(100.0, world.language_progress + base)
        new = world.language_progress
    max_b = max(BUMP.values()) if BUMP else 1.0
    gain = 0.35 + 0.4 * (base / max_b)
    with world.lock:
        world.raise_pillar("Language", min(2.0, gain))

    for th, tab, title, body in LANGUAGE_STAGES:
        if old < th <= new:
            key = f"lang_{th}"
            with world.lock:
                if key in world.milestones:
                    continue
                world.milestones.add(key)
                world.add_book_entry(tab, title, body)
