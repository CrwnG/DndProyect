"""Tests for the tactical AI system."""
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from app.core.ai.tactical_ai import (
    ActionType,
    TacticalDecision,
    AIDecision,
    TacticalAI,
    get_ai_for_role,
    get_ai_for_combatant,
)


class TestActionTypeEnum:
    """Tests for ActionType enum."""

    def test_all_action_types_defined(self):
        """All action types should be defined."""
        assert ActionType.ATTACK.value == "attack"
        assert ActionType.RANGED_ATTACK.value == "ranged_attack"
        assert ActionType.MOVE.value == "move"
        assert ActionType.DASH.value == "dash"
        assert ActionType.DISENGAGE.value == "disengage"
        assert ActionType.DODGE.value == "dodge"
        assert ActionType.HIDE.value == "hide"
        assert ActionType.HELP.value == "help"
        assert ActionType.SPELL.value == "spell"
        assert ActionType.CANTRIP.value == "cantrip"
        assert ActionType.ABILITY.value == "ability"
        assert ActionType.MULTIATTACK.value == "multiattack"
        assert ActionType.NONE.value == "none"

    def test_action_type_count(self):
        """Should have 13 action types."""
        assert len(ActionType) == 13


class TestTacticalDecision:
    """Tests for TacticalDecision dataclass."""

    def test_default_values(self):
        """Defaults should be set correctly."""
        decision = TacticalDecision(action_type=ActionType.ATTACK)
        assert decision.target_id is None
        assert decision.position is None
        assert decision.ability_id is None
        assert decision.spell_id is None
        assert decision.score == 0.0
        assert decision.reasoning == ""
        assert decision.is_bonus_action is False

    def test_to_dict(self):
        """to_dict should serialize correctly."""
        decision = TacticalDecision(
            action_type=ActionType.ATTACK,
            target_id="target-1",
            position=(5, 10),
            score=75.5,
            reasoning="Attack high priority target",
            is_bonus_action=False
        )
        d = decision.to_dict()
        assert d["action_type"] == "attack"
        assert d["target_id"] == "target-1"
        assert d["position"] == (5, 10)
        assert d["score"] == 75.5
        assert d["reasoning"] == "Attack high priority target"
        assert d["is_bonus_action"] is False

    def test_alias_backward_compatible(self):
        """AIDecision should be an alias for TacticalDecision."""
        assert AIDecision is TacticalDecision


class TestTacticalAIInit:
    """Tests for TacticalAI initialization."""

    def _create_mock_engine(self, combatant_id="enemy-1", stats=None):
        """Create a mock combat engine."""
        engine = MagicMock()

        # Mock combatant
        combatant = MagicMock()
        combatant.id = combatant_id
        combatant.name = "Goblin"
        combatant.is_active = True

        # Mock initiative tracker
        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.initiative_tracker.combatants = [combatant]
        engine.state.initiative_tracker.current_round = 1

        # Mock stats
        default_stats = {
            "current_hp": 20,
            "max_hp": 30,
            "ac": 12,
            "speed": 30,
            "type": "enemy",
            "damage_dice": "1d6+2",
            "attack_bonus": 4,
        }
        if stats:
            default_stats.update(stats)
        engine.state.combatant_stats = {combatant_id: default_stats}

        # Mock positions
        engine.state.positions = {combatant_id: (5, 5)}

        # Mock current turn
        engine.state.current_turn = MagicMock()
        engine.state.current_turn.combatant_id = combatant_id
        engine.state.current_turn.action_used = False
        engine.state.current_turn.movement_used = 0

        return engine

    def test_init_loads_combatant(self):
        """AI should load combatant data on init."""
        engine = self._create_mock_engine()
        ai = TacticalAI(engine, "enemy-1")

        assert ai.combatant_id == "enemy-1"
        assert ai.combatant is not None

    def test_position_property(self):
        """Position property should return tuple."""
        engine = self._create_mock_engine()
        ai = TacticalAI(engine, "enemy-1")

        pos = ai.position
        assert isinstance(pos, tuple)
        assert pos == (5, 5)

    def test_position_from_dict(self):
        """Position should handle dict format."""
        engine = self._create_mock_engine()
        engine.state.positions = {"enemy-1": {"x": 3, "y": 7}}

        ai = TacticalAI(engine, "enemy-1")
        assert ai.position == (3, 7)


