"""
Random encounter generation system.

Provides terrain-based encounter tables, XP budget calculation,
and wandering monster mechanics for dynamic gameplay.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import random
import re
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class TerrainType(str, Enum):
    """Types of terrain for encounter tables."""
    DUNGEON = "dungeon"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    SWAMP = "swamp"
    UNDERDARK = "underdark"
    URBAN = "urban"
    PLAINS = "plains"
    COASTAL = "coastal"
    DESERT = "desert"
    ARCTIC = "arctic"


class EncounterDifficulty(str, Enum):
    """D&D 5e encounter difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    DEADLY = "deadly"


class ActivityType(str, Enum):
    """Party activity types for wandering monster chance."""
    TRAVELING = "traveling"       # Normal travel
    RESTING = "resting"           # Short/long rest
    EXPLORING = "exploring"       # Dungeon exploration
    CAMPING = "camping"           # Night camp
    COMBAT = "combat"             # During/after combat
    STEALTH = "stealth"          # Sneaking


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EncounterEntry:
    """
    A single entry in an encounter table.

    Each entry represents a possible random encounter with
    weighted probability and enemy composition.
    """
    name: str
    weight: int                             # Relative probability
    enemies: List[Dict[str, Any]]           # [{template, count, dice}]
    cr_range: Tuple[float, float]           # (min_cr, max_cr)
    narrative_hook: str
    special_conditions: List[str] = field(default_factory=list)
    terrain_features: List[str] = field(default_factory=list)
    loot_modifier: float = 1.0              # Multiplier for loot

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "weight": self.weight,
            "enemies": self.enemies,
            "cr_range": list(self.cr_range),
            "narrative_hook": self.narrative_hook,
            "special_conditions": self.special_conditions,
            "terrain_features": self.terrain_features,
            "loot_modifier": self.loot_modifier,
        }


@dataclass
class GeneratedEncounter:
    """Result of generating a random encounter."""
    name: str
    difficulty: EncounterDifficulty
    terrain: TerrainType
    enemies: List[Dict[str, Any]]           # Final resolved enemies
    total_xp: int
    adjusted_xp: int                        # XP adjusted for number of monsters
    narrative_hook: str
    special_conditions: List[str]
    terrain_features: List[str]
    loot_modifier: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "difficulty": self.difficulty.value,
            "terrain": self.terrain.value,
            "enemies": self.enemies,
            "total_xp": self.total_xp,
            "adjusted_xp": self.adjusted_xp,
            "narrative_hook": self.narrative_hook,
            "special_conditions": self.special_conditions,
            "terrain_features": self.terrain_features,
            "loot_modifier": self.loot_modifier,
        }


# =============================================================================
# XP BUDGET TABLES (D&D 5e DMG)
# =============================================================================

# XP thresholds per character level
XP_THRESHOLDS = {
    # level: (easy, medium, hard, deadly)
    1: (25, 50, 75, 100),
    2: (50, 100, 150, 200),
    3: (75, 150, 225, 400),
    4: (125, 250, 375, 500),
    5: (250, 500, 750, 1100),
    6: (300, 600, 900, 1400),
    7: (350, 750, 1100, 1700),
    8: (450, 900, 1400, 2100),
    9: (550, 1100, 1600, 2400),
    10: (600, 1200, 1900, 2800),
    11: (800, 1600, 2400, 3600),
    12: (1000, 2000, 3000, 4500),
    13: (1100, 2200, 3400, 5100),
    14: (1250, 2500, 3800, 5700),
    15: (1400, 2800, 4300, 6400),
    16: (1600, 3200, 4800, 7200),
    17: (2000, 3900, 5900, 8800),
    18: (2100, 4200, 6300, 9500),
    19: (2400, 4900, 7300, 10900),
    20: (2800, 5700, 8500, 12700),
}

# CR to XP mapping
CR_XP = {
    0: 10, 0.125: 25, 0.25: 50, 0.5: 100,
    1: 200, 2: 450, 3: 700, 4: 1100, 5: 1800,
    6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900,
    11: 7200, 12: 8400, 13: 10000, 14: 11500, 15: 13000,
    16: 15000, 17: 18000, 18: 20000, 19: 22000, 20: 25000,
    21: 33000, 22: 41000, 23: 50000, 24: 62000, 25: 75000,
    26: 90000, 27: 105000, 28: 120000, 29: 135000, 30: 155000,
}

