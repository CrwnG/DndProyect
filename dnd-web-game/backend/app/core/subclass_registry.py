"""
Subclass Registry System.

Provides executable combat features for all class subclasses.
Loads subclass data from JSON and provides implementations for:
- Champion: Improved/Superior Critical
- Battle Master: Maneuvers with Superiority Dice
- Psi Warrior: Psionic Energy dice
- And all other subclasses
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
import json
from pathlib import Path

from app.core.dice import roll_damage, roll_d20


class SubclassResourceType(Enum):
    """Types of subclass-specific resources."""
    NONE = "none"
    SUPERIORITY_DICE = "superiority_dice"
    PSIONIC_DICE = "psionic_dice"
    KI_POINTS = "ki_points"
    SORCERY_POINTS = "sorcery_points"
    CHANNEL_DIVINITY = "channel_divinity"
    BARDIC_INSPIRATION = "bardic_inspiration"
    RAGE = "rage"
    WILD_SHAPE = "wild_shape"


@dataclass
class SubclassResource:
    """Tracks a subclass-specific resource pool."""
    resource_type: SubclassResourceType
    max_uses: int
    current_uses: int
    dice_size: int = 8  # d8, d10, d12
    recharge: str = "short_rest"  # "short_rest", "long_rest"

    def use(self, count: int = 1) -> bool:
        """Use resources. Returns True if successful."""
        if self.current_uses >= count:
            self.current_uses -= count
            return True
        return False

    def regain(self, count: int = 1) -> None:
        """Regain resources up to max."""
        self.current_uses = min(self.max_uses, self.current_uses + count)

    def reset(self) -> None:
        """Reset to full."""
        self.current_uses = self.max_uses

    def roll(self) -> int:
        """Roll a resource die."""
        from random import randint
        return randint(1, self.dice_size)


@dataclass
class SubclassFeatureResult:
    """Result of using a subclass feature."""
    success: bool
    description: str
    damage: int = 0
    healing: int = 0
    bonus: int = 0
    condition_applied: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# FIGHTER SUBCLASS IMPLEMENTATIONS
# =============================================================================

def get_critical_range(subclass_id: str, level: int) -> int:
    """Get the minimum roll needed for a critical hit."""
    if subclass_id == "champion":
        if level >= 15:
            return 18  # Superior Critical
        elif level >= 3:
            return 19  # Improved Critical
    return 20  # Default


def get_superiority_dice_info(level: int) -> Tuple[int, int]:
    """Get number and size of superiority dice for Battle Master."""
    # Number of dice
    if level >= 15:
        dice_count = 6
    elif level >= 7:
        dice_count = 5
    else:
        dice_count = 4

    # Dice size
    if level >= 18:
        dice_size = 12
    elif level >= 10:
        dice_size = 10
    else:
        dice_size = 8

    return dice_count, dice_size


def execute_maneuver(
    maneuver_id: str,
    resource: SubclassResource,
    attacker_stats: Dict[str, Any],
    target_stats: Optional[Dict[str, Any]] = None,
    attack_roll: int = 0,
    damage_roll: int = 0
) -> SubclassFeatureResult:
    """Execute a Battle Master maneuver."""
    if not resource.use(1):
        return SubclassFeatureResult(
            success=False,
            description="No superiority dice remaining"
        )

    die_roll = resource.roll()
    str_mod = (attacker_stats.get("ability_scores", {}).get("STR", 10) - 10) // 2
    dex_mod = (attacker_stats.get("ability_scores", {}).get("DEX", 10) - 10) // 2
    int_mod = (attacker_stats.get("ability_scores", {}).get("INT", 10) - 10) // 2
    prof_bonus = attacker_stats.get("proficiency_bonus", 2)
    save_dc = 8 + prof_bonus + max(str_mod, dex_mod)

    # Maneuver implementations
    if maneuver_id == "precision_attack":
        return SubclassFeatureResult(
            success=True,
            description=f"Precision Attack adds {die_roll} to attack roll",
            bonus=die_roll,
            extra_data={"type": "attack_bonus", "value": die_roll}
        )

    elif maneuver_id == "trip_attack":
        # Add damage and force save
        if target_stats:
            target_str = (target_stats.get("ability_scores", {}).get("STR", 10) - 10) // 2
            save_roll = roll_d20(modifier=target_str).total
            tripped = save_roll < save_dc
            return SubclassFeatureResult(
                success=True,
                description=f"Trip Attack deals +{die_roll} damage" + (", target falls prone!" if tripped else ", target resists!"),
                damage=die_roll,
                condition_applied="prone" if tripped else None,
                extra_data={"save_dc": save_dc, "save_roll": save_roll}
            )
        return SubclassFeatureResult(
            success=True,
            description=f"Trip Attack deals +{die_roll} damage",
            damage=die_roll
        )

    elif maneuver_id == "menacing_attack":
        if target_stats:
            target_wis = (target_stats.get("ability_scores", {}).get("WIS", 10) - 10) // 2
            save_roll = roll_d20(modifier=target_wis).total
            frightened = save_roll < save_dc
            return SubclassFeatureResult(
                success=True,
                description=f"Menacing Attack deals +{die_roll} damage" + (", target is frightened!" if frightened else ""),
                damage=die_roll,
                condition_applied="frightened" if frightened else None
            )
        return SubclassFeatureResult(
            success=True,
            description=f"Menacing Attack deals +{die_roll} damage",
            damage=die_roll
        )

    elif maneuver_id == "riposte":
        return SubclassFeatureResult(
            success=True,
            description=f"Riposte! Attack deals +{die_roll} bonus damage",
            damage=die_roll,
            extra_data={"type": "reaction_attack"}
        )

    elif maneuver_id == "parry":
        reduction = die_roll + max(str_mod, dex_mod)
        return SubclassFeatureResult(
            success=True,
            description=f"Parry reduces damage by {reduction}",
            extra_data={"type": "damage_reduction", "value": reduction}
        )

    elif maneuver_id == "disarming_attack":
        if target_stats:
            target_str = (target_stats.get("ability_scores", {}).get("STR", 10) - 10) // 2
            save_roll = roll_d20(modifier=target_str).total
            disarmed = save_roll < save_dc
            return SubclassFeatureResult(
                success=True,
                description=f"Disarming Attack deals +{die_roll} damage" + (", target drops weapon!" if disarmed else ""),
                damage=die_roll,
                extra_data={"disarmed": disarmed}
            )
        return SubclassFeatureResult(
            success=True,
            description=f"Disarming Attack deals +{die_roll} damage",
            damage=die_roll
        )

    elif maneuver_id == "pushing_attack":
        if target_stats:
            target_str = (target_stats.get("ability_scores", {}).get("STR", 10) - 10) // 2
            save_roll = roll_d20(modifier=target_str).total
            pushed = save_roll < save_dc
            return SubclassFeatureResult(
                success=True,
                description=f"Pushing Attack deals +{die_roll} damage" + (", target pushed 15 feet!" if pushed else ""),
                damage=die_roll,
                extra_data={"pushed": pushed, "distance": 15 if pushed else 0}
            )
        return SubclassFeatureResult(
            success=True,
            description=f"Pushing Attack deals +{die_roll} damage",
            damage=die_roll
        )

    elif maneuver_id == "goading_attack":
        if target_stats:
            target_wis = (target_stats.get("ability_scores", {}).get("WIS", 10) - 10) // 2
            save_roll = roll_d20(modifier=target_wis).total
            goaded = save_roll < save_dc
            return SubclassFeatureResult(
                success=True,
                description=f"Goading Attack deals +{die_roll} damage" + (", target has disadvantage vs others!" if goaded else ""),
                damage=die_roll,
                extra_data={"goaded": goaded}
            )
        return SubclassFeatureResult(
            success=True,
            description=f"Goading Attack deals +{die_roll} damage",
            damage=die_roll
        )

    elif maneuver_id == "feinting_attack":
        return SubclassFeatureResult(
            success=True,
            description=f"Feinting Attack grants advantage and +{die_roll} damage on hit",
            damage=die_roll,
            extra_data={"type": "advantage_attack"}
        )

    elif maneuver_id == "distracting_strike":
        return SubclassFeatureResult(
            success=True,
            description=f"Distracting Strike deals +{die_roll} damage, next ally has advantage",
            damage=die_roll,
            extra_data={"type": "ally_advantage"}
        )

    elif maneuver_id == "rally":
        temp_hp = die_roll + max(int_mod, (attacker_stats.get("ability_scores", {}).get("WIS", 10) - 10) // 2)
        return SubclassFeatureResult(
            success=True,
            description=f"Rally grants {temp_hp} temporary HP to ally",
            healing=temp_hp,
            extra_data={"type": "temp_hp"}
        )

    # Default for other maneuvers - just add the die to damage
    return SubclassFeatureResult(
        success=True,
        description=f"Maneuver adds +{die_roll} damage",
        damage=die_roll
    )


# =============================================================================
# PSI WARRIOR IMPLEMENTATIONS
# =============================================================================

def get_psionic_dice_info(level: int) -> Tuple[int, int]:
    """Get number and size of psionic energy dice."""
    prof_bonus = (level - 1) // 4 + 2
    dice_count = prof_bonus * 2

    # Dice size by level
    if level >= 17:
        dice_size = 12
    elif level >= 11:
        dice_size = 10
    elif level >= 5:
        dice_size = 8
    else:
        dice_size = 6

    return dice_count, dice_size


def execute_psionic_power(
    power_id: str,
    resource: SubclassResource,
    attacker_stats: Dict[str, Any],
    target_stats: Optional[Dict[str, Any]] = None
) -> SubclassFeatureResult:
    """Execute a Psi Warrior psionic power."""
    int_mod = (attacker_stats.get("ability_scores", {}).get("INT", 10) - 10) // 2
    prof_bonus = attacker_stats.get("proficiency_bonus", 2)
    save_dc = 8 + prof_bonus + int_mod

    if power_id == "psionic_strike":
        if not resource.use(1):
            return SubclassFeatureResult(
                success=False,
                description="No psionic energy dice remaining"
            )
        die_roll = resource.roll()
        total_damage = die_roll + int_mod
        return SubclassFeatureResult(
            success=True,
            description=f"Psionic Strike deals {total_damage} force damage",
            damage=total_damage,
            extra_data={"damage_type": "force"}
        )

    elif power_id == "protective_field":
        if not resource.use(1):
            return SubclassFeatureResult(
                success=False,
                description="No psionic energy dice remaining"
            )
        die_roll = resource.roll()
        reduction = die_roll + int_mod
        return SubclassFeatureResult(
            success=True,
            description=f"Protective Field reduces damage by {reduction}",
            extra_data={"type": "damage_reduction", "value": reduction}
        )

    elif power_id == "telekinetic_thrust":
        if target_stats:
            target_str = (target_stats.get("ability_scores", {}).get("STR", 10) - 10) // 2
            save_roll = roll_d20(modifier=target_str).total
            affected = save_roll < save_dc
            return SubclassFeatureResult(
                success=True,
                description="Telekinetic Thrust" + (" knocks target prone or pushes 10 feet!" if affected else " - target resists!"),
                condition_applied="prone" if affected else None,
                extra_data={"pushed": affected, "distance": 10 if affected else 0}
            )

    return SubclassFeatureResult(
        success=False,
        description=f"Unknown psionic power: {power_id}"
    )


# =============================================================================
# ROGUE SUBCLASS IMPLEMENTATIONS
# =============================================================================

def assassinate_bonus(target_surprised: bool, attacker_first: bool) -> Dict[str, Any]:
    """Calculate Assassin's Assassinate feature bonus."""
    result = {
        "advantage": False,
        "auto_crit": False,
        "description": ""
    }

    if target_surprised:
        result["advantage"] = True
        result["auto_crit"] = True
        result["description"] = "Assassinate! Auto-critical against surprised target!"
    elif attacker_first:
        result["advantage"] = True
        result["description"] = "Assassinate grants advantage (you acted before target)"

    return result


