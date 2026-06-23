"""Batch 25: created characters get their class's starting equipment (armor + weapon).

Before, finalize_character hard-coded ``ac = 10 + DEX`` and emitted no weapons, so a
created Fighter fought at AC 12 with 1d4 unarmed instead of AC 16 (chain mail) with a
greatsword. Now finalize resolves the class's `starting_equipment` (iconic first
option of each choice + defaults) into real armor/shield → AC and weapons → damage,
honoring per-armor DEX caps, shields (+2), and Barbarian/Monk unarmored defense.

Ability spread used: STR 16 (+3), DEX 15 (+2), CON 14 (+2), WIS 10 (0).
"""
import pytest

from app.core.character_builder import CharacterBuilder
from app.services.character_service import builder_to_combatant_data

# All RAW-verified for DEX +2 / CON +2 / WIS 0:
#   fighter chain_mail 16; cleric scale_mail(16)+shield=18; paladin chain_mail+shield=18;
#   barbarian 10+DEX+CON=14; monk 10+DEX+WIS=12; rogue/bard/warlock leather 11+DEX=13;
#   druid leather+shield=15; ranger studded_leather 12+DEX=14; casters unarmored 12.
EXPECTED_AC = {
    "barbarian": 14, "bard": 13, "cleric": 18, "druid": 15, "fighter": 16, "monk": 12,
    "paladin": 18, "ranger": 14, "rogue": 13, "sorcerer": 12, "warlock": 13, "wizard": 12,
}

_SCORES = {"strength": 15, "dexterity": 14, "constitution": 13,
           "intelligence": 12, "wisdom": 10, "charisma": 8}


def _finalize(cls, scores=None, bonuses=None):
    b = CharacterBuilder()
    of = b.rules.get_origin_feats()
    ofeat = of[0]["id"] if isinstance(of[0], dict) else getattr(of[0], "id", of[0])
    build = b.create_new_build()
    b.set_species(build, "human")
    b.set_size_choice(build, "Medium")
    b.set_class(build, cls)
    b.set_ability_scores(build, dict(scores or _SCORES))
    b.set_background(build, "soldier")
    b.set_ability_bonuses(build, bonuses or {"strength": 1, "dexterity": 1, "constitution": 1})
    b.set_origin_feat(build, ofeat)
    opts, count = b._get_skill_options(b.rules.get_class(cls))
    b.set_skill_choices(build, list(opts)[:count])
    b.set_details(build, cls.title())
    ok, result = b.finalize_character(build)
    assert ok, result
    return result


def test_calculate_ac_heavy_armor_ignores_dex_even_when_negative():
    """Verify (caught by adversarial review): heavy armor is a FLAT AC — DEX gives
    neither bonus nor penalty. Light/medium still apply DEX (incl. negative)."""
    from app.core.rules_engine import calculate_ac
    # Heavy (max_dex_bonus=0): flat, regardless of DEX sign.
    assert calculate_ac(base_ac=16, dex_modifier=-1, max_dex_bonus=0) == 16
    assert calculate_ac(base_ac=16, dex_modifier=3, max_dex_bonus=0) == 16
    # Medium (cap +2): negative DEX still reduces; high DEX capped at +2.
    assert calculate_ac(base_ac=14, dex_modifier=-1, max_dex_bonus=2) == 13
    assert calculate_ac(base_ac=14, dex_modifier=5, max_dex_bonus=2) == 16
    # Light (no cap): full DEX, including negative.
    assert calculate_ac(base_ac=11, dex_modifier=-1, max_dex_bonus=None) == 10
    assert calculate_ac(base_ac=11, dex_modifier=4, max_dex_bonus=None) == 15


def test_low_dex_fighter_in_heavy_armor_is_flat_16():
    """A STR fighter who dumped DEX (mod -1) still gets chain mail's flat AC 16,
    not 15 (the heavy-armor-negative-DEX bug the review caught)."""
    scores = {"strength": 15, "dexterity": 8, "constitution": 14,
              "intelligence": 13, "wisdom": 12, "charisma": 10}
    c = builder_to_combatant_data(_finalize("fighter", scores))  # DEX 8+1=9 -> mod -1
    assert c["dex_mod"] == -1
    assert c["ac"] == 16


@pytest.mark.parametrize("cls", sorted(EXPECTED_AC))
def test_starting_armor_gives_each_class_the_right_ac(cls):
    c = builder_to_combatant_data(_finalize(cls))
    assert c["ac"] == EXPECTED_AC[cls], f"{cls}: AC {c['ac']} != {EXPECTED_AC[cls]}"
    # Armor/shield only ever raises AC above the bare 10+DEX(=12) floor (casters stay 12).
    assert c["ac"] >= 12