# Multiplier based on number of monsters
MONSTER_MULTIPLIERS = [
    (1, 1.0),
    (2, 1.5),
    (3, 2.0),    # 3-6
    (7, 2.5),    # 7-10
    (11, 3.0),   # 11-14
    (15, 4.0),   # 15+
]


# =============================================================================
# ENCOUNTER TABLES
# =============================================================================

ENCOUNTER_TABLES: Dict[TerrainType, List[EncounterEntry]] = {
    TerrainType.DUNGEON: [
        EncounterEntry(
            name="Goblin Patrol",
            weight=20,
            enemies=[{"template": "goblin", "count": "1d4+2"}],
            cr_range=(0.25, 0.25),
            narrative_hook="Chittering voices echo from ahead. A goblin patrol rounds the corner.",
            special_conditions=["ambush_possible"],
        ),
        EncounterEntry(
            name="Skeleton Guardians",
            weight=15,
            enemies=[{"template": "skeleton", "count": "1d6"}],
            cr_range=(0.25, 0.25),
            narrative_hook="Bones clatter as ancient guardians rise from the shadows.",
            terrain_features=["dim_light", "bones_scattered"],
        ),
        EncounterEntry(
            name="Giant Rats",
            weight=25,
            enemies=[{"template": "giant_rat", "count": "2d4"}],
            cr_range=(0.125, 0.125),
            narrative_hook="Squeaking fills the air as large rats emerge from the darkness.",
            special_conditions=["disease_risk"],
        ),
        EncounterEntry(
            name="Orc Raiders",
            weight=10,
            enemies=[{"template": "orc", "count": "1d3"}],
            cr_range=(0.5, 0.5),
            narrative_hook="Heavy footsteps and guttural speech - orcs are nearby.",
            special_conditions=["negotiations_possible"],
        ),
        EncounterEntry(
            name="Zombie Shamble",
            weight=15,
            enemies=[{"template": "zombie", "count": "1d4"}],
            cr_range=(0.25, 0.25),
            narrative_hook="The stench of decay precedes shuffling, rotting corpses.",
            terrain_features=["foul_smell"],
        ),
        EncounterEntry(
            name="Bugbear Ambush",
            weight=8,
            enemies=[{"template": "bugbear", "count": "1d2"}],
            cr_range=(1, 1),
            narrative_hook="Silence... then a massive shape drops from above!",
            special_conditions=["ambush", "surprise_round"],
            loot_modifier=1.5,
        ),
        EncounterEntry(
            name="Mimic Trap",
            weight=5,
            enemies=[{"template": "mimic", "count": "1"}],
            cr_range=(2, 2),
            narrative_hook="That treasure chest... something's not right about it.",
            special_conditions=["disguised"],
            terrain_features=["treasure_room"],
            loot_modifier=2.0,
        ),
        EncounterEntry(
            name="Gelatinous Cube",
            weight=5,
            enemies=[{"template": "gelatinous_cube", "count": "1"}],
            cr_range=(2, 2),
            narrative_hook="The corridor seems oddly clean. Then you notice the shimmer...",
            special_conditions=["nearly_invisible"],
            terrain_features=["narrow_corridor"],
        ),
    ],
    TerrainType.FOREST: [
        EncounterEntry(
            name="Wolf Pack",
            weight=25,
            enemies=[{"template": "wolf", "count": "1d6"}],
            cr_range=(0.25, 0.25),
            narrative_hook="Howls echo through the trees as shapes emerge from the underbrush.",
            special_conditions=["pack_tactics"],
        ),
        EncounterEntry(
            name="Goblin Scouts",
            weight=20,
            enemies=[{"template": "goblin", "count": "1d4"}, {"template": "goblin_boss", "count": "1"}],
            cr_range=(0.25, 1),
            narrative_hook="Crude traps and goblin tracks - a scouting party is nearby.",
            special_conditions=["traps_possible"],
            terrain_features=["undergrowth"],
        ),
        EncounterEntry(
            name="Owlbear",
            weight=10,
            enemies=[{"template": "owlbear", "count": "1"}],
            cr_range=(3, 3),
            narrative_hook="A terrifying screech echoes as a feathered horror bursts from the trees!",
            special_conditions=["territorial"],
            loot_modifier=0.5,
        ),
        EncounterEntry(
            name="Bandit Ambush",
            weight=15,
            enemies=[{"template": "bandit", "count": "1d4+2"}, {"template": "bandit_captain", "count": "1"}],
            cr_range=(0.125, 2),
            narrative_hook="\"Your money or your life!\" Figures step out from behind the trees.",
            special_conditions=["negotiations_possible", "ambush"],
        ),
        EncounterEntry(
            name="Giant Spider Nest",
            weight=15,
            enemies=[{"template": "giant_spider", "count": "1d3"}],
            cr_range=(1, 1),
            narrative_hook="Webs stretch between the trees. Something moves in the shadows above.",
            terrain_features=["web_covered", "difficult_terrain"],
        ),
        EncounterEntry(
            name="Dryad's Grove",
            weight=8,
            enemies=[{"template": "dryad", "count": "1"}],
            cr_range=(1, 1),
            narrative_hook="The forest seems to watch you. A beautiful figure emerges from a tree.",
            special_conditions=["negotiations_possible", "charm_possible"],
        ),
        EncounterEntry(
            name="Treant Guardian",
            weight=5,
            enemies=[{"template": "treant", "count": "1"}],
            cr_range=(9, 9),
            narrative_hook="That ancient oak... did it just move?",
            special_conditions=["negotiations_possible", "territorial"],
        ),
    ],
    TerrainType.MOUNTAIN: [
        EncounterEntry(
            name="Harpy Flight",
            weight=15,
            enemies=[{"template": "harpy", "count": "1d3"}],
            cr_range=(1, 1),
            narrative_hook="Screeching song echoes off the cliffs as winged figures descend.",
            terrain_features=["cliffs", "elevation"],
        ),
        EncounterEntry(
            name="Orc War Band",
            weight=20,
            enemies=[{"template": "orc", "count": "1d4+1"}, {"template": "orc_war_chief", "count": "1"}],
            cr_range=(0.5, 4),
            narrative_hook="War drums echo from the mountain pass. Orcs block your path.",
            special_conditions=["war_party"],
        ),
        EncounterEntry(
            name="Stone Giant",
            weight=5,
            enemies=[{"template": "stone_giant", "count": "1"}],
            cr_range=(7, 7),
            narrative_hook="Boulders begin to move. A massive figure rises from the rocks.",
            special_conditions=["negotiations_possible"],
            terrain_features=["boulder_field"],
        ),
        EncounterEntry(
            name="Peryton Attack",
            weight=12,
            enemies=[{"template": "peryton", "count": "1d2"}],
            cr_range=(2, 2),
            narrative_hook="Shadows pass overhead. Antlered, winged predators circle above.",
            terrain_features=["open_sky"],
        ),
        EncounterEntry(
            name="Ogre Camp",
            weight=15,
            enemies=[{"template": "ogre", "count": "1d2"}],
            cr_range=(2, 2),
            narrative_hook="Smoke rises from a cave entrance. The stench of ogre is unmistakable.",
            terrain_features=["cave_entrance"],
            loot_modifier=1.5,
        ),
        EncounterEntry(
            name="Hippogriff Nest",
            weight=10,
            enemies=[{"template": "hippogriff", "count": "1d3"}],
            cr_range=(1, 1),
            narrative_hook="Screeches from above - you've wandered too close to a nest.",
            special_conditions=["territorial", "tameable"],
        ),
    ],
    TerrainType.SWAMP: [
        EncounterEntry(
            name="Lizardfolk Hunters",
            weight=20,
            enemies=[{"template": "lizardfolk", "count": "1d4+1"}],
            cr_range=(0.5, 0.5),
            narrative_hook="Ripples in the water. Scaled figures rise from the muck.",
            special_conditions=["amphibious", "negotiations_possible"],
        ),
        EncounterEntry(
            name="Giant Crocodile",
            weight=15,
            enemies=[{"template": "giant_crocodile", "count": "1"}],
            cr_range=(5, 5),
            narrative_hook="What you thought was a log suddenly moves...",
            terrain_features=["deep_water", "difficult_terrain"],
        ),
        EncounterEntry(
            name="Will-o'-Wisps",
            weight=12,
            enemies=[{"template": "will_o_wisp", "count": "1d3"}],
            cr_range=(2, 2),
            narrative_hook="Ghostly lights flicker in the mist, beckoning you deeper...",
            special_conditions=["lure", "invisible"],
            terrain_features=["heavy_fog"],
        ),
        EncounterEntry(
            name="Shambling Mound",
            weight=8,
            enemies=[{"template": "shambling_mound", "count": "1"}],
            cr_range=(5, 5),
            narrative_hook="That pile of vegetation is moving. And it's hungry.",
            terrain_features=["heavy_vegetation"],
        ),
        EncounterEntry(
            name="Bullywug Tribe",
            weight=18,
            enemies=[{"template": "bullywug", "count": "2d4"}],
            cr_range=(0.25, 0.25),
            narrative_hook="Croaking fills the air. Frog-like creatures emerge from the water.",
            special_conditions=["amphibious"],
        ),
        EncounterEntry(
            name="Black Dragon Wyrmling",
            weight=5,
            enemies=[{"template": "black_dragon_wyrmling", "count": "1"}],
            cr_range=(2, 2),
            narrative_hook="Acid drips from above. A small but deadly dragon surveys its domain.",
            special_conditions=["lair_nearby"],
            loot_modifier=2.0,
        ),
    ],
    TerrainType.URBAN: [
        EncounterEntry(
            name="Street Gang",
            weight=25,
            enemies=[{"template": "thug", "count": "1d4+1"}],
            cr_range=(0.5, 0.5),
            narrative_hook="\"You're in the wrong neighborhood, friends.\" Thugs emerge from the shadows.",
            special_conditions=["negotiations_possible"],
        ),
        EncounterEntry(
            name="Assassin's Mark",
            weight=8,
            enemies=[{"template": "assassin", "count": "1"}],
            cr_range=(8, 8),
            narrative_hook="A glint of steel in the crowd. Someone has paid for your death.",
            special_conditions=["ambush", "poison"],
        ),
        EncounterEntry(
            name="Wererat Infestation",
            weight=12,
            enemies=[{"template": "wererat", "count": "1d3"}],
            cr_range=(2, 2),
            narrative_hook="The beggars in the alley... their eyes are too intelligent.",
            special_conditions=["lycanthropy_risk", "sewer_access"],
        ),
        EncounterEntry(
            name="Cult Gathering",
            weight=15,
            enemies=[{"template": "cultist", "count": "1d6"}, {"template": "cult_fanatic", "count": "1"}],
            cr_range=(0.125, 2),
            narrative_hook="Chanting echoes from the abandoned building. Dark rituals are underway.",
            special_conditions=["ritual_in_progress"],
        ),
        EncounterEntry(
            name="Doppelganger",
            weight=10,
            enemies=[{"template": "doppelganger", "count": "1"}],
            cr_range=(3, 3),
            narrative_hook="Something about that familiar face seems... off.",
            special_conditions=["shapeshifter", "social_encounter"],
        ),
    ],
    TerrainType.PLAINS: [
        EncounterEntry(
            name="Gnoll Pack",
            weight=20,
            enemies=[{"template": "gnoll", "count": "1d4+1"}, {"template": "gnoll_pack_lord", "count": "1"}],
            cr_range=(0.5, 2),
            narrative_hook="Hyena-like laughter echoes across the grassland. Gnolls!",
            special_conditions=["bloodthirsty"],
        ),
        EncounterEntry(
            name="Centaur Patrol",
            weight=15,
            enemies=[{"template": "centaur", "count": "1d3"}],
            cr_range=(2, 2),
            narrative_hook="Hoofbeats thunder as horse-bodied warriors approach.",
            special_conditions=["negotiations_possible", "territorial"],
        ),
        EncounterEntry(
            name="Ankheg",
            weight=12,
            enemies=[{"template": "ankheg", "count": "1"}],
            cr_range=(2, 2),
            narrative_hook="The ground trembles. Something bursts up from below!",
            terrain_features=["burrowed_tunnels"],
        ),
        EncounterEntry(
            name="Griffon Hunt",
            weight=10,
            enemies=[{"template": "griffon", "count": "1d2"}],
            cr_range=(2, 2),
            narrative_hook="Shadows pass overhead. Majestic but deadly hunters circle above.",
            special_conditions=["aerial_combat"],
        ),
    ],
}


