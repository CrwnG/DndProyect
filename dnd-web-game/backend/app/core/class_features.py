"""
Class Features System.

Handles class features for Fighter, Rogue, Wizard, and Cleric.
Supports both 2014 (5e Classic) and 2024 rules with proper toggling.

Each class has:
- Core features (always available)
- 2024 enhanced features (toggleable)
- Level progression
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

from app.core.dice import roll_damage, roll_d20
from app.core.rules_config import is_2024_class_features_enabled, is_weapon_mastery_enabled


class FeatureType(Enum):
    """Types of class features."""
    PASSIVE = "passive"  # Always active
    ACTION = "action"  # Uses an action
    BONUS_ACTION = "bonus_action"  # Uses a bonus action
    REACTION = "reaction"  # Uses a reaction
    FREE = "free"  # No action required
    SPECIAL = "special"  # Special timing


class ResourceType(Enum):
    """Types of resources features can use."""
    NONE = "none"
    PER_SHORT_REST = "per_short_rest"
    PER_LONG_REST = "per_long_rest"
    PER_TURN = "per_turn"
    SPELL_SLOTS = "spell_slots"
    PROFICIENCY_PER_LONG_REST = "proficiency_per_long_rest"  # Uses = prof bonus


@dataclass
class ClassFeature:
    """Definition of a class feature."""
    id: str
    name: str
    description: str
    feature_type: FeatureType
    resource_type: ResourceType = ResourceType.NONE
    uses_per_rest: int = 0  # 0 = unlimited or based on resource_type
    min_level: int = 1
    is_2024_feature: bool = False  # True if this is a 2024-only feature
    replaces_feature: Optional[str] = None  # ID of feature this replaces in 2024

    def is_available(self, level: int) -> bool:
        """Check if feature is available at given level."""
        if level < self.min_level:
            return False
        if self.is_2024_feature and not is_2024_class_features_enabled():
            return False
        return True


@dataclass
class FeatureUseResult:
    """Result of using a class feature."""
    success: bool
    description: str
    value: int = 0  # Healing, damage, bonus, etc.
    extra_data: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# FIGHTER FEATURES
# =============================================================================

FIGHTER_FEATURES: List[ClassFeature] = [
    # 2014 Core Features
    ClassFeature(
        id="fighting_style",
        name="Fighting Style",
        description="You adopt a particular style of fighting as your specialty.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="second_wind",
        name="Second Wind",
        description="On your turn, you can use a bonus action to regain hit points equal to 1d10 + your fighter level.",
        feature_type=FeatureType.BONUS_ACTION,
        resource_type=ResourceType.PER_SHORT_REST,
        uses_per_rest=1,
        min_level=1,
    ),
    ClassFeature(
        id="action_surge",
        name="Action Surge",
        description="On your turn, you can take one additional action.",
        feature_type=FeatureType.FREE,
        resource_type=ResourceType.PER_SHORT_REST,
        uses_per_rest=1,
        min_level=2,
    ),
    ClassFeature(
        id="extra_attack",
        name="Extra Attack",
        description="You can attack twice when you take the Attack action on your turn.",
        feature_type=FeatureType.PASSIVE,
        min_level=5,
    ),
    ClassFeature(
        id="indomitable",
        name="Indomitable",
        description="You can reroll a saving throw that you fail. You must use the new roll.",
        feature_type=FeatureType.SPECIAL,
        resource_type=ResourceType.PER_LONG_REST,
        uses_per_rest=1,
        min_level=9,
    ),

    # 2024 Enhanced Features
    ClassFeature(
        id="weapon_mastery_fighter",
        name="Weapon Mastery",
        description="You gain Weapon Mastery for 3 weapons of your choice (4 at level 4, 5 at level 10, 6 at level 16).",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="tactical_mind",
        name="Tactical Mind",
        description="When you fail an ability check, you can add a d10 to the roll, potentially turning failure into success.",
        feature_type=FeatureType.SPECIAL,
        resource_type=ResourceType.PROFICIENCY_PER_LONG_REST,
        min_level=2,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="second_wind_2024",
        name="Second Wind (Enhanced)",
        description="Second Wind now heals 1d10 + Fighter level (improved formula).",
        feature_type=FeatureType.BONUS_ACTION,
        resource_type=ResourceType.PER_SHORT_REST,
        uses_per_rest=1,
        min_level=1,
        is_2024_feature=True,
        replaces_feature="second_wind",
    ),
]


def use_second_wind(fighter_level: int, is_2024: bool = None) -> FeatureUseResult:
    """
    Use Second Wind to regain hit points.

    Args:
        fighter_level: The fighter's class level
        is_2024: Override for 2024 rules check

    Returns:
        FeatureUseResult with healing amount
    """
    if is_2024 is None:
        is_2024 = is_2024_class_features_enabled()

    # Both versions use 1d10 + fighter level
    roll_result = roll_damage("1d10", modifier=fighter_level)
    healing = roll_result.total

    return FeatureUseResult(
        success=True,
        description=f"Second Wind heals for {healing} hit points!",
        value=healing,
        extra_data={"roll": roll_result.rolls, "modifier": fighter_level}
    )


def use_action_surge() -> FeatureUseResult:
    """
    Use Action Surge to gain an extra action.

    Returns:
        FeatureUseResult indicating success
    """
    return FeatureUseResult(
        success=True,
        description="Action Surge grants an additional action this turn!",
        extra_data={"grants_action": True}
    )


def use_tactical_mind(
    original_roll: int,
    check_dc: int,
    proficiency_bonus: int
) -> FeatureUseResult:
    """
    Use Tactical Mind to add d10 to a failed ability check.

    Args:
        original_roll: The original check total
        check_dc: The DC of the check
        proficiency_bonus: Character's proficiency bonus (for uses tracking)

    Returns:
        FeatureUseResult with new total and success status
    """
    if not is_2024_class_features_enabled():
        return FeatureUseResult(
            success=False,
            description="Tactical Mind is only available with 2024 rules enabled."
        )

    bonus_roll = roll_damage("1d10")
    new_total = original_roll + bonus_roll.total

    if new_total >= check_dc:
        return FeatureUseResult(
            success=True,
            description=f"Tactical Mind adds {bonus_roll.total}! New total {new_total} succeeds vs DC {check_dc}!",
            value=new_total,
            extra_data={"bonus": bonus_roll.total, "original": original_roll}
        )
    else:
        return FeatureUseResult(
            success=False,
            description=f"Tactical Mind adds {bonus_roll.total}. New total {new_total} still fails vs DC {check_dc}.",
            value=new_total,
            extra_data={"bonus": bonus_roll.total, "original": original_roll}
        )


def use_indomitable(save_result: int, save_dc: int) -> FeatureUseResult:
    """
    Use Indomitable to reroll a failed saving throw.

    Args:
        save_result: The original save total
        save_dc: The DC of the save

    Returns:
        FeatureUseResult with new roll
    """
    # Extract modifier from original result (assume d20 roll)
    # We'll just do a fresh d20 roll with same modifier
    modifier = save_result - 10  # Rough estimate
    new_roll = roll_d20(modifier=max(0, modifier))

    success = new_roll.total >= save_dc

    return FeatureUseResult(
        success=success,
        description=f"Indomitable reroll: {new_roll.total} vs DC {save_dc}. {'Success!' if success else 'Still failed.'}",
        value=new_roll.total,
        extra_data={"original": save_result, "new_roll": new_roll.rolls}
    )


# =============================================================================
# ROGUE FEATURES
# =============================================================================

ROGUE_FEATURES: List[ClassFeature] = [
    # 2014 Core Features
    ClassFeature(
        id="expertise",
        name="Expertise",
        description="Double your proficiency bonus for two chosen skill proficiencies.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="sneak_attack",
        name="Sneak Attack",
        description="Once per turn, deal extra damage when you have advantage or an ally is within 5ft of target.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="thieves_cant",
        name="Thieves' Cant",
        description="You know Thieves' Cant, a secret mix of dialect, jargon, and code.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="cunning_action",
        name="Cunning Action",
        description="Use a bonus action to Dash, Disengage, or Hide.",
        feature_type=FeatureType.BONUS_ACTION,
        min_level=2,
    ),
    ClassFeature(
        id="uncanny_dodge",
        name="Uncanny Dodge",
        description="When an attacker you can see hits you, use reaction to halve the damage.",
        feature_type=FeatureType.REACTION,
        min_level=5,
    ),
    ClassFeature(
        id="evasion",
        name="Evasion",
        description="On DEX saves for half damage: take no damage on success, half on failure.",
        feature_type=FeatureType.PASSIVE,
        min_level=7,
    ),

    # 2024 Enhanced Features
    ClassFeature(
        id="weapon_mastery_rogue",
        name="Weapon Mastery",
        description="You gain Weapon Mastery for 2 weapons of your choice (3 at level 4).",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="steady_aim",
        name="Steady Aim",
        description="As a bonus action (Cunning Action), give yourself advantage on your next attack roll this turn. You can't move this turn before or after using this.",
        feature_type=FeatureType.BONUS_ACTION,
        min_level=3,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="cunning_strike",
        name="Cunning Strike",
        description="Trade Sneak Attack dice for special effects: Poison (1d6), Trip (1d6), Withdraw (1d6).",
        feature_type=FeatureType.SPECIAL,
        min_level=5,
        is_2024_feature=True,
    ),
]


def calculate_sneak_attack_dice(rogue_level: int) -> str:
    """
    Calculate Sneak Attack damage dice based on rogue level.

    Args:
        rogue_level: The rogue's class level

    Returns:
        Dice notation string (e.g., "3d6")
    """
    dice_count = (rogue_level + 1) // 2  # 1 at 1, 2 at 3, 3 at 5, etc.
    return f"{dice_count}d6"


def roll_sneak_attack(rogue_level: int) -> FeatureUseResult:
    """
    Roll Sneak Attack damage.

    Args:
        rogue_level: The rogue's class level

    Returns:
        FeatureUseResult with damage
    """
    dice = calculate_sneak_attack_dice(rogue_level)
    result = roll_damage(dice)

    return FeatureUseResult(
        success=True,
        description=f"Sneak Attack deals {result.total} extra damage!",
        value=result.total,
        extra_data={"dice": dice, "rolls": result.rolls}
    )


class CunningStrikeEffect(Enum):
    """Available Cunning Strike effects (2024 feature)."""
    POISON = "poison"  # Cost: 1d6, target must save vs poison
    TRIP = "trip"  # Cost: 1d6, target falls prone
    WITHDRAW = "withdraw"  # Cost: 1d6, move half speed without opportunity attacks


def use_cunning_strike(
    rogue_level: int,
    effect: CunningStrikeEffect,
    target_con_save_mod: int = 0,
    attacker_dc: int = 13
) -> FeatureUseResult:
    """
    Use Cunning Strike to trade Sneak Attack dice for an effect.

    Args:
        rogue_level: The rogue's class level
        effect: The Cunning Strike effect to apply
        target_con_save_mod: Target's CON save modifier (for Poison)
        attacker_dc: DC for saves (8 + prof + DEX mod)

    Returns:
        FeatureUseResult with effect details
    """
    if not is_2024_class_features_enabled():
        return FeatureUseResult(
            success=False,
            description="Cunning Strike is only available with 2024 rules enabled."
        )

    if rogue_level < 5:
        return FeatureUseResult(
            success=False,
            description="Cunning Strike requires rogue level 5."
        )

    # All effects cost 1d6 from Sneak Attack
    if effect == CunningStrikeEffect.POISON:
        save_roll = roll_d20(modifier=target_con_save_mod)
        if save_roll.total >= attacker_dc:
            return FeatureUseResult(
                success=False,
                description=f"Target resists poison (rolled {save_roll.total} vs DC {attacker_dc}).",
                extra_data={"effect": "poison", "saved": True}
            )
        return FeatureUseResult(
            success=True,
            description="Target is poisoned for 1 minute!",
            extra_data={"effect": "poison", "condition": "poisoned", "duration": "1 minute"}
        )

    elif effect == CunningStrikeEffect.TRIP:
        return FeatureUseResult(
            success=True,
            description="Target falls prone!",
            extra_data={"effect": "trip", "condition": "prone"}
        )

    elif effect == CunningStrikeEffect.WITHDRAW:
        return FeatureUseResult(
            success=True,
            description="You can move half your speed without provoking opportunity attacks!",
            extra_data={"effect": "withdraw", "movement": "half_speed_no_aoo"}
        )

    return FeatureUseResult(success=False, description="Unknown Cunning Strike effect.")


def use_uncanny_dodge(incoming_damage: int) -> FeatureUseResult:
    """
    Use Uncanny Dodge to halve incoming damage.

    Args:
        incoming_damage: The damage from the attack

    Returns:
        FeatureUseResult with reduced damage
    """
    reduced_damage = incoming_damage // 2

    return FeatureUseResult(
        success=True,
        description=f"Uncanny Dodge reduces damage from {incoming_damage} to {reduced_damage}!",
        value=reduced_damage,
        extra_data={"original_damage": incoming_damage}
    )


# =============================================================================
# WIZARD FEATURES
# =============================================================================

WIZARD_FEATURES: List[ClassFeature] = [
    # 2014 Core Features
    ClassFeature(
        id="spellcasting_wizard",
        name="Spellcasting",
        description="You can cast wizard spells using Intelligence as your spellcasting ability.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="arcane_recovery",
        name="Arcane Recovery",
        description="Once per day during a short rest, recover spell slots with combined level up to half wizard level.",
        feature_type=FeatureType.SPECIAL,
        resource_type=ResourceType.PER_LONG_REST,
        uses_per_rest=1,
        min_level=1,
    ),
    ClassFeature(
        id="spell_mastery",
        name="Spell Mastery",
        description="Cast a 1st and 2nd level spell at will without expending a spell slot.",
        feature_type=FeatureType.PASSIVE,
        min_level=18,
    ),

    # 2024 Enhanced Features
    ClassFeature(
        id="scholar",
        name="Scholar",
        description="You gain proficiency in one skill: Arcana, History, Investigation, Medicine, Nature, or Religion.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="modify_spell",
        name="Modify Spell",
        description="When you cast a spell that deals damage, you can change the damage type to another type.",
        feature_type=FeatureType.SPECIAL,
        min_level=5,
        is_2024_feature=True,
    ),
]


def calculate_arcane_recovery_slots(wizard_level: int) -> int:
    """
    Calculate max spell slot levels recoverable via Arcane Recovery.

    Args:
        wizard_level: The wizard's class level

    Returns:
        Maximum combined spell slot levels recoverable
    """
    return max(1, wizard_level // 2)


def use_arcane_recovery(
    wizard_level: int,
    slots_to_recover: Dict[int, int]
) -> FeatureUseResult:
    """
    Use Arcane Recovery to regain spell slots.

    Args:
        wizard_level: The wizard's class level
        slots_to_recover: Dict of {slot_level: count} to recover

    Returns:
        FeatureUseResult with recovery details
    """
    max_levels = calculate_arcane_recovery_slots(wizard_level)

    # Calculate total levels being recovered
    total_levels = sum(level * count for level, count in slots_to_recover.items())

    # Check for 6th level or higher slots (not allowed)
    for level in slots_to_recover.keys():
        if level >= 6:
            return FeatureUseResult(
                success=False,
                description="Cannot recover spell slots of 6th level or higher."
            )

    if total_levels > max_levels:
        return FeatureUseResult(
            success=False,
            description=f"Cannot recover more than {max_levels} levels of spell slots. Requested: {total_levels}."
        )

    slot_descriptions = []
    for level, count in sorted(slots_to_recover.items()):
        if count > 0:
            slot_descriptions.append(f"{count}x level {level}")

    return FeatureUseResult(
        success=True,
        description=f"Arcane Recovery restores: {', '.join(slot_descriptions)}!",
        extra_data={"slots_recovered": slots_to_recover, "total_levels": total_levels}
    )


def use_modify_spell(
    original_damage_type: str,
    new_damage_type: str
) -> FeatureUseResult:
    """
    Use Modify Spell to change a spell's damage type.

    Args:
        original_damage_type: The spell's original damage type
        new_damage_type: The new damage type to use

    Returns:
        FeatureUseResult with modification details
    """
    if not is_2024_class_features_enabled():
        return FeatureUseResult(
            success=False,
            description="Modify Spell is only available with 2024 rules enabled."
        )

    valid_damage_types = [
        "acid", "cold", "fire", "force", "lightning",
        "necrotic", "poison", "psychic", "radiant", "thunder"
    ]

    if new_damage_type.lower() not in valid_damage_types:
        return FeatureUseResult(
            success=False,
            description=f"Invalid damage type: {new_damage_type}"
        )

    return FeatureUseResult(
        success=True,
        description=f"Spell damage changed from {original_damage_type} to {new_damage_type}!",
        extra_data={
            "original_type": original_damage_type,
            "new_type": new_damage_type
        }
    )


# =============================================================================
# CLERIC FEATURES
# =============================================================================

CLERIC_FEATURES: List[ClassFeature] = [
    # 2014 Core Features
    ClassFeature(
        id="spellcasting_cleric",
        name="Spellcasting",
        description="You can cast cleric spells using Wisdom as your spellcasting ability.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="channel_divinity",
        name="Channel Divinity",
        description="Channel divine energy for powerful effects. Uses refresh on short or long rest.",
        feature_type=FeatureType.ACTION,
        resource_type=ResourceType.PER_SHORT_REST,
        uses_per_rest=1,
        min_level=2,
    ),
    ClassFeature(
        id="turn_undead",
        name="Turn Undead",
        description="Channel Divinity to turn undead within 30ft. They must make WIS save or flee.",
        feature_type=FeatureType.ACTION,
        min_level=2,
    ),
    ClassFeature(
        id="destroy_undead",
        name="Destroy Undead",
        description="Undead of CR 1/2 or lower that fail Turn Undead save are destroyed.",
        feature_type=FeatureType.PASSIVE,
        min_level=5,
    ),
    ClassFeature(
        id="divine_intervention",
        name="Divine Intervention",
        description="Call on your deity for aid. Roll d100; if you roll ≤ cleric level, deity intervenes.",
        feature_type=FeatureType.ACTION,
        resource_type=ResourceType.PER_LONG_REST,
        uses_per_rest=1,
        min_level=10,
    ),

    # 2024 Enhanced Features
    ClassFeature(
        id="divine_order",
        name="Divine Order",
        description="Choose Protector (martial weapon + heavy armor) or Thaumaturge (extra cantrip + enhanced effects).",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="blessed_strikes",
        name="Blessed Strikes",
        description="Divine Strike or Potent Spellcasting - deal extra damage with weapon or cantrip.",
        feature_type=FeatureType.PASSIVE,
        min_level=8,
        is_2024_feature=True,
    ),
]


class DivineOrderChoice(Enum):
    """Divine Order options (2024 feature)."""
    PROTECTOR = "protector"  # Martial weapons + heavy armor
    THAUMATURGE = "thaumaturge"  # Extra cantrip + enhanced effects


def get_channel_divinity_uses(cleric_level: int) -> int:
    """
    Get number of Channel Divinity uses based on cleric level.

    Args:
        cleric_level: The cleric's class level

    Returns:
        Number of uses per rest
    """
    if cleric_level >= 18:
        return 3
    elif cleric_level >= 6:
        return 2
    elif cleric_level >= 2:
        return 1
    return 0


def use_turn_undead(
    cleric_wisdom_mod: int,
    cleric_proficiency: int,
    undead_targets: List[Dict[str, Any]]
) -> FeatureUseResult:
    """
    Use Turn Undead on nearby undead.

    Args:
        cleric_wisdom_mod: Cleric's WIS modifier
        cleric_proficiency: Cleric's proficiency bonus
        undead_targets: List of undead with their WIS save modifiers

    Returns:
        FeatureUseResult with turned undead list
    """
    dc = 8 + cleric_proficiency + cleric_wisdom_mod
    turned = []
    resisted = []

    for undead in undead_targets:
        save_roll = roll_d20(modifier=undead.get("wis_save_mod", 0))
        if save_roll.total < dc:
            turned.append(undead.get("id", "unknown"))
        else:
            resisted.append(undead.get("id", "unknown"))

    return FeatureUseResult(
        success=len(turned) > 0,
        description=f"Turn Undead (DC {dc}): {len(turned)} turned, {len(resisted)} resisted.",
        extra_data={"turned": turned, "resisted": resisted, "dc": dc}
    )


def apply_divine_order(choice: DivineOrderChoice) -> FeatureUseResult:
    """
    Apply Divine Order choice benefits.

    Args:
        choice: The Divine Order chosen

    Returns:
        FeatureUseResult with benefits granted
    """
    if not is_2024_class_features_enabled():
        return FeatureUseResult(
            success=False,
            description="Divine Order is only available with 2024 rules enabled."
        )

    if choice == DivineOrderChoice.PROTECTOR:
        return FeatureUseResult(
            success=True,
            description="Divine Order: Protector - You gain martial weapon and heavy armor proficiency!",
            extra_data={
                "proficiencies": ["martial_weapons", "heavy_armor"],
                "choice": "protector"
            }
        )
    else:  # THAUMATURGE
        return FeatureUseResult(
            success=True,
            description="Divine Order: Thaumaturge - You gain an extra cleric cantrip and enhanced cantrip effects!",
            extra_data={
                "extra_cantrips": 1,
                "enhanced_cantrips": True,
                "choice": "thaumaturge"
            }
        )


# =============================================================================
# PALADIN FEATURES
# =============================================================================

PALADIN_FEATURES: List[ClassFeature] = [
    # Core Features
    ClassFeature(
        id="divine_sense",
        name="Divine Sense",
        description="Detect celestials, fiends, and undead within 60ft. Uses = 1 + CHA modifier per long rest.",
        feature_type=FeatureType.ACTION,
        resource_type=ResourceType.PER_LONG_REST,
        min_level=1,
    ),
    ClassFeature(
        id="lay_on_hands",
        name="Lay on Hands",
        description="Pool of healing = 5 × paladin level. Restore HP or cure disease/poison (5 points each).",
        feature_type=FeatureType.ACTION,
        resource_type=ResourceType.PER_LONG_REST,
        min_level=1,
    ),
    ClassFeature(
        id="divine_smite",
        name="Divine Smite",
        description="Expend spell slot to deal extra radiant damage on melee hit: 2d8 + 1d8 per slot level above 1st (max 5d8). +1d8 vs undead/fiends.",
        feature_type=FeatureType.SPECIAL,  # Triggered on hit
        resource_type=ResourceType.SPELL_SLOTS,
        min_level=2,
    ),
    ClassFeature(
        id="divine_smite_2024",
        name="Divine Smite (2024)",
        description="Expend spell slot to deal extra FORCE damage on ANY weapon hit: 2d8 + 1d8 per slot level above 1st (max 5d8). +1d8 vs undead/fiends.",
        feature_type=FeatureType.SPECIAL,  # Triggered on hit
        resource_type=ResourceType.SPELL_SLOTS,
        min_level=2,
        is_2024_feature=True,
        replaces_feature="divine_smite",
    ),
    ClassFeature(
        id="extra_attack_paladin",
        name="Extra Attack",
        description="You can attack twice when you take the Attack action on your turn.",
        feature_type=FeatureType.PASSIVE,
        min_level=5,
    ),
    ClassFeature(
        id="aura_of_protection",
        name="Aura of Protection",
        description="You and allies within 10ft gain bonus to saves equal to your CHA modifier (min +1).",
        feature_type=FeatureType.PASSIVE,
        min_level=6,
    ),
]


def use_divine_smite(slot_level: int, is_undead_or_fiend: bool = False) -> FeatureUseResult:
    """
    Use Divine Smite on a successful hit.

    D&D 5e Rules (2014):
    - 2d8 radiant damage base, melee only
    - +1d8 per slot level above 1st (max 5d8 from slots)
    - +1d8 vs undead or fiends
    - Maximum 6d8 total

    D&D 5e Rules (2024):
    - 2d8 FORCE damage base, ANY weapon
    - +1d8 per slot level above 1st (max 5d8 from slots)
    - +1d8 vs undead or fiends
    - Maximum 6d8 total

    Args:
        slot_level: The spell slot level to expend (1-5)
        is_undead_or_fiend: True if target is undead or fiend

    Returns:
        FeatureUseResult with damage dealt
    """
    # Check if using 2024 rules
    is_2024 = is_2024_class_features_enabled()

    # Base damage is 2d8
    base_dice = 2

    # +1d8 per slot level above 1st (max 5d8 total from slot scaling)
    extra_dice = min(slot_level - 1, 3)  # Caps at 5d8 (2 base + 3 from slot)
    total_dice = base_dice + extra_dice

    # +1d8 vs undead/fiends
    if is_undead_or_fiend:
        total_dice += 1

    # Absolute cap at 6d8
    total_dice = min(total_dice, 6)

    result = roll_damage(f"{total_dice}d8")

    # 2024: Force damage, 2014: Radiant damage
    damage_type = "force" if is_2024 else "radiant"

    return FeatureUseResult(
        success=True,
        description=f"Divine Smite deals {result.total} {damage_type} damage!",
        value=result.total,
        extra_data={
            "dice": f"{total_dice}d8",
            "rolls": result.rolls,
            "slot_used": slot_level,
            "damage_type": damage_type,
            "vs_undead_fiend": is_undead_or_fiend,
            "is_2024_rules": is_2024
        }
    )


def get_lay_on_hands_pool(paladin_level: int) -> int:
    """
    Get Lay on Hands pool size based on paladin level.

    Args:
        paladin_level: The paladin's class level

    Returns:
        Total pool size (5 × level)
    """
    return paladin_level * 5


def use_lay_on_hands(points_to_spend: int, cure_disease: bool = False, cure_poison: bool = False) -> FeatureUseResult:
    """
    Use Lay on Hands to heal or cure conditions.

    Args:
        points_to_spend: HP to restore (or 5 to cure disease/poison)
        cure_disease: Whether to cure a disease (costs 5 points)
        cure_poison: Whether to cure poison (costs 5 points)

    Returns:
        FeatureUseResult with healing/curing details
    """
    effects = []

    if cure_disease:
        effects.append("cured disease")
    if cure_poison:
        effects.append("cured poison")

    healing = points_to_spend if not (cure_disease or cure_poison) else 0

    if healing > 0:
        effects.append(f"healed {healing} HP")

    return FeatureUseResult(
        success=True,
        description=f"Lay on Hands: {', '.join(effects)}",
        value=healing,
        extra_data={
            "points_spent": points_to_spend,
            "cured_disease": cure_disease,
            "cured_poison": cure_poison
        }
    )


# =============================================================================
# BARBARIAN FEATURES
# =============================================================================

BARBARIAN_FEATURES: List[ClassFeature] = [
    # Core Features
    ClassFeature(
        id="rage",
        name="Rage",
        description="Enter rage for 1 minute: advantage on STR checks/saves, +2 damage (scales), resistance to B/P/S damage.",
        feature_type=FeatureType.BONUS_ACTION,
        resource_type=ResourceType.PER_LONG_REST,
        uses_per_rest=2,  # Increases at higher levels
        min_level=1,
    ),
    ClassFeature(
        id="unarmored_defense_barbarian",
        name="Unarmored Defense",
        description="AC = 10 + DEX mod + CON mod when not wearing armor.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="reckless_attack",
        name="Reckless Attack",
        description="Gain advantage on melee STR attacks this turn, but attacks against you have advantage until your next turn.",
        feature_type=FeatureType.SPECIAL,
        min_level=2,
    ),
    ClassFeature(
        id="danger_sense",
        name="Danger Sense",
        description="Advantage on DEX saves against effects you can see (traps, spells).",
        feature_type=FeatureType.PASSIVE,
        min_level=2,
    ),
    ClassFeature(
        id="extra_attack_barbarian",
        name="Extra Attack",
        description="You can attack twice when you take the Attack action on your turn.",
        feature_type=FeatureType.PASSIVE,
        min_level=5,
    ),
    ClassFeature(
        id="feral_instinct",
        name="Feral Instinct",
        description="Advantage on initiative. If surprised, can act normally if you enter rage.",
        feature_type=FeatureType.PASSIVE,
        min_level=7,
    ),
    ClassFeature(
        id="brutal_critical",
        name="Brutal Critical",
        description="Roll one additional weapon damage die on critical hits.",
        feature_type=FeatureType.PASSIVE,
        min_level=9,
    ),
    ClassFeature(
        id="relentless_rage",
        name="Relentless Rage",
        description="If you drop to 0 HP while raging, DC 10 CON save to drop to 1 HP instead. DC increases by 5 each use.",
        feature_type=FeatureType.PASSIVE,
        min_level=11,
    ),
]


def get_rage_damage_bonus(barbarian_level: int) -> int:
    """
    Get rage damage bonus based on barbarian level.

    D&D 5e Rage Damage:
    - Levels 1-8: +2
    - Levels 9-15: +3
    - Levels 16+: +4

    Args:
        barbarian_level: The barbarian's class level

    Returns:
        Rage damage bonus
    """
    if barbarian_level >= 16:
        return 4
    elif barbarian_level >= 9:
        return 3
    return 2


def get_rage_uses(barbarian_level: int) -> int:
    """
    Get number of rage uses per long rest.

    D&D 5e Rage Uses:
    - Levels 1-2: 2
    - Levels 3-5: 3
    - Levels 6-11: 4
    - Levels 12-16: 5
    - Levels 17-19: 6
    - Level 20: Unlimited

    Args:
        barbarian_level: The barbarian's class level

    Returns:
        Number of rage uses per long rest
    """
    if barbarian_level >= 20:
        return 999  # Unlimited
    elif barbarian_level >= 17:
        return 6
    elif barbarian_level >= 12:
        return 5
    elif barbarian_level >= 6:
        return 4
    elif barbarian_level >= 3:
        return 3
    return 2


def use_rage(barbarian_level: int) -> FeatureUseResult:
    """
    Activate Barbarian Rage.

    Benefits:
    - Advantage on STR checks and saves
    - Bonus to melee damage (level-based)
    - Resistance to bludgeoning, piercing, slashing damage

    Args:
        barbarian_level: The barbarian's class level

    Returns:
        FeatureUseResult with rage details
    """
    damage_bonus = get_rage_damage_bonus(barbarian_level)

    return FeatureUseResult(
        success=True,
        description=f"RAGE! +{damage_bonus} melee damage, resistance to physical damage!",
        value=damage_bonus,
        extra_data={
            "damage_bonus": damage_bonus,
            "resistances": ["bludgeoning", "piercing", "slashing"],
            "advantage_on": ["str_checks", "str_saves"],
            "duration": "1 minute",
        }
    )


def use_reckless_attack() -> FeatureUseResult:
    """
    Use Reckless Attack for advantage at a cost.

    D&D 5e Rule:
    - Gain advantage on melee weapon attacks using STR this turn
    - Attack rolls against you have advantage until your next turn

    Returns:
        FeatureUseResult indicating reckless attack is active
    """
    return FeatureUseResult(
        success=True,
        description="Reckless Attack! Advantage on melee attacks, but enemies have advantage against you!",
        extra_data={
            "grants_advantage": True,
            "enemies_have_advantage": True,
            "duration": "until_next_turn"
        }
    )


# =============================================================================
# BARD FEATURES
# =============================================================================

BARD_FEATURES: List[ClassFeature] = [
    ClassFeature(
        id="spellcasting_bard",
        name="Spellcasting",
        description="You can cast bard spells using Charisma as your spellcasting ability.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="bardic_inspiration",
        name="Bardic Inspiration",
        description="Use bonus action to give one creature within 60ft an inspiration die (d6) to add to one ability check, attack roll, or save within 10 minutes.",
        feature_type=FeatureType.BONUS_ACTION,
        resource_type=ResourceType.PROFICIENCY_PER_LONG_REST,
        min_level=1,
    ),
    ClassFeature(
        id="jack_of_all_trades",
        name="Jack of All Trades",
        description="Add half your proficiency bonus (rounded down) to any ability check that doesn't already use your proficiency bonus.",
        feature_type=FeatureType.PASSIVE,
        min_level=2,
    ),
    ClassFeature(
        id="song_of_rest",
        name="Song of Rest",
        description="During short rest, allies who spend hit dice regain extra 1d6 HP (scales with level).",
        feature_type=FeatureType.PASSIVE,
        min_level=2,
    ),
    ClassFeature(
        id="expertise_bard",
        name="Expertise",
        description="Double proficiency bonus for two skill proficiencies of your choice.",
        feature_type=FeatureType.PASSIVE,
        min_level=3,
    ),
    ClassFeature(
        id="font_of_inspiration",
        name="Font of Inspiration",
        description="Bardic Inspiration now recharges on short or long rest.",
        feature_type=FeatureType.PASSIVE,
        min_level=5,
    ),
    ClassFeature(
        id="countercharm",
        name="Countercharm",
        description="As an action, you and allies within 30ft have advantage on saves vs frightened/charmed until your next turn.",
        feature_type=FeatureType.ACTION,
        min_level=6,
    ),
    ClassFeature(
        id="magical_secrets",
        name="Magical Secrets",
        description="Learn two spells from any class. They count as bard spells for you.",
        feature_type=FeatureType.PASSIVE,
        min_level=10,
    ),
    ClassFeature(
        id="superior_inspiration",
        name="Superior Inspiration",
        description="When you roll initiative and have no Bardic Inspiration uses, you regain one use.",
        feature_type=FeatureType.PASSIVE,
        min_level=20,
    ),
]


def get_bardic_inspiration_die(bard_level: int) -> str:
    """Get Bardic Inspiration die size for bard level."""
    if bard_level >= 15:
        return "1d12"
    elif bard_level >= 10:
        return "1d10"
    elif bard_level >= 5:
        return "1d8"
    return "1d6"


def get_song_of_rest_die(bard_level: int) -> str:
    """Get Song of Rest die size for bard level."""
    if bard_level >= 17:
        return "1d12"
    elif bard_level >= 13:
        return "1d10"
    elif bard_level >= 9:
        return "1d8"
    elif bard_level >= 2:
        return "1d6"
    return "0"


def use_bardic_inspiration(bard_level: int, target_name: str) -> FeatureUseResult:
    """Give Bardic Inspiration to a creature."""
    die = get_bardic_inspiration_die(bard_level)
    return FeatureUseResult(
        success=True,
        description=f"Bardic Inspiration ({die}) granted to {target_name}!",
        extra_data={"die": die, "target": target_name, "duration": "10 minutes"}
    )


# =============================================================================
# RANGER FEATURES
# =============================================================================

RANGER_FEATURES: List[ClassFeature] = [
    ClassFeature(
        id="favored_enemy",
        name="Favored Enemy",
        description="Choose a favored enemy type. Advantage on Survival checks to track them and Intelligence checks to recall info about them.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="deft_explorer",
        name="Deft Explorer",
        description="Gain expertise in one skill proficiency, and additional benefits at higher levels.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="natural_explorer",
        name="Natural Explorer",
        description="Choose a favored terrain. Benefits include faster travel and foraging in that terrain.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="fighting_style_ranger",
        name="Fighting Style",
        description="Adopt a particular style of fighting as your specialty.",
        feature_type=FeatureType.PASSIVE,
        min_level=2,
    ),
    ClassFeature(
        id="spellcasting_ranger",
        name="Spellcasting",
        description="You can cast ranger spells using Wisdom as your spellcasting ability.",
        feature_type=FeatureType.PASSIVE,
        min_level=2,
    ),
    ClassFeature(
        id="primal_awareness",
        name="Primal Awareness",
        description="You can cast certain spells without expending a spell slot (once each per long rest).",
        feature_type=FeatureType.PASSIVE,
        min_level=3,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="extra_attack_ranger",
        name="Extra Attack",
        description="You can attack twice when you take the Attack action on your turn.",
        feature_type=FeatureType.PASSIVE,
        min_level=5,
    ),
    ClassFeature(
        id="lands_stride",
        name="Land's Stride",
        description="Moving through nonmagical difficult terrain costs no extra movement. You can pass through plants without being slowed or taking damage.",
        feature_type=FeatureType.PASSIVE,
        min_level=8,
    ),
    ClassFeature(
        id="hide_in_plain_sight",
        name="Hide in Plain Sight",
        description="Spend 1 minute creating camouflage for +10 to Stealth checks while motionless.",
        feature_type=FeatureType.SPECIAL,
        min_level=10,
    ),
    ClassFeature(
        id="natures_veil",
        name="Nature's Veil",
        description="As a bonus action, become invisible until start of next turn. Uses = proficiency bonus per long rest.",
        feature_type=FeatureType.BONUS_ACTION,
        resource_type=ResourceType.PROFICIENCY_PER_LONG_REST,
        min_level=10,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="vanish",
        name="Vanish",
        description="You can use Hide as a bonus action. You can't be tracked by nonmagical means unless you choose to leave a trail.",
        feature_type=FeatureType.BONUS_ACTION,
        min_level=14,
    ),
    ClassFeature(
        id="feral_senses",
        name="Feral Senses",
        description="No disadvantage on attacks against invisible creatures. Aware of invisible creatures within 30ft.",
        feature_type=FeatureType.PASSIVE,
        min_level=18,
    ),
    ClassFeature(
        id="foe_slayer",
        name="Foe Slayer",
        description="Add WIS modifier to attack or damage roll against favored enemy once per turn.",
        feature_type=FeatureType.PASSIVE,
        min_level=20,
    ),
]


# =============================================================================
# DRUID FEATURES
# =============================================================================

DRUID_FEATURES: List[ClassFeature] = [
    ClassFeature(
        id="druidic",
        name="Druidic",
        description="You know Druidic, the secret language of druids.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="spellcasting_druid",
        name="Spellcasting",
        description="You can cast druid spells using Wisdom as your spellcasting ability.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="wild_shape",
        name="Wild Shape",
        description="Transform into a beast you have seen. Uses = 2 per short/long rest. Limited by CR and movement types based on level.",
        feature_type=FeatureType.ACTION,
        resource_type=ResourceType.PER_SHORT_REST,
        uses_per_rest=2,
        min_level=2,
    ),
    ClassFeature(
        id="wild_companion",
        name="Wild Companion",
        description="Expend a Wild Shape use to cast Find Familiar without material components.",
        feature_type=FeatureType.ACTION,
        min_level=2,
        is_2024_feature=True,
    ),
    ClassFeature(
        id="timeless_body_druid",
        name="Timeless Body",
        description="You age 10 times slower and can't be aged magically.",
        feature_type=FeatureType.PASSIVE,
        min_level=18,
    ),
    ClassFeature(
        id="beast_spells",
        name="Beast Spells",
        description="You can cast spells while in Wild Shape (can't use material components).",
        feature_type=FeatureType.PASSIVE,
        min_level=18,
    ),
    ClassFeature(
        id="archdruid",
        name="Archdruid",
        description="Unlimited Wild Shape uses. Ignore V and S components of druid spells.",
        feature_type=FeatureType.PASSIVE,
        min_level=20,
    ),
]


# =============================================================================
# MONK FEATURES
# =============================================================================

MONK_FEATURES: List[ClassFeature] = [
    ClassFeature(
        id="unarmored_defense_monk",
        name="Unarmored Defense",
        description="AC = 10 + DEX mod + WIS mod when not wearing armor or shield.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="martial_arts",
        name="Martial Arts",
        description="Use DEX for unarmed strikes. Martial Arts die for damage. Bonus action unarmed strike after Attack action.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="ki",
        name="Ki",
        description="Harness mystic energy for special abilities. Ki points = monk level. Recharge on short/long rest.",
        feature_type=FeatureType.PASSIVE,
        min_level=2,
    ),
    ClassFeature(
        id="flurry_of_blows",
        name="Flurry of Blows",
        description="Spend 1 ki after Attack action to make two unarmed strikes as bonus action.",
        feature_type=FeatureType.BONUS_ACTION,
        min_level=2,
    ),
    ClassFeature(
        id="patient_defense",
        name="Patient Defense",
        description="Spend 1 ki to take Dodge action as bonus action.",
        feature_type=FeatureType.BONUS_ACTION,
        min_level=2,
    ),
    ClassFeature(
        id="step_of_the_wind",
        name="Step of the Wind",
        description="Spend 1 ki to Dash or Disengage as bonus action, and double jump distance.",
        feature_type=FeatureType.BONUS_ACTION,
        min_level=2,
    ),
    ClassFeature(
        id="unarmored_movement",
        name="Unarmored Movement",
        description="Speed increases when not wearing armor (+10ft at 2, scaling up).",
        feature_type=FeatureType.PASSIVE,
        min_level=2,
    ),
    ClassFeature(
        id="deflect_missiles",
        name="Deflect Missiles",
        description="Reduce ranged weapon damage by 1d10 + DEX + level. If reduced to 0, catch it. Spend 1 ki to throw it back.",
        feature_type=FeatureType.REACTION,
        min_level=3,
    ),
    ClassFeature(
        id="slow_fall",
        name="Slow Fall",
        description="Reduce falling damage by 5 × monk level.",
        feature_type=FeatureType.REACTION,
        min_level=4,
    ),
    ClassFeature(
        id="extra_attack_monk",
        name="Extra Attack",
        description="You can attack twice when you take the Attack action on your turn.",
        feature_type=FeatureType.PASSIVE,
        min_level=5,
    ),
    ClassFeature(
        id="stunning_strike",
        name="Stunning Strike",
        description="Spend 1 ki when you hit. Target must pass CON save or be stunned until end of your next turn.",
        feature_type=FeatureType.SPECIAL,
        min_level=5,
    ),
    ClassFeature(
        id="ki_empowered_strikes",
        name="Ki-Empowered Strikes",
        description="Unarmed strikes count as magical for overcoming resistance.",
        feature_type=FeatureType.PASSIVE,
        min_level=6,
    ),
    ClassFeature(
        id="evasion_monk",
        name="Evasion",
        description="On DEX saves for half damage: take no damage on success, half on failure.",
        feature_type=FeatureType.PASSIVE,
        min_level=7,
    ),
    ClassFeature(
        id="stillness_of_mind",
        name="Stillness of Mind",
        description="Use action to end charmed or frightened condition on yourself.",
        feature_type=FeatureType.ACTION,
        min_level=7,
    ),
    ClassFeature(
        id="purity_of_body",
        name="Purity of Body",
        description="Immune to disease and poison.",
        feature_type=FeatureType.PASSIVE,
        min_level=10,
    ),
    ClassFeature(
        id="diamond_soul",
        name="Diamond Soul",
        description="Proficiency in all saving throws. Spend 1 ki to reroll a failed save.",
        feature_type=FeatureType.PASSIVE,
        min_level=14,
    ),
    ClassFeature(
        id="timeless_body_monk",
        name="Timeless Body",
        description="No frailty of old age. Can't be aged magically. Don't need food or water.",
        feature_type=FeatureType.PASSIVE,
        min_level=15,
    ),
    ClassFeature(
        id="empty_body",
        name="Empty Body",
        description="Spend 4 ki to become invisible with resistance to all damage except force for 1 minute.",
        feature_type=FeatureType.ACTION,
        min_level=18,
    ),
]


# =============================================================================
# WARLOCK FEATURES
# =============================================================================

WARLOCK_FEATURES: List[ClassFeature] = [
    ClassFeature(
        id="pact_magic",
        name="Pact Magic",
        description="Cast warlock spells using Charisma. Spell slots refresh on short rest.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="eldritch_invocations",
        name="Eldritch Invocations",
        description="Learn fragments of forbidden knowledge that grant magical abilities.",
        feature_type=FeatureType.PASSIVE,
        min_level=2,
    ),
    ClassFeature(
        id="pact_boon",
        name="Pact Boon",
        description="Choose Pact of the Blade, Chain, Tome, or Talisman for special abilities.",
        feature_type=FeatureType.PASSIVE,
        min_level=3,
    ),
    ClassFeature(
        id="mystic_arcanum",
        name="Mystic Arcanum",
        description="Learn a spell of 6th level or higher you can cast once per long rest without a spell slot.",
        feature_type=FeatureType.PASSIVE,
        min_level=11,
    ),
    ClassFeature(
        id="eldritch_master",
        name="Eldritch Master",
        description="Spend 1 minute entreating patron to regain all Pact Magic spell slots.",
        feature_type=FeatureType.SPECIAL,
        resource_type=ResourceType.PER_LONG_REST,
        uses_per_rest=1,
        min_level=20,
    ),
]


# =============================================================================
# SORCERER FEATURES
# =============================================================================

SORCERER_FEATURES: List[ClassFeature] = [
    ClassFeature(
        id="spellcasting_sorcerer",
        name="Spellcasting",
        description="Cast sorcerer spells using Charisma as your spellcasting ability.",
        feature_type=FeatureType.PASSIVE,
        min_level=1,
    ),
    ClassFeature(
        id="font_of_magic",
        name="Font of Magic",
        description="Sorcery points = sorcerer level. Convert spell slots to points or points to slots.",
        feature_type=FeatureType.PASSIVE,
        min_level=2,
    ),
    ClassFeature(
        id="metamagic",
        name="Metamagic",
        description="Modify spells with special effects. Learn 2 options at level 3, more at higher levels.",
        feature_type=FeatureType.PASSIVE,
        min_level=3,
    ),
    ClassFeature(
        id="sorcerous_restoration",
        name="Sorcerous Restoration",
        description="Regain 4 sorcery points when you finish a short rest.",
        feature_type=FeatureType.PASSIVE,
        min_level=20,
    ),
]


# =============================================================================
# CLASS FEATURE REGISTRY
# =============================================================================

CLASS_FEATURES: Dict[str, List[ClassFeature]] = {
    "fighter": FIGHTER_FEATURES,
    "rogue": ROGUE_FEATURES,
    "wizard": WIZARD_FEATURES,
    "cleric": CLERIC_FEATURES,
    "paladin": PALADIN_FEATURES,
    "barbarian": BARBARIAN_FEATURES,
    "bard": BARD_FEATURES,
    "ranger": RANGER_FEATURES,
    "druid": DRUID_FEATURES,
    "monk": MONK_FEATURES,
    "warlock": WARLOCK_FEATURES,
    "sorcerer": SORCERER_FEATURES,
}


def get_class_features(class_id: str, level: int) -> List[ClassFeature]:
    """
    Get all available features for a class at a given level.

    Args:
        class_id: The class ID (fighter, rogue, wizard, cleric)
        level: The character level

    Returns:
        List of available ClassFeature objects
    """
    class_id = class_id.lower()
    if class_id not in CLASS_FEATURES:
        return []

    available = []
    replaced_ids = set()

    # First pass: collect features that are replaced by 2024 versions
    for feature in CLASS_FEATURES[class_id]:
        if feature.is_available(level) and feature.replaces_feature:
            replaced_ids.add(feature.replaces_feature)

    # Second pass: add features that aren't replaced
    for feature in CLASS_FEATURES[class_id]:
        if not feature.is_available(level):
            continue
        if feature.id in replaced_ids and not feature.is_2024_feature:
            continue  # Skip 2014 version if replaced by 2024
        available.append(feature)

    return available


def get_feature_by_id(class_id: str, feature_id: str) -> Optional[ClassFeature]:
    """
    Get a specific feature by ID.

    Args:
        class_id: The class ID
        feature_id: The feature ID

    Returns:
        ClassFeature if found, None otherwise
    """
    class_id = class_id.lower()
    if class_id not in CLASS_FEATURES:
        return None

    for feature in CLASS_FEATURES[class_id]:
        if feature.id == feature_id:
            return feature

    return None


def get_weapon_mastery_count(class_id: str, level: int) -> int:
    """
    Get how many weapon masteries a class can have.

    Args:
        class_id: The class ID
        level: Character level

    Returns:
        Number of weapon masteries available
    """
    if not is_weapon_mastery_enabled():
        return 0

    class_id = class_id.lower()

    mastery_progression = {
        "fighter": {1: 3, 4: 4, 10: 5, 16: 6},
        "rogue": {1: 2, 4: 3},
        "ranger": {1: 2, 4: 3},
        "barbarian": {1: 2, 4: 3},
        "paladin": {1: 2, 4: 3},
    }

    if class_id not in mastery_progression:
        return 0

    progression = mastery_progression[class_id]
    count = 0

    for req_level, masteries in sorted(progression.items()):
        if level >= req_level:
            count = masteries

    return count


def get_extra_attack_count(class_id: str, level: int) -> int:
    """
    Get number of extra attacks for a class.

    Args:
        class_id: The class ID
        level: Character level

    Returns:
        Number of extra attacks (0 means just one attack)
    """
    class_id = class_id.lower()

    # Fighter gets the most extra attacks
    if class_id == "fighter":
        if level >= 20:
            return 3  # 4 total attacks
        elif level >= 11:
            return 2  # 3 total attacks
        elif level >= 5:
            return 1  # 2 total attacks

    # Other martial classes get one extra attack at level 5
    martial_classes = ["paladin", "ranger", "barbarian"]
    if class_id in martial_classes and level >= 5:
        return 1

    # Rogue doesn't get Extra Attack (relies on Sneak Attack)
    # Casters don't get Extra Attack

    return 0


# ============================================================================
# EVASION (Rogue/Monk)
# ============================================================================

def apply_evasion(
    save_success: bool,
    original_damage: int,
    has_evasion: bool = False
) -> Dict[str, Any]:
    """
    Apply Evasion feature to a DEX save for half damage.

    D&D 5e Rule:
    - On success: Take no damage (instead of half)
    - On failure: Take half damage (instead of full)

    Args:
        save_success: Whether the saving throw succeeded
        original_damage: The original damage before halving
        has_evasion: Whether the character has Evasion

    Returns:
        Dict with final_damage, damage_reduction, and description
    """
    if not has_evasion:
        # Normal half-damage save
        if save_success:
            return {
                "final_damage": original_damage // 2,
                "damage_reduction": original_damage - (original_damage // 2),
                "description": "Save succeeded - half damage"
            }
        else:
            return {
                "final_damage": original_damage,
                "damage_reduction": 0,
                "description": "Save failed - full damage"
            }

    # With Evasion
    if save_success:
        return {
            "final_damage": 0,
            "damage_reduction": original_damage,
            "description": "Evasion - no damage on successful save!"
        }
    else:
        return {
            "final_damage": original_damage // 2,
            "damage_reduction": original_damage - (original_damage // 2),
            "description": "Evasion - half damage on failed save"
        }


# ============================================================================
# BRUTAL CRITICAL (Barbarian)
# ============================================================================

def get_brutal_critical_dice(barbarian_level: int) -> int:
    """
    Get number of extra dice for Brutal Critical.

    D&D 5e Rule:
    - Level 9: +1 extra damage die on crits
    - Level 13: +2 extra damage dice on crits
    - Level 17: +3 extra damage dice on crits

    Args:
        barbarian_level: Barbarian class level

    Returns:
        Number of extra dice to roll on critical hits
    """
    if barbarian_level >= 17:
        return 3
    elif barbarian_level >= 13:
        return 2
    elif barbarian_level >= 9:
        return 1
    return 0


def apply_brutal_critical(
    base_crit_dice: str,
    barbarian_level: int
) -> FeatureUseResult:
    """
    Roll additional dice for Brutal Critical on a critical hit.

    Args:
        base_crit_dice: The dice to use (e.g., "1d12" for greataxe)
        barbarian_level: Barbarian class level

    Returns:
        FeatureUseResult with extra damage
    """
    extra_dice_count = get_brutal_critical_dice(barbarian_level)

    if extra_dice_count == 0:
        return FeatureUseResult(
            success=False,
            value=0,
            description="Brutal Critical not available at this level"
        )

    from app.core.dice import roll_damage

    # Roll the extra dice
    total_extra = 0
    dice_results = []
    for _ in range(extra_dice_count):
        result = roll_damage(base_crit_dice)
        total_extra += result.total
        dice_results.append(result.total)

    return FeatureUseResult(
        success=True,
        value=total_extra,
        description=f"Brutal Critical! +{extra_dice_count}d extra = {total_extra} damage",
        extra_data={
            "extra_dice": extra_dice_count,
            "dice_results": dice_results
        }
    )


# ============================================================================
# AURA OF PROTECTION (Paladin)
# ============================================================================

def get_aura_of_protection_bonus(
    paladin_level: int,
    charisma_modifier: int
) -> int:
    """
    Get the saving throw bonus from Aura of Protection.

    D&D 5e Rule:
    - Level 6+: Bonus equals CHA modifier (minimum +1)
    - Applies to Paladin and all allies within 10ft (18th level: 30ft)

    Args:
        paladin_level: Paladin class level
        charisma_modifier: Paladin's Charisma modifier

    Returns:
        Bonus to add to saving throws
    """
    if paladin_level < 6:
        return 0

    return max(1, charisma_modifier)


def get_aura_radius(paladin_level: int) -> int:
    """
    Get the radius of Paladin auras.

    D&D 5e Rule:
    - Level 6-17: 10ft radius
    - Level 18+: 30ft radius

    Args:
        paladin_level: Paladin class level

    Returns:
        Aura radius in feet
    """
    if paladin_level >= 18:
        return 30
    elif paladin_level >= 6:
        return 10
    return 0


# ============================================================================
# DEFLECT MISSILES (Monk)
# ============================================================================

def use_deflect_missiles(
    incoming_damage: int,
    dexterity_modifier: int,
    monk_level: int,
    ki_points: int = 0
) -> FeatureUseResult:
    """
    Use Deflect Missiles to reduce ranged weapon damage.

    D&D 5e Rule:
    - Reduce damage by 1d10 + DEX mod + monk level
    - If reduced to 0, you catch the missile
    - Can spend 1 ki to throw it back (ranged attack, 20/60, monk weapon damage)

    Args:
        incoming_damage: The ranged attack damage
        dexterity_modifier: Monk's DEX modifier
        monk_level: Monk class level
        ki_points: Available ki points (for throwing back)

    Returns:
        FeatureUseResult with damage reduction details
    """
    if monk_level < 3:
        return FeatureUseResult(
            success=False,
            value=0,
            description="Deflect Missiles not available until level 3"
        )

    from app.core.dice import roll_damage

    # Roll 1d10 + DEX + level
    deflect_roll = roll_damage("1d10")
    reduction = deflect_roll.total + dexterity_modifier + monk_level
    final_damage = max(0, incoming_damage - reduction)
    caught = final_damage == 0

    result_data = {
        "reduction_roll": deflect_roll.total,
        "dex_mod": dexterity_modifier,
        "monk_level": monk_level,
        "total_reduction": reduction,
        "final_damage": final_damage,
        "caught": caught,
        "can_throw_back": caught and ki_points >= 1
    }

    if caught:
        if ki_points >= 1:
            desc = f"Deflect Missiles catches the projectile! (1d10+{dexterity_modifier}+{monk_level}={reduction}). Can spend 1 ki to throw it back."
        else:
            desc = f"Deflect Missiles catches the projectile! (1d10+{dexterity_modifier}+{monk_level}={reduction})"
    else:
        desc = f"Deflect Missiles reduces damage by {reduction}. {final_damage} damage taken."

    return FeatureUseResult(
        success=True,
        value=reduction,
        description=desc,
        extra_data=result_data
    )


# ============================================================================
# UNCANNY DODGE (Rogue)
# ============================================================================

def use_uncanny_dodge(incoming_damage: int) -> FeatureUseResult:
    """
    Use Uncanny Dodge to halve attack damage.

    D&D 5e Rule:
    - When an attacker you can see hits you
    - Use your reaction to halve the damage

    Args:
        incoming_damage: The attack damage before Uncanny Dodge

    Returns:
        FeatureUseResult with halved damage
    """
    halved_damage = incoming_damage // 2
    reduction = incoming_damage - halved_damage

    return FeatureUseResult(
        success=True,
        value=halved_damage,
        description=f"Uncanny Dodge halves the damage! ({incoming_damage} → {halved_damage})",
        extra_data={
            "original_damage": incoming_damage,
            "final_damage": halved_damage,
            "damage_reduced": reduction
        }
    )


# ============================================================================
# DANGER SENSE (Barbarian)
# ============================================================================

def has_danger_sense(barbarian_level: int) -> bool:
    """
    Check if Barbarian has Danger Sense.

    D&D 5e Rule:
    - Level 2+: Advantage on DEX saves against effects you can see
    - Cannot be blinded, deafened, or incapacitated

    Args:
        barbarian_level: Barbarian class level

    Returns:
        True if Danger Sense is available
    """
    return barbarian_level >= 2


# ============================================================================
# STUNNING STRIKE (Monk)
# ============================================================================

def use_stunning_strike(
    ki_points: int,
    target_con_save: int,
    monk_dc: int
) -> FeatureUseResult:
    """
    Attempt Stunning Strike on a hit.

    D&D 5e Rule:
    - Spend 1 ki point when you hit
    - Target makes CON save vs Ki save DC
    - On failure: Stunned until end of your next turn

    Args:
        ki_points: Available ki points
        target_con_save: Target's CON save roll result
        monk_dc: Monk's Ki save DC (8 + prof + WIS mod)

    Returns:
        FeatureUseResult with stun success/failure
    """
    if ki_points < 1:
        return FeatureUseResult(
            success=False,
            value=0,
            description="Not enough ki points for Stunning Strike"
        )

    stunned = target_con_save < monk_dc

    return FeatureUseResult(
        success=True,
        value=1 if stunned else 0,
        description=f"Stunning Strike {'stuns' if stunned else 'fails'}! (Save {target_con_save} vs DC {monk_dc})",
        extra_data={
            "ki_spent": 1,
            "target_stunned": stunned,
            "save_roll": target_con_save,
            "dc": monk_dc
        }
    )


# =============================================================================
# MULTICLASS FEATURE SUPPORT
# =============================================================================

def get_multiclass_features(
    class_levels: Dict[str, int],
    subclasses: Optional[Dict[str, str]] = None
) -> Dict[str, List[ClassFeature]]:
    """
    Get all available features for a multiclass character.

    Each class's features are determined by that class's level, not total level.
    Features from different classes stack (no conflict resolution needed).

    Args:
        class_levels: Dict of class_name -> level in that class
        subclasses: Optional dict of class_name -> subclass_name

    Returns:
        Dict of class_name -> list of ClassFeature objects
    """
    subclasses = subclasses or {}
    result = {}

    for class_name, level in class_levels.items():
        class_lower = class_name.lower()
        features = get_class_features(class_lower, level)
        if features:
            result[class_name] = features

    return result


def get_multiclass_features_flat(
    class_levels: Dict[str, int],
    subclasses: Optional[Dict[str, str]] = None
) -> List[ClassFeature]:
    """
    Get all features for a multiclass character as a flat list.

    Args:
        class_levels: Dict of class_name -> level in that class
        subclasses: Optional dict of class_name -> subclass_name

    Returns:
        Flat list of all ClassFeature objects
    """
    features_by_class = get_multiclass_features(class_levels, subclasses)
    all_features = []
    for features in features_by_class.values():
        all_features.extend(features)
    return all_features


def get_multiclass_extra_attacks(class_levels: Dict[str, int]) -> int:
    """
    Get the number of extra attacks for a multiclass character.

    Per D&D 5e rules, Extra Attack doesn't stack between classes.
    Use the highest value from any class.

    Args:
        class_levels: Dict of class_name -> level in that class

    Returns:
        Highest number of extra attacks from any class
    """
    max_extra = 0
    for class_name, level in class_levels.items():
        extra = get_extra_attack_count(class_name, level)
        if extra > max_extra:
            max_extra = extra
    return max_extra


def get_multiclass_feature_summary(
    class_levels: Dict[str, int],
    subclasses: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Get a summary of all features for a multiclass character.

    Args:
        class_levels: Dict of class_name -> level in that class
        subclasses: Optional dict of class_name -> subclass_name

    Returns:
        Summary dict with features organized by type and class
    """
    features_by_class = get_multiclass_features(class_levels, subclasses)

    # Organize features by type
    passive_features = []
    action_features = []
    bonus_action_features = []
    reaction_features = []
    other_features = []

    for class_name, features in features_by_class.items():
        for feature in features:
            feature_info = {
                "id": feature.id,
                "name": feature.name,
                "description": feature.description,
                "class": class_name,
                "resource_type": feature.resource_type.value,
                "uses_per_rest": feature.uses_per_rest,
            }

            if feature.feature_type == FeatureType.PASSIVE:
                passive_features.append(feature_info)
            elif feature.feature_type == FeatureType.ACTION:
                action_features.append(feature_info)
            elif feature.feature_type == FeatureType.BONUS_ACTION:
                bonus_action_features.append(feature_info)
            elif feature.feature_type == FeatureType.REACTION:
                reaction_features.append(feature_info)
            else:
                other_features.append(feature_info)

    return {
        "passive": passive_features,
        "action": action_features,
        "bonus_action": bonus_action_features,
        "reaction": reaction_features,
        "other": other_features,
        "extra_attacks": get_multiclass_extra_attacks(class_levels),
        "total_features": sum(len(f) for f in features_by_class.values()),
        "classes": list(class_levels.keys()),
    }