@pytest.mark.parametrize("cls", sorted(EXPECTED_AC))
def test_attack_bonus_is_not_regressed_by_adding_a_weapon(cls):
    # to_combatant_data reads the weapon's attack_bonus; it must still include
    # proficiency (STR +3 + prof +2 = 5), not collapse to the bare ability mod.
    c = builder_to_combatant_data(_finalize(cls))
    assert c["attack_bonus"] == 5, f"{cls}: attack_bonus {c['attack_bonus']}"


def test_martials_wield_real_weapons_not_unarmed():
    f = builder_to_combatant_data(_finalize("fighter"))
    assert f["damage_dice"] == "2d6"          # greatsword, not 1d4 unarmed
    assert f["damage_type"] == "slashing"
    barb = builder_to_combatant_data(_finalize("barbarian"))
    assert barb["damage_dice"] == "1d12"      # greataxe


def test_casters_have_no_armor_and_a_weapon():
    w = builder_to_combatant_data(_finalize("wizard"))
    assert w["ac"] == 12                       # 10 + DEX, no armor proficiency
    assert w["damage_dice"] == "1d6"           # quarterstaff, not 1d4 unarmed


def test_shield_adds_two_for_classes_that_start_with_one():
    # Cleric: scale_mail (14 + min(DEX,2)=16) + shield (+2) = 18.
    assert builder_to_combatant_data(_finalize("cleric"))["ac"] == 18
    # Paladin: chain_mail (16) + shield (+2) = 18.
    assert builder_to_combatant_data(_finalize("paladin"))["ac"] == 18


def test_barbarian_and_monk_use_unarmored_defense():
    # Barbarian 10 + DEX(2) + CON(2) = 14; Monk 10 + DEX(2) + WIS(0) = 12.
    assert builder_to_combatant_data(_finalize("barbarian"))["ac"] == 14
    assert builder_to_combatant_data(_finalize("monk"))["ac"] == 12


def test_weapons_carry_damage_and_proficient_attack_bonus():
    weapons = _finalize("fighter")["weapons"]
    assert weapons, "fighter should start with weapons"
    primary = weapons[0]
    assert primary["damage"] == "2d6"
    assert primary["attack_bonus"] == 5       # STR +3 + proficiency +2


def test_finesse_weapon_damage_uses_dex_in_combat(monkeypatch):
    """Caught by adversarial review: when a combatant has a precomputed attack_bonus
    (which created characters now always do), the DAMAGE modifier was forced to STR.
    A finesse attacker (STR 10 / DEX 18) must deal DEX-based damage, not STR-based."""
    import app.core.rules_engine as rules_engine
    import app.core.dice as dice
    from app.core.dice import D20Result
    from app.core.combat_engine import CombatEngine, CombatState, ActionType, TurnState

    monkeypatch.setattr(rules_engine, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[12], modifier=modifier, total=12 + modifier))
    monkeypatch.setattr(dice, "roll_die", lambda sides: 1)   # every damage die rolls 1

    player = {"id": "rog", "name": "Rogue", "type": "player", "hp": 20, "max_hp": 20,
              "ac": 14, "speed": 30, "str_mod": 0, "dex_mod": 4, "attack_bonus": 6,
              "abilities": {"strength": 10, "dexterity": 18, "constitution": 12,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}   # fighter: no sneak-attack noise
    enemy = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 40, "max_hp": 40,
             "ac": 10, "speed": 30,
             "abilities": {"strength": 12, "dexterity": 10, "constitution": 12,
                           "intelligence": 8, "wisdom": 8, "charisma": 8},
             "class": "monster", "level": 2, "conditions": []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(i for i, c in enumerate(tracker.combatants) if c.id == "rog")
    eng.state.current_turn = TurnState(combatant_id="rog")

    r = eng.take_action(ActionType.ATTACK, target_id="ogre", weapon_name="dagger")
    # dagger 1d4 -> die=1; finesse uses max(STR 0, DEX 4) = 4. Damage = 1 + 4 = 5
    # (the old bug forced STR -> 1 + 0 = 1).
    assert r.damage_dealt == 5


def test_ranged_weapons_use_dex_for_their_attack_bonus():
    """Fighter starts with a light crossbow (ammunition → DEX). With STR +3 / DEX +2
    its attack bonus must be DEX+prof (4), not STR+prof (5)."""
    weapons = _finalize("fighter")["weapons"]
    ranged = [w for w in weapons if "ammunition" in (w.get("properties") or [])]
    assert ranged, "fighter should have a ranged weapon (light crossbow)"
    assert ranged[0]["attack_bonus"] == 4     # DEX +2 + proficiency +2
    # The melee primary still uses STR.
    assert weapons[0]["attack_bonus"] == 5
