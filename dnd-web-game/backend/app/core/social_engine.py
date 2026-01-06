"""
Social encounter engine.

Handles social skill checks, skill challenges, and relationship management.
Implements D&D 5e social mechanics with disposition-based DC modifiers.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import random
import logging

from app.models.social import (
    NPCRelationship,
    FactionReputation,
    SocialState,
    Disposition,
    InteractionType,
    InteractionRecord,
    FactionType,
    ReputationTier,
)

logger = logging.getLogger(__name__)


# =============================================================================
# RESULT DATA CLASSES
# =============================================================================

@dataclass
class SocialCheckResult:
    """Result of a social skill check."""
    success: bool
    roll: int
    total: int
    dc: int
    skill: str
    margin: int                         # How much they beat/missed DC by
    disposition_change: int = 0
    trust_change: int = 0
    critical: bool = False              # Natural 20 or 1
    npc_reaction: str = ""              # Short description of NPC reaction
    new_disposition: Optional[Disposition] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "roll": self.roll,
            "total": self.total,
            "dc": self.dc,
            "skill": self.skill,
            "margin": self.margin,
            "disposition_change": self.disposition_change,
            "trust_change": self.trust_change,
            "critical": self.critical,
            "npc_reaction": self.npc_reaction,
            "new_disposition": self.new_disposition.value if self.new_disposition else None,
        }


@dataclass
class SkillChallengeState:
    """Tracks state of an ongoing skill challenge."""
    challenge_id: str
    name: str
    description: str
    successes_needed: int
    failures_allowed: int
    current_successes: int = 0
    current_failures: int = 0
    skills_used: List[str] = field(default_factory=list)
    skill_limits: Dict[str, int] = field(default_factory=dict)  # Max uses per skill
    rolls: List[Dict[str, Any]] = field(default_factory=list)
    is_complete: bool = False
    is_success: bool = False
    started_at: Optional[datetime] = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.utcnow()

    @property
    def successes_remaining(self) -> int:
        """How many more successes needed."""
        return self.successes_needed - self.current_successes

    @property
    def failures_remaining(self) -> int:
        """How many more failures allowed."""
        return self.failures_allowed - self.current_failures

    def can_use_skill(self, skill: str) -> bool:
        """Check if skill can still be used in this challenge."""
        if skill not in self.skill_limits:
            return True
        uses = sum(1 for s in self.skills_used if s.lower() == skill.lower())
        return uses < self.skill_limits[skill]

    def record_attempt(
        self,
        skill: str,
        roll: int,
        total: int,
        dc: int,
        success: bool,
    ) -> None:
        """Record a skill check attempt."""
        self.skills_used.append(skill)
        self.rolls.append({
            "skill": skill,
            "roll": roll,
            "total": total,
            "dc": dc,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        })

        if success:
            self.current_successes += 1
        else:
            self.current_failures += 1

        # Check for completion
        if self.current_successes >= self.successes_needed:
            self.is_complete = True
            self.is_success = True
        elif self.current_failures >= self.failures_allowed:
            self.is_complete = True
            self.is_success = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "challenge_id": self.challenge_id,
            "name": self.name,
            "description": self.description,
            "successes_needed": self.successes_needed,
            "failures_allowed": self.failures_allowed,
            "current_successes": self.current_successes,
            "current_failures": self.current_failures,
            "successes_remaining": self.successes_remaining,
            "failures_remaining": self.failures_remaining,
            "skills_used": self.skills_used,
            "skill_limits": self.skill_limits,
            "rolls": self.rolls,
            "is_complete": self.is_complete,
            "is_success": self.is_success,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }


# =============================================================================
# SOCIAL ENGINE
# =============================================================================

class SocialEngine:
    """
    Engine for handling social encounters and skill challenges.

    Implements D&D 5e social mechanics with extensions for:
    - Disposition-based DC modifiers
    - Trust tracking
    - Multi-stage skill challenges
    - Relationship consequences
    """

    # Skill to ability mapping
    SOCIAL_SKILLS = {
        "persuasion": "charisma",
        "deception": "charisma",
        "intimidation": "charisma",
        "insight": "wisdom",
        "performance": "charisma",
        "animal handling": "wisdom",
    }

    # Base DC for various social situations
    BASE_DCS = {
        "trivial": 5,
        "easy": 10,
        "medium": 15,
        "hard": 20,
        "very_hard": 25,
        "nearly_impossible": 30,
    }

    # Disposition changes based on check results
    DISPOSITION_CHANGES = {
        "critical_success": 10,     # Natural 20
        "major_success": 5,         # Beat DC by 5+
        "success": 2,               # Beat DC by 0-4
        "failure": -2,              # Missed DC by 1-4
        "major_failure": -5,        # Missed DC by 5+
        "critical_failure": -10,    # Natural 1
    }

    # Trust changes based on interaction type
    TRUST_CHANGES = {
        InteractionType.GIFT: 5,
        InteractionType.QUEST: 10,
        InteractionType.ASSISTANCE: 3,
        InteractionType.BETRAYAL: -20,
        InteractionType.DECEPTION: -5,  # If discovered
        InteractionType.COMBAT: -15,
        InteractionType.INSULT: -3,
    }

    def __init__(self):
        """Initialize the social engine."""
        self._active_challenges: Dict[str, SkillChallengeState] = {}
        logger.info("Social engine initialized")

    def perform_social_check(
        self,
        skill: str,
        base_dc: int,
        character_modifier: int,
        npc_relationship: Optional[NPCRelationship] = None,
        advantage: bool = False,
        disadvantage: bool = False,
        faction_reputation: Optional[FactionReputation] = None,
    ) -> SocialCheckResult:
        """
        Perform a social skill check.

        Args:
            skill: The social skill being used
            base_dc: Base DC before modifiers
            character_modifier: Character's skill modifier
            npc_relationship: Relationship with the NPC (affects DC)
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage
            faction_reputation: Faction reputation (affects DC)

        Returns:
            SocialCheckResult with full outcome details
        """
        # Calculate final DC with modifiers
        dc = base_dc

        if npc_relationship:
            dc += npc_relationship.get_dc_modifier()

        if faction_reputation:
            # Faction reputation provides additional modifier
            tier_modifiers = {
                ReputationTier.ENEMY: 5,
                ReputationTier.HATED: 3,
                ReputationTier.DISLIKED: 1,
                ReputationTier.NEUTRAL: 0,
                ReputationTier.LIKED: -1,
                ReputationTier.HONORED: -2,
                ReputationTier.REVERED: -3,
            }
            dc += tier_modifiers.get(faction_reputation.tier, 0)

        # Roll the dice
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)

        if advantage and not disadvantage:
            roll = max(roll1, roll2)
        elif disadvantage and not advantage:
            roll = min(roll1, roll2)
        else:
            roll = roll1

        total = roll + character_modifier
        margin = total - dc
        success = total >= dc

        # Check for critical
        critical = roll == 20 or roll == 1
        if roll == 20:
            success = True
        elif roll == 1:
            success = False

        # Calculate disposition change
        disposition_change = self._calculate_disposition_change(
            success=success,
            margin=margin,
            critical=critical,
            roll=roll,
        )

        # Calculate trust change (only on significant events)
        trust_change = 0
        if critical:
            trust_change = 3 if success else -3

        # Generate NPC reaction
        npc_reaction = self._generate_npc_reaction(
            skill=skill,
            success=success,
            margin=margin,
            critical=critical,
            disposition=npc_relationship.disposition if npc_relationship else Disposition.INDIFFERENT,
        )

        # Determine new disposition if relationship exists
        new_disposition = None
        if npc_relationship:
            npc_relationship.adjust_disposition(disposition_change)
            npc_relationship.adjust_trust(trust_change)
            new_disposition = npc_relationship.disposition

            # Record the interaction
            npc_relationship.add_interaction(InteractionRecord(
                timestamp=datetime.utcnow(),
                interaction_type=self._skill_to_interaction_type(skill),
                skill_used=skill,
                roll_result=roll,
                dc=dc,
                success=success,
                disposition_change=disposition_change,
                trust_change=trust_change,
            ))

        return SocialCheckResult(
            success=success,
            roll=roll,
            total=total,
            dc=dc,
            skill=skill,
            margin=margin,
            disposition_change=disposition_change,
            trust_change=trust_change,
            critical=critical,
            npc_reaction=npc_reaction,
            new_disposition=new_disposition,
        )

    def _calculate_disposition_change(
        self,
        success: bool,
        margin: int,
        critical: bool,
        roll: int,
    ) -> int:
        """Calculate disposition change based on check result."""
        if roll == 20:
            return self.DISPOSITION_CHANGES["critical_success"]
        elif roll == 1:
            return self.DISPOSITION_CHANGES["critical_failure"]
        elif success:
            if margin >= 5:
                return self.DISPOSITION_CHANGES["major_success"]
            return self.DISPOSITION_CHANGES["success"]
        else:
            if margin <= -5:
                return self.DISPOSITION_CHANGES["major_failure"]
            return self.DISPOSITION_CHANGES["failure"]

    def _generate_npc_reaction(
        self,
        skill: str,
        success: bool,
        margin: int,
        critical: bool,
        disposition: Disposition,
    ) -> str:
        """Generate a short NPC reaction description."""
        reactions = {
            ("persuasion", True, True): "They are completely won over by your words.",
            ("persuasion", True, False): "They nod, warming to your argument.",
            ("persuasion", False, True): "Your words fall on deaf ears - they seem offended.",
            ("persuasion", False, False): "They shake their head, unconvinced.",

            ("intimidation", True, True): "Fear flashes in their eyes as they back away.",
            ("intimidation", True, False): "They flinch slightly, wary of your threat.",
            ("intimidation", False, True): "They laugh at your attempt to frighten them.",
            ("intimidation", False, False): "They stand firm, unimpressed by your threats.",

            ("deception", True, True): "They believe every word without question.",
            ("deception", True, False): "They seem to accept your story.",
            ("deception", False, True): "Their eyes narrow - they clearly don't believe you.",
            ("deception", False, False): "They look skeptical but don't press the issue.",

            ("insight", True, True): "You read them like an open book.",
            ("insight", True, False): "You pick up on subtle cues about their intentions.",
            ("insight", False, True): "Their expression is completely unreadable to you.",
            ("insight", False, False): "You can't quite tell what they're thinking.",
        }

        skill_lower = skill.lower()
        key = (skill_lower, success, critical)

        if key in reactions:
            return reactions[key]

        # Default reactions
        if success:
            return "They respond favorably to your approach."
        return "Your attempt doesn't achieve the desired effect."

    def _skill_to_interaction_type(self, skill: str) -> InteractionType:
        """Map skill to interaction type."""
        mapping = {
            "persuasion": InteractionType.PERSUASION,
            "deception": InteractionType.DECEPTION,
            "intimidation": InteractionType.INTIMIDATION,
            "insight": InteractionType.INSIGHT,
        }
        return mapping.get(skill.lower(), InteractionType.GREETING)

    # =========================================================================
    # SKILL CHALLENGES
    # =========================================================================

    def create_skill_challenge(
        self,
        challenge_id: str,
        name: str,
        description: str,
        successes_needed: int = 3,
        failures_allowed: int = 3,
        skill_limits: Optional[Dict[str, int]] = None,
    ) -> SkillChallengeState:
        """
        Create a new skill challenge.

        Skill challenges are multi-stage social encounters where the party
        must accumulate successes before too many failures.

        Args:
            challenge_id: Unique identifier for this challenge
            name: Display name
            description: Flavor text description
            successes_needed: Number of successes to win
            failures_allowed: Number of failures before losing
            skill_limits: Optional limits on skill reuse

        Returns:
            New SkillChallengeState
        """
        challenge = SkillChallengeState(
            challenge_id=challenge_id,
            name=name,
            description=description,
            successes_needed=successes_needed,
            failures_allowed=failures_allowed,
            skill_limits=skill_limits or {},
        )

        self._active_challenges[challenge_id] = challenge
        logger.info(f"Created skill challenge: {name} ({successes_needed} successes needed)")

        return challenge

    def attempt_skill_challenge(
        self,
        challenge_id: str,
        skill: str,
        character_modifier: int,
        base_dc: int = 15,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> Tuple[SocialCheckResult, SkillChallengeState]:
        """
        Make an attempt in a skill challenge.

        Args:
            challenge_id: ID of the active challenge
            skill: Skill being used
            character_modifier: Character's skill modifier
            base_dc: DC for this attempt
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage

        Returns:
            Tuple of (check result, updated challenge state)

        Raises:
            ValueError: If challenge not found or already complete
        """
        if challenge_id not in self._active_challenges:
            raise ValueError(f"Skill challenge not found: {challenge_id}")

        challenge = self._active_challenges[challenge_id]

        if challenge.is_complete:
            raise ValueError(f"Skill challenge already complete: {challenge_id}")

        if not challenge.can_use_skill(skill):
            raise ValueError(f"Skill '{skill}' has reached its usage limit in this challenge")

        # Perform the check
        result = self.perform_social_check(
            skill=skill,
            base_dc=base_dc,
            character_modifier=character_modifier,
            advantage=advantage,
            disadvantage=disadvantage,
        )

        # Record the attempt
        challenge.record_attempt(
            skill=skill,
            roll=result.roll,
            total=result.total,
            dc=result.dc,
            success=result.success,
        )

        if challenge.is_complete:
            logger.info(
                f"Skill challenge complete: {challenge.name} - "
                f"{'SUCCESS' if challenge.is_success else 'FAILURE'}"
            )

        return result, challenge

    def get_skill_challenge(self, challenge_id: str) -> Optional[SkillChallengeState]:
        """Get an active skill challenge by ID."""
        return self._active_challenges.get(challenge_id)

    def end_skill_challenge(self, challenge_id: str) -> Optional[SkillChallengeState]:
        """
        End and remove a skill challenge.

        Returns the final state before removal.
        """
        return self._active_challenges.pop(challenge_id, None)

    # =========================================================================
    # REPUTATION HELPERS
    # =========================================================================

    def adjust_faction_reputation(
        self,
        faction: FactionReputation,
        amount: int,
        reason: str = "",
    ) -> Tuple[int, Optional[ReputationTier]]:
        """
        Adjust faction reputation with tier change tracking.

        Args:
            faction: The faction reputation to adjust
            amount: Amount to adjust (positive or negative)
            reason: Optional reason for the change

        Returns:
            Tuple of (new reputation value, new tier if changed)
        """
        old_tier = faction.tier
        new_value = faction.adjust_reputation(amount)
        new_tier = faction.tier

        if old_tier != new_tier:
            logger.info(
                f"Faction reputation changed: {faction.faction_name} "
                f"{old_tier.value} -> {new_tier.value} ({reason})"
            )
            return new_value, new_tier

        return new_value, None

    def get_faction_services(
        self,
        faction: FactionReputation,
    ) -> Dict[str, bool]:
        """
        Get available services based on faction reputation.

        Returns dict of service names to availability.
        """
        tier = faction.tier

        services = {
            "basic_trade": tier not in [ReputationTier.ENEMY, ReputationTier.HATED],
            "advanced_trade": tier in [
                ReputationTier.LIKED,
                ReputationTier.HONORED,
                ReputationTier.REVERED,
            ],
            "quest_board": tier not in [
                ReputationTier.ENEMY,
                ReputationTier.HATED,
                ReputationTier.DISLIKED,
            ],
            "special_quests": tier in [ReputationTier.HONORED, ReputationTier.REVERED],
            "training": tier in [
                ReputationTier.LIKED,
                ReputationTier.HONORED,
                ReputationTier.REVERED,
            ] and faction.is_member,
            "safe_house": tier == ReputationTier.REVERED and faction.is_member,
            "faction_vault": tier == ReputationTier.REVERED and faction.is_member,
        }

        return services


# Singleton instance
_social_engine: Optional[SocialEngine] = None


def get_social_engine() -> SocialEngine:
    """Get the singleton social engine instance."""
    global _social_engine
    if _social_engine is None:
        _social_engine = SocialEngine()
    return _social_engine
