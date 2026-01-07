"""
NPC (Non-Player Character) Models.

BG3-inspired NPC system with:
- Rich personality traits and quirks
- Relationship tracking (approval system)
- Dynamic dialogue based on disposition
- Character arcs and secrets
- Situational bark lines
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid


class NPCRole(str, Enum):
    """Role an NPC plays in the campaign."""
    COMPANION = "companion"      # Can join party, has approval system
    VILLAIN = "villain"         # Main antagonist
    QUEST_GIVER = "quest_giver"  # Provides quests/missions
    MERCHANT = "merchant"       # Sells items
    INFORMANT = "informant"     # Provides lore/information
    ALLY = "ally"               # Helps party but doesn't join
    NEUTRAL = "neutral"         # Bystander, may have info
    HOSTILE = "hostile"         # Enemy but not main villain


class HumorStyle(str, Enum):
    """NPC's sense of humor (BG3 companions have distinct humor)."""
    DRY = "dry"             # Deadpan, sarcastic (like Astarion)
    SLAPSTICK = "slapstick"  # Physical comedy
    DARK = "dark"           # Gallows humor (like Shadowheart)
    WITTY = "witty"         # Clever wordplay
    EARNEST = "earnest"     # Genuine, sometimes unintentionally funny
    NONE = "none"           # Serious character


class SpeechPattern(str, Enum):
    """How the NPC speaks (affects dialogue generation)."""
    FORMAL = "formal"       # Proper grammar, courtly
    CASUAL = "casual"       # Relaxed, modern-ish
    ARCHAIC = "archaic"     # Old-fashioned, poetic
    CRUDE = "crude"         # Rough, uses slang
    SCHOLARLY = "scholarly"  # Technical, uses big words
    CRYPTIC = "cryptic"     # Mysterious, speaks in riddles


class RelationshipTier(str, Enum):
    """Relationship status based on disposition (BG3-style)."""
    HOSTILE = "hostile"       # -100 to -60: Will attack or betray
    UNFRIENDLY = "unfriendly"  # -59 to -20: Refuses help, rude
    NEUTRAL = "neutral"       # -19 to 19: Indifferent
    FRIENDLY = "friendly"     # 20 to 59: Helpful, may give bonuses
    DEVOTED = "devoted"       # 60 to 89: Loyal, unlocks special content
    ROMANCE = "romance"       # 90 to 100: Romance option (if applicable)


