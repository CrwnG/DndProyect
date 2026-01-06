"""
Social encounter data models.

Defines NPC relationships, faction reputations, and social interaction tracking
for rich roleplay and social skill challenge mechanics.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class Disposition(str, Enum):
    """NPC disposition levels toward the party."""
    HOSTILE = "hostile"         # -100 to -60: Will attack or sabotage
    UNFRIENDLY = "unfriendly"   # -59 to -20: Unhelpful, may refuse service
    INDIFFERENT = "indifferent" # -19 to +19: Neutral, transactional
    FRIENDLY = "friendly"       # +20 to +59: Helpful, offers discounts
    ALLIED = "allied"           # +60 to +100: Loyal, will take risks for party

    @classmethod
    def from_value(cls, value: int) -> "Disposition":
        """
        Get disposition level from numeric value.

        Args:
            value: Disposition value from -100 to 100

        Returns:
            Corresponding Disposition enum
        """
        if value <= -60:
            return cls.HOSTILE
        elif value <= -20:
            return cls.UNFRIENDLY
        elif value <= 19:
            return cls.INDIFFERENT
        elif value <= 59:
            return cls.FRIENDLY
        else:
            return cls.ALLIED


class InteractionType(str, Enum):
    """Types of social interactions."""
    GREETING = "greeting"
    PERSUASION = "persuasion"
    DECEPTION = "deception"
    INTIMIDATION = "intimidation"
    INSIGHT = "insight"
    TRADE = "trade"
    QUEST = "quest"
    GIFT = "gift"
    INSULT = "insult"
    COMBAT = "combat"
    BETRAYAL = "betrayal"
    ASSISTANCE = "assistance"


class FactionType(str, Enum):
    """Types of factions."""
    GUILD = "guild"             # Trade/craft organizations
    MILITARY = "military"       # Armies, guards, knights
    RELIGIOUS = "religious"     # Temples, cults, churches
    CRIMINAL = "criminal"       # Thieves, assassins, smugglers
    POLITICAL = "political"     # Nobles, governments
    ARCANE = "arcane"          # Wizard schools, magical societies
    NATURAL = "natural"        # Druid circles, ranger lodges
    MERCHANT = "merchant"       # Trading companies
    SECRET = "secret"          # Hidden organizations


class ReputationTier(str, Enum):
    """Reputation standing with a faction."""
    ENEMY = "enemy"             # -100 to -60: Kill on sight
    HATED = "hated"             # -59 to -30: Hostile, no service
    DISLIKED = "disliked"       # -29 to -10: Suspicious, higher prices
    NEUTRAL = "neutral"         # -9 to +9: No opinion
    LIKED = "liked"             # +10 to +29: Friendly, small discounts
    HONORED = "honored"         # +30 to +59: Trusted, access to services
    REVERED = "revered"         # +60 to +100: Legendary, special privileges

    @classmethod
    def from_value(cls, value: int) -> "ReputationTier":
        """Get reputation tier from numeric value."""
        if value <= -60:
            return cls.ENEMY
        elif value <= -30:
            return cls.HATED
        elif value <= -10:
            return cls.DISLIKED
        elif value <= 9:
            return cls.NEUTRAL
        elif value <= 29:
            return cls.LIKED
        elif value <= 59:
            return cls.HONORED
        else:
            return cls.REVERED


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class InteractionRecord:
    """Record of a single interaction with an NPC."""
    timestamp: datetime
    interaction_type: InteractionType
    skill_used: Optional[str] = None
    roll_result: Optional[int] = None
    dc: Optional[int] = None
    success: Optional[bool] = None
    disposition_change: int = 0
    trust_change: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "interaction_type": self.interaction_type.value,
            "skill_used": self.skill_used,
            "roll_result": self.roll_result,
            "dc": self.dc,
            "success": self.success,
            "disposition_change": self.disposition_change,
            "trust_change": self.trust_change,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractionRecord":
        """Deserialize from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            interaction_type=InteractionType(data["interaction_type"]),
            skill_used=data.get("skill_used"),
            roll_result=data.get("roll_result"),
            dc=data.get("dc"),
            success=data.get("success"),
            disposition_change=data.get("disposition_change", 0),
            trust_change=data.get("trust_change", 0),
            notes=data.get("notes", ""),
        )