# =============================================================================
# SUBCLASS REGISTRY
# =============================================================================

class SubclassRegistry:
    """Registry for subclass data and feature implementations."""

    _instance = None
    _data: Dict[str, Dict[str, Any]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_subclasses()
        return cls._instance

    def _load_subclasses(self) -> None:
        """Load all subclass data from class JSON files."""
        data_path = Path(__file__).parent.parent / "data" / "rules" / "2024" / "classes"

        for class_file in data_path.glob("*.json"):
            try:
                with open(class_file, encoding="utf-8") as f:
                    class_data = json.load(f)
                    class_id = class_data.get("id")
                    if class_id and "subclasses" in class_data:
                        self._data[class_id] = {}
                        for subclass in class_data["subclasses"]:
                            subclass_id = subclass.get("id")
                            if subclass_id:
                                self._data[class_id][subclass_id] = subclass
            except (json.JSONDecodeError, IOError):
                continue

    def get_subclass(self, class_id: str, subclass_id: str) -> Optional[Dict[str, Any]]:
        """Get subclass data by class and subclass ID."""
        return self._data.get(class_id, {}).get(subclass_id)

    def get_subclasses_for_class(self, class_id: str) -> List[Dict[str, Any]]:
        """Get all subclasses for a class."""
        return list(self._data.get(class_id, {}).values())

    def get_subclass_features(
        self,
        class_id: str,
        subclass_id: str,
        level: int
    ) -> List[Dict[str, Any]]:
        """Get all subclass features available at given level."""
        subclass = self.get_subclass(class_id, subclass_id)
        if not subclass:
            return []

        features = []
        for feature in subclass.get("features", []):
            if feature.get("level", 1) <= level:
                features.append(feature)

        return features

    def create_resource_pool(
        self,
        class_id: str,
        subclass_id: str,
        level: int
    ) -> Optional[SubclassResource]:
        """Create appropriate resource pool for subclass."""
        if class_id == "fighter":
            if subclass_id == "battle_master":
                dice_count, dice_size = get_superiority_dice_info(level)
                return SubclassResource(
                    resource_type=SubclassResourceType.SUPERIORITY_DICE,
                    max_uses=dice_count,
                    current_uses=dice_count,
                    dice_size=dice_size,
                    recharge="short_rest"
                )
            elif subclass_id == "psi_warrior":
                dice_count, dice_size = get_psionic_dice_info(level)
                return SubclassResource(
                    resource_type=SubclassResourceType.PSIONIC_DICE,
                    max_uses=dice_count,
                    current_uses=dice_count,
                    dice_size=dice_size,
                    recharge="short_rest"
                )

        return None

    def has_feature(
        self,
        class_id: str,
        subclass_id: str,
        feature_id: str,
        level: int
    ) -> bool:
        """Check if subclass has a specific feature at given level."""
        features = self.get_subclass_features(class_id, subclass_id, level)
        return any(f.get("id") == feature_id for f in features)


def get_subclass_registry() -> SubclassRegistry:
    """Get the singleton subclass registry."""
    return SubclassRegistry()


# =============================================================================
# COMBAT INTEGRATION HELPERS
# =============================================================================

def get_combat_modifiers(
    class_id: str,
    subclass_id: str,
    level: int,
    context: str = "attack"
) -> Dict[str, Any]:
    """Get combat modifiers based on subclass features."""
    modifiers = {}

    if class_id == "fighter":
        if subclass_id == "champion":
            modifiers["crit_range"] = get_critical_range(subclass_id, level)
            if level >= 10:
                modifiers["heroic_inspiration_on_turn_start"] = True
            if level >= 18:
                modifiers["survivor_healing"] = True

    elif class_id == "rogue":
        if subclass_id == "assassin":
            modifiers["assassinate"] = level >= 3
        elif subclass_id == "thief" and level >= 3:
            modifiers["fast_hands"] = True

    return modifiers


def process_subclass_attack_modifiers(
    class_id: str,
    subclass_id: str,
    level: int,
    attack_roll: int,
    is_critical: bool
) -> Tuple[int, bool]:
    """Process attack modifiers from subclass features."""
    modified_roll = attack_roll
    modified_crit = is_critical

    # Champion: Expanded crit range
    if class_id == "fighter" and subclass_id == "champion":
        crit_range = get_critical_range(subclass_id, level)
        if attack_roll >= crit_range:
            modified_crit = True

    return modified_roll, modified_crit
