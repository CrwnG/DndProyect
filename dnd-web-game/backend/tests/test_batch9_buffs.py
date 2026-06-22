"""Batch 9: buff spells take effect.

Buff spells (Bless's +1d4 to attack rolls, …) were computed by the core but never
applied to combat state, so they were cosmetic. Store them on the targets, roll
the bonus into the attacker's roll, and remove them when the caster's
concentration ends.
"""
from app.core.combat_engine import CombatEngine, CombatState


def _engine():
    player = {
        "id": "hero", "name": "Hero", "type": "player",
        "hp": 24, "max_hp": 24, "ac": 15, "speed": 30,
        "str_mod": 3, "attack_bonus": 5, "damage_dice": "1d8", "damage_type": "slashing",
        "abilities": {"strength": 16, "dexterity": 12, "constitution": 14,
                      "intelligence": 10, "wisdom": 10, "charisma": 10},
        "class": "fighter", "level": 3, "conditions": [],
    }
    enemy = {
        "id": "goblin", "name": "Goblin", "type": "enemy",
        "hp": 12, "max_hp": 12, "ac": 13, "speed": 30,
        "abilities": {"strength": 8, "dexterity": 14, "constitution": 10,
                      "intelligence": 10, "wisdom": 8, "charisma": 8},
        "class": "monster", "level": 1, "conditions": [],
    }
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    return eng


def test_apply_spell_buffs_stores_on_targets():
    eng = _engine()
    eng.apply_spell_buffs("cleric", {"attack_bonus_dice": "1d4", "save_bonus_dice": "1d4"}, ["hero"])
    buffs = eng.state.combatant_stats["hero"]["active_buffs"]
    assert any(b.get("attack_bonus_dice") == "1d4" and b["source"] == "cleric" for b in buffs)


def test_attack_buff_bonus_rolls_and_stacks():
    eng = _engine()
    stats = eng.state.combatant_stats["hero"]
    assert eng._attack_buff_bonus(stats) == 0                       # no buffs

    stats["active_buffs"] = [{"source": "c", "attack_bonus_dice": "1d4"}]
    for _ in range(25):
        assert 1 <= eng._attack_buff_bonus(stats) <= 4             # one 1d4

    stats["active_buffs"] = [{"attack_bonus_dice": "1d4"}, {"attack_bonus_dice": "1d4"}]
    for _ in range(25):
        assert 2 <= eng._attack_buff_bonus(stats) <= 8             # two 1d4 stack

    # A non-attack buff (e.g. AC) contributes nothing to the attack bonus.
    stats["active_buffs"] = [{"ac_bonus": 2}]
    assert eng._attack_buff_bonus(stats) == 0


def test_recasting_bless_does_not_stack():
    """QA: re-casting the same spell (or the same spell from another caster) must
    replace, not stack, the buff on a target."""
    eng = _engine()
    eng.apply_spell_buffs("cleric", {"attack_bonus_dice": "1d4"}, ["hero"], spell_id="bless")
    eng.apply_spell_buffs("cleric", {"attack_bonus_dice": "1d4"}, ["hero"], spell_id="bless")
    buffs = [b for b in eng.state.combatant_stats["hero"]["active_buffs"]
             if b.get("spell_id") == "bless"]
    assert len(buffs) == 1                       # not two

    # Bless from a DIFFERENT caster also doesn't stack (same spell).
    eng.apply_spell_buffs("bard", {"attack_bonus_dice": "1d4"}, ["hero"], spell_id="bless")
    bless = [b for b in eng.state.combatant_stats["hero"]["active_buffs"]
             if b.get("spell_id") == "bless"]
    assert len(bless) == 1


def test_buff_inactive_once_caster_stops_concentrating():
    """QA: a concentration buff stops applying as soon as the caster is no longer
    concentrating on it (covers voluntary drop / switch / death, not just a failed
    save)."""
    eng = _engine()
    # Caster 'hero' concentrates on bless and buffs itself.
    stats = eng.state.combatant_stats["hero"]
    stats["spellcasting"] = {"concentrating_on": "bless"}
    eng.apply_spell_buffs("hero", {"attack_bonus_dice": "1d4"}, ["hero"], spell_id="bless")
    for _ in range(10):
        assert eng._attack_buff_bonus(stats) >= 1        # active while concentrating

    # Concentration ends (any reason) -> the buff no longer applies.
    stats["spellcasting"]["concentrating_on"] = None
    assert eng._attack_buff_bonus(stats) == 0


def test_remove_buffs_from_caster_on_concentration_end():
    eng = _engine()
    eng.apply_spell_buffs("cleric", {"attack_bonus_dice": "1d4"}, ["hero"])
    eng.apply_spell_buffs("wizard", {"ac_bonus": 2}, ["hero"])

    eng.remove_buffs_from_caster("cleric")
    remaining = eng.state.combatant_stats["hero"]["active_buffs"]
    assert all(b["source"] != "cleric" for b in remaining)         # cleric's Bless gone
    assert any(b["source"] == "wizard" for b in remaining)         # other buff stays
