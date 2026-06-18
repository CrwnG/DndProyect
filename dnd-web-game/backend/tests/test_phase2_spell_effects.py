"""Phase 2 — structured spell combat fields + upcasting (see ROADMAP.md Phase 2).

Combat effects were regex-parsed from prose, so iconic spells silently did
nothing: Cure Wounds healed 0 (the healing regex fails on "regains a number of
Hit Points equal to 2d8") and Fireball never upcast (higher_levels is null).
The fix: read explicit structured fields from the spell JSON and let them win
over prose, plus a `scaling` field that drives upcasting.
"""
from app.core.spell_system import SpellRegistry, SpellEffectResolver, SpellCaster, cast_spell


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


def test_at_higher_levels_key_enables_upcasting():
    """Spells keyed `at_higher_levels` (not `higher_levels`) must still upcast.

    Lightning Bolt uses `at_higher_levels` ("increases by 1d6 ..."), which the
    loader ignored, so its damage never scaled.
    """
    reg = _registry()
    lb = reg.get_spell("lightning_bolt")
    assert lb is not None
    assert lb.damage_dice == "8d6"
    # 5th-level slot on a 3rd-level spell -> +2d6 = 10d6
    assert SpellEffectResolver._calculate_spell_damage(lb, caster_level=9, slot_level=5) == "10d6"
    SpellRegistry.reset()


def test_regex_resistant_damage_spells_get_explicit_fields():
    """Spells whose prose defeats the damage regex need explicit fields.

    Chromatic Orb ("3d8 damage of the chosen type") and Magic Missile
    ("1d4 + 1 Force") both parsed to no damage before enrichment.
    """
    reg = _registry()
    co = reg.get_spell("chromatic_orb")
    assert co.damage_dice == "3d8"
    assert co.attack_type == "ranged_spell"          # from prose ("ranged spell attack")
    assert SpellEffectResolver._calculate_spell_damage(co, caster_level=9, slot_level=3) == "5d8"
    mm = reg.get_spell("magic_missile")
    assert mm.damage_dice == "3d4+3"                  # three darts of 1d4+1, auto-hit
    assert mm.damage_type == "force"
    SpellRegistry.reset()


def test_cast_spell_consumes_slot_on_caster_data():
    """cast_spell must persist slot consumption back to caster_data.

    Previously use_slot ran on a local SpellCaster that was discarded, so any
    caller outside the combat route consumed zero slots.
    """
    SpellRegistry.reset()
    caster = {
        "id": "wiz", "name": "Wizard", "class": "wizard", "level": 5,
        "stats": {"intelligence": 16},
        "spellcasting": {
            "ability": "intelligence", "spell_save_dc": 14, "spell_attack_bonus": 6,
            "spell_slots_max": {1: 2, 2: 2}, "spell_slots_used": {},
            "cantrips_known": [], "spells_known": ["magic_missile"],
            "prepared_spells": ["magic_missile"],
        },
    }
    target = {"id": "t1", "name": "Goblin", "current_hp": 20, "max_hp": 20,
              "ac": 12, "position": {"x": 0, "y": 0}}

    before = SpellCaster(caster).spellcasting.get_available_slots(1)
    result = cast_spell(caster, "magic_missile", 1, [target])
    assert result.success, result.description
    after = SpellCaster(caster).spellcasting.get_available_slots(1)
    assert after == before - 1, f"slot not consumed on caster_data: {before} -> {after}"
    SpellRegistry.reset()
