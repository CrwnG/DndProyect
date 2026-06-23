"""Batch 28: a Monk's main-action Unarmed Strike uses Martial Arts (DEX + the MA die).

RAW 2024 Martial Arts: while unarmed (or wielding a Monk weapon) a Monk may use DEX
in place of STR for the attack and damage rolls, and the Unarmed Strike's damage die
is the level-scaled Martial Arts die (1d6 -> 1d8 -> 1d10 -> 1d12) instead of the
default 1.  The main Attack action (``_handle_attack``) ignored both: a DEX monk's
unarmed strike rolled to-hit and for damage with STR and used the default unarmed
die.  This batch makes the main-action unarmed strike honor Martial Arts.

It also resolves the documented Ray-of-Enfeeblement follow-up: an enfeebled DEX monk
striking unarmed uses DEX, so the "halve Strength damage" debuff must NOT halve it.
"""
import app.core.rules_engine as rules_engine
import app.core.dice as dice
from app.core.dice import D20Result
from app.core.combat_engine import CombatEngine, CombatState, ActionType, TurnState


def _combat(monkeypatch, *, str_mod, dex_mod, level=3, cls="monk", buffs=None):
    # roll_d20 -> base 10 + modifier (so .modifier exposes ability+prof; non-crit hit).
    monkeypatch.setattr(rules_engine, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[10], modifier=modifier, total=10 + modifier))
    # Each damage die returns its own size, so damage reveals which die was rolled.
    monkeypatch.setattr(dice, "roll_die", lambda sides: sides)

    attacker = {"id": "mk", "name": "Striker", "type": "player", "hp": 30, "max_hp": 30,
                "ac": 15, "speed": 30, "str_mod": str_mod, "dex_mod": dex_mod,
                "abilities": {"strength": 10 + str_mod * 2, "dexterity": 10 + dex_mod * 2,
                              "constitution": 14, "intelligence": 10, "wisdom": 14,
                              "charisma": 10},
                "class": cls, "level": level, "conditions": []}
    enemy = {"id": "dummy", "name": "Dummy", "type": "enemy", "hp": 200, "max_hp": 200,
             "ac": 5, "speed": 30,
             "abilities": {"strength": 10, "dexterity": 10, "constitution": 10,
                           "intelligence": 8, "wisdom": 8, "charisma": 8},
             "class": "monster", "level": 1, "conditions": []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([attacker], [enemy])
    if buffs is not None:
        eng.state.combatant_stats["mk"]["active_buffs"] = buffs
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(i for i, c in enumerate(tracker.combatants) if c.id == "mk")
    eng.state.current_turn = TurnState(combatant_id="mk")
    return eng


def test_monk_unarmed_uses_dex_for_attack_and_damage(monkeypatch):
    """L3 monk STR0/DEX4 unarmed: attack mod = DEX 4 + prof 2 = 6; damage = 1d6 + DEX 4."""
    eng = _combat(monkeypatch, str_mod=0, dex_mod=4)
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="unarmed")
    assert r.success
    assert r.extra_data["attack_roll"].modifier == 6      # DEX 4 + prof 2 (not STR 0 -> 2)
    assert r.damage_dealt == 10                            # MA die 1d6 -> 6, + DEX 4


def test_monk_unarmed_die_scales_with_level(monkeypatch):
    """L5 monk steps up to the 1d8 Martial Arts die -> 8 + DEX 4 = 12."""
    eng = _combat(monkeypatch, str_mod=0, dex_mod=4, level=5)
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="unarmed")
    assert r.damage_dealt == 12                            # 1d8 -> 8, + DEX 4


def test_monk_unarmed_uses_str_when_strength_is_better(monkeypatch):
    """Martial Arts uses the HIGHER of STR/DEX: a STR4/DEX0 monk uses STR."""
    eng = _combat(monkeypatch, str_mod=4, dex_mod=0)
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="unarmed")
    assert r.extra_data["attack_roll"].modifier == 6       # STR 4 + prof 2
    assert r.damage_dealt == 10                             # 1d6 -> 6, + STR 4


def test_monk_greatsword_uses_str_not_dex(monkeypatch):
    """A two-handed/heavy weapon is NOT a Monk weapon: a DEX monk wields it with STR."""
    eng = _combat(monkeypatch, str_mod=0, dex_mod=4)
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="greatsword")
    assert r.extra_data["attack_roll"].modifier == 2       # STR 0 + prof 2 (not DEX -> 6)
    assert r.damage_dealt == 12                             # greatsword 2d6 -> 12, + STR 0


def test_non_monk_unarmed_uses_str(monkeypatch):
    """Martial Arts is monk-only: a fighter's unarmed strike still uses STR."""
    eng = _combat(monkeypatch, str_mod=0, dex_mod=4, cls="fighter")
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="unarmed")
    assert r.extra_data["attack_roll"].modifier == 2       # STR 0 + prof 2 (not DEX -> 6)


def test_enfeebled_dex_monk_unarmed_is_not_halved(monkeypatch):
    """Ray of Enfeeblement halves STR attacks; a DEX monk's unarmed strike dodges it."""
    eng = _combat(monkeypatch, str_mod=0, dex_mod=4,
                  buffs=[{"halve_strength_damage": True}])
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="unarmed")
    assert r.damage_dealt == 10                             # NOT halved (uses DEX)


def test_enfeebled_str_monk_unarmed_is_halved(monkeypatch):
    """A STR-based monk's unarmed strike DOES use Strength, so it is halved."""
    eng = _combat(monkeypatch, str_mod=4, dex_mod=0,
                  buffs=[{"halve_strength_damage": True}])
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="unarmed")
    assert r.damage_dealt == 5                              # (6 + 4) // 2


def test_monk_finesse_weapon_already_uses_dex(monkeypatch):
    """A monk's shortsword (finesse) gets DEX via the existing finesse branch — the
    Martial Arts change must not regress that."""
    eng = _combat(monkeypatch, str_mod=0, dex_mod=4)
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="shortsword")
    assert r.extra_data["attack_roll"].modifier == 6       # DEX 4 + prof 2


def test_monk_nonfinesse_simple_weapon_scope_limitation(monkeypatch):
    """Documented scope limit: a non-finesse simple monk weapon (quarterstaff) still
    uses STR because we don't yet load simple/martial weapon-category data. This test
    pins that intended behavior so a future category-aware change is a deliberate one."""
    eng = _combat(monkeypatch, str_mod=0, dex_mod=4)
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="quarterstaff")
    assert r.extra_data["attack_roll"].modifier == 2       # STR 0 + prof 2 (not DEX -> 6)
