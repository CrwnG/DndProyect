"""
Reactions System.

Handles reaction economy and specific reaction abilities like:
- Opportunity Attacks
- Shield spell
- Counterspell
- Absorb Elements
- Ready action triggers
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Callable

from app.core.dice import roll_d20


class ReactionType(Enum):
    """Types of reactions available."""
    OPPORTUNITY_ATTACK = "opportunity_attack"
    SHIELD = "shield"
    COUNTERSPELL = "counterspell"
    ABSORB_ELEMENTS = "absorb_elements"
    HELLISH_REBUKE = "hellish_rebuke"
    UNCANNY_DODGE = "uncanny_dodge"
    READIED_ACTION = "readied_action"
    PARRY = "parry"  # Defensive Duelist
    RIPOSTE = "riposte"  # Battlemaster


class ReactionTrigger(Enum):
    """What triggers a reaction."""
    ENEMY_LEAVES_REACH = "enemy_leaves_reach"
    BEING_HIT = "being_hit"
    BEING_ATTACKED = "being_attacked"
    BEING_MISSED = "being_missed"  # For Riposte
    ENEMY_CASTS_SPELL = "enemy_casts_spell"
    TAKING_DAMAGE = "taking_damage"
    ALLY_ATTACKED = "ally_attacked"
    ENEMY_DISENGAGES = "enemy_disengages"  # For Sentinel
    ENEMY_ATTACKS_ALLY = "enemy_attacks_ally"  # For Sentinel
    ENEMY_ENTERS_REACH = "enemy_enters_reach"  # For Polearm Master
    CUSTOM = "custom"  # For readied actions


@dataclass
class ReactionResult:
    """Result of using a reaction."""
    success: bool
    reaction_type: str
    description: str
    damage_dealt: int = 0
    damage_prevented: int = 0
    spell_countered: bool = False
    ac_bonus: int = 0
    effects_applied: List[str] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReactionOption:
    """An available reaction a combatant can take."""
    reaction_type: ReactionType
    trigger: ReactionTrigger
    trigger_source_id: str  # Who/what triggered it
    can_use: bool  # Has reaction available, meets requirements
    description: str
    cost: Optional[str] = None  # e.g., "1st level spell slot"
    extra_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReactionState:
    """Tracks a combatant's reaction availability."""
    combatant_id: str
    reaction_available: bool = True
    readied_action: Optional[Dict[str, Any]] = None
    reaction_used_this_round: bool = False

    def use_reaction(self) -> bool:
        """Attempt to use reaction. Returns True if successful."""
        if self.reaction_available:
            self.reaction_available = False
            self.reaction_used_this_round = True
            return True
        return False

    def reset_for_round(self) -> None:
        """Reset reaction at the start of combatant's turn."""
        self.reaction_available = True
        self.reaction_used_this_round = False


class ReactionsManager:
    """
    Manages reactions for all combatants in combat.

    Handles:
    - Tracking reaction availability
    - Determining when reactions can be triggered
    - Resolving reaction effects
    """

    def __init__(self):
        """Initialize the reactions manager."""
        self.reaction_states: Dict[str, ReactionState] = {}

    def register_combatant(self, combatant_id: str) -> None:
        """Register a combatant for reaction tracking."""
        if combatant_id not in self.reaction_states:
            self.reaction_states[combatant_id] = ReactionState(
                combatant_id=combatant_id
            )

    def remove_combatant(self, combatant_id: str) -> None:
        """Remove a combatant from tracking."""
        self.reaction_states.pop(combatant_id, None)

    def get_reaction_state(self, combatant_id: str) -> Optional[ReactionState]:
        """Get a combatant's reaction state."""
        return self.reaction_states.get(combatant_id)

    def has_reaction_available(self, combatant_id: str) -> bool:
        """Check if combatant can use a reaction."""
        state = self.reaction_states.get(combatant_id)
        return state is not None and state.reaction_available

    def use_reaction(self, combatant_id: str) -> bool:
        """Mark reaction as used. Returns True if successful."""
        state = self.reaction_states.get(combatant_id)
        if state:
            return state.use_reaction()
        return False

    def reset_combatant_reaction(self, combatant_id: str) -> None:
        """Reset reaction at the start of combatant's turn."""
        state = self.reaction_states.get(combatant_id)
        if state:
            state.reset_for_round()

    def set_readied_action(
        self,
        combatant_id: str,
        action: str,
        trigger: str,
        extra_data: Optional[Dict] = None
    ) -> bool:
        """Set a readied action for a combatant."""
        state = self.reaction_states.get(combatant_id)
        if state:
            state.readied_action = {
                "action": action,
                "trigger": trigger,
                "extra_data": extra_data or {}
            }
            return True
        return False

    def clear_readied_action(self, combatant_id: str) -> None:
        """Clear a readied action (used or expired)."""
        state = self.reaction_states.get(combatant_id)
        if state:
            state.readied_action = None