class TestBattlefieldAssessment:
    """Tests for battlefield assessment."""

    def _create_mock_engine_with_combatants(self):
        """Create mock engine with multiple combatants."""
        engine = MagicMock()

        # Create combatants
        enemy = MagicMock()
        enemy.id = "enemy-1"
        enemy.name = "Goblin"
        enemy.is_active = True

        player = MagicMock()
        player.id = "player-1"
        player.name = "Fighter"
        player.is_active = True

        ally = MagicMock()
        ally.id = "enemy-2"
        ally.name = "Goblin Archer"
        ally.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = enemy
        engine.state.initiative_tracker.combatants = [enemy, player, ally]
        engine.state.initiative_tracker.current_round = 1

        engine.state.combatant_stats = {
            "enemy-1": {"current_hp": 20, "max_hp": 30, "ac": 12, "type": "enemy", "speed": 30},
            "player-1": {"current_hp": 25, "max_hp": 40, "ac": 16, "type": "player", "class": "fighter"},
            "enemy-2": {"current_hp": 15, "max_hp": 20, "ac": 11, "type": "enemy"},
        }

        engine.state.positions = {
            "enemy-1": (5, 5),
            "player-1": (6, 5),
            "enemy-2": (3, 5),
        }

        engine.state.current_turn = MagicMock()
        engine.state.current_turn.combatant_id = "enemy-1"
        engine.state.current_turn.movement_used = 0

        return engine

    @patch('app.core.ai.tactical_ai.TargetEvaluator')
    def test_assess_battlefield_hp_percent(self, mock_evaluator):
        """Should calculate HP percentage correctly."""
        mock_evaluator.return_value.evaluate_all_targets.return_value = []

        engine = self._create_mock_engine_with_combatants()
        ai = TacticalAI(engine, "enemy-1")

        situation = ai._assess_battlefield()

        # 20/30 = 0.666...
        assert 0.66 < situation["my_hp_percent"] < 0.67
        assert situation["my_hp"] == 20
        assert situation["my_max_hp"] == 30

    @patch('app.core.ai.tactical_ai.TargetEvaluator')
    def test_assess_battlefield_identifies_enemies(self, mock_evaluator):
        """Should correctly identify enemies (different type)."""
        mock_evaluator.return_value.evaluate_all_targets.return_value = []

        engine = self._create_mock_engine_with_combatants()
        ai = TacticalAI(engine, "enemy-1")

        situation = ai._assess_battlefield()

        # Player should be an enemy (different type)
        assert len(situation["enemies"]) == 1
        assert situation["enemies"][0]["id"] == "player-1"

    @patch('app.core.ai.tactical_ai.TargetEvaluator')
    def test_assess_battlefield_identifies_allies(self, mock_evaluator):
        """Should correctly identify allies (same type)."""
        mock_evaluator.return_value.evaluate_all_targets.return_value = []

        engine = self._create_mock_engine_with_combatants()
        ai = TacticalAI(engine, "enemy-1")

        situation = ai._assess_battlefield()

        # Other enemy should be an ally
        assert len(situation["allies"]) == 1
        assert situation["allies"][0]["id"] == "enemy-2"


