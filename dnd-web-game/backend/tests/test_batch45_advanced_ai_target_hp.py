"""Batch 45: the advanced enemy AI no longer crashes on every turn.

`TargetEvaluator._calculate_hp_score` did `target_stats.get("current_hp", target.hp)`. Python
evaluates the default eagerly, and a `Combatant` has no `.hp` attribute (it's `current_hp`),
so EVERY advanced-AI target evaluation raised `AttributeError` — the route caught it and fell
back to the simple AI on every enemy turn, so the tactical AI was dead. Fixed to read
`current_hp` from the combatant via getattr.
"""
from app.core.combat_engine import CombatEngine, CombatState
from app.core.ai import get_ai_for_combatant
from app.core.ai.targeting import TargetEvaluator, TargetPriority


def _mk(cid, ctype, **over):
    base = {"id": cid, "name": cid, "type": ctype, "hp": 30, "max_hp": 30, "ac": 12,
            "speed": 30, "str_mod": 2, "attack_bonus": 4, "damage_dice": "1d8",
            "damage_type": "slashing",
            "abilities": {"strength": 14, "dexterity": 12, "constitution": 14,
                          "intelligence": 10, "wisdom": 10, "charisma": 10},
            "class": "fighter", "level": 3, "conditions": []}
    base.update(over)
    return base


def _engine(enemy_class="monster"):
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat(
        [_mk("pc_full", "player"), _mk("pc_hurt", "player", hp=4, max_hp=30)],
        [_mk("gob", "enemy", **{"class": enemy_class})],
        positions={"pc_full": (0, 0), "pc_hurt": (1, 0), "gob": (3, 0)},
    )
    return eng


def test_advanced_ai_decide_action_does_not_crash():
    eng = _engine()
    ai = get_ai_for_combatant(eng, "gob")
    decision = ai.decide_action()           # previously raised AttributeError: 'Combatant' has no 'hp'
    assert decision is not None
    assert decision.action_type             # some concrete action, not a crash


def test_hp_score_ranks_wounded_target_higher():
    eng = _engine()
    evaluator = TargetEvaluator(eng, "gob")
    hurt = evaluator.evaluate_target("pc_hurt", TargetPriority.LOWEST_HP)
    full = evaluator.evaluate_target("pc_full", TargetPriority.LOWEST_HP)
    assert hurt.hp_score > full.hp_score    # a 4/30 target is a better finish-off than 30/30
