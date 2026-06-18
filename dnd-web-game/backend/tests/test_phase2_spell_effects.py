"""Phase 2 — structured spell combat fields + upcasting (see ROADMAP.md Phase 2).

Combat effects were regex-parsed from prose, so iconic spells silently did
nothing: Cure Wounds healed 0 (the healing regex fails on "regains a number of
Hit Points equal to 2d8") and Fireball never upcast (higher_levels is null).
The fix: read explicit structured fields from the spell JSON and let them win
over prose, plus a `scaling` field that drives upcasting.
"""
from app.core.spell_system import SpellRegistry, SpellEffectResolver


def _registry():
    SpellRegistry.reset()
    return SpellRegistry.get_instance()


def test_explicit_healing_dice_is_read():
    reg = _registry()
    cw = reg.get_spell("cure_wounds")
    assert cw is not None
    assert cw.healing_dice == "2d8"   # explicit JSON field; prose regex previously gave None
    SpellRegistry.reset()


def test_fireball_upcasts_via_scaling_field():
    reg = _registry()
    fb = reg.get_spell("fireball")
    assert fb is not None
    assert fb.damage_dice == "8d6"
    # base 3rd-level slot -> 8d6; cast in a 5th-level slot -> +2d6 = 10d6
    assert SpellEffectResolver._calculate_spell_damage(fb, caster_level=9, slot_level=3) == "8d6"
    assert SpellEffectResolver._calculate_spell_damage(fb, caster_level=9, slot_level=5) == "10d6"
    SpellRegistry.reset()