@dataclass
class NPCRelationship:
    """
    Tracks the relationship between the party and a specific NPC.

    Includes disposition (how they feel), trust (reliability of relationship),
    and interaction history for AI DM context.
    """
    npc_id: str
    npc_name: str
    disposition_value: int = 0      # -100 to 100
    trust: int = 0                   # 0 to 100
    interactions: List[InteractionRecord] = field(default_factory=list)
    known_facts: List[str] = field(default_factory=list)
    secrets_revealed: List[str] = field(default_factory=list)
    gifts_given: List[str] = field(default_factory=list)
    quests_completed: List[str] = field(default_factory=list)
    last_interaction: Optional[datetime] = None
    first_met: Optional[datetime] = None
    times_met: int = 0

    def __post_init__(self):
        """Set first_met if not set."""
        if self.first_met is None:
            self.first_met = datetime.utcnow()

    @property
    def disposition(self) -> Disposition:
        """Get disposition level from value."""
        return Disposition.from_value(self.disposition_value)

    def adjust_disposition(self, amount: int) -> int:
        """
        Adjust disposition value, clamped to -100 to 100.

        Args:
            amount: Amount to adjust (positive or negative)

        Returns:
            New disposition value
        """
        self.disposition_value = max(-100, min(100, self.disposition_value + amount))
        return self.disposition_value

    def adjust_trust(self, amount: int) -> int:
        """
        Adjust trust value, clamped to 0 to 100.

        Args:
            amount: Amount to adjust (positive or negative)

        Returns:
            New trust value
        """
        self.trust = max(0, min(100, self.trust + amount))
        return self.trust

    def add_interaction(self, record: InteractionRecord) -> None:
        """
        Add an interaction record.

        Args:
            record: The interaction record to add
        """
        self.interactions.append(record)
        self.last_interaction = record.timestamp
        self.times_met += 1

        # Apply disposition and trust changes
        if record.disposition_change:
            self.adjust_disposition(record.disposition_change)
        if record.trust_change:
            self.adjust_trust(record.trust_change)

    def get_recent_interactions(self, count: int = 5) -> List[InteractionRecord]:
        """Get most recent interactions."""
        return self.interactions[-count:] if self.interactions else []

    def get_dc_modifier(self) -> int:
        """
        Get DC modifier based on disposition.

        Friendly NPCs are easier to persuade, hostile ones harder.

        Returns:
            DC modifier (negative makes checks easier)
        """
        modifiers = {
            Disposition.HOSTILE: 5,
            Disposition.UNFRIENDLY: 2,
            Disposition.INDIFFERENT: 0,
            Disposition.FRIENDLY: -2,
            Disposition.ALLIED: -5,
        }
        return modifiers.get(self.disposition, 0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "npc_id": self.npc_id,
            "npc_name": self.npc_name,
            "disposition_value": self.disposition_value,
            "disposition": self.disposition.value,
            "trust": self.trust,
            "interactions": [i.to_dict() for i in self.interactions],
            "known_facts": self.known_facts,
            "secrets_revealed": self.secrets_revealed,
            "gifts_given": self.gifts_given,
            "quests_completed": self.quests_completed,
            "last_interaction": self.last_interaction.isoformat() if self.last_interaction else None,
            "first_met": self.first_met.isoformat() if self.first_met else None,
            "times_met": self.times_met,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NPCRelationship":
        """Deserialize from dictionary."""
        rel = cls(
            npc_id=data["npc_id"],
            npc_name=data["npc_name"],
            disposition_value=data.get("disposition_value", 0),
            trust=data.get("trust", 0),
            known_facts=data.get("known_facts", []),
            secrets_revealed=data.get("secrets_revealed", []),
            gifts_given=data.get("gifts_given", []),
            quests_completed=data.get("quests_completed", []),
            times_met=data.get("times_met", 0),
        )

        # Parse interactions
        if "interactions" in data:
            rel.interactions = [InteractionRecord.from_dict(i) for i in data["interactions"]]

        # Parse timestamps
        if data.get("last_interaction"):
            rel.last_interaction = datetime.fromisoformat(data["last_interaction"])
        if data.get("first_met"):
            rel.first_met = datetime.fromisoformat(data["first_met"])

        return rel


@dataclass
class FactionReputation:
    """
    Tracks reputation with a faction.

    Affects prices, available services, quests, and NPC initial dispositions.
    """
    faction_id: str
    faction_name: str
    faction_type: FactionType = FactionType.GUILD
    reputation: int = 0             # -100 to 100
    rank: Optional[str] = None      # If member, their rank
    is_member: bool = False
    contribution_points: int = 0    # For tracking progress to next rank
    quests_completed: int = 0
    enemies_killed: int = 0         # For military factions
    gold_donated: int = 0           # For religious/merchant factions
    banned_until: Optional[datetime] = None

    @property
    def tier(self) -> ReputationTier:
        """Get reputation tier from value."""
        return ReputationTier.from_value(self.reputation)

    @property
    def is_banned(self) -> bool:
        """Check if currently banned from faction."""
        if self.banned_until is None:
            return False
        return datetime.utcnow() < self.banned_until

    def adjust_reputation(self, amount: int) -> int:
        """
        Adjust reputation value, clamped to -100 to 100.

        Args:
            amount: Amount to adjust (positive or negative)

        Returns:
            New reputation value
        """
        self.reputation = max(-100, min(100, self.reputation + amount))
        return self.reputation

    def get_price_modifier(self) -> float:
        """
        Get shop price modifier based on reputation.

        Returns:
            Multiplier for prices (lower = cheaper)
        """
        modifiers = {
            ReputationTier.ENEMY: 2.0,      # 200% price
            ReputationTier.HATED: 1.5,      # 150% price
            ReputationTier.DISLIKED: 1.2,   # 120% price
            ReputationTier.NEUTRAL: 1.0,    # Normal price
            ReputationTier.LIKED: 0.95,     # 95% price
            ReputationTier.HONORED: 0.85,   # 85% price
            ReputationTier.REVERED: 0.75,   # 75% price
        }
        return modifiers.get(self.tier, 1.0)

    def get_npc_disposition_bonus(self) -> int:
        """
        Get initial disposition bonus for faction NPCs.

        Returns:
            Bonus to add to NPC's initial disposition
        """
        bonuses = {
            ReputationTier.ENEMY: -40,
            ReputationTier.HATED: -20,
            ReputationTier.DISLIKED: -10,
            ReputationTier.NEUTRAL: 0,
            ReputationTier.LIKED: 10,
            ReputationTier.HONORED: 20,
            ReputationTier.REVERED: 40,
        }
        return bonuses.get(self.tier, 0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "faction_id": self.faction_id,
            "faction_name": self.faction_name,
            "faction_type": self.faction_type.value,
            "reputation": self.reputation,
            "tier": self.tier.value,
            "rank": self.rank,
            "is_member": self.is_member,
            "contribution_points": self.contribution_points,
            "quests_completed": self.quests_completed,
            "enemies_killed": self.enemies_killed,
            "gold_donated": self.gold_donated,
            "banned_until": self.banned_until.isoformat() if self.banned_until else None,
            "is_banned": self.is_banned,
            "price_modifier": self.get_price_modifier(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FactionReputation":
        """Deserialize from dictionary."""
        rep = cls(
            faction_id=data["faction_id"],
            faction_name=data["faction_name"],
            faction_type=FactionType(data.get("faction_type", "guild")),
            reputation=data.get("reputation", 0),
            rank=data.get("rank"),
            is_member=data.get("is_member", False),
            contribution_points=data.get("contribution_points", 0),
            quests_completed=data.get("quests_completed", 0),
            enemies_killed=data.get("enemies_killed", 0),
            gold_donated=data.get("gold_donated", 0),
        )

        if data.get("banned_until"):
            rep.banned_until = datetime.fromisoformat(data["banned_until"])

        return rep


@dataclass
class SocialState:
    """
    Complete social state for a session.

    Tracks all NPC relationships and faction reputations.
    """
    session_id: str
    npc_relationships: Dict[str, NPCRelationship] = field(default_factory=dict)
    faction_reputations: Dict[str, FactionReputation] = field(default_factory=dict)

    def get_npc_relationship(self, npc_id: str) -> Optional[NPCRelationship]:
        """Get relationship with specific NPC."""
        return self.npc_relationships.get(npc_id)

    def get_or_create_npc_relationship(
        self,
        npc_id: str,
        npc_name: str,
        initial_disposition: int = 0,
    ) -> NPCRelationship:
        """
        Get existing relationship or create new one.

        Args:
            npc_id: Unique NPC identifier
            npc_name: Display name of NPC
            initial_disposition: Starting disposition if new

        Returns:
            NPCRelationship instance
        """
        if npc_id not in self.npc_relationships:
            self.npc_relationships[npc_id] = NPCRelationship(
                npc_id=npc_id,
                npc_name=npc_name,
                disposition_value=initial_disposition,
            )
        return self.npc_relationships[npc_id]

    def get_faction_reputation(self, faction_id: str) -> Optional[FactionReputation]:
        """Get reputation with specific faction."""
        return self.faction_reputations.get(faction_id)

    def get_or_create_faction_reputation(
        self,
        faction_id: str,
        faction_name: str,
        faction_type: FactionType = FactionType.GUILD,
    ) -> FactionReputation:
        """
        Get existing reputation or create new one.

        Args:
            faction_id: Unique faction identifier
            faction_name: Display name of faction
            faction_type: Type of faction

        Returns:
            FactionReputation instance
        """
        if faction_id not in self.faction_reputations:
            self.faction_reputations[faction_id] = FactionReputation(
                faction_id=faction_id,
                faction_name=faction_name,
                faction_type=faction_type,
            )
        return self.faction_reputations[faction_id]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "npc_relationships": {
                k: v.to_dict() for k, v in self.npc_relationships.items()
            },
            "faction_reputations": {
                k: v.to_dict() for k, v in self.faction_reputations.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SocialState":
        """Deserialize from dictionary."""
        state = cls(session_id=data["session_id"])

        # Parse NPC relationships
        for npc_id, rel_data in data.get("npc_relationships", {}).items():
            state.npc_relationships[npc_id] = NPCRelationship.from_dict(rel_data)

        # Parse faction reputations
        for faction_id, rep_data in data.get("faction_reputations", {}).items():
            state.faction_reputations[faction_id] = FactionReputation.from_dict(rep_data)

        return state
