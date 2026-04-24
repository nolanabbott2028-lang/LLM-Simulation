import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from world import WorldState
from language import bump_language, stage_label


def test_stage_label_monotonic():
    assert "touch" in stage_label(0).lower() or len(stage_label(0)) > 3
    assert stage_label(100) != stage_label(0)


def test_bump_adds_progress_and_book():
    w = WorldState()
    assert w.language_progress == 0.0
    bump_language(w, "teach", "Adam")
    assert w.language_progress > 0
    bump_language(w, "writing", "Adam")
    assert w.language_progress > 1.0
    # hit first threshold at 8
    w.language_progress = 7.0
    bump_language(w, "teach", "Adam")
    assert any(e["tab"] == "Language" for e in w.book_entries)
