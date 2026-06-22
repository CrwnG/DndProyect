"""Batch 19: Haste isn't mis-routed by a spurious prose-parsed save.

save_type is prose-extracted from "<ability> saving throw" anywhere in the
description. Haste's text ("advantage on Dexterity saving throws") tripped it, so
Haste carried save_type=dexterity and the cast dispatch sent it down the SAVE
branch instead of the buff branch — so even after the #23 pipeline fix, Haste's
+2 AC never applied. Clear the spurious save so Haste reaches the buff branch.
"""
from app.core.spell_system import SpellRegistry, cast_spell


def test_haste_has_no_save_type():
    SpellRegistry.reset()
    assert SpellRegistry.get_instance().get_spell("haste").save_type is None
    SpellRegistry.reset()


def test_haste_reaches_the_buff_branch_and_buffs_ac():
    SpellRegistry.reset()
    caster = {
        "id": "w", "name": "Wiz", "class": "wizard", "level": 7,
        "stats": {"intelligence": 16},
        "spellcasting": {
            "ability": "intelligence", "spell_save_dc": 15, "spell_attack_bonus": 7,
            "spell_slots_max": {1: 4, 2: 3, 3: 3}, "spell_slots_used": {},
            "cantrips_known": [], "spells_known": ["haste"], "prepared_spells": ["haste"],
        },
    }
    target = {"id": "w", "name": "Wiz", "current_hp": 30, "max_hp": 30, "ac": 14, "dex_mod": 2}
    r = cast_spell(caster, "haste", 3, [target])
    assert r.success, r.description
    assert r.buff_effects and r.buff_effects.get("ac_bonus") == 2
    SpellRegistry.reset()


def test_real_save_spells_keep_their_save():
    SpellRegistry.reset()
    reg = SpellRegistry.get_instance()
    assert reg.get_spell("fireball").save_type == "dexterity"
    assert reg.get_spell("hold_person").save_type == "wisdom"
    SpellRegistry.reset()