def has_feature(
    class_levels: Dict[str, int],
    feature_id: str,
    subclasses: Optional[Dict[str, str]] = None
) -> bool:
    """
    Check if a multiclass character has a specific feature.

    Args:
        class_levels: Dict of class_name -> level in that class
        feature_id: The feature ID to check
        subclasses: Optional dict of class_name -> subclass_name

    Returns:
        True if character has the feature
    """
    features = get_multiclass_features_flat(class_levels, subclasses)
    return any(f.id == feature_id for f in features)


def get_feature_uses_remaining(
    class_levels: Dict[str, int],
    feature_id: str,
    current_uses: Dict[str, int]
) -> int:
    """
    Get remaining uses of a feature for a multiclass character.

    Args:
        class_levels: Dict of class_name -> level
        feature_id: The feature ID
        current_uses: Dict of feature_id -> uses spent

    Returns:
        Remaining uses (-1 for unlimited)
    """
    for class_name, level in class_levels.items():
        feature = get_feature_by_id(class_name, feature_id)
        if feature:
            if feature.resource_type == ResourceType.NONE:
                return -1  # Unlimited

            max_uses = feature.uses_per_rest
            if feature.resource_type == ResourceType.PROFICIENCY_PER_LONG_REST:
                # Uses = proficiency bonus
                total_level = sum(class_levels.values())
                max_uses = 2 + ((total_level - 1) // 4)

            spent = current_uses.get(feature_id, 0)
            return max(0, max_uses - spent)

    return 0  # Feature not found
