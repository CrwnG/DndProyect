"""Batch 21 (Goal a): smite spells are a pending rider on the next weapon hit.

Searing/Wrathful/Blinding/Branding/Staggering/Banishing Smite are cast on yourself
and "the next time you hit a creature with a weapon attack before the spell ends"
they add damage (+ a save-or-condition). They were mis-modeled as SELF-target
save spells (so they did nothing useful / hit the caster). Now casting one stows a
``pending_smite`` on the caster, and the next weapon hit consumes it.
"""
import app.core.dice as dice
from app.core.dice import D20Result
from app.core.combat_engine import CombatEngine, CombatState, ActionType
from app.core.spell_system import SpellRegistry, SpellEffectResolver, cast_spell


def _engine():
    player = {
        "id": "pal", "name": "Paladin", "type": "player",
        "hp": 30, "max_hp": 30, "ac": 16, "speed": 30,
        "str_mod": 3, "attack_bonus": 20, "damage_dice": "1d8", "damage_type": "slashing",
        "abilities": {"strength": 16, "dexterity": 12, "constitution": 14,
                      "intelligence": 10, "wisdom": 10, "charisma": 16},
        "class": "paladin", "level": 5, "conditions": [],
    }
    enemy = {
        "id": "ogre", "name": "Ogre", "type": "enemy",
        "hp": 60, "max_hp": 60, "ac": 1, "speed": 30,
        "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                      "intelligence": 6, "wisdom": 7, "charisma": 7},
        "class": "monster", "level": 3, "conditions": [],
    }
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    # start_combat recomputes save mods from abilities, so pin them on the CACHE so
    # the rider's save is deterministic (always fails).
    eng.state.combatant_stats["ogre"]["wis_save"] = -100
    eng.state.combatant_stats["ogre"]["con_save"] = -100
    return eng


def test_determine_smite_effects():
    reg = SpellRegistry.get_instance()
    wrath = SpellEffectResolver._determine_smite_effects(reg.get_spell("wrathful_smite"))
    assert wrath and wrath["damage_dice"] == "1d6" and wrath["condition"] == "frightened"
    assert wrath["save_type"] == "wisdom"
    blind = SpellEffectResolver._determine_smite_effects(reg.get_spell("blinding_smite"))
    assert blind and blind["condition"] == "blinded"
    # Divine Smite is a separate post-hit action, and Fireball is no smite.
    assert SpellEffectResolver._determine_smite_effects(reg.get_spell("divine_smite")) is None
    assert SpellEffectResolver._determine_smite_effects(reg.get_spell("fireball")) is None


def test_casting_a_smite_stows_a_pending_rider_not_self_damage():
    SpellRegistry.reset()
    caster = {
        "id": "pal", "name": "Paladin", "class": "paladin", "level": 5,
        "stats": {"charisma": 16},
        "spellcasting": {
            "ability": "charisma", "spell_save_dc": 15, "spell_attack_bonus": 7,
            "spell_slots_max": {1: 4, 2: 3}, "spell_slots_used": {},
            "cantrips_known": [], "spells_known": ["wrathful_smite"],
            "prepared_spells": ["wrathful_smite"],
        },
    }
    me = {"id": "pal", "name": "Paladin", "current_hp": 30, "max_hp": 30, "ac": 16}
    r = cast_spell(caster, "wrathful_smite", 1, [me])
    assert r.success, r.description
    assert r.pending_smite and r.pending_smite["condition"] == "frightened"
    assert r.pending_smite["save_dc"] == 15
    assert not (r.damage_dealt or {})            # no self-damage
    assert not (r.conditions_applied or {})      # caster isn't frightened
    SpellRegistry.reset()


def test_consume_pending_smite_rolls_doubles_on_crit_and_clears():
    eng = _engine()
    stats = eng.state.combatant_stats["pal"]
    stats["pending_smite"] = {"damage_dice": "2d6", "damage_type": "necrotic",
                              "save_type": "wisdom", "condition": "frightened", "save_dc": 15}
    rider = eng._consume_pending_smite("pal", is_crit=False)
    assert rider and 2 <= rider["bonus_damage"] <= 12
    assert rider["condition"] == "frightened"
    assert stats.get("pending_smite") is None        # consumed (next-hit only)
    assert eng._consume_pending_smite("pal") is None  # nothing left

    stats["pending_smite"] = {"damage_dice": "2d6", "damage_type": "necrotic"}
    crit = eng._consume_pending_smite("pal", is_crit=True)
    assert 4 <= crit["bonus_damage"] <= 24           # doubled dice


def test_apply_smite_condition_respects_the_save():
    eng = _engine()
    rider = {"condition": "frightened", "save_type": "wisdom", "save_dc": 15}
    eng._apply_smite_condition("ogre", rider)         # ogre wis_save -100 -> fails
    assert "frightened" in eng.state.combatant_stats["ogre"]["conditions"]

    # A target that always saves is not afflicted.
    eng.state.combatant_stats["ogre"]["conditions"] = []
    eng.state.combatant_stats["ogre"]["wis_save"] = 100
    eng._apply_smite_condition("ogre", rider)
    assert "frightened" not in eng.state.combatant_stats["ogre"]["conditions"]


def test_weapon_hit_consumes_the_pending_smite(monkeypatch):
    import app.core.rules_engine as rules_engine
    # Force a clean hit (base 12, no crit/fumble) so the rider reliably triggers.
    # resolve_attack binds roll_d20 from rules_engine, so patch it there.
    monkeypatch.setattr(rules_engine, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[12], modifier=modifier, total=12 + modifier))
    eng = _engine()
    # Make the paladin the current combatant.
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(
        i for i, c in enumerate(tracker.combatants) if c.id == "pal")
    eng.state.combatant_stats["pal"]["pending_smite"] = {
        "damage_dice": "3d8", "damage_type": "radiant",
        "save_type": "wisdom", "condition": "frightened", "save_dc": 15,
    }
    hp_before = eng.state.combatant_stats["ogre"]["current_hp"]
    eng.take_action(ActionType.ATTACK, target_id="ogre")

    assert eng.state.combatant_stats["pal"].get("pending_smite") is None     # consumed
    assert "frightened" in eng.state.combatant_stats["ogre"]["conditions"]    # rider landed
    assert eng.state.combatant_stats["ogre"]["current_hp"] < hp_before        # took damage
