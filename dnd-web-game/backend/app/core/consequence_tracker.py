"""
Consequence Tracker for Campaign Choices.

Implements BG3-style consequence system where:
- Player choices have immediate effects
- Some effects trigger later (delayed consequences)
- NPC relationships evolve based on choices
- Story branches based on accumulated decisions
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from app.models.campaign import (
    WorldState,
    DelayedConsequence,
    ConsequenceEffectType,
    ChoiceRecord,
    Encounter,
)

logger = logging.getLogger(__name__)


@dataclass
class ConsequenceEffect:
    """Result of a triggered consequence."""
    effect_type: ConsequenceEffectType
    target: str  # What was affected (flag name, NPC ID, encounter ID, etc.)
    params: Dict[str, Any]
    narrative_text: str  # Text to show player
    source_choice_id: str  # Which choice caused this


class ConsequenceTracker:
    """
    Tracks how player choices ripple through the campaign.

    BG3-style consequences:
    - Immediate effects (flag set, NPC reaction)
    - Short-term effects (manifest within 1-2 encounters)
    - Long-term effects (manifest chapters/acts later)
    - Compound effects (multiple choices combine)
    - NPC memory (characters remember how you treated them)
    """

    def __init__(self, world_state: WorldState):
        self.world_state = world_state

    # =========================================================================
    # CHOICE RECORDING
    # =========================================================================

    def record_choice(
        self,
        choice_id: str,
        encounter_id: str,
        outcome: str,
        context: Dict[str, Any] = None,
    ) -> List[ConsequenceEffect]:
        """
        Record a player choice and return immediate effects.

        Args:
            choice_id: ID of the choice made
            encounter_id: ID of the encounter where choice was made
            outcome: Result of the choice (success, failure, specific outcome)
            context: Additional context (party member who made choice, etc.)

        Returns:
            List of immediate effects triggered
        """
        # Record the choice
        self.world_state.record_choice(
            choice_id=choice_id,
            encounter_id=encounter_id,
            outcome=outcome,
            context=context,
        )

        self.world_state.encounters_completed += 1

        logger.info(f"Recorded choice: {choice_id} -> {outcome}")

        # Get immediate effects from the choice definition
        # (These would be defined in the encounter/choice data)
        immediate_effects = context.get("immediate_effects", []) if context else []

        return self._process_immediate_effects(choice_id, immediate_effects)

    def _process_immediate_effects(
        self,
        choice_id: str,
        effects: List[Dict[str, Any]],
    ) -> List[ConsequenceEffect]:
        """Process immediate effects from a choice."""
        results = []

        for effect_data in effects:
            effect = self._apply_effect(choice_id, effect_data)
            if effect:
                results.append(effect)

        return results

    # =========================================================================
    # CONSEQUENCE CHECKING
    # =========================================================================

    def check_triggers(
        self,
        encounter_id: str,
        current_act: str = None,
        current_chapter: str = None,
    ) -> List[ConsequenceEffect]:
        """
        Check if any delayed consequences should trigger.

        Called before each encounter to see if past choices
        should manifest their effects now.

        Args:
            encounter_id: ID of the upcoming encounter
            current_act: Current act ID (optional)
            current_chapter: Current chapter ID (optional)

        Returns:
            List of triggered consequence effects
        """
        triggered_effects = []

        for consequence in self.world_state.pending_consequences:
            if consequence.triggered:
                continue

            if self._should_trigger(consequence, encounter_id, current_act, current_chapter):
                effect = self._trigger_consequence(consequence)
                if effect:
                    triggered_effects.append(effect)

        return triggered_effects

    def _should_trigger(
        self,
        consequence: DelayedConsequence,
        encounter_id: str,
        current_act: str,
        current_chapter: str,
    ) -> bool:
        """Check if a consequence should trigger now."""
        condition = consequence.trigger_condition

        condition_type = condition.get("type", "")

        if condition_type == "encounter":
            # Trigger at specific encounter
            return condition.get("id") == encounter_id

        elif condition_type == "act":
            # Trigger at start of specific act
            return condition.get("act_id") == current_act

        elif condition_type == "chapter":
            # Trigger at start of specific chapter
            return condition.get("chapter_id") == current_chapter

        elif condition_type == "encounters_after":
            # Trigger after N encounters
            encounters_needed = condition.get("count", 1)
            choice_record = self._find_choice_record(consequence.trigger_choice_id)
            if choice_record:
                encounters_since = self.world_state.encounters_completed - \
                    self._get_encounter_count_at_choice(choice_record)
                return encounters_since >= encounters_needed

        elif condition_type == "chapters_delay":
            # Trigger after N chapters
            chapters_needed = condition.get("count", 1)
            # Simplified: use encounters as proxy (assume ~5 encounters per chapter)
            choice_record = self._find_choice_record(consequence.trigger_choice_id)
            if choice_record:
                encounters_since = self.world_state.encounters_completed - \
                    self._get_encounter_count_at_choice(choice_record)
                return encounters_since >= chapters_needed * 5

        elif condition_type == "flag_set":
            # Trigger when a specific flag is set
            return self.world_state.has_flag(condition.get("flag", ""))

        elif condition_type == "npc_disposition":
            # Trigger when NPC disposition reaches threshold
            npc_id = condition.get("npc_id", "")
            threshold = condition.get("threshold", 0)
            comparison = condition.get("comparison", ">=")
            current = self.world_state.get_npc_disposition(npc_id)

            if comparison == ">=":
                return current >= threshold
            elif comparison == "<=":
                return current <= threshold
            elif comparison == "==":
                return current == threshold

        return False

    def _trigger_consequence(
        self,
        consequence: DelayedConsequence,
    ) -> Optional[ConsequenceEffect]:
        """Trigger a delayed consequence and apply its effect."""
        consequence.triggered = True

        effect_data = {
            "type": consequence.effect_type.value,
            "params": consequence.effect_params,
            "narrative": consequence.narrative_text,
        }

        return self._apply_effect(consequence.trigger_choice_id, effect_data)

    def _find_choice_record(self, choice_id: str) -> Optional[ChoiceRecord]:
        """Find a choice record by ID."""
        for record in self.world_state.choice_history:
            if record.choice_id == choice_id:
                return record
        return None

    def _get_encounter_count_at_choice(self, choice_record: ChoiceRecord) -> int:
        """Get the encounter count when a choice was made."""
        # Store this in context when recording choice
        return choice_record.context.get("encounter_count", 0)

    # =========================================================================
    # EFFECT APPLICATION
    # =========================================================================

    def _apply_effect(
        self,
        source_choice_id: str,
        effect_data: Dict[str, Any],
    ) -> Optional[ConsequenceEffect]:
        """Apply a consequence effect to the world state."""
        effect_type_str = effect_data.get("type", "set_flag")
        params = effect_data.get("params", {})
        narrative = effect_data.get("narrative", "")

        try:
            effect_type = ConsequenceEffectType(effect_type_str)
        except ValueError:
            effect_type = ConsequenceEffectType.SET_FLAG

        target = ""

        if effect_type == ConsequenceEffectType.SET_FLAG:
            flag_name = params.get("flag", "")
            flag_value = params.get("value", True)
            self.world_state.set_flag(flag_name, flag_value)
            target = flag_name
            logger.debug(f"Set flag: {flag_name} = {flag_value}")

        elif effect_type == ConsequenceEffectType.MODIFY_NPC:
            npc_id = params.get("npc_id", "")
            delta = params.get("disposition_delta", 0)
            reason = params.get("reason", "")
            self.world_state.modify_npc_disposition(npc_id, delta, reason)
            target = npc_id
            logger.debug(f"Modified NPC disposition: {npc_id} by {delta}")

        elif effect_type == ConsequenceEffectType.UNLOCK_DIALOGUE:
            npc_id = params.get("npc_id", "")
            dialogue_id = params.get("dialogue_id", "")
            # Store as flag for now
            self.world_state.set_flag(f"dialogue_unlocked:{npc_id}:{dialogue_id}")
            target = dialogue_id
            logger.debug(f"Unlocked dialogue: {dialogue_id} for {npc_id}")

        elif effect_type == ConsequenceEffectType.UNLOCK_ENCOUNTER:
            encounter_id = params.get("encounter_id", "")
            self.world_state.set_flag(f"encounter_available:{encounter_id}")
            target = encounter_id
            logger.debug(f"Unlocked encounter: {encounter_id}")

        elif effect_type == ConsequenceEffectType.MODIFY_ENCOUNTER:
            encounter_id = params.get("encounter_id", "")
            modification = params.get("modification", "")
            self.world_state.set_flag(f"encounter_mod:{encounter_id}:{modification}")
            target = encounter_id
            logger.debug(f"Modified encounter: {encounter_id} with {modification}")

        elif effect_type == ConsequenceEffectType.GRANT_ITEM:
            item_id = params.get("item_id", "")
            # Store as variable
            current_items = self.world_state.get_var("granted_items", [])
            if isinstance(current_items, list):
                current_items.append(item_id)
                self.world_state.set_var("granted_items", current_items)
            target = item_id
            logger.debug(f"Granted item: {item_id}")

        elif effect_type == ConsequenceEffectType.NARRATIVE:
            # Just show the narrative text, no state change
            target = "narrative"
            logger.debug(f"Showing narrative: {narrative[:50]}...")

        return ConsequenceEffect(
            effect_type=effect_type,
            target=target,
            params=params,
            narrative_text=narrative,
            source_choice_id=source_choice_id,
        )

    # =========================================================================
    # NPC RELATIONSHIP QUERIES
    # =========================================================================

    def get_npc_disposition(self, npc_id: str, base: int = 0) -> int:
        """
        Get NPC's current disposition including all modifications.

        Args:
            npc_id: ID of the NPC
            base: Base disposition if not already tracked

        Returns:
            Current disposition value (-100 to 100)
        """
        return self.world_state.get_npc_disposition(npc_id, base)

    def get_relationship_tier(self, npc_id: str) -> str:
        """
        Get the relationship tier for an NPC.

        Returns:
            One of: "hostile", "unfriendly", "neutral", "friendly", "devoted"
        """
        disposition = self.get_npc_disposition(npc_id)

        if disposition <= -60:
            return "hostile"
        elif disposition <= -20:
            return "unfriendly"
        elif disposition < 20:
            return "neutral"
        elif disposition < 60:
            return "friendly"
        else:
            return "devoted"

    def get_npc_reaction(
        self,
        npc_id: str,
        action_type: str,
    ) -> Tuple[int, str]:
        """
        Get NPC's reaction to a type of action.

        Args:
            npc_id: ID of the NPC
            action_type: Type of action (e.g., "help_innocent", "lie", "fight")

        Returns:
            Tuple of (disposition_change, reaction_text)
        """
        # This would typically be looked up from NPC data
        # For now, return generic responses

        positive_actions = ["help", "rescue", "donate", "protect", "truth"]
        negative_actions = ["lie", "steal", "abandon", "betray", "kill_innocent"]

        tier = self.get_relationship_tier(npc_id)

        for pos in positive_actions:
            if pos in action_type.lower():
                if tier in ["hostile", "unfriendly"]:
                    return (5, "They seem surprised by your kindness.")
                else:
                    return (10, "They appreciate your actions.")

        for neg in negative_actions:
            if neg in action_type.lower():
                if tier in ["friendly", "devoted"]:
                    return (-15, "They look at you with disappointment.")
                else:
                    return (-10, "They disapprove of your actions.")

        return (0, "")

    # =========================================================================
    # DIALOGUE FILTERING
    # =========================================================================

    def get_available_dialogue_options(
        self,
        npc_id: str,
        base_options: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Filter dialogue options based on relationship and flags.

        Args:
            npc_id: ID of the NPC
            base_options: All possible dialogue options

        Returns:
            Filtered list of available options
        """
        available = []
        disposition = self.get_npc_disposition(npc_id)

        for option in base_options:
            # Check disposition requirement
            min_disposition = option.get("requires_disposition")
            if min_disposition is not None and disposition < min_disposition:
                continue

            # Check flag requirements
            required_flags = option.get("requires_flags", [])
            if not all(self.world_state.has_flag(f) for f in required_flags):
                continue

            # Check flag exclusions
            hidden_flags = option.get("hidden_if_flags", [])
            if any(self.world_state.has_flag(f) for f in hidden_flags):
                continue

            available.append(option)

        return available

    # =========================================================================
    # ENCOUNTER MODIFICATION
    # =========================================================================

    def get_modified_encounter(
        self,
        encounter: Encounter,
    ) -> Encounter:
        """
        Apply consequence-based modifications to an encounter.

        Args:
            encounter: Original encounter

        Returns:
            Modified encounter (or original if no modifications)
        """
        # Check for modifications
        modifications = []

        for flag, value in self.world_state.flags.items():
            if flag.startswith(f"encounter_mod:{encounter.id}:") and value:
                mod_type = flag.split(":")[-1]
                modifications.append(mod_type)

        if not modifications:
            return encounter

        # Apply modifications (create a copy to avoid mutating original)
        # This is a simplified implementation
        modified = encounter

        for mod in modifications:
            if mod == "ally_joins" and encounter.combat:
                # Add an ally to combat
                logger.info(f"Adding ally to encounter {encounter.id}")
                # Would modify combat.allies here

            elif mod == "enemy_removed" and encounter.combat:
                # Remove an enemy
                if encounter.combat.enemies:
                    encounter.combat.enemies = encounter.combat.enemies[:-1]
                    logger.info(f"Removed enemy from encounter {encounter.id}")

            elif mod == "peaceful_option":
                # Add a non-combat resolution
                logger.info(f"Added peaceful option to encounter {encounter.id}")

            elif mod == "harder":
                # Increase difficulty
                if encounter.combat and encounter.combat.enemies:
                    for enemy in encounter.combat.enemies:
                        enemy.count += 1
                    logger.info(f"Increased difficulty of encounter {encounter.id}")

            elif mod == "easier":
                # Decrease difficulty
                if encounter.combat and encounter.combat.enemies:
                    for enemy in encounter.combat.enemies:
                        enemy.count = max(1, enemy.count - 1)
                    logger.info(f"Decreased difficulty of encounter {encounter.id}")

        return modified

    # =========================================================================
    # CONSEQUENCE CHAIN MANAGEMENT
    # =========================================================================

    def add_delayed_consequence(
        self,
        trigger_choice_id: str,
        trigger_condition: Dict[str, Any],
        effect_type: ConsequenceEffectType,
        effect_params: Dict[str, Any],
        narrative_text: str = "",
    ):
        """
        Add a delayed consequence to be triggered later.

        Args:
            trigger_choice_id: Which choice caused this
            trigger_condition: When to trigger (see DelayedConsequence)
            effect_type: Type of effect
            effect_params: Parameters for the effect
            narrative_text: Text to show when triggered
        """
        import uuid

        consequence = DelayedConsequence(
            id=str(uuid.uuid4()),
            trigger_choice_id=trigger_choice_id,
            trigger_condition=trigger_condition,
            effect_type=effect_type,
            effect_params=effect_params,
            narrative_text=narrative_text,
            triggered=False,
        )

        self.world_state.add_pending_consequence(consequence)
        logger.debug(f"Added delayed consequence for choice {trigger_choice_id}")

    def get_pending_consequences(self) -> List[DelayedConsequence]:
        """Get all pending (untriggered) consequences."""
        return [c for c in self.world_state.pending_consequences if not c.triggered]

    def get_triggered_consequences(self) -> List[DelayedConsequence]:
        """Get all already-triggered consequences."""
        return [c for c in self.world_state.pending_consequences if c.triggered]

    # =========================================================================
    # SUMMARY AND ANALYSIS
    # =========================================================================

    def get_choice_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all choices made and their effects.

        Returns:
            Summary dictionary for display/export
        """
        return {
            "total_choices": len(self.world_state.choice_history),
            "choices": [
                {
                    "choice_id": c.choice_id,
                    "encounter_id": c.encounter_id,
                    "outcome": c.outcome,
                    "timestamp": c.timestamp,
                }
                for c in self.world_state.choice_history
            ],
            "npc_relationships": dict(self.world_state.npc_dispositions),
            "active_flags": [f for f, v in self.world_state.flags.items() if v],
            "pending_consequences": len(self.get_pending_consequences()),
            "triggered_consequences": len(self.get_triggered_consequences()),
        }

    def analyze_player_tendencies(self) -> Dict[str, Any]:
        """
        Analyze player's decision-making tendencies.

        Returns:
            Analysis of player behavior patterns
        """
        if not self.world_state.choice_history:
            return {"analysis": "No choices recorded yet."}

        # Count outcomes
        successes = sum(1 for c in self.world_state.choice_history if c.outcome == "success")
        failures = sum(1 for c in self.world_state.choice_history if c.outcome == "failure")
        total = len(self.world_state.choice_history)

        # Analyze NPC relationships
        relationships = self.world_state.npc_dispositions
        avg_disposition = sum(relationships.values()) / len(relationships) if relationships else 0

        # Analyze flags for tendencies
        flags = self.world_state.flags
        merciful = sum(1 for f in flags if "spare" in f.lower() or "save" in f.lower())
        ruthless = sum(1 for f in flags if "kill" in f.lower() or "abandon" in f.lower())
        diplomatic = sum(1 for f in flags if "negotiate" in f.lower() or "persuade" in f.lower())

        return {
            "success_rate": successes / total if total > 0 else 0,
            "total_choices": total,
            "average_npc_disposition": avg_disposition,
            "tendencies": {
                "merciful": merciful > ruthless,
                "diplomatic": diplomatic > 0,
                "pragmatic": abs(merciful - ruthless) < 2,
            },
        }