@dataclass
class NPCPersonality:
    """
    Five-factor personality model for consistent NPC behavior.

    Based on BG3's companion design:
    - Astarion: ["vain", "cunning", "secretly vulnerable"]
    - Shadowheart: ["secretive", "pragmatic", "loyal when trusted"]
    - Gale: ["scholarly", "romantic", "self-deprecating"]
    """
    # Core traits (3-5 adjectives that define the character)
    traits: List[str] = field(default_factory=list)

    # Quirks (memorable behaviors/habits)
    quirks: List[str] = field(default_factory=list)

    # Motivations
    surface_motivation: str = ""  # What they claim to want
    true_motivation: str = ""     # What they actually need
    fear: str = ""                # What they're running from

    # Hidden depth
    secret: Optional[str] = None  # Hidden truth players can discover
    tragic_flaw: Optional[str] = None  # Character weakness

    # Communication style
    humor_style: HumorStyle = HumorStyle.DRY
    speech_pattern: SpeechPattern = SpeechPattern.CASUAL
    catchphrase: Optional[str] = None  # Recurring line

    # Preferences (affects approval changes)
    likes: List[str] = field(default_factory=list)   # Actions that increase approval
    dislikes: List[str] = field(default_factory=list)  # Actions that decrease approval

    def to_dict(self) -> Dict[str, Any]:
        return {
            "traits": self.traits,
            "quirks": self.quirks,
            "surface_motivation": self.surface_motivation,
            "true_motivation": self.true_motivation,
            "fear": self.fear,
            "secret": self.secret,
            "tragic_flaw": self.tragic_flaw,
            "humor_style": self.humor_style.value,
            "speech_pattern": self.speech_pattern.value,
            "catchphrase": self.catchphrase,
            "likes": self.likes,
            "dislikes": self.dislikes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NPCPersonality":
        humor_str = data.get("humor_style", "dry")
        speech_str = data.get("speech_pattern", "casual")

        try:
            humor = HumorStyle(humor_str)
        except ValueError:
            humor = HumorStyle.DRY

        try:
            speech = SpeechPattern(speech_str)
        except ValueError:
            speech = SpeechPattern.CASUAL

        return cls(
            traits=data.get("traits", []),
            quirks=data.get("quirks", []),
            surface_motivation=data.get("surface_motivation", ""),
            true_motivation=data.get("true_motivation", ""),
            fear=data.get("fear", ""),
            secret=data.get("secret"),
            tragic_flaw=data.get("tragic_flaw"),
            humor_style=humor,
            speech_pattern=speech,
            catchphrase=data.get("catchphrase"),
            likes=data.get("likes", []),
            dislikes=data.get("dislikes", []),
        )


@dataclass
class RelationshipEvent:
    """Record of an interaction that affected relationship."""
    timestamp: str
    event_type: str  # "dialogue", "quest", "combat", "gift"
    description: str
    disposition_change: int
    choice_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "description": self.description,
            "disposition_change": self.disposition_change,
            "choice_id": self.choice_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipEvent":
        return cls(
            timestamp=data.get("timestamp", ""),
            event_type=data.get("event_type", "dialogue"),
            description=data.get("description", ""),
            disposition_change=data.get("disposition_change", 0),
            choice_id=data.get("choice_id"),
        )


@dataclass
class DialogueOption:
    """A single dialogue choice in a conversation."""
    id: str
    text: str  # What player sees
    npc_response: str  # NPC's reply
    requires_disposition: Optional[int] = None  # Min disposition to see this
    requires_flags: List[str] = field(default_factory=list)
    sets_flags: List[str] = field(default_factory=list)
    disposition_change: int = 0
    leads_to: Optional[str] = None  # Next dialogue node ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "npc_response": self.npc_response,
            "requires_disposition": self.requires_disposition,
            "requires_flags": self.requires_flags,
            "sets_flags": self.sets_flags,
            "disposition_change": self.disposition_change,
            "leads_to": self.leads_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueOption":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            text=data.get("text", ""),
            npc_response=data.get("npc_response", ""),
            requires_disposition=data.get("requires_disposition"),
            requires_flags=data.get("requires_flags", []),
            sets_flags=data.get("sets_flags", []),
            disposition_change=data.get("disposition_change", 0),
            leads_to=data.get("leads_to"),
        )


@dataclass
class DialogueNode:
    """A node in a dialogue tree."""
    id: str
    npc_text: str  # What NPC says
    options: List[DialogueOption] = field(default_factory=list)
    is_exit: bool = False  # Ends conversation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "npc_text": self.npc_text,
            "options": [o.to_dict() for o in self.options],
            "is_exit": self.is_exit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueNode":
        options = [DialogueOption.from_dict(o) for o in data.get("options", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            npc_text=data.get("npc_text", ""),
            options=options,
            is_exit=data.get("is_exit", False),
        )


@dataclass
class DialogueTree:
    """Complete dialogue tree for a topic/encounter."""
    id: str
    topic: str  # "greeting", "quest_intro", "romance", etc.
    nodes: Dict[str, DialogueNode] = field(default_factory=dict)
    entry_node: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "entry_node": self.entry_node,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueTree":
        nodes = {k: DialogueNode.from_dict(v) for k, v in data.get("nodes", {}).items()}
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            topic=data.get("topic", ""),
            nodes=nodes,
            entry_node=data.get("entry_node", ""),
        )