class TestWeaponReach:
    """Tests for weapon reach calculations."""

    def _create_ai_with_stats(self, stats):
        """Create AI with specific stats."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        combatant.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.initiative_tracker.combatants = [combatant]
        engine.state.combatant_stats = {"enemy-1": stats}
        engine.state.positions = {"enemy-1": (5, 5)}
        engine.state.current_turn = MagicMock()
        engine.state.current_turn.movement_used = 0

        return TacticalAI(engine, "enemy-1")

    def test_default_reach_is_5(self):
        """Default melee reach should be 5 feet."""
        ai = self._create_ai_with_stats({"speed": 30})
        assert ai._get_weapon_reach() == 5

    def test_reach_weapon_property(self):
        """Weapon with reach property should have 10ft reach."""
        ai = self._create_ai_with_stats({
            "speed": 30,
            "equipment": {
                "mainhand": {"name": "Glaive", "properties": ["reach", "two-handed"]}
            }
        })
        assert ai._get_weapon_reach() == 10

    def test_explicit_reach_value(self):
        """Explicit reach value should be used."""
        ai = self._create_ai_with_stats({
            "speed": 30,
            "equipment": {"mainhand": {"name": "Custom", "reach": 15}}
        })
        assert ai._get_weapon_reach() == 15

    def test_monster_action_reach(self):
        """Monster action description should be parsed for reach."""
        ai = self._create_ai_with_stats({
            "speed": 30,
            "actions": [{"name": "Bite", "desc": "Melee Weapon Attack: reach 10 ft., one target."}]
        })
        assert ai._get_weapon_reach() == 10


class TestDamageEstimation:
    """Tests for damage estimation."""

    def _create_ai_with_damage(self, damage_dice):
        """Create AI with specific damage dice."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        combatant.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.combatant_stats = {"enemy-1": {"damage_dice": damage_dice}}
        engine.state.positions = {"enemy-1": (0, 0)}

        return TacticalAI(engine, "enemy-1")

    def test_estimate_d6(self):
        """1d6 should average 3.5 -> 3."""
        ai = self._create_ai_with_damage("1d6")
        assert ai._estimate_damage() == 3

    def test_estimate_2d6(self):
        """2d6 should average 7."""
        ai = self._create_ai_with_damage("2d6")
        assert ai._estimate_damage() == 7

    def test_estimate_d8(self):
        """1d8 should average 4.5 -> 4."""
        ai = self._create_ai_with_damage("1d8")
        assert ai._estimate_damage() == 4

    def test_estimate_d10(self):
        """1d10 should average 5.5 -> 5."""
        ai = self._create_ai_with_damage("1d10")
        assert ai._estimate_damage() == 5

    def test_estimate_with_bonus(self):
        """Dice with bonus should be parsed (bonus ignored in avg)."""
        ai = self._create_ai_with_damage("1d6+3")
        assert ai._estimate_damage() == 3  # Just the dice average