# =============================================================================
# REACTION IMPLEMENTATIONS
# =============================================================================

def resolve_opportunity_attack(
    attacker_id: str,
    attacker_name: str,
    target_id: str,
    target_name: str,
    attack_bonus: int,
    target_ac: int,
    damage_dice: str,
    damage_modifier: int = 0
) -> ReactionResult:
    """
    Resolve an opportunity attack.

    Opportunity attacks are triggered when an enemy leaves your reach
    without taking the Disengage action.

    Args:
        attacker_id: ID of the attacking combatant
        attacker_name: Name of attacker
        target_id: ID of the fleeing combatant
        target_name: Name of target
        attack_bonus: Attacker's attack bonus
        target_ac: Target's AC
        damage_dice: Damage dice notation
        damage_modifier: Damage modifier

    Returns:
        ReactionResult with attack outcome
    """
    from app.core.rules_engine import resolve_attack, DamageType

    # Make the attack
    attack_result = resolve_attack(
        attack_bonus=attack_bonus,
        target_ac=target_ac,
        damage_dice=damage_dice,
        damage_modifier=damage_modifier,
        damage_type=DamageType.SLASHING  # Default, could be parameterized
    )

    if attack_result.hit:
        damage = attack_result.total_damage

        if attack_result.critical_hit:
            desc = f"{attacker_name} lands a critical opportunity attack on {target_name} for {damage} damage!"
        else:
            desc = f"{attacker_name} makes an opportunity attack against {target_name}, dealing {damage} damage"

        return ReactionResult(
            success=True,
            reaction_type=ReactionType.OPPORTUNITY_ATTACK.value,
            description=desc,
            damage_dealt=damage,
            extra_data={
                "attack_roll": attack_result.attack_roll.total,
                "critical": attack_result.critical_hit,
                "target_id": target_id
            }
        )
    else:
        desc = f"{attacker_name}'s opportunity attack against {target_name} misses"
        return ReactionResult(
            success=True,  # Reaction was used, even if attack missed
            reaction_type=ReactionType.OPPORTUNITY_ATTACK.value,
            description=desc,
            damage_dealt=0,
            extra_data={
                "attack_roll": attack_result.attack_roll.total,
                "target_id": target_id,
                "hit": False
            }
        )


def resolve_shield_spell(
    caster_id: str,
    caster_name: str,
    attack_roll: int,
    current_ac: int,
    has_spell_slot: bool = True
) -> ReactionResult:
    """
    Resolve the Shield spell reaction.

    Shield gives +5 AC until the start of your next turn.
    Can be cast after seeing the attack roll but before damage.

    Args:
        caster_id: ID of the caster
        caster_name: Name of caster
        attack_roll: The incoming attack roll
        current_ac: Caster's current AC
        has_spell_slot: Whether caster has a 1st level slot

    Returns:
        ReactionResult with spell outcome
    """
    if not has_spell_slot:
        return ReactionResult(
            success=False,
            reaction_type=ReactionType.SHIELD.value,
            description=f"{caster_name} has no spell slots for Shield"
        )

    new_ac = current_ac + 5
    would_miss = attack_roll < new_ac

    if would_miss:
        desc = f"{caster_name} casts Shield! AC becomes {new_ac} - the attack misses!"
    else:
        desc = f"{caster_name} casts Shield! AC becomes {new_ac} - but the attack still hits"

    return ReactionResult(
        success=True,
        reaction_type=ReactionType.SHIELD.value,
        description=desc,
        ac_bonus=5,
        effects_applied=["shield"],
        extra_data={
            "new_ac": new_ac,
            "attack_would_miss": would_miss,
            "spell_slot_used": 1
        }
    )