# =============================================================================
# DICE NOTATION PARSER
# =============================================================================

def parse_dice_notation(notation: str) -> int:
    """
    Parse dice notation and return a result.

    Supports: XdY, XdY+Z, XdY-Z, plain numbers

    Args:
        notation: Dice notation string (e.g., "2d6+3", "1d4", "5")

    Returns:
        Rolled result
    """
    if isinstance(notation, int):
        return notation

    notation = str(notation).strip().lower()

    # Plain number
    if notation.isdigit():
        return int(notation)

    # Dice notation: XdY+Z or XdY-Z or XdY
    match = re.match(r'(\d+)d(\d+)([+-]\d+)?', notation)
    if not match:
        logger.warning(f"Invalid dice notation: {notation}, defaulting to 1")
        return 1

    num_dice = int(match.group(1))
    die_size = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0

    total = sum(random.randint(1, die_size) for _ in range(num_dice))
    return max(1, total + modifier)


# =============================================================================
# RANDOM ENCOUNTER GENERATOR
# =============================================================================

class RandomEncounterGenerator:
    """
    Generates random encounters based on terrain and party level.

    Uses D&D 5e XP budget system to create balanced encounters.
    """

    def __init__(self):
        """Initialize the generator."""
        logger.info("Random encounter generator initialized")

    def calculate_xp_budget(
        self,
        party_level: int,
        party_size: int,
        difficulty: EncounterDifficulty,
    ) -> int:
        """
        Calculate XP budget for an encounter.

        Args:
            party_level: Average party level
            party_size: Number of party members
            difficulty: Desired difficulty

        Returns:
            Total XP budget
        """
        level = max(1, min(20, party_level))
        thresholds = XP_THRESHOLDS[level]

        difficulty_index = {
            EncounterDifficulty.EASY: 0,
            EncounterDifficulty.MEDIUM: 1,
            EncounterDifficulty.HARD: 2,
            EncounterDifficulty.DEADLY: 3,
        }

        per_character = thresholds[difficulty_index[difficulty]]
        return per_character * party_size

    def get_monster_multiplier(self, monster_count: int) -> float:
        """Get XP multiplier based on number of monsters."""
        for threshold, multiplier in reversed(MONSTER_MULTIPLIERS):
            if monster_count >= threshold:
                return multiplier
        return 1.0

    def generate_encounter(
        self,
        terrain: TerrainType,
        party_level: int,
        party_size: int,
        difficulty: EncounterDifficulty = EncounterDifficulty.MEDIUM,
    ) -> GeneratedEncounter:
        """
        Generate a random encounter.

        Args:
            terrain: Type of terrain
            party_level: Average party level
            party_size: Number of party members
            difficulty: Desired difficulty

        Returns:
            GeneratedEncounter with resolved enemies
        """
        xp_budget = self.calculate_xp_budget(party_level, party_size, difficulty)

        # Get encounter table for terrain
        table = ENCOUNTER_TABLES.get(terrain, ENCOUNTER_TABLES[TerrainType.DUNGEON])

        # Weighted random selection
        entry = self._weighted_select(table)

        # Resolve enemy counts
        enemies, total_xp = self._resolve_enemies(entry.enemies, xp_budget)

        # Calculate adjusted XP
        monster_count = sum(e.get("count", 1) for e in enemies)
        multiplier = self.get_monster_multiplier(monster_count)
        adjusted_xp = int(total_xp * multiplier)

        return GeneratedEncounter(
            name=entry.name,
            difficulty=difficulty,
            terrain=terrain,
            enemies=enemies,
            total_xp=total_xp,
            adjusted_xp=adjusted_xp,
            narrative_hook=entry.narrative_hook,
            special_conditions=entry.special_conditions,
            terrain_features=entry.terrain_features,
            loot_modifier=entry.loot_modifier,
        )

    def _weighted_select(self, table: List[EncounterEntry]) -> EncounterEntry:
        """Select an entry from table using weights."""
        total_weight = sum(e.weight for e in table)
        roll = random.randint(1, total_weight)

        cumulative = 0
        for entry in table:
            cumulative += entry.weight
            if roll <= cumulative:
                return entry

        return table[-1]

    def _resolve_enemies(
        self,
        enemy_specs: List[Dict[str, Any]],
        xp_budget: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Resolve enemy specifications to concrete enemies.

        Args:
            enemy_specs: List of enemy specifications with dice counts
            xp_budget: Target XP budget

        Returns:
            Tuple of (resolved enemies, total XP)
        """
        enemies = []
        total_xp = 0

        for spec in enemy_specs:
            template = spec.get("template", "goblin")
            count_spec = spec.get("count", 1)

            # Parse count (could be dice notation)
            count = parse_dice_notation(count_spec)

            # Get CR for this template (simplified - would lookup from enemy data)
            cr = self._get_template_cr(template)
            xp_per_enemy = CR_XP.get(cr, 25)

            enemies.append({
                "template": template,
                "count": count,
                "cr": cr,
                "xp_each": xp_per_enemy,
                "xp_total": xp_per_enemy * count,
            })

            total_xp += xp_per_enemy * count

        return enemies, total_xp

    def _get_template_cr(self, template: str) -> float:
        """Get CR for an enemy template."""
        # Simplified CR lookup - would use actual enemy data
        cr_map = {
            "goblin": 0.25,
            "goblin_boss": 1,
            "skeleton": 0.25,
            "zombie": 0.25,
            "orc": 0.5,
            "orc_war_chief": 4,
            "giant_rat": 0.125,
            "wolf": 0.25,
            "bugbear": 1,
            "mimic": 2,
            "gelatinous_cube": 2,
            "owlbear": 3,
            "bandit": 0.125,
            "bandit_captain": 2,
            "giant_spider": 1,
            "dryad": 1,
            "treant": 9,
            "harpy": 1,
            "stone_giant": 7,
            "peryton": 2,
            "ogre": 2,
            "hippogriff": 1,
            "lizardfolk": 0.5,
            "giant_crocodile": 5,
            "will_o_wisp": 2,
            "shambling_mound": 5,
            "bullywug": 0.25,
            "black_dragon_wyrmling": 2,
            "thug": 0.5,
            "assassin": 8,
            "wererat": 2,
            "cultist": 0.125,
            "cult_fanatic": 2,
            "doppelganger": 3,
            "gnoll": 0.5,
            "gnoll_pack_lord": 2,
            "centaur": 2,
            "ankheg": 2,
            "griffon": 2,
        }
        return cr_map.get(template.lower(), 0.5)


# =============================================================================
# WANDERING MONSTER SYSTEM
# =============================================================================

class WanderingMonsterSystem:
    """
    Handles random encounter checks based on party activity.

    Different activities have different encounter chances.
    """

    # Base chance of encounter per hour (percentage)
    ENCOUNTER_CHANCES = {
        ActivityType.TRAVELING: 10,
        ActivityType.RESTING: 5,
        ActivityType.EXPLORING: 20,
        ActivityType.CAMPING: 15,
        ActivityType.COMBAT: 25,
        ActivityType.STEALTH: 5,
    }

    def __init__(self, generator: Optional[RandomEncounterGenerator] = None):
        """Initialize the system."""
        self._generator = generator or RandomEncounterGenerator()
        logger.info("Wandering monster system initialized")

    def check_for_encounter(
        self,
        activity: ActivityType,
        hours_passed: float = 1.0,
        stealth_modifier: int = 0,
        danger_level: int = 0,
    ) -> Tuple[bool, Optional[int]]:
        """
        Roll to check if a wandering encounter occurs.

        Args:
            activity: Current party activity
            hours_passed: Time spent on activity
            stealth_modifier: Bonus/penalty to avoid encounters
            danger_level: Area danger level modifier (-5 to +5)

        Returns:
            Tuple of (encounter_triggered, roll_result)
        """
        base_chance = self.ENCOUNTER_CHANCES.get(activity, 10)

        # Modify by time
        modified_chance = base_chance * hours_passed

        # Modify by stealth and danger
        modified_chance -= stealth_modifier
        modified_chance += danger_level * 5

        # Clamp to 5-95%
        modified_chance = max(5, min(95, modified_chance))

        roll = random.randint(1, 100)
        triggered = roll <= modified_chance

        logger.debug(
            f"Wandering check: {activity.value}, chance={modified_chance}%, "
            f"roll={roll}, triggered={triggered}"
        )

        return triggered, roll

    def generate_wandering_encounter(
        self,
        terrain: TerrainType,
        party_level: int,
        party_size: int,
    ) -> GeneratedEncounter:
        """
        Generate a wandering encounter (typically easier difficulty).

        Args:
            terrain: Current terrain
            party_level: Party level
            party_size: Party size

        Returns:
            Generated encounter (usually easy or medium)
        """
        # Wandering encounters tend to be easier
        difficulty = random.choices(
            [EncounterDifficulty.EASY, EncounterDifficulty.MEDIUM, EncounterDifficulty.HARD],
            weights=[50, 40, 10],
        )[0]

        return self._generator.generate_encounter(
            terrain=terrain,
            party_level=party_level,
            party_size=party_size,
            difficulty=difficulty,
        )


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_generator: Optional[RandomEncounterGenerator] = None
_wandering_system: Optional[WanderingMonsterSystem] = None


def get_encounter_generator() -> RandomEncounterGenerator:
    """Get the singleton encounter generator."""
    global _generator
    if _generator is None:
        _generator = RandomEncounterGenerator()
    return _generator


def get_wandering_system() -> WanderingMonsterSystem:
    """Get the singleton wandering monster system."""
    global _wandering_system
    if _wandering_system is None:
        _wandering_system = WanderingMonsterSystem()
    return _wandering_system