class TestCriticalConditions:
    """Tests for critical condition checks."""

    def _create_ai_with_hp(self, current_hp, max_hp, flee_threshold=0.15):
        """Create AI with specific HP values."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        combatant.is_active = True

        player = MagicMock()
        player.id = "player-1"
        player.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.initiative_tracker.combatants = [combatant, player]
        engine.state.initiative_tracker.current_round = 1

        engine.state.combatant_stats = {
            "enemy-1": {
                "current_hp": current_hp,
                "max_hp": max_hp,
                "speed": 30,
                "type": "enemy",
                "ai_behavior": {"flee_threshold": flee_threshold},
            },
            "player-1": {"current_hp": 30, "max_hp": 30, "type": "player"},
        }
        engine.state.positions = {
            "enemy-1": (5, 5),
            "player-1": (3, 3),
        }
        engine.state.current_turn = MagicMock()
        engine.state.current_turn.movement_used = 0

        engine.grid_width = 20
        engine.grid_height = 20

        return TacticalAI(engine, "enemy-1")

    @patch('app.core.ai.tactical_ai.TargetEvaluator')
    def test_flee_when_below_threshold(self, mock_evaluator):
        """Should flee when HP below threshold."""
        mock_evaluator.return_value.evaluate_all_targets.return_value = []

        ai = self._create_ai_with_hp(3, 30, flee_threshold=0.15)  # 10% HP
        situation = ai._assess_battlefield()

        critical = ai._check_critical_conditions(situation)

        assert critical is not None
        assert critical.action_type == ActionType.DASH
        assert "Fleeing" in critical.reasoning

    @patch('app.core.ai.tactical_ai.TargetEvaluator')
    def test_no_flee_above_threshold(self, mock_evaluator):
        """Should not flee when HP above threshold."""
        mock_evaluator.return_value.evaluate_all_targets.return_value = []

        ai = self._create_ai_with_hp(15, 30, flee_threshold=0.15)  # 50% HP
        situation = ai._assess_battlefield()

        critical = ai._check_critical_conditions(situation)

        assert critical is None


class TestActionScoring:
    """Tests for action scoring."""

    def _create_situation(self, my_hp_percent=0.5, can_reach=None, enemies=None, priority_targets=None):
        """Create a mock situation dictionary."""
        return {
            "my_hp_percent": my_hp_percent,
            "my_hp": int(my_hp_percent * 30),
            "my_max_hp": 30,
            "my_ac": 12,
            "my_position": (5, 5),
            "allies": [],
            "enemies": enemies or [],
            "priority_targets": priority_targets or [],
            "can_reach": can_reach or [],
            "round_number": 1,
            "movement_remaining": 30,
        }

    def _create_mock_ai(self):
        """Create a mock AI instance."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        combatant.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.combatant_stats = {
            "enemy-1": {"damage_dice": "1d8", "speed": 30}
        }
        engine.state.positions = {"enemy-1": (5, 5)}

        return TacticalAI(engine, "enemy-1")

    def test_score_attack_base(self):
        """Attack should have base score of 50."""
        ai = self._create_mock_ai()
        action = TacticalDecision(action_type=ActionType.ATTACK, target_id="player-1")

        situation = self._create_situation(
            priority_targets=[{"id": "player-1", "priority_score": 0, "hp": 30, "max_hp": 30}]
        )

        score = ai._score_attack(action, situation)

        # Base 50 + 0 priority + 0 low hp bonus
        assert score >= 50

    def test_score_attack_low_hp_target_bonus(self):
        """Attacking low HP target should score higher."""
        ai = self._create_mock_ai()
        action = TacticalDecision(action_type=ActionType.ATTACK, target_id="player-1")

        situation = self._create_situation(
            priority_targets=[{"id": "player-1", "priority_score": 0, "hp": 5, "max_hp": 30}]
        )

        score = ai._score_attack(action, situation)

        # Should get bonus for low HP target
        assert score > 60

    def test_score_attack_potential_kill_bonus(self):
        """Potential kill should give big bonus."""
        ai = self._create_mock_ai()
        action = TacticalDecision(action_type=ActionType.ATTACK, target_id="player-1")

        # Target with 3 HP, we do ~4 damage average
        situation = self._create_situation(
            priority_targets=[{"id": "player-1", "priority_score": 0, "hp": 3, "max_hp": 30}]
        )

        score = ai._score_attack(action, situation)

        # Should include kill bonus
        assert score > 90

    def test_score_attack_no_target_returns_zero(self):
        """Attack on unknown target should score 0."""
        ai = self._create_mock_ai()
        action = TacticalDecision(action_type=ActionType.ATTACK, target_id="unknown")

        situation = self._create_situation(priority_targets=[])

        score = ai._score_attack(action, situation)
        assert score == 0

    def test_score_dash_higher_when_no_reach(self):
        """Dash should score higher when can't reach anyone."""
        ai = self._create_mock_ai()
        action = TacticalDecision(action_type=ActionType.DASH, target_id="player-1")

        situation = self._create_situation(can_reach=[])  # No reachable enemies

        score = ai._score_dash(action, situation)

        # Base 20 + 30 for no reach
        assert score >= 50

    def test_score_dodge_low_hp_bonus(self):
        """Dodge should score higher at low HP."""
        ai = self._create_mock_ai()
        action = TacticalDecision(action_type=ActionType.DODGE)

        situation = self._create_situation(
            my_hp_percent=0.2,  # 20% HP
            enemies=[{"id": "p1", "distance": 5}]
        )

        score = ai._score_dodge(action, situation)

        # Base 10 + 40 for low HP + 10 for adjacent enemy
        assert score >= 50

    def test_score_disengage_surrounded(self):
        """Disengage should score higher when surrounded."""
        ai = self._create_mock_ai()
        action = TacticalDecision(action_type=ActionType.DISENGAGE)

        situation = self._create_situation(
            my_hp_percent=0.4,
            enemies=[{"id": "p1", "distance": 5}, {"id": "p2", "distance": 5}]
        )

        score = ai._score_disengage(action, situation)

        # Base 15 + 25 low HP + 30 for 2 adjacent
        assert score >= 70