def resolve_counterspell(
    caster_id: str,
    caster_name: str,
    spell_level: int,
    slot_used: int,
    caster_ability_mod: int = 0,
    target_spell_name: str = "a spell"
) -> ReactionResult:
    """
    Resolve the Counterspell reaction.

    Automatically counters spells of slot level or lower.
    Higher level spells require an ability check (DC = 10 + spell level).

    Args:
        caster_id: ID of the counterspelling caster
        caster_name: Name of caster
        spell_level: Level of the spell being countered
        slot_used: Level of slot used for Counterspell
        caster_ability_mod: Spellcasting ability modifier
        target_spell_name: Name of spell being countered

    Returns:
        ReactionResult with counterspell outcome
    """
    if slot_used >= spell_level:
        # Automatic success
        return ReactionResult(
            success=True,
            reaction_type=ReactionType.COUNTERSPELL.value,
            description=f"{caster_name} counters {target_spell_name}!",
            spell_countered=True,
            extra_data={
                "slot_used": slot_used,
                "target_spell_level": spell_level,
                "automatic": True
            }
        )

    # Need ability check
    dc = 10 + spell_level
    check = roll_d20(modifier=caster_ability_mod)

    if check.total >= dc:
        return ReactionResult(
            success=True,
            reaction_type=ReactionType.COUNTERSPELL.value,
            description=f"{caster_name} counters {target_spell_name}! (Check: {check.total} vs DC {dc})",
            spell_countered=True,
            extra_data={
                "slot_used": slot_used,
                "target_spell_level": spell_level,
                "check_roll": check.total,
                "dc": dc
            }
        )
    else:
        return ReactionResult(
            success=True,  # Reaction was used
            reaction_type=ReactionType.COUNTERSPELL.value,
            description=f"{caster_name} fails to counter {target_spell_name} (Check: {check.total} vs DC {dc})",
            spell_countered=False,
            extra_data={
                "slot_used": slot_used,
                "target_spell_level": spell_level,
                "check_roll": check.total,
                "dc": dc
            }
        )


def resolve_absorb_elements(
    caster_id: str,
    caster_name: str,
    damage_type: str,
    damage_amount: int,
    slot_used: int = 1
) -> ReactionResult:
    """
    Resolve the Absorb Elements spell.

    Gives resistance to the triggering damage and adds 1d6 damage
    (per slot level) to your next melee attack.

    Args:
        caster_id: ID of the caster
        caster_name: Name of caster
        damage_type: Type of damage being absorbed
        damage_amount: Amount of incoming damage
        slot_used: Spell slot level used

    Returns:
        ReactionResult with spell outcome
    """
    # Calculate damage reduction (resistance = half)
    damage_prevented = damage_amount // 2

    # Calculate bonus damage for next attack
    bonus_dice = f"{slot_used}d6"

    return ReactionResult(
        success=True,
        reaction_type=ReactionType.ABSORB_ELEMENTS.value,
        description=f"{caster_name} absorbs {damage_type} damage! Takes {damage_amount - damage_prevented} instead of {damage_amount}",
        damage_prevented=damage_prevented,
        effects_applied=["absorb_elements"],
        extra_data={
            "damage_type": damage_type,
            "original_damage": damage_amount,
            "damage_taken": damage_amount - damage_prevented,
            "bonus_melee_damage": bonus_dice,
            "slot_used": slot_used
        }
    )


