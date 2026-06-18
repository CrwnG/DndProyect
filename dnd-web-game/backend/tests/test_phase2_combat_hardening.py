"""Phase 2 — combat hardening regression tests (see ROADMAP.md Phase 2).

The combat/environment modules import `roll_dice` from app.core.dice at module
top level, but that function never existed (only roll_die/roll_damage). So
surfaces.py, falling.py and throwing.py were unimportable, and every monster
Multiattack / save-AoE path in combat_engine crashed with ImportError.
"""
import importlib

import pytest


def test_roll_dice_exists_and_totals_in_range():
    from app.core.dice import roll_dice

    for _ in range(100):
        assert 2 <= roll_dice("2d6") <= 12
    assert roll_dice("1d1") == 1
    assert roll_dice("3") == 3          # flat number
    for _ in range(100):
        assert 11 <= roll_dice("1d4+10") <= 14


@pytest.mark.parametrize("module", [
    "app.core.surfaces",
    "app.core.falling",
    "app.core.throwing",
])
def test_dice_dependent_modules_import(module):
    """These modules import roll_dice at top level and were unimportable."""
    importlib.import_module(module)


def test_breath_weapon_evasion_records_extra_data():
    """Breath weapon vs an Evasion target must not crash on a missing extra_data field."""
    from app.core.monster_abilities import MonsterAbility, AbilityType, execute_breath_weapon

    ability = MonsterAbility(
        id="fire_breath", name="Fire Breath", original_description="",
        ability_type=AbilityType.BREATH_WEAPON,
        damage_dice="2d6", save_type="dex", save_dc=100, half_on_save=True,
    )
    # save_dc 100 => the target always fails; Evasion + a DEX save => half damage + a note.
    result = execute_breath_weapon(
        ability,
        [{"id": "rogue", "save_mod": 0, "has_evasion": True}],
        attacker_id="dragon",
    )
    assert result.extra_data["rogue_evasion"] == "half_damage"