class TestBonusActions:
    """Tests for bonus action decisions."""

    def _create_ai_with_class(self, char_class, hp_percent=1.0, extra_stats=None):
        """Create AI with specific class."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        combatant.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.initiative_tracker.combatants = [combatant]
        engine.state.initiative_tracker.current_round = 1

        stats = {
            "class": char_class,
            "current_hp": int(hp_percent * 30),
            "max_hp": 30,
            "type": "enemy",
            "speed": 30,
        }
        if extra_stats:
            stats.update(extra_stats)

        engine.state.combatant_stats = {"enemy-1": stats}
        engine.state.positions = {"enemy-1": (5, 5)}
        engine.state.current_turn = MagicMock()
        engine.state.current_turn.combatant_id = "enemy-1"
        engine.state.current_turn.action_used = False
        engine.state.current_turn.movement_used = 0

        return TacticalAI(engine, "enemy-1")

    def test_rogue_cunning_action_options(self):
        """Rogue should have Cunning Action options."""
        ai = self._create_ai_with_class("rogue")

        options = ai._get_cunning_action_options()

        assert len(options) == 3
        action_types = [o.action_type for o in options]
        assert ActionType.DASH in action_types
        assert ActionType.DISENGAGE in action_types
        assert ActionType.HIDE in action_types

        for option in options:
            assert option.is_bonus_action is True
            assert "Cunning Action" in option.reasoning

    @patch('app.core.ai.tactical_ai.TargetEvaluator')
    def test_fighter_second_wind_when_hurt(self, mock_evaluator):
        """Fighter should consider Second Wind when hurt."""
        mock_evaluator.return_value.evaluate_all_targets.return_value = []

        ai = self._create_ai_with_class(
            "fighter",
            hp_percent=0.4,  # 40% HP
            extra_stats={"class_resources": {"second_wind": 1}}
        )

        result = ai.decide_bonus_action()

        # Should suggest second wind
        assert result is not None
        assert result.ability_id == "second_wind"

    @patch('app.core.ai.tactical_ai.TargetEvaluator')
    def test_barbarian_rage_considered(self, mock_evaluator):
        """Barbarian should consider Rage."""
        mock_evaluator.return_value.evaluate_all_targets.return_value = []

        ai = self._create_ai_with_class(
            "barbarian",
            hp_percent=0.8,
            extra_stats={
                "class_resources": {"rages": 2},
                "conditions": [],
            }
        )

        result = ai.decide_bonus_action()

        # Should suggest rage
        assert result is not None
        assert result.ability_id == "rage"

    def test_is_bonus_action_spell(self):
        """Should identify bonus action spells."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.combatant_stats = {"enemy-1": {}}
        engine.state.positions = {"enemy-1": (0, 0)}

        ai = TacticalAI(engine, "enemy-1")

        assert ai._is_bonus_action_spell("misty_step") is True
        assert ai._is_bonus_action_spell("healing_word") is True
        assert ai._is_bonus_action_spell("hex") is True
        assert ai._is_bonus_action_spell("fireball") is False
        assert ai._is_bonus_action_spell("magic_missile") is False

    def test_offhand_weapon_detection(self):
        """Should detect offhand weapon."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.combatant_stats = {
            "enemy-1": {
                "equipment": {
                    "mainhand": {"name": "Shortsword", "type": "weapon"},
                    "offhand": {"name": "Dagger", "type": "weapon"},
                }
            }
        }
        engine.state.positions = {"enemy-1": (0, 0)}

        ai = TacticalAI(engine, "enemy-1")
        offhand = ai._get_offhand_weapon()

        assert offhand is not None
        assert offhand["name"] == "Dagger"

    def test_no_offhand_weapon(self):
        """Should return None when no offhand weapon."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.combatant_stats = {
            "enemy-1": {
                "equipment": {"mainhand": {"name": "Greatsword", "type": "weapon"}}
            }
        }
        engine.state.positions = {"enemy-1": (0, 0)}

        ai = TacticalAI(engine, "enemy-1")
        offhand = ai._get_offhand_weapon()

        assert offhand is None