def resolve_uncanny_dodge(
    rogue_id: str,
    rogue_name: str,
    damage_amount: int
) -> ReactionResult:
    """
    Resolve Uncanny Dodge (Rogue feature).

    Halves the damage from an attack you can see.

    Args:
        rogue_id: ID of the rogue
        rogue_name: Name of rogue
        damage_amount: Incoming damage

    Returns:
        ReactionResult with halved damage
    """
    halved = damage_amount // 2
    damage_prevented = damage_amount - halved

    return ReactionResult(
        success=True,
        reaction_type=ReactionType.UNCANNY_DODGE.value,
        description=f"{rogue_name} uses Uncanny Dodge! Takes {halved} damage instead of {damage_amount}",
        damage_prevented=damage_prevented,
        extra_data={
            "original_damage": damage_amount,
            "damage_taken": halved
        }
    )


def resolve_hellish_rebuke(
    caster_id: str,
    caster_name: str,
    target_id: str,
    target_name: str,
    target_dex_mod: int,
    slot_used: int = 1,
    spell_dc: int = 13
) -> ReactionResult:
    """
    Resolve Hellish Rebuke.

    When you take damage, the attacker must make a DEX save
    or take 2d10 (+ 1d10/slot above 1st) fire damage.

    Args:
        caster_id: ID of the caster
        caster_name: Name of caster
        target_id: ID of the attacker
        target_name: Name of attacker
        target_dex_mod: Target's DEX modifier
        slot_used: Spell slot level
        spell_dc: Spell save DC

    Returns:
        ReactionResult with damage result
    """
    from app.core.dice import roll_damage

    # Target makes DEX save
    save = roll_d20(modifier=target_dex_mod)
    save_success = save.total >= spell_dc

    # Calculate damage
    dice_count = 1 + slot_used
    damage_result = roll_damage(f"{dice_count}d10")
    full_damage = damage_result.total

    if save_success:
        damage = full_damage // 2
        desc = f"{caster_name} casts Hellish Rebuke! {target_name} saves and takes {damage} fire damage"
    else:
        damage = full_damage
        desc = f"{caster_name} casts Hellish Rebuke! {target_name} takes {damage} fire damage"

    return ReactionResult(
        success=True,
        reaction_type=ReactionType.HELLISH_REBUKE.value,
        description=desc,
        damage_dealt=damage,
        extra_data={
            "target_id": target_id,
            "save_roll": save.total,
            "save_dc": spell_dc,
            "save_success": save_success,
            "slot_used": slot_used
        }
    )


def resolve_parry(
    defender_id: str,
    defender_name: str,
    proficiency_bonus: int,
    attack_roll: int,
    current_ac: int
) -> ReactionResult:
    """
    Resolve Parry (Defensive Duelist feat).

    Add proficiency bonus to AC against one melee attack.

    Args:
        defender_id: ID of defender
        defender_name: Name of defender
        proficiency_bonus: Proficiency bonus to add
        attack_roll: The incoming attack roll
        current_ac: Current AC

    Returns:
        ReactionResult with parry outcome
    """
    new_ac = current_ac + proficiency_bonus
    would_miss = attack_roll < new_ac

    if would_miss:
        desc = f"{defender_name} parries! AC becomes {new_ac} - the attack misses!"
    else:
        desc = f"{defender_name} parries, raising AC to {new_ac}, but the attack still hits"

    return ReactionResult(
        success=True,
        reaction_type=ReactionType.PARRY.value,
        description=desc,
        ac_bonus=proficiency_bonus,
        extra_data={
            "new_ac": new_ac,
            "attack_would_miss": would_miss
        }
    )