@dataclass
class NPCArc:
    """Character arc/growth trajectory."""
    starting_state: str  # Initial characterization
    growth_triggers: List[str]  # Events that cause growth
    ending_state: str  # How they can end up
    current_stage: int = 0  # 0 = start, increases with growth

    def to_dict(self) -> Dict[str, Any]:
        return {
            "starting_state": self.starting_state,
            "growth_triggers": self.growth_triggers,
            "ending_state": self.ending_state,
            "current_stage": self.current_stage,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NPCArc":
        return cls(
            starting_state=data.get("starting_state", ""),
            growth_triggers=data.get("growth_triggers", []),
            ending_state=data.get("ending_state", ""),
            current_stage=data.get("current_stage", 0),
        )


@dataclass
class NPC:
    """
    A fully-realized NPC with BG3-quality depth.

    Key features:
    - Rich personality with traits, quirks, motivations
    - Relationship tracking (disposition -100 to 100)
    - Dynamic dialogue trees that unlock based on relationship
    - Character arc with potential growth
    - Situational bark lines for immersion
    """
    id: str
    name: str
    role: NPCRole = NPCRole.NEUTRAL

    # Visual/descriptive
    description: str = ""
    appearance: str = ""
    voice_description: str = ""  # For AI narration hints

    # Personality system
    personality: NPCPersonality = field(default_factory=NPCPersonality)

    # Relationship tracking
    base_disposition: int = 0  # Starting disposition
    current_disposition: int = 0  # Modified by player actions
    relationship_history: List[RelationshipEvent] = field(default_factory=list)
    romance_available: bool = False

    # Dialogue system
    dialogue_trees: Dict[str, DialogueTree] = field(default_factory=dict)

    # Situational lines (keyed by situation type)
    bark_lines: Dict[str, List[str]] = field(default_factory=dict)
    # Example: {"combat_start": ["Finally, some action!", "Stay behind me."],
    #           "low_health": ["I need healing!", "This isn't going well..."],
    #           "victory": ["That was almost too easy.", "We make a good team."]}

    # Character arc
    arc: Optional[NPCArc] = None

    # Combat behavior (if NPC can fight)
    combat_disposition: str = "neutral"  # "fights_alongside", "flees", "neutral", "hostile"
    stat_block_id: Optional[str] = None  # Reference to monster/character stat block

    # Location and availability
    current_location: Optional[str] = None
    available_encounters: List[str] = field(default_factory=list)  # When they appear

    def get_relationship_tier(self) -> RelationshipTier:
        """Get relationship tier based on current disposition."""
        d = self.current_disposition
        if d <= -60:
            return RelationshipTier.HOSTILE
        elif d <= -20:
            return RelationshipTier.UNFRIENDLY
        elif d < 20:
            return RelationshipTier.NEUTRAL
        elif d < 60:
            return RelationshipTier.FRIENDLY
        elif d < 90:
            return RelationshipTier.DEVOTED
        else:
            return RelationshipTier.ROMANCE if self.romance_available else RelationshipTier.DEVOTED

    def modify_disposition(self, delta: int, event_type: str, description: str, choice_id: str = None):
        """Modify disposition and record the event."""
        from datetime import datetime

        old_tier = self.get_relationship_tier()
        self.current_disposition = max(-100, min(100, self.current_disposition + delta))
        new_tier = self.get_relationship_tier()

        event = RelationshipEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            description=description,
            disposition_change=delta,
            choice_id=choice_id,
        )
        self.relationship_history.append(event)

        # Return tier change info for narrative purposes
        return {
            "old_tier": old_tier.value,
            "new_tier": new_tier.value,
            "tier_changed": old_tier != new_tier,
        }

    def get_bark_line(self, situation: str) -> Optional[str]:
        """Get a random bark line for a situation."""
        import random
        lines = self.bark_lines.get(situation, [])
        return random.choice(lines) if lines else None

    def get_available_dialogue_trees(self, world_state_flags: List[str]) -> List[str]:
        """Get dialogue trees available based on disposition and flags."""
        available = []
        for topic, tree in self.dialogue_trees.items():
            # Could add disposition requirements per tree
            available.append(topic)
        return available

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "description": self.description,
            "appearance": self.appearance,
            "voice_description": self.voice_description,
            "personality": self.personality.to_dict(),
            "base_disposition": self.base_disposition,
            "current_disposition": self.current_disposition,
            "relationship_history": [e.to_dict() for e in self.relationship_history],
            "romance_available": self.romance_available,
            "dialogue_trees": {k: v.to_dict() for k, v in self.dialogue_trees.items()},
            "bark_lines": self.bark_lines,
            "arc": self.arc.to_dict() if self.arc else None,
            "combat_disposition": self.combat_disposition,
            "stat_block_id": self.stat_block_id,
            "current_location": self.current_location,
            "available_encounters": self.available_encounters,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NPC":
        role_str = data.get("role", "neutral")
        try:
            role = NPCRole(role_str)
        except ValueError:
            role = NPCRole.NEUTRAL

        personality = NPCPersonality.from_dict(data.get("personality", {}))
        history = [RelationshipEvent.from_dict(e) for e in data.get("relationship_history", [])]
        dialogue_trees = {k: DialogueTree.from_dict(v) for k, v in data.get("dialogue_trees", {}).items()}
        arc_data = data.get("arc")
        arc = NPCArc.from_dict(arc_data) if arc_data else None

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Unknown"),
            role=role,
            description=data.get("description", ""),
            appearance=data.get("appearance", ""),
            voice_description=data.get("voice_description", ""),
            personality=personality,
            base_disposition=data.get("base_disposition", 0),
            current_disposition=data.get("current_disposition", 0),
            relationship_history=history,
            romance_available=data.get("romance_available", False),
            dialogue_trees=dialogue_trees,
            bark_lines=data.get("bark_lines", {}),
            arc=arc,
            combat_disposition=data.get("combat_disposition", "neutral"),
            stat_block_id=data.get("stat_block_id"),
            current_location=data.get("current_location"),
            available_encounters=data.get("available_encounters", []),
        )