class TestDecideAction:
    """Tests for main decide_action method."""

    def _create_full_mock_engine(self):
        """Create a fully mocked engine for decision tests."""
        engine = MagicMock()

        enemy = MagicMock()
        enemy.id = "enemy-1"
        enemy.name = "Goblin"
        enemy.is_active = True

        player = MagicMock()
        player.id = "player-1"
        player.name = "Fighter"
        player.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = enemy
        engine.state.initiative_tracker.combatants = [enemy, player]
        engine.state.initiative_tracker.current_round = 1

        engine.state.combatant_stats = {
            "enemy-1": {
                "current_hp": 20,
                "max_hp": 30,
                "ac": 12,
                "type": "enemy",
                "speed": 30,
                "damage_dice": "1d6+2",
            },
            "player-1": {
                "current_hp": 30,
                "max_hp": 40,
                "ac": 16,
                "type": "player",
            },
        }

        engine.state.positions = {
            "enemy-1": (5, 5),
            "player-1": (6, 5),  # Adjacent
        }

        engine.state.current_turn = MagicMock()
        engine.state.current_turn.combatant_id = "enemy-1"
        engine.state.current_turn.action_used = False
        engine.state.current_turn.movement_used = 0

        engine.grid_width = 20
        engine.grid_height = 20

        return engine

    @patch('app.core.ai.tactical_ai.TargetEvaluator')
    def test_decide_action_attacks_reachable_enemy(self, mock_evaluator):
        """Should attack reachable enemy."""
        # Mock target evaluator
        mock_score = MagicMock()
        mock_score.target_id = "player-1"
        mock_score.target_name = "Fighter"
        mock_score.total_score = 50
        mock_score.reasons = []
        mock_evaluator.return_value.evaluate_all_targets.return_value = [mock_score]

        engine = self._create_full_mock_engine()
        ai = TacticalAI(engine, "enemy-1")

        decision = ai.decide_action()

        assert decision.action_type == ActionType.ATTACK
        assert decision.target_id == "player-1"

    @patch('app.core.ai.tactical_ai.TargetEvaluator')
    def test_decide_action_no_enemies_returns_none_action(self, mock_evaluator):
        """Should return NONE action when no valid actions."""
        mock_evaluator.return_value.evaluate_all_targets.return_value = []

        engine = self._create_full_mock_engine()
        # Remove player so no enemies
        engine.state.initiative_tracker.combatants = [engine.state.initiative_tracker.combatants[0]]

        ai = TacticalAI(engine, "enemy-1")
        decision = ai.decide_action()

        assert decision.action_type == ActionType.NONE