def resolve_riposte(
    attacker_id: str,
    attacker_name: str,
    target_id: str,
    target_name: str,
    attack_bonus: int,
    target_ac: int,
    damage_dice: str,
    damage_modifier: int = 0,
    superiority_die: str = "1d8"
) -> ReactionResult:
    """
    Resolve Riposte (Battlemaster maneuver).

    When a creature misses you with a melee attack, use reaction
    and expend one Superiority Die to make a melee attack.
    Add Superiority Die to damage on hit.

    Args:
        attacker_id: ID of the riposting combatant
        attacker_name: Name of attacker
        target_id: ID of the creature that missed
        target_name: Name of target
        attack_bonus: Attacker's attack bonus
        target_ac: Target's AC
        damage_dice: Weapon damage dice
        damage_modifier: Damage modifier
        superiority_die: Superiority die to add (e.g., "1d8", "1d10", "1d12")

    Returns:
        ReactionResult with riposte outcome
    """
    from app.core.rules_engine import resolve_attack, DamageType
    from app.core.dice import roll_damage

    # Make the attack
    attack_result = resolve_attack(
        attack_bonus=attack_bonus,
        target_ac=target_ac,
        damage_dice=damage_dice,
        damage_modifier=damage_modifier,
        damage_type=DamageType.SLASHING
    )

    if attack_result.hit:
        # Roll superiority die and add to damage
        superiority_roll = roll_damage(superiority_die)
        total_damage = attack_result.total_damage + superiority_roll.total

        if attack_result.critical_hit:
            desc = f"{attacker_name} ripostes with a critical hit against {target_name} for {total_damage} damage! (Superiority: +{superiority_roll.total})"
        else:
            desc = f"{attacker_name} ripostes against {target_name}, dealing {total_damage} damage! (Superiority: +{superiority_roll.total})"

        return ReactionResult(
            success=True,
            reaction_type=ReactionType.RIPOSTE.value,
            description=desc,
            damage_dealt=total_damage,
            extra_data={
                "attack_roll": attack_result.attack_roll.total,
                "critical": attack_result.critical_hit,
                "target_id": target_id,
                "superiority_die_roll": superiority_roll.total,
                "superiority_die_used": True
            }
        )
    else:
        desc = f"{attacker_name}'s riposte against {target_name} misses (Superiority Die expended)"
        return ReactionResult(
            success=True,  # Reaction was used, even if attack missed
            reaction_type=ReactionType.RIPOSTE.value,
            description=desc,
            damage_dealt=0,
            extra_data={
                "attack_roll": attack_result.attack_roll.total,
                "target_id": target_id,
                "hit": False,
                "superiority_die_used": True
            }
        )


def resolve_sentinel_opportunity_attack(
    attacker_id: str,
    attacker_name: str,
    target_id: str,
    target_name: str,
    attack_bonus: int,
    target_ac: int,
    damage_dice: str,
    damage_modifier: int = 0,
    trigger_reason: str = "leaving reach"
) -> ReactionResult:
    """
    Resolve a Sentinel opportunity attack.

    Sentinel feat allows OA when:
    - Creature within 5ft takes Disengage action
    - Creature within 5ft hits an ally (not you)

    On hit, target's speed becomes 0 for the rest of the turn.

    Args:
        attacker_id: ID of the Sentinel combatant
        attacker_name: Name of attacker
        target_id: ID of the target
        target_name: Name of target
        attack_bonus: Attacker's attack bonus
        target_ac: Target's AC
        damage_dice: Damage dice notation
        damage_modifier: Damage modifier
        trigger_reason: What triggered this OA

    Returns:
        ReactionResult with attack outcome and speed reduction
    """
    from app.core.rules_engine import resolve_attack, DamageType

    # Make the attack
    attack_result = resolve_attack(
        attack_bonus=attack_bonus,
        target_ac=target_ac,
        damage_dice=damage_dice,
        damage_modifier=damage_modifier,
        damage_type=DamageType.SLASHING
    )

    if attack_result.hit:
        damage = attack_result.total_damage

        if attack_result.critical_hit:
            desc = f"{attacker_name} lands a critical Sentinel attack on {target_name} (triggered by {trigger_reason}) for {damage} damage! {target_name}'s speed becomes 0!"
        else:
            desc = f"{attacker_name} makes a Sentinel attack against {target_name} (triggered by {trigger_reason}), dealing {damage} damage! {target_name}'s speed becomes 0!"

        return ReactionResult(
            success=True,
            reaction_type=ReactionType.OPPORTUNITY_ATTACK.value,
            description=desc,
            damage_dealt=damage,
            effects_applied=["speed_zero"],
            extra_data={
                "attack_roll": attack_result.attack_roll.total,
                "critical": attack_result.critical_hit,
                "target_id": target_id,
                "sentinel": True,
                "speed_reduced_to_zero": True,
                "trigger_reason": trigger_reason
            }
        )
    else:
        desc = f"{attacker_name}'s Sentinel attack against {target_name} misses"
        return ReactionResult(
            success=True,
            reaction_type=ReactionType.OPPORTUNITY_ATTACK.value,
            description=desc,
            damage_dealt=0,
            extra_data={
                "attack_roll": attack_result.attack_roll.total,
                "target_id": target_id,
                "hit": False,
                "sentinel": True
            }
        )


