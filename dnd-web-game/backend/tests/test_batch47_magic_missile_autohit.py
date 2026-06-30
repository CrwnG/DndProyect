"""Batch 47: auto-hit damage spells (Magic Missile) actually deal damage.

`cast_spell` resolved attack spells, save spells, and healing — but a spell with `damage_dice`
and NO `attack_type`/`save_type`/`healing_dice` (an auto-hit spell like Magic Missile, whose
darts always strike) fell through to the utility/buff `else` branch and dealt **0**. Magic
Missile now resolves through a dedicated auto-hit branch: roll the (upcast-scaled) damage and
apply it to the target.
"""
import pytest
from app.core.spell_system import cast_spell


def _caster():
    sc = {"ability": "intelligence", "spell_attack_bonus": 7, "spell_save_dc": 15,
          "spell_slots": {"1": 9, "2": 9, "3": 9},
          "prepared_spells": ["magic_missile"], "spells_known": ["magic_missile"]}
    return {"id": "w", "name": "Wiz", "level": 5, "spellcasting": sc, "int_mod": 4}


def _target():
    return [{"id": "a", "name": "a", "hp": 40, "max_hp": 40, "current_hp": 40, "ac": 99}]


def test_magic_missile_l1_deals_force_damage():
    r = cast_spell(_caster(), "magic_missile", 1, _target())
    assert r.success
    dmg = r.damage_dealt.get("a")
    assert dmg is not None and 6 <= dmg <= 15      # 3d4+3, auto-hit (even vs AC 99)
    assert r.damage_type == "force"


def test_magic_missile_auto_hits_every_time():
    """Auto-hit: never a miss, always non-zero — regardless of target AC."""
    caster = _caster()
    for _ in range(8):
        caster["spellcasting"]["spell_slots"] = {"1": 9}
        r = cast_spell(caster, "magic_missile", 1, _target())
        assert r.damage_dealt.get("a", 0) > 0


def test_magic_missile_upcast_adds_darts():
    """A 3rd-level slot fires 5 darts (5d4+5 = 10..25) — more than the 3-dart base."""
    r = cast_spell(_caster(), "magic_missile", 3, _target())
    dmg = r.damage_dealt.get("a")
    assert dmg is not None and 10 <= dmg <= 25
