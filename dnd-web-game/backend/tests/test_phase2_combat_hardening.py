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


def _make_combatant(cid, ctype, **overrides):
    base = {
        "id": cid, "name": cid, "type": ctype,
        "hp": 30, "max_hp": 30, "ac": 10, "speed": 30,
        "str_mod": 3, "dex_mod": 1, "con_mod": 2,
        "attack_bonus": 5, "damage_dice": "1d6", "damage_type": "slashing",
        "abilities": {"strength": 16, "dexterity": 12, "constitution": 14,
                      "intelligence": 10, "wisdom": 10, "charisma": 10},
        "class": "fighter", "level": 5, "conditions": [],
    }
    base.update(overrides)
    return base


def test_monster_damage_honors_resistance_subclass_and_attack_path():
    """Integration: monster damage respects resist/immunity (key fix), subclass_id is
    cached (Champion crit), and a single monster attack resolves (natural_roll fix)."""
    from app.core.combat_engine import CombatEngine, CombatState
    from app.core.monster_abilities import MonsterAbility, AbilityType

    engine = CombatEngine(combat_state=CombatState())
    player = _make_combatant("player-1", "player", subclass_id="champion")
    enemy = _make_combatant("enemy-1", "enemy", hp=20, max_hp=20, ac=1,
                            resistances=["slashing"])
    engine.start_combat([player], [enemy])

    # subclass_id must be cached so Champion expanded-crit logic can fire.
    assert engine.state.combatant_stats["player-1"].get("subclass_id") == "champion"

    # Resistance: 10 slashing -> halved to 5 (was ignored due to damage_* key mismatch).
    engine.state.combatant_stats["enemy-1"]["current_hp"] = 20
    engine._apply_damage_to_target("enemy-1", 10, "slashing")
    assert engine.state.combatant_stats["enemy-1"]["current_hp"] == 15

    # Immunity: piercing-immune target takes no damage.
    engine.state.combatant_stats["enemy-1"]["immunities"] = ["piercing"]
    engine.state.combatant_stats["enemy-1"]["current_hp"] = 15
    engine._apply_damage_to_target("enemy-1", 8, "piercing")
    assert engine.state.combatant_stats["enemy-1"]["current_hp"] == 15

    # natural_roll path: a single monster attack resolves without AttributeError.
    attacker = engine.state.initiative_tracker.get_combatant("enemy-1")
    stats = engine.state.combatant_stats["enemy-1"]
    attack = MonsterAbility(id="bite", name="Bite", original_description="",
                            ability_type=AbilityType.MELEE_ATTACK,
                            attack_bonus=10, damage_dice="1d6", damage_type="piercing")
    result = engine._execute_single_monster_attack(attacker, stats, attack, "player-1")
    assert "hit" in result
