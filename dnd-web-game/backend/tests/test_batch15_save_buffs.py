"""Batch 15: Bless's +1d4 reaches the two remaining save paths.

Batch 13 added save_bonus_dice to the monster-ability save paths, but two saves
were still un-buffed (found by Codex QA on #18):

1. Spell saves — a Blessed PC saving against an enemy's Sacred Flame / Burning
   Hands / Hold Person went through spell_system._get_target_save_modifier, which
   knows nothing about active_buffs.
2. Concentration CON saves — a Blessed concentrator taking damage didn't add the
   1d4 to the check to keep their spell up.

The spell save resolver is combat-state-agnostic, so the engine pre-rolls the
(concentration-gated) buff and stamps it under ``_save_buff_bonus`` on each target;
``_get_target_save_modifier`` just adds that number.
"""
from app.core.combat_engine import CombatEngine, CombatState
from app.core.spell_system import _get_target_save_modifier


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


# ---- 1. Spell-save mechanic ------------------------------------------------

def test_get_target_save_modifier_adds_stamped_save_buff():
    assert _get_target_save_modifier({"dex_save": 3}, "dex") == 3            # no stamp
    assert _get_target_save_modifier({"dex_save": 3, "_save_buff_bonus": 2}, "dex") == 5
    # works on the ability-mod fallback path, too
    assert _get_target_save_modifier({"dex_mod": 1, "_save_buff_bonus": 2}, "dex") == 3
    # and when there is no base save at all
    assert _get_target_save_modifier({"_save_buff_bonus": 2}, "dex") == 2
    # no save_type -> still 0 (unchanged contract)
    assert _get_target_save_modifier({"_save_buff_bonus": 2}, None) == 0


# ---- 2. Engine stamps the gated, pre-rolled buff ---------------------------

def test_stamp_save_buff_uses_gated_roll():
    eng = _engine()
    src = eng.state.combatant_stats["hero"]

    # Default source = the target dict itself (player route: target IS a stats copy).
    d = {"active_buffs": [{"save_bonus_dice": "1d4"}]}
    eng.stamp_save_buff(d)
    assert 1 <= d["_save_buff_bonus"] <= 4

    # Explicit source (enemy route: a hand-built target dict with no active_buffs).
    src["active_buffs"] = [{"save_bonus_dice": "1d4"}]
    tgt = {"id": "hero"}
    eng.stamp_save_buff(tgt, source_stats=src)
    assert 1 <= tgt["_save_buff_bonus"] <= 4

    # Concentration gating: a buff whose caster has stopped concentrating = 0.
    src["spellcasting"] = {"concentrating_on": None}
    src["active_buffs"] = [{"source": "hero", "spell_id": "bless", "save_bonus_dice": "1d4"}]
    t2 = {}
    eng.stamp_save_buff(t2, source_stats=src)
    assert t2["_save_buff_bonus"] == 0


# ---- 3. Concentration CON save honors the buff -----------------------------

def test_concentration_save_includes_active_save_buff():
    eng = _engine()
    stats = eng.state.combatant_stats["hero"]
    stats["class"] = "wizard"                       # not CON-save proficient
    stats["abilities"]["constitution"] = 10         # con_mod 0
    stats["con_mod"] = 0
    bless = {"source": "hero", "spell_id": "bless", "save_bonus_dice": "1d4"}

    # The reported modifier is computed before a failed save can break concentration
    # (and strip the buff), so reset both each iteration to read the buff cleanly.
    mods = []
    for _ in range(30):
        stats["spellcasting"] = {"concentrating_on": "bless"}
        stats["active_buffs"] = [dict(bless)]
        mods.append(eng._check_concentration_on_damage("hero", 10)["modifier"])
    assert all(1 <= m <= 4 for m in mods)           # 0 base + 1d4

    # Drop the buff -> back to the bare CON modifier (0).
    stats["spellcasting"] = {"concentrating_on": "bless"}
    stats["active_buffs"] = []
    assert eng._check_concentration_on_damage("hero", 10)["modifier"] == 0