def check_available_reactions(
    combatant_id: str,
    trigger: ReactionTrigger,
    trigger_source_id: str,
    reactions_manager: ReactionsManager,
    combatant_abilities: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> List[ReactionOption]:
    """
    Check what reactions a combatant can take for a given trigger.

    Args:
        combatant_id: ID of the potential reactor
        trigger: What triggered the check
        trigger_source_id: Who/what caused the trigger
        reactions_manager: The reactions manager
        combatant_abilities: Dict of combatant's abilities/spells
        context: Additional context (attack roll, damage, etc.)

    Returns:
        List of available reaction options
    """
    options = []
    context = context or {}

    # Check if reaction is available
    if not reactions_manager.has_reaction_available(combatant_id):
        return []

    # Opportunity Attack - triggered when enemy leaves reach
    if trigger == ReactionTrigger.ENEMY_LEAVES_REACH:
        if combatant_abilities.get("can_opportunity_attack", True):
            options.append(ReactionOption(
                reaction_type=ReactionType.OPPORTUNITY_ATTACK,
                trigger=trigger,
                trigger_source_id=trigger_source_id,
                can_use=True,
                description=f"Make an opportunity attack"
            ))

    # Shield spell - triggered when being attacked
    if trigger == ReactionTrigger.BEING_ATTACKED:
        if combatant_abilities.get("knows_shield", False):
            has_slot = combatant_abilities.get("spell_slots_1st", 0) > 0
            options.append(ReactionOption(
                reaction_type=ReactionType.SHIELD,
                trigger=trigger,
                trigger_source_id=trigger_source_id,
                can_use=has_slot,
                description="Cast Shield (+5 AC)",
                cost="1st level spell slot"
            ))

    # Uncanny Dodge - triggered when being hit
    if trigger == ReactionTrigger.BEING_HIT:
        if combatant_abilities.get("uncanny_dodge", False):
            options.append(ReactionOption(
                reaction_type=ReactionType.UNCANNY_DODGE,
                trigger=trigger,
                trigger_source_id=trigger_source_id,
                can_use=True,
                description="Use Uncanny Dodge (halve damage)"
            ))

    # Parry - triggered when being attacked
    if trigger == ReactionTrigger.BEING_ATTACKED:
        if combatant_abilities.get("defensive_duelist", False):
            options.append(ReactionOption(
                reaction_type=ReactionType.PARRY,
                trigger=trigger,
                trigger_source_id=trigger_source_id,
                can_use=True,
                description="Parry (add proficiency to AC)"
            ))

    # Counterspell - triggered when enemy casts spell
    if trigger == ReactionTrigger.ENEMY_CASTS_SPELL:
        if combatant_abilities.get("knows_counterspell", False):
            for slot_level in [3, 4, 5, 6, 7, 8, 9]:
                slot_key = f"spell_slots_{slot_level}"
                if combatant_abilities.get(slot_key, 0) > 0:
                    options.append(ReactionOption(
                        reaction_type=ReactionType.COUNTERSPELL,
                        trigger=trigger,
                        trigger_source_id=trigger_source_id,
                        can_use=True,
                        description=f"Cast Counterspell at {slot_level}th level",
                        cost=f"{slot_level}th level spell slot",
                        extra_data={"slot_level": slot_level}
                    ))
                    break  # Only show one option (lowest available)

    # Hellish Rebuke - triggered when taking damage
    if trigger == ReactionTrigger.TAKING_DAMAGE:
        if combatant_abilities.get("knows_hellish_rebuke", False):
            has_slot = combatant_abilities.get("spell_slots_1st", 0) > 0
            options.append(ReactionOption(
                reaction_type=ReactionType.HELLISH_REBUKE,
                trigger=trigger,
                trigger_source_id=trigger_source_id,
                can_use=has_slot,
                description="Cast Hellish Rebuke",
                cost="1st level spell slot"
            ))

    # Absorb Elements - triggered when taking elemental damage
    if trigger == ReactionTrigger.TAKING_DAMAGE:
        damage_type = context.get("damage_type", "")
        elemental_types = ["fire", "cold", "lightning", "thunder", "acid"]
        if combatant_abilities.get("knows_absorb_elements", False):
            if damage_type.lower() in elemental_types:
                has_slot = combatant_abilities.get("spell_slots_1st", 0) > 0
                options.append(ReactionOption(
                    reaction_type=ReactionType.ABSORB_ELEMENTS,
                    trigger=trigger,
                    trigger_source_id=trigger_source_id,
                    can_use=has_slot,
                    description=f"Cast Absorb Elements (resist {damage_type})",
                    cost="1st level spell slot"
                ))

    # Riposte - triggered when being missed (Battlemaster maneuver)
    if trigger == ReactionTrigger.BEING_MISSED:
        if combatant_abilities.get("has_riposte", False):
            superiority_dice = combatant_abilities.get("superiority_dice", 0)
            if superiority_dice > 0:
                die_size = combatant_abilities.get("superiority_die", "1d8")
                options.append(ReactionOption(
                    reaction_type=ReactionType.RIPOSTE,
                    trigger=trigger,
                    trigger_source_id=trigger_source_id,
                    can_use=True,
                    description=f"Riposte (counter-attack + {die_size} damage)",
                    cost="1 Superiority Die",
                    extra_data={"superiority_die": die_size}
                ))

    # Sentinel - triggered when enemy disengages within reach
    if trigger == ReactionTrigger.ENEMY_DISENGAGES:
        if combatant_abilities.get("sentinel", False):
            if combatant_abilities.get("can_opportunity_attack", True):
                options.append(ReactionOption(
                    reaction_type=ReactionType.OPPORTUNITY_ATTACK,
                    trigger=trigger,
                    trigger_source_id=trigger_source_id,
                    can_use=True,
                    description="Sentinel Attack (OA on Disengage, stops movement)",
                    extra_data={"sentinel": True, "trigger_reason": "disengaging"}
                ))

    # Sentinel - triggered when enemy attacks ally within reach
    if trigger == ReactionTrigger.ENEMY_ATTACKS_ALLY:
        if combatant_abilities.get("sentinel", False):
            if combatant_abilities.get("can_opportunity_attack", True):
                options.append(ReactionOption(
                    reaction_type=ReactionType.OPPORTUNITY_ATTACK,
                    trigger=trigger,
                    trigger_source_id=trigger_source_id,
                    can_use=True,
                    description="Sentinel Attack (OA when ally is attacked, stops movement)",
                    extra_data={"sentinel": True, "trigger_reason": "attacking ally"}
                ))

    # Polearm Master - triggered when enemy enters reach
    if trigger == ReactionTrigger.ENEMY_ENTERS_REACH:
        if combatant_abilities.get("polearm_master", False):
            if combatant_abilities.get("can_opportunity_attack", True):
                options.append(ReactionOption(
                    reaction_type=ReactionType.OPPORTUNITY_ATTACK,
                    trigger=trigger,
                    trigger_source_id=trigger_source_id,
                    can_use=True,
                    description="Polearm Master Attack (OA on approach)"
                ))

    # Readied Action
    if trigger == ReactionTrigger.CUSTOM:
        state = reactions_manager.get_reaction_state(combatant_id)
        if state and state.readied_action:
            options.append(ReactionOption(
                reaction_type=ReactionType.READIED_ACTION,
                trigger=trigger,
                trigger_source_id=trigger_source_id,
                can_use=True,
                description=f"Take readied action: {state.readied_action.get('action', 'action')}",
                extra_data=state.readied_action
            ))

    return options
