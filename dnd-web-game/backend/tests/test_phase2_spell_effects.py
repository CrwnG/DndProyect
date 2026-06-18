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


def test_upcast_preserves_flat_modifier_and_per_slot_scaling():
    """Upcasting must keep NdM+K flats and apply the per-slot scaling (incl. its flat).

    Magic Missile is 3d4+3 and gains one dart (1d4+1) per slot above 1st.
    The old upcast collapsed NdM+K -> NdM, dropping every flat.
    """
    reg = _registry()
    mm = reg.get_spell("magic_missile")
    # base 1st-level slot is unchanged
    assert SpellEffectResolver._calculate_spell_damage(mm, caster_level=9, slot_level=1) == "3d4+3"
    # 2nd-level slot: +1 dart (1d4+1) -> 4d4+4
    assert SpellEffectResolver._calculate_spell_damage(mm, caster_level=9, slot_level=2) == "4d4+4"
    # 3rd-level slot: +2 darts -> 5d4+5
    assert SpellEffectResolver._calculate_spell_damage(mm, caster_level=9, slot_level=3) == "5d4+5"
    # Fireball (same-die scaling, no flat) still works
    fb = reg.get_spell("fireball")
    assert SpellEffectResolver._calculate_spell_damage(fb, caster_level=9, slot_level=5) == "10d6"
    SpellRegistry.reset()


def test_save_damage_spells_apply_damage():
    """Save-based damage spells that defeated the regex must deal damage.

    Disintegrate (10d6+40, nothing on save) and Finger of Death (7d8+30, half
    on save) parsed to no damage before enrichment.
    """
    reg = _registry()
    dis = reg.get_spell("disintegrate")
    assert dis.damage_dice == "10d6+40"
    assert dis.half_damage_on_save is False
    # upcast at a 7th-level slot: +3d6 -> 13d6+40
    assert SpellEffectResolver._calculate_spell_damage(dis, caster_level=12, slot_level=7) == "13d6+40"
    # forced-fail save (DC 100) deals full damage; forced-success (DC 1) deals nothing
    failed = SpellEffectResolver.resolve_save_spell(dis, spell_save_dc=100, target_save_bonus=0,
                                                    caster_level=12, slot_level=6)
    assert not failed["saved"] and failed["damage"] > 0
    saved = SpellEffectResolver.resolve_save_spell(dis, spell_save_dc=1, target_save_bonus=0,
                                                   caster_level=12, slot_level=6)
    assert saved["saved"] and saved["damage"] == 0

    fod = reg.get_spell("finger_of_death")
    assert fod.damage_dice == "7d8+30"
    # half on save -> still > 0
    fod_saved = SpellEffectResolver.resolve_save_spell(fod, spell_save_dc=1, target_save_bonus=0,
                                                       caster_level=13, slot_level=7)
    assert fod_saved["saved"] and fod_saved["damage"] > 0
    SpellRegistry.reset()


def test_healing_upcasts_via_scaling():
    """Healing must upcast using the structured scaling field, not a flat +1 die.

    Cure Wounds is 2d8 and scales by 2d8 per slot above 1st.
    """
    reg = _registry()
    cw = reg.get_spell("cure_wounds")
    r1 = SpellEffectResolver.resolve_healing_spell(cw, ability_mod=0, slot_level=1)
    assert r1["healing_dice"] == "2d8"
    r3 = SpellEffectResolver.resolve_healing_spell(cw, ability_mod=0, slot_level=3)
    assert r3["healing_dice"] == "6d8"   # base 2d8 + 2 levels * 2d8
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
