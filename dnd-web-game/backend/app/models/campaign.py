"""
Campaign and Encounter System Models.

BG3-inspired campaign structure supporting:
- JSON-based campaign definitions
- Multiple encounter types (combat, social, exploration, rest)
- Story narrative with typewriter display
- Transition between encounters based on outcomes
- World state tracking (flags, variables, time)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
import uuid


class EncounterType(str, Enum):
    """Types of encounters in a campaign."""
    COMBAT = "combat"
    SOCIAL = "social"         # NPC dialogue, choices
    EXPLORATION = "exploration"  # Puzzle, investigation
    REST = "rest"             # Short or long rest
    CUTSCENE = "cutscene"     # Non-interactive story
    CHOICE = "choice"         # Decision point with skill checks and branching


class Difficulty(str, Enum):
    """Campaign/encounter difficulty settings."""
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"
    DEADLY = "deadly"


class DMMode(str, Enum):
    """Dungeon Master mode."""
    AI = "ai"           # AI controls enemies and narrates
    HUMAN = "human"     # Human DM has full control
    HYBRID = "hybrid"   # Human DM with AI assistance


class RestType(str, Enum):
    """D&D 5e rest types."""
    SHORT = "short"   # 1 hour, Hit Dice healing
    LONG = "long"     # 8 hours, full restoration


class CheckType(str, Enum):
    """Types of skill checks."""
    INDIVIDUAL = "individual"     # One character rolls (party leader)
    PLAYER_CHOICE = "player_choice"  # Party chooses who rolls
    GROUP = "group"               # All party members roll (D&D 5e group check)


@dataclass
class SkillCheck:
    """A skill check requirement for a choice."""
    skill: str              # Skill name (stealth, persuasion, etc.) or ability (str, dex)
    dc: int                 # Difficulty Class
    check_type: CheckType = CheckType.INDIVIDUAL  # How the check is performed
    advantage: bool = False
    disadvantage: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill,
            "dc": self.dc,
            "check_type": self.check_type.value,
            "advantage": self.advantage,
            "disadvantage": self.disadvantage,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillCheck":
        # Parse check_type - support both string and enum
        check_type_str = data.get("check_type", "individual")
        try:
            check_type = CheckType(check_type_str)
        except ValueError:
            check_type = CheckType.INDIVIDUAL

        return cls(
            skill=data.get("skill", "perception"),
            dc=data.get("dc", 15),
            check_type=check_type,
            advantage=data.get("advantage", False),
            disadvantage=data.get("disadvantage", False),
        )


@dataclass
class Choice:
    """A single choice option in a choice encounter."""
    id: str
    text: str                            # Display text for the choice
    description: Optional[str] = None    # Additional context/hint

    # Skill check (optional - if None, choice auto-succeeds)
    skill_check: Optional[SkillCheck] = None

    # Outcomes - which encounter to go to
    on_success: Optional[str] = None     # Next encounter if check succeeds or no check
    on_failure: Optional[str] = None     # Next encounter if check fails
    on_select: Optional[str] = None      # Next encounter if no skill check (auto-success)

    # Narrative for the choice result
    success_text: Optional[str] = None   # Text shown on success
    failure_text: Optional[str] = None   # Text shown on failure

    # Requirements to show this choice
    requires_flags: List[str] = field(default_factory=list)
    hidden_if_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "description": self.description,
            "skill_check": self.skill_check.to_dict() if self.skill_check else None,
            "on_success": self.on_success,
            "on_failure": self.on_failure,
            "on_select": self.on_select,
            "success_text": self.success_text,
            "failure_text": self.failure_text,
            "requires_flags": self.requires_flags,
            "hidden_if_flags": self.hidden_if_flags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Choice":
        skill_check_data = data.get("skill_check")
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            text=data.get("text", "Continue"),
            description=data.get("description"),
            skill_check=SkillCheck.from_dict(skill_check_data) if skill_check_data else None,
            on_success=data.get("on_success"),
            on_failure=data.get("on_failure"),
            on_select=data.get("on_select"),
            success_text=data.get("success_text"),
            failure_text=data.get("failure_text"),
            requires_flags=data.get("requires_flags", []),
            hidden_if_flags=data.get("hidden_if_flags", []),
        )


@dataclass
class ChoiceSetup:
    """Configuration for a choice encounter."""
    choices: List[Choice] = field(default_factory=list)

    # Who makes the check - first party member, specific character, or player chooses
    who_checks: str = "party_leader"  # party_leader, player_chooses, best_modifier

    def to_dict(self) -> Dict[str, Any]:
        return {
            "choices": [c.to_dict() for c in self.choices],
            "who_checks": self.who_checks,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChoiceSetup":
        choices = [Choice.from_dict(c) for c in data.get("choices", [])]
        return cls(
            choices=choices,
            who_checks=data.get("who_checks", "party_leader"),
        )


@dataclass
class StoryContent:
    """Narrative content for an encounter."""

    # Main story text (null = AI generates)
    intro_text: Optional[str] = None

    # Hints for AI to generate appropriate text
    intro_prompts: List[str] = field(default_factory=list)

    # Outcome texts
    outcome_victory: Optional[str] = None
    outcome_defeat: Optional[str] = None
    outcome_flee: Optional[str] = None

    # NPC dialogue trees (keyed by NPC ID)
    # Format: {"npc_id": [{"text": "Hello", "responses": [...]}]}
    npc_dialogue: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # Background music/ambiance cue
    ambiance: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intro_text": self.intro_text,
            "intro_prompts": self.intro_prompts,
            "outcome_victory": self.outcome_victory,
            "outcome_defeat": self.outcome_defeat,
            "outcome_flee": self.outcome_flee,
            "npc_dialogue": self.npc_dialogue,
            "ambiance": self.ambiance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryContent":
        return cls(
            intro_text=data.get("intro_text"),
            intro_prompts=data.get("intro_prompts", []),
            outcome_victory=data.get("outcome_victory"),
            outcome_defeat=data.get("outcome_defeat"),
            outcome_flee=data.get("outcome_flee"),
            npc_dialogue=data.get("npc_dialogue", {}),
            ambiance=data.get("ambiance"),
        )


@dataclass
class EnemySpawn:
    """Enemy spawn configuration for combat."""
    template: str       # Enemy template ID (goblin, skeleton, etc.)
    count: int = 1
    position: Optional[List[int]] = None  # [x, y] spawn position
    name_override: Optional[str] = None   # Custom name for this enemy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template": self.template,
            "count": self.count,
            "position": self.position,
            "name_override": self.name_override,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnemySpawn":
        return cls(
            template=data.get("template", "goblin"),
            count=data.get("count", 1),
            position=data.get("position"),
            name_override=data.get("name_override"),
        )


@dataclass
class GridEnvironment:
    """Combat grid environment settings."""
    width: int = 8
    height: int = 8

    # Terrain features (list of [x, y] coordinates)
    obstacles: List[List[int]] = field(default_factory=list)
    difficult_terrain: List[List[int]] = field(default_factory=list)
    water: List[List[int]] = field(default_factory=list)
    hazards: List[Dict[str, Any]] = field(default_factory=list)  # {position, type, damage}

    # Cover positions (half/three-quarters)
    cover_positions: List[Dict[str, Any]] = field(default_factory=list)

    # Spawn zones
    player_spawns: List[List[int]] = field(default_factory=list)
    enemy_spawns: List[List[int]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "obstacles": self.obstacles,
            "difficult_terrain": self.difficult_terrain,
            "water": self.water,
            "hazards": self.hazards,
            "cover_positions": self.cover_positions,
            "player_spawns": self.player_spawns,
            "enemy_spawns": self.enemy_spawns,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GridEnvironment":
        return cls(
            width=data.get("width", 8),
            height=data.get("height", 8),
            obstacles=data.get("obstacles", []),
            difficult_terrain=data.get("difficult_terrain", []),
            water=data.get("water", []),
            hazards=data.get("hazards", []),
            cover_positions=data.get("cover_positions", []),
            player_spawns=data.get("player_spawns", []),
            enemy_spawns=data.get("enemy_spawns", []),
        )


@dataclass
class CombatSetup:
    """Combat encounter configuration."""
    enemies: List[EnemySpawn] = field(default_factory=list)
    environment: GridEnvironment = field(default_factory=GridEnvironment)

    # AI behavior hints
    ai_tactics: str = "mixed"  # aggressive, defensive, mixed

    # Reinforcement triggers
    reinforcements: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {"trigger": "round_3" | "hp_below_50", "enemies": [...]}

    # Victory/defeat conditions (defaults: all enemies dead / all players dead)
    victory_condition: Optional[str] = None  # Custom victory condition
    defeat_condition: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enemies": [e.to_dict() for e in self.enemies],
            "environment": self.environment.to_dict(),
            "ai_tactics": self.ai_tactics,
            "reinforcements": self.reinforcements,
            "victory_condition": self.victory_condition,
            "defeat_condition": self.defeat_condition,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CombatSetup":
        enemies = [EnemySpawn.from_dict(e) for e in data.get("enemies", [])]
        env_data = data.get("environment", {})
        environment = GridEnvironment.from_dict(env_data) if env_data else GridEnvironment()

        return cls(
            enemies=enemies,
            environment=environment,
            ai_tactics=data.get("ai_tactics", "mixed"),
            reinforcements=data.get("reinforcements", []),
            victory_condition=data.get("victory_condition"),
            defeat_condition=data.get("defeat_condition"),
        )


@dataclass
class Rewards:
    """Rewards for completing an encounter."""
    xp: int = 0
    gold: int = 0
    items: List[str] = field(default_factory=list)  # Item template IDs

    # Story flags to set on completion
    story_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "xp": self.xp,
            "gold": self.gold,
            "items": self.items,
            "story_flags": self.story_flags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rewards":
        return cls(
            xp=data.get("xp", 0),
            gold=data.get("gold", 0),
            items=data.get("items", []),
            story_flags=data.get("story_flags", []),
        )


@dataclass
class EncounterTransitions:
    """Defines what happens after an encounter."""
    on_victory: Optional[str] = None    # Next encounter ID
    on_defeat: str = "game_over"        # "game_over", "retry", or encounter ID
    on_flee: Optional[str] = None       # Encounter ID if player flees

    # Conditional transitions based on story flags
    conditional: List[Dict[str, Any]] = field(default_factory=list)
    # Format: [{"condition": "has_flag:saved_prisoner", "goto": "encounter-3b"}]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "on_victory": self.on_victory,
            "on_defeat": self.on_defeat,
            "on_flee": self.on_flee,
            "conditional": self.conditional,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncounterTransitions":
        return cls(
            on_victory=data.get("on_victory"),
            on_defeat=data.get("on_defeat", "game_over"),
            on_flee=data.get("on_flee"),
            conditional=data.get("conditional", []),
        )


@dataclass
class Encounter:
    """A single encounter in the campaign."""
    id: str
    type: EncounterType
    name: str

    # Narrative content
    story: StoryContent = field(default_factory=StoryContent)

    # Type-specific content
    combat: Optional[CombatSetup] = None      # For combat encounters
    rest_type: Optional[RestType] = None       # For rest encounters
    choices: Optional[ChoiceSetup] = None      # For choice encounters

    # Rewards and transitions
    rewards: Rewards = field(default_factory=Rewards)
    transitions: EncounterTransitions = field(default_factory=EncounterTransitions)

    # Requirements to access this encounter
    requires_flags: List[str] = field(default_factory=list)

    # Optional difficulty override
    difficulty: Optional[Difficulty] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "story": self.story.to_dict(),
            "combat": self.combat.to_dict() if self.combat else None,
            "rest_type": self.rest_type.value if self.rest_type else None,
            "choices": self.choices.to_dict() if self.choices else None,
            "rewards": self.rewards.to_dict(),
            "transitions": self.transitions.to_dict(),
            "requires_flags": self.requires_flags,
            "difficulty": self.difficulty.value if self.difficulty else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Encounter":
        story_data = data.get("story", {})
        combat_data = data.get("combat")
        choices_data = data.get("choices")

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=EncounterType(data.get("type", "combat")),
            name=data.get("name", "Unnamed Encounter"),
            story=StoryContent.from_dict(story_data) if story_data else StoryContent(),
            combat=CombatSetup.from_dict(combat_data) if combat_data else None,
            rest_type=RestType(data["rest_type"]) if data.get("rest_type") else None,
            choices=ChoiceSetup.from_dict(choices_data) if choices_data else None,
            rewards=Rewards.from_dict(data.get("rewards", {})),
            transitions=EncounterTransitions.from_dict(data.get("transitions", {})),
            requires_flags=data.get("requires_flags", []),
            difficulty=Difficulty(data["difficulty"]) if data.get("difficulty") else None,
        )


@dataclass
class Chapter:
    """A chapter grouping multiple encounters."""
    id: str
    title: str
    description: str = ""
    encounters: List[str] = field(default_factory=list)  # Encounter IDs in order

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "encounters": self.encounters,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chapter":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", "Untitled Chapter"),
            description=data.get("description", ""),
            encounters=data.get("encounters", []),
        )


@dataclass
class CampaignSettings:
    """Campaign configuration settings."""
    difficulty: Difficulty = Difficulty.NORMAL
    allow_ai_dm: bool = True
    ai_creativity_level: float = 0.7  # 0-1, how much AI improvises
    ruleset: str = "5e_2024"  # 5e_2014, 5e_2024
    dm_mode: DMMode = DMMode.AI

    # Party settings
    max_party_size: int = 4
    allow_permadeath: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "difficulty": self.difficulty.value,
            "allow_ai_dm": self.allow_ai_dm,
            "ai_creativity_level": self.ai_creativity_level,
            "ruleset": self.ruleset,
            "dm_mode": self.dm_mode.value,
            "max_party_size": self.max_party_size,
            "allow_permadeath": self.allow_permadeath,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignSettings":
        return cls(
            difficulty=Difficulty(data.get("difficulty", "normal")),
            allow_ai_dm=data.get("allow_ai_dm", True),
            ai_creativity_level=data.get("ai_creativity_level", 0.7),
            ruleset=data.get("ruleset", "5e_2024"),
            dm_mode=DMMode(data.get("dm_mode", "ai")),
            max_party_size=data.get("max_party_size", 4),
            allow_permadeath=data.get("allow_permadeath", False),
        )


@dataclass
class Campaign:
    """A complete campaign definition."""
    id: str
    name: str
    description: str = ""
    author: str = ""
    version: str = "1.0.0"

    # Campaign structure
    settings: CampaignSettings = field(default_factory=CampaignSettings)
    chapters: List[Chapter] = field(default_factory=list)
    encounters: Dict[str, Encounter] = field(default_factory=dict)  # Keyed by encounter ID

    # Starting configuration
    starting_encounter: Optional[str] = None
    starting_level: int = 1
    starting_gold: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign": {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "author": self.author,
                "version": self.version,
                "settings": self.settings.to_dict(),
            },
            "chapters": [c.to_dict() for c in self.chapters],
            "encounters": {k: v.to_dict() for k, v in self.encounters.items()},
            "starting_encounter": self.starting_encounter,
            "starting_level": self.starting_level,
            "starting_gold": self.starting_gold,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Campaign":
        """Load campaign from JSON dict structure."""
        campaign_data = data.get("campaign", data)  # Support both nested and flat

        # Parse chapters
        chapters = [Chapter.from_dict(c) for c in data.get("chapters", [])]

        # Parse encounters
        encounters_data = data.get("encounters", {})
        encounters = {}
        for enc_id, enc_data in encounters_data.items():
            enc_data["id"] = enc_id  # Ensure ID is set
            encounters[enc_id] = Encounter.from_dict(enc_data)

        # Determine starting encounter
        starting_enc = data.get("starting_encounter")
        if not starting_enc and chapters:
            # Default to first encounter of first chapter
            if chapters[0].encounters:
                starting_enc = chapters[0].encounters[0]

        return cls(
            id=campaign_data.get("id", str(uuid.uuid4())),
            name=campaign_data.get("name", "Unnamed Campaign"),
            description=campaign_data.get("description", ""),
            author=campaign_data.get("author", ""),
            version=campaign_data.get("version", "1.0.0"),
            settings=CampaignSettings.from_dict(campaign_data.get("settings", {})),
            chapters=chapters,
            encounters=encounters,
            starting_encounter=starting_enc,
            starting_level=data.get("starting_level", 1),
            starting_gold=data.get("starting_gold", 0),
        )

    def get_encounter(self, encounter_id: str) -> Optional[Encounter]:
        """Get an encounter by ID."""
        return self.encounters.get(encounter_id)

    def get_next_encounter(self, current_id: str, outcome: str = "victory") -> Optional[str]:
        """Get next encounter ID based on outcome."""
        encounter = self.get_encounter(current_id)
        if not encounter:
            return None

        transitions = encounter.transitions

        if outcome == "victory":
            return transitions.on_victory
        elif outcome == "defeat":
            return transitions.on_defeat if transitions.on_defeat != "game_over" else None
        elif outcome == "flee":
            return transitions.on_flee

        return None

    def validate(self) -> List[str]:
        """Validate campaign structure, return list of errors."""
        errors = []

        # Check for orphan encounter references
        all_encounter_refs = set()
        for chapter in self.chapters:
            all_encounter_refs.update(chapter.encounters)

        for enc_id in all_encounter_refs:
            if enc_id not in self.encounters:
                errors.append(f"Chapter references unknown encounter: {enc_id}")

        # Check transition references
        for enc_id, encounter in self.encounters.items():
            trans = encounter.transitions
            for target in [trans.on_victory, trans.on_flee]:
                if target and target not in self.encounters:
                    errors.append(f"Encounter {enc_id} references unknown transition: {target}")

        # Check starting encounter exists
        if self.starting_encounter and self.starting_encounter not in self.encounters:
            errors.append(f"Starting encounter not found: {self.starting_encounter}")

        return errors


@dataclass
class WorldState:
    """Tracks campaign world state (flags, variables, time)."""
    flags: Dict[str, bool] = field(default_factory=dict)
    variables: Dict[str, Union[int, str, float]] = field(default_factory=dict)
    time: Dict[str, int] = field(default_factory=lambda: {"day": 1, "hour": 8})

    def has_flag(self, flag: str) -> bool:
        return self.flags.get(flag, False)

    def set_flag(self, flag: str, value: bool = True):
        self.flags[flag] = value

    def get_var(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def set_var(self, key: str, value: Union[int, str, float]):
        self.variables[key] = value

    def advance_time(self, hours: int):
        """Advance game time by hours."""
        self.time["hour"] += hours
        while self.time["hour"] >= 24:
            self.time["hour"] -= 24
            self.time["day"] += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flags": self.flags,
            "variables": self.variables,
            "time": self.time,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldState":
        return cls(
            flags=data.get("flags", {}),
            variables=data.get("variables", {}),
            time=data.get("time", {"day": 1, "hour": 8}),
        )
