"""Phase 1 — spell-level loader regression (see ROADMAP.md Phase 1, Task B).

L3-L9 spell files key the level as `spell_level` (file-level) and `level` (per-spell),
while cantrips/L1/L2 use file-level `level`. The loader read only file-level `level`,
so every level 3-9 spell was indexed as level 0 (a cantrip).
"""
from app.core.spell_system import SpellRegistry


def test_spell_levels_loaded_correctly():
    SpellRegistry.reset()
    reg = SpellRegistry.get_instance()

    animate_dead = reg.get_spell("animate_dead")  # lives in level_3.json
    assert animate_dead is not None, "animate_dead should load"
    assert animate_dead.level == 3, f"expected level 3, got {animate_dead.level}"

    acid_splash = reg.get_spell("acid_splash")  # lives in cantrips.json
    assert acid_splash is not None, "acid_splash should load"
    assert acid_splash.level == 0, f"expected level 0, got {acid_splash.level}"

    SpellRegistry.reset()