# Convenience functions for NPC creation

def create_companion_npc(
    name: str,
    traits: List[str],
    motivation: str,
    fear: str,
    likes: List[str],
    dislikes: List[str],
    secret: str = None,
    humor: HumorStyle = HumorStyle.DRY,
    speech: SpeechPattern = SpeechPattern.CASUAL,
) -> NPC:
    """Create a companion NPC with BG3-style depth."""
    personality = NPCPersonality(
        traits=traits,
        surface_motivation=motivation,
        true_motivation=motivation,  # Can be different for mystery
        fear=fear,
        secret=secret,
        humor_style=humor,
        speech_pattern=speech,
        likes=likes,
        dislikes=dislikes,
    )

    return NPC(
        id=str(uuid.uuid4()),
        name=name,
        role=NPCRole.COMPANION,
        personality=personality,
        base_disposition=0,
        current_disposition=0,
        romance_available=True,
        combat_disposition="fights_alongside",
        bark_lines={
            "combat_start": [],
            "low_health": [],
            "victory": [],
            "rest": [],
            "exploration": [],
        },
    )


def create_villain_npc(
    name: str,
    traits: List[str],
    motivation: str,
    tragic_flaw: str = None,
) -> NPC:
    """Create a villain NPC."""
    personality = NPCPersonality(
        traits=traits,
        surface_motivation=motivation,
        true_motivation=motivation,
        tragic_flaw=tragic_flaw,
        humor_style=HumorStyle.DARK,
        speech_pattern=SpeechPattern.FORMAL,
    )

    return NPC(
        id=str(uuid.uuid4()),
        name=name,
        role=NPCRole.VILLAIN,
        personality=personality,
        base_disposition=-50,
        current_disposition=-50,
        combat_disposition="hostile",
    )