class TestFactoryFunctions:
    """Tests for AI factory functions."""

    def test_get_ai_for_role_melee_brute(self):
        """Should return MeleeBruteAI for melee_brute role."""
        engine = MagicMock()
        engine.state.combatant_stats = {"enemy-1": {}}
        engine.state.positions = {"enemy-1": (0, 0)}
        engine.state.initiative_tracker.get_combatant.return_value = MagicMock()

        with patch('app.core.ai.tactical_ai.MeleeBruteAI', create=True) as MockAI:
            from app.core.ai.behaviors import MeleeBruteAI
            ai = get_ai_for_role("melee_brute", engine, "enemy-1")
            assert ai is not None

    def test_get_ai_for_role_class_mapping(self):
        """Should map character classes to appropriate AI."""
        engine = MagicMock()
        engine.state.combatant_stats = {"enemy-1": {}}
        engine.state.positions = {"enemy-1": (0, 0)}
        engine.state.initiative_tracker.get_combatant.return_value = MagicMock()

        # These should not raise - just verify function works
        ai = get_ai_for_role("fighter", engine, "enemy-1")
        assert ai is not None

        ai = get_ai_for_role("wizard", engine, "enemy-1")
        assert ai is not None

        ai = get_ai_for_role("rogue", engine, "enemy-1")
        assert ai is not None

    def test_get_ai_for_combatant_uses_explicit_role(self):
        """Should use explicit role from ai_behavior config."""
        engine = MagicMock()
        engine.state.combatant_stats = {
            "enemy-1": {
                "ai_behavior": {"role": "spellcaster"}
            }
        }
        engine.state.positions = {"enemy-1": (0, 0)}
        engine.state.initiative_tracker.get_combatant.return_value = MagicMock()

        ai = get_ai_for_combatant(engine, "enemy-1")
        assert ai is not None

    def test_get_ai_for_combatant_infers_from_class(self):
        """Should infer role from character class."""
        engine = MagicMock()
        engine.state.combatant_stats = {
            "enemy-1": {"class": "wizard"}
        }
        engine.state.positions = {"enemy-1": (0, 0)}
        engine.state.initiative_tracker.get_combatant.return_value = MagicMock()

        ai = get_ai_for_combatant(engine, "enemy-1")
        assert ai is not None

    def test_get_ai_for_combatant_infers_from_spellcasting(self):
        """Should use spellcaster AI if has spellcasting."""
        engine = MagicMock()
        engine.state.combatant_stats = {
            "enemy-1": {"spellcasting": {"slots": {1: 2}}}
        }
        engine.state.positions = {"enemy-1": (0, 0)}
        engine.state.initiative_tracker.get_combatant.return_value = MagicMock()

        ai = get_ai_for_combatant(engine, "enemy-1")
        assert ai is not None

    def test_get_ai_for_combatant_infers_from_ranged(self):
        """Should use ranged AI if has ranged weapon."""
        engine = MagicMock()
        engine.state.combatant_stats = {
            "enemy-1": {"equipment": {"ranged": {"name": "Longbow"}}}
        }
        engine.state.positions = {"enemy-1": (0, 0)}
        engine.state.initiative_tracker.get_combatant.return_value = MagicMock()

        ai = get_ai_for_combatant(engine, "enemy-1")
        assert ai is not None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_stats(self):
        """Should handle empty stats gracefully."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        combatant.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.combatant_stats = {"enemy-1": {}}
        engine.state.positions = {"enemy-1": (0, 0)}

        ai = TacticalAI(engine, "enemy-1")

        assert ai.stats == {}
        assert ai._get_weapon_reach() == 5  # Default
        assert ai._estimate_damage() == 3   # Default 1d6

    def test_missing_position_defaults_to_origin(self):
        """Should default to (0,0) if position missing."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        combatant.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.combatant_stats = {"enemy-1": {}}
        engine.state.positions = {}  # No position

        ai = TacticalAI(engine, "enemy-1")
        assert ai.position == (0, 0)

    def test_escape_position_clamps_to_grid(self):
        """Escape position should stay within grid bounds."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        combatant.is_active = True

        player = MagicMock()
        player.id = "player-1"
        player.is_active = True

        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.initiative_tracker.combatants = [combatant, player]
        engine.state.combatant_stats = {
            "enemy-1": {"speed": 30, "type": "enemy"},
            "player-1": {"type": "player"},
        }
        # Position at edge of grid
        engine.state.positions = {
            "enemy-1": (0, 0),
            "player-1": (1, 1),
        }
        engine.state.current_turn = MagicMock()
        engine.state.current_turn.movement_used = 0

        engine.grid_width = 10
        engine.grid_height = 10

        ai = TacticalAI(engine, "enemy-1")

        situation = {
            "my_position": (0, 0),
            "enemies": [{"id": "player-1", "position": (1, 1)}],
            "movement_remaining": 30,
        }

        escape = ai._find_escape_position(situation)

        # Should be clamped to grid
        assert escape[0] >= 0
        assert escape[1] >= 0
        assert escape[0] < 10
        assert escape[1] < 10

    def test_no_enemies_no_escape(self):
        """Should return None for escape with no enemies."""
        engine = MagicMock()
        combatant = MagicMock()
        combatant.id = "enemy-1"
        engine.state.initiative_tracker.get_combatant.return_value = combatant
        engine.state.combatant_stats = {"enemy-1": {}}
        engine.state.positions = {"enemy-1": (5, 5)}

        ai = TacticalAI(engine, "enemy-1")

        situation = {
            "my_position": (5, 5),
            "enemies": [],
            "movement_remaining": 30,
        }

        escape = ai._find_escape_position(situation)
        assert escape is None
