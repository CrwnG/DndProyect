"""
Tests for Monster Ability System.

Tests:
- Ability parsing from JSON descriptions
- Breath weapon execution
- Multiattack patterns
- Recharge mechanics
- Frightful Presence
- Mind Blast
- Legendary actions
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.monster_abilities import (
    MonsterAbility,
    AbilityType,
    AreaShape,
    parse_monster_action,
    parse_legendary_action,
    roll_recharge,
    execute_breath_weapon,
    execute_frightful_presence,
    execute_mind_blast,
    get_monster_abilities,
    get_breath_weapons,
    get_melee_attacks,
    get_multiattack,
)


class TestAbilityParsing:
    """Test parsing monster actions from JSON descriptions."""

    def test_parse_melee_attack(self):
        """Parse a basic melee attack."""
        action = {
            "name": "Bite",
            "description": "Melee Weapon Attack: +11 to hit, reach 10 ft., one target. Hit: 17 (2d10+6) piercing damage plus 4 (1d8) acid damage."
        }
        ability = parse_monster_action(action, "adult_black_dragon")

        assert ability.ability_type == AbilityType.MELEE_ATTACK
        assert ability.attack_bonus == 11
        assert ability.reach == 10
        assert ability.damage_dice == "2d10+6"
        assert ability.damage_type == "piercing"
        assert ability.extra_damage_dice == "1d8"
        assert ability.extra_damage_type == "acid"

    def test_parse_breath_weapon_line(self):
        """Parse a line-shaped breath weapon."""
        action = {
            "name": "Acid Breath (Recharge 5-6)",
            "description": "The dragon exhales acid in a 60-foot line that is 5 feet wide. Each creature in that line must make a DC 18 Dexterity saving throw, taking 54 (12d8) acid damage on a failed save, or half as much damage on a successful one."
        }
        ability = parse_monster_action(action, "adult_black_dragon")

        assert ability.ability_type == AbilityType.BREATH_WEAPON
        assert ability.area_shape == AreaShape.LINE
        assert ability.area_size == 60
        assert ability.area_width == 5
        assert ability.save_dc == 18
        assert ability.save_type == "dex"
        assert ability.damage_dice == "12d8"
        assert ability.damage_type == "acid"
        assert ability.half_on_save is True
        assert ability.recharge_type == "5-6"
        assert ability.recharge_min == 5

    def test_parse_breath_weapon_cone(self):
        """Parse a cone-shaped breath weapon."""
        action = {
            "name": "Fire Breath (Recharge 5-6)",
            "description": "The dragon exhales fire in a 90-foot cone. Each creature in that area must make a DC 24 Dexterity saving throw, taking 91 (26d6) fire damage on a failed save, or half as much damage on a successful one."
        }
        ability = parse_monster_action(action, "ancient_red_dragon")

        assert ability.ability_type == AbilityType.BREATH_WEAPON
        assert ability.area_shape == AreaShape.CONE
        assert ability.area_size == 90
        assert ability.save_dc == 24
        assert ability.save_type == "dex"
        assert ability.damage_dice == "26d6"
        assert ability.damage_type == "fire"

    def test_parse_multiattack(self):
        """Parse a multiattack action."""
        action = {
            "name": "Multiattack",
            "description": "The dragon can use its Frightful Presence. It then makes three attacks: one with its bite and two with its claws."
        }
        ability = parse_monster_action(action, "adult_black_dragon")

        assert ability.ability_type == AbilityType.MULTIATTACK
        assert ability.includes_frightful_presence is True
        assert ability.multiattack_pattern == ["bite", "claw", "claw"]

    def test_parse_multiattack_simple(self):
        """Parse a simple multiattack without frightful presence."""
        action = {
            "name": "Multiattack",
            "description": "The dragon makes three attacks: one with its bite and two with its claws."
        }
        ability = parse_monster_action(action, "young_dragon")

        assert ability.ability_type == AbilityType.MULTIATTACK
        assert ability.includes_frightful_presence is False
        assert ability.multiattack_pattern == ["bite", "claw", "claw"]

    def test_parse_frightful_presence(self):
        """Parse Frightful Presence."""
        action = {
            "name": "Frightful Presence",
            "description": "Each creature of the dragon's choice that is within 120 feet of the dragon and aware of it must succeed on a DC 16 Wisdom saving throw or become frightened for 1 minute."
        }
        ability = parse_monster_action(action, "adult_black_dragon")

        assert ability.ability_type == AbilityType.FRIGHTFUL_PRESENCE
        assert ability.area_shape == AreaShape.SPHERE
        assert ability.area_size == 120
        assert ability.save_dc == 16
        assert ability.save_type == "wis"
        assert "frightened" in ability.conditions

    def test_parse_mind_blast(self):
        """Parse Mind Blast (Mind Flayer)."""
        action = {
            "name": "Mind Blast (Recharge 5-6)",
            "description": "The mind flayer magically emits psychic energy in a 60-foot cone. Each creature in that area must succeed on a DC 15 Intelligence saving throw or take 22 (4d8+4) psychic damage and be stunned for 1 minute."
        }
        ability = parse_monster_action(action, "mind_flayer")

        assert ability.ability_type == AbilityType.MIND_BLAST
        assert ability.area_shape == AreaShape.CONE
        assert ability.area_size == 60
        assert ability.save_dc == 15
        assert ability.save_type == "int"
        assert ability.damage_dice == "4d8+4"
        assert "stunned" in ability.conditions

    def test_parse_recharge_5_6(self):
        """Parse recharge 5-6 mechanic."""
        action = {
            "name": "Acid Breath (Recharge 5-6)",
            "description": "The dragon exhales acid..."
        }
        ability = parse_monster_action(action, "dragon")

        assert ability.recharge_type == "5-6"
        assert ability.recharge_min == 5

    def test_parse_recharge_6(self):
        """Parse recharge 6 mechanic."""
        action = {
            "name": "Lightning Breath (Recharge 6)",
            "description": "The dragon exhales lightning..."
        }
        ability = parse_monster_action(action, "dragon")

        assert ability.recharge_type == "6"
        assert ability.recharge_min == 6


class TestLegendaryActionParsing:
    """Test parsing legendary actions."""

    def test_parse_legendary_action_standard(self):
        """Parse a standard legendary action (1 cost)."""
        action = {
            "name": "Detect",
            "description": "The dragon makes a Wisdom (Perception) check."
        }
        ability = parse_legendary_action(action, "adult_dragon")

        assert ability.ability_type == AbilityType.LEGENDARY_ACTION
        assert ability.legendary_cost == 1

    def test_parse_legendary_action_cost_2(self):
        """Parse a legendary action costing 2 actions."""
        action = {
            "name": "Wing Attack (Costs 2 Actions)",
            "description": "The dragon beats its wings. Each creature within 10 feet must succeed on a DC 19 Dexterity saving throw or take 13 (2d6+6) bludgeoning damage and be knocked prone."
        }
        ability = parse_legendary_action(action, "adult_dragon")

        assert ability.ability_type == AbilityType.LEGENDARY_ACTION
        assert ability.legendary_cost == 2


class TestRecharge:
    """Test recharge mechanics."""

    def test_roll_recharge_succeeds_on_5(self):
        """Recharge should succeed on roll of 5 or higher for 5-6 abilities."""
        ability = MonsterAbility(
            id="test",
            name="Test Breath",
            original_description="",
            ability_type=AbilityType.BREATH_WEAPON,
            recharge_min=5
        )

        # Mock random to return specific values
        with patch('app.core.monster_abilities.random.randint') as mock_roll:
            mock_roll.return_value = 5
            assert roll_recharge(ability) is True

            mock_roll.return_value = 6
            assert roll_recharge(ability) is True

            mock_roll.return_value = 4
            assert roll_recharge(ability) is False

    def test_roll_recharge_no_recharge_needed(self):
        """Abilities without recharge always return True."""
        ability = MonsterAbility(
            id="test",
            name="Bite",
            original_description="",
            ability_type=AbilityType.MELEE_ATTACK,
            recharge_min=None
        )

        assert roll_recharge(ability) is True


class TestBreathWeaponExecution:
    """Test breath weapon execution."""

    @patch('app.core.monster_abilities.roll_damage')
    @patch('app.core.monster_abilities.roll_d20')
    def test_breath_weapon_full_damage(self, mock_d20, mock_damage):
        """Target fails save, takes full damage."""
        mock_damage.return_value = MagicMock(total=50)  # 12d8 damage
        mock_d20.return_value = MagicMock(total=8)  # Failed save

        ability = MonsterAbility(
            id="test_breath",
            name="Acid Breath",
            original_description="",
            ability_type=AbilityType.BREATH_WEAPON,
            save_dc=18,
            save_type="dex",
            damage_dice="12d8",
            damage_type="acid",
            half_on_save=True
        )

        targets = [{"id": "player1", "save_mod": 2}]
        result = execute_breath_weapon(ability, targets, "dragon")

        assert result.success is True
        assert "player1" in result.targets_hit
        assert result.damage_dealt["player1"] == 50

    @patch('app.core.monster_abilities.roll_damage')
    @patch('app.core.monster_abilities.roll_d20')
    def test_breath_weapon_half_damage_on_save(self, mock_d20, mock_damage):
        """Target succeeds save, takes half damage."""
        mock_damage.return_value = MagicMock(total=50)
        mock_d20.return_value = MagicMock(total=20)  # Passed save

        ability = MonsterAbility(
            id="test_breath",
            name="Acid Breath",
            original_description="",
            ability_type=AbilityType.BREATH_WEAPON,
            save_dc=18,
            save_type="dex",
            damage_dice="12d8",
            damage_type="acid",
            half_on_save=True
        )

        targets = [{"id": "player1", "save_mod": 2}]
        result = execute_breath_weapon(ability, targets, "dragon")

        assert "player1" in result.targets_saved
        assert result.damage_dealt["player1"] == 25  # Half damage

    @patch('app.core.monster_abilities.roll_damage')
    @patch('app.core.monster_abilities.roll_d20')
    def test_breath_weapon_multiple_targets(self, mock_d20, mock_damage):
        """Breath weapon hits multiple targets."""
        mock_damage.return_value = MagicMock(total=40)

        # First target fails, second saves
        mock_d20.side_effect = [
            MagicMock(total=5),   # player1 fails
            MagicMock(total=20),  # player2 saves
        ]

        ability = MonsterAbility(
            id="test_breath",
            name="Fire Breath",
            original_description="",
            ability_type=AbilityType.BREATH_WEAPON,
            save_dc=15,
            save_type="dex",
            damage_dice="10d6",
            half_on_save=True
        )

        targets = [
            {"id": "player1", "save_mod": 0},
            {"id": "player2", "save_mod": 5}
        ]
        result = execute_breath_weapon(ability, targets, "dragon")

        assert "player1" in result.targets_hit
        assert "player2" in result.targets_saved
        assert result.damage_dealt["player1"] == 40
        assert result.damage_dealt["player2"] == 20


class TestFrightfulPresenceExecution:
    """Test Frightful Presence execution."""

    @patch('app.core.monster_abilities.roll_d20')
    def test_frightful_presence_frightens_on_fail(self, mock_d20):
        """Target fails save, becomes frightened."""
        mock_d20.return_value = MagicMock(total=10)

        ability = MonsterAbility(
            id="test_fp",
            name="Frightful Presence",
            original_description="",
            ability_type=AbilityType.FRIGHTFUL_PRESENCE,
            save_dc=16,
            save_type="wis",
            conditions=["frightened"]
        )

        targets = [{"id": "player1", "save_mod": 2}]
        result = execute_frightful_presence(ability, targets, "dragon")

        assert "player1" in result.targets_hit
        assert "frightened" in result.conditions_applied.get("player1", [])

    @patch('app.core.monster_abilities.roll_d20')
    def test_frightful_presence_immune_targets_skipped(self, mock_d20):
        """Immune targets are not affected."""
        mock_d20.return_value = MagicMock(total=10)

        ability = MonsterAbility(
            id="test_fp",
            name="Frightful Presence",
            original_description="",
            ability_type=AbilityType.FRIGHTFUL_PRESENCE,
            save_dc=16,
            save_type="wis",
            conditions=["frightened"]
        )

        targets = [
            {"id": "player1", "save_mod": 2},
            {"id": "player2", "save_mod": 0}
        ]
        immune = ["player1"]

        result = execute_frightful_presence(ability, targets, "dragon", immune)

        assert "player1" in result.targets_saved  # Immune, auto-saved
        assert "player2" in result.targets_hit  # Not immune, failed


class TestMindBlastExecution:
    """Test Mind Blast execution."""

    @patch('app.core.monster_abilities.roll_damage')
    @patch('app.core.monster_abilities.roll_d20')
    def test_mind_blast_damage_and_stun(self, mock_d20, mock_damage):
        """Mind Blast deals damage and stuns on failed save."""
        mock_damage.return_value = MagicMock(total=22)
        mock_d20.return_value = MagicMock(total=8)  # Failed save

        ability = MonsterAbility(
            id="test_mb",
            name="Mind Blast",
            original_description="",
            ability_type=AbilityType.MIND_BLAST,
            save_dc=15,
            save_type="int",
            damage_dice="4d8+4",
            damage_type="psychic",
            conditions=["stunned"]
        )

        targets = [{"id": "player1", "save_mod": -1}]
        result = execute_mind_blast(ability, targets, "mind_flayer")

        assert result.success is True
        assert "player1" in result.targets_hit
        assert result.damage_dealt["player1"] == 22
        assert "stunned" in result.conditions_applied.get("player1", [])

    @patch('app.core.monster_abilities.roll_damage')
    @patch('app.core.monster_abilities.roll_d20')
    def test_mind_blast_half_damage_no_stun_on_save(self, mock_d20, mock_damage):
        """Mind Blast deals half damage and no stun on successful save."""
        mock_damage.return_value = MagicMock(total=22)
        mock_d20.return_value = MagicMock(total=18)  # Passed save

        ability = MonsterAbility(
            id="test_mb",
            name="Mind Blast",
            original_description="",
            ability_type=AbilityType.MIND_BLAST,
            save_dc=15,
            save_type="int",
            damage_dice="4d8+4",
            conditions=["stunned"]
        )

        targets = [{"id": "player1", "save_mod": 3}]
        result = execute_mind_blast(ability, targets, "mind_flayer")

        assert "player1" in result.targets_saved
        assert result.damage_dealt["player1"] == 11  # Half damage
        assert "player1" not in result.conditions_applied


class TestGetMonsterAbilities:
    """Test getting all abilities from monster stats."""

    def test_get_monster_abilities_from_stats(self):
        """Parse all abilities from a monster stat block."""
        monster_stats = {
            "id": "adult_black_dragon",
            "actions": [
                {
                    "name": "Multiattack",
                    "description": "The dragon makes three attacks: one with its bite and two with its claws."
                },
                {
                    "name": "Bite",
                    "description": "Melee Weapon Attack: +11 to hit, reach 10 ft., one target. Hit: 17 (2d10+6) piercing damage."
                },
                {
                    "name": "Acid Breath (Recharge 5-6)",
                    "description": "The dragon exhales acid in a 60-foot line. DC 18 Dexterity saving throw, taking 54 (12d8) acid damage."
                }
            ],
            "legendary_actions": [
                {
                    "name": "Detect",
                    "description": "The dragon makes a Perception check."
                }
            ]
        }

        abilities = get_monster_abilities(monster_stats)

        assert len(abilities) == 4  # 3 actions + 1 legendary
        assert any(a.ability_type == AbilityType.MULTIATTACK for a in abilities)
        assert any(a.ability_type == AbilityType.MELEE_ATTACK for a in abilities)
        assert any(a.ability_type == AbilityType.BREATH_WEAPON for a in abilities)
        assert any(a.ability_type == AbilityType.LEGENDARY_ACTION for a in abilities)

    def test_get_breath_weapons(self):
        """Filter to only breath weapons."""
        abilities = [
            MonsterAbility("bite", "Bite", "", AbilityType.MELEE_ATTACK),
            MonsterAbility("breath", "Acid Breath", "", AbilityType.BREATH_WEAPON),
            MonsterAbility("claw", "Claw", "", AbilityType.MELEE_ATTACK),
        ]

        breath_weapons = get_breath_weapons(abilities)
        assert len(breath_weapons) == 1
        assert breath_weapons[0].name == "Acid Breath"

    def test_get_melee_attacks(self):
        """Filter to only melee attacks."""
        abilities = [
            MonsterAbility("bite", "Bite", "", AbilityType.MELEE_ATTACK),
            MonsterAbility("breath", "Acid Breath", "", AbilityType.BREATH_WEAPON),
            MonsterAbility("claw", "Claw", "", AbilityType.MELEE_ATTACK),
        ]

        melee = get_melee_attacks(abilities)
        assert len(melee) == 2

    def test_get_multiattack(self):
        """Get the multiattack ability."""
        abilities = [
            MonsterAbility("multi", "Multiattack", "", AbilityType.MULTIATTACK),
            MonsterAbility("bite", "Bite", "", AbilityType.MELEE_ATTACK),
        ]

        multi = get_multiattack(abilities)
        assert multi is not None
        assert multi.name == "Multiattack"


class TestMonsterAbilityDataclass:
    """Test MonsterAbility dataclass."""

    def test_is_available_no_recharge(self):
        """Abilities without recharge are always available."""
        ability = MonsterAbility(
            id="bite",
            name="Bite",
            original_description="",
            ability_type=AbilityType.MELEE_ATTACK
        )

        assert ability.is_available({}) is True
        assert ability.is_available({"bite": False}) is True

    def test_is_available_with_recharge(self):
        """Abilities with recharge check the state."""
        ability = MonsterAbility(
            id="breath",
            name="Breath",
            original_description="",
            ability_type=AbilityType.BREATH_WEAPON,
            recharge_type="5-6"
        )

        assert ability.is_available({}) is True
        assert ability.is_available({"breath": True}) is True
        assert ability.is_available({"breath": False}) is False

    def test_to_dict(self):
        """Convert ability to dictionary."""
        ability = MonsterAbility(
            id="acid_breath",
            name="Acid Breath",
            original_description="...",
            ability_type=AbilityType.BREATH_WEAPON,
            damage_dice="12d8",
            damage_type="acid",
            save_dc=18,
            save_type="dex",
            area_shape=AreaShape.LINE,
            area_size=60,
            recharge_type="5-6",
            conditions=[]
        )

        d = ability.to_dict()
        assert d["id"] == "acid_breath"
        assert d["name"] == "Acid Breath"
        assert d["ability_type"] == "breath_weapon"
        assert d["damage_dice"] == "12d8"
        assert d["save_dc"] == 18
        assert d["area_shape"] == "line"
