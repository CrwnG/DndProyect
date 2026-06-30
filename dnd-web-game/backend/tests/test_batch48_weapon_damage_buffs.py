"""Batch 48 (A1): weapon-buff spells add per-hit damage while concentration holds.

Spirit Shroud (+1d8), Elemental Weapon (+1d4), and Holy Weapon (+2d8) add extra damage to
every weapon attack the caster makes for the spell's duration. `_determine_buff_effects`
returned {} for them (no mechanical effect) and the attack path had no per-hit weapon-damage
buff, so all three spells did nothing. They now produce a `bonus_weapon_damage` buff that the
attack path consumes on each hit, gated by the caster's concentration.
"""
from app.core.spell_system import SpellRegistry, SpellEffectResolver
from app.core.combat_engine import CombatEngine, CombatState, ActionType, TurnState


def test_determine_buff_effects_recognizes_weapon_damage_spells():
    reg = SpellRegistry.get_instance()
    for sid, dice in [("spirit_shroud", "1d8"), ("elemental_weapon", "1d4"), ("holy_weapon", "2d8")]:
        eff = SpellEffectResolver._determine_buff_effects(reg.get_spell(sid))
        assert eff.get("bonus_weapon_damage") == dice, f"{sid} should add {dice}"
        assert eff.get("bonus_weapon_damage_type"), f"{sid} should carry a damage type"


def _combat():
    p = {"id": "pal", "name": "Pal", "type": "player", "hp": 40, "max_hp": 40, "ac": 10,
         "speed": 30, "str_mod": 3, "attack_bonus": 12, "damage_dice": "1d8", "damage_type": "slashing",
         "abilities": {"strength": 16, "dexterity": 10, "constitution": 14,
                       "intelligence": 10, "wisdom": 12, "charisma": 16},
         "class": "paladin", "level": 5, "conditions": []}
    e = {"id": "dummy", "name": "Dummy", "type": "enemy", "hp": 100000, "max_hp": 100000, "ac": 1,
         "speed": 30, "abilities": {"strength": 10, "dexterity": 10, "constitution": 10,
                                    "intelligence": 10, "wisdom": 10, "charisma": 10},
         "class": "monster", "level": 1, "conditions": []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([p], [e], positions={"pal": (0, 0), "dummy": (1, 0)})
    tr = eng.state.initiative_tracker
    tr.current_turn_index = next(i for i, c in enumerate(tr.combatants) if c.id == "pal")
    eng.state.current_turn = TurnState(combatant_id="pal")
    return eng


def _arm_spirit_shroud(eng):
    stats = eng.state.combatant_stats["pal"]
    stats.setdefault("active_buffs", []).append({
        "source": "pal", "spell_id": "spirit_shroud",
        "bonus_weapon_damage": "1d8", "bonus_weapon_damage_type": "radiant",
    })
    sc = stats.get("spellcasting")
    if not isinstance(sc, dict):
        sc = {}; stats["spellcasting"] = sc
    sc["concentrating_on"] = "spirit_shroud"


def test_consume_weapon_damage_buff_gated_by_concentration():
    eng = _combat()
    _arm_spirit_shroud(eng)
    amount, dtype = eng._consume_weapon_damage_buff("pal")
    assert 1 <= amount <= 8 and dtype == "radiant"     # 1d8 while concentrating

    # Drop concentration -> buff inactive -> no bonus
    eng.state.combatant_stats["pal"]["spellcasting"]["concentrating_on"] = None
    amount2, _ = eng._consume_weapon_damage_buff("pal")
    assert amount2 == 0


def test_spirit_shroud_adds_damage_in_the_real_attack_path():
    def _sum_damage(buffed):
        eng = _combat()
        if buffed:
            _arm_spirit_shroud(eng)
        hp0 = eng.state.combatant_stats["dummy"]["current_hp"]
        for _ in range(30):
            eng.state.current_turn = TurnState(combatant_id="pal")
            eng.take_action(ActionType.ATTACK, target_id="dummy")
        return hp0 - eng.state.combatant_stats["dummy"]["current_hp"]

    # +1d8 (avg 4.5) over 30 hits ~= +135 — well above weapon-damage noise.
    assert _sum_damage(True) > _sum_damage(False)
