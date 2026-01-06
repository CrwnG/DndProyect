"""
Difficulty Scaling for Battlemap Generation.

Scales map complexity, size, and enemy density based on party level.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Tuple
import random


class DifficultyLevel(str, Enum):
    """Encounter difficulty levels (per D&D 5e)."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    DEADLY = "deadly"


@dataclass
class DifficultyConfig:
    """Configuration for a difficulty level."""
    name: str
    map_size_multiplier: float
    enemy_count_multiplier: float
    hazard_multiplier: float
    cover_multiplier: float
    trap_dc_bonus: int
    enemy_cr_adjustment: float  # Relative to party average level


# Difficulty configurations
DIFFICULTY_CONFIGS: Dict[DifficultyLevel, DifficultyConfig] = {
    DifficultyLevel.EASY: DifficultyConfig(
        name="Easy",
        map_size_multiplier=0.8,
        enemy_count_multiplier=0.6,
        hazard_multiplier=0.3,
        cover_multiplier=1.2,  # More cover for players
        trap_dc_bonus=-2,
        enemy_cr_adjustment=-0.5,
    ),
    DifficultyLevel.MEDIUM: DifficultyConfig(
        name="Medium",
        map_size_multiplier=1.0,
        enemy_count_multiplier=1.0,
        hazard_multiplier=0.5,
        cover_multiplier=1.0,
        trap_dc_bonus=0,
        enemy_cr_adjustment=0,
    ),
    DifficultyLevel.HARD: DifficultyConfig(
        name="Hard",
        map_size_multiplier=1.1,
        enemy_count_multiplier=1.3,
        hazard_multiplier=0.7,
        cover_multiplier=0.8,  # Less cover
        trap_dc_bonus=2,
        enemy_cr_adjustment=0.5,
    ),
    DifficultyLevel.DEADLY: DifficultyConfig(
        name="Deadly",
        map_size_multiplier=1.2,
        enemy_count_multiplier=1.6,
        hazard_multiplier=1.0,
        cover_multiplier=0.6,
        trap_dc_bonus=4,
        enemy_cr_adjustment=1.0,
    ),
}


@dataclass
class ScaledEncounterParams:
    """Scaled parameters for an encounter."""
    map_width: int
    map_height: int
    num_enemies: int
    enemy_cr: float
    num_hazards: int
    trap_dc: int
    has_boss: bool
    difficulty: DifficultyLevel


class DifficultyScaler:
    """
    Scales encounter parameters based on party composition and difficulty.

    Uses D&D 5e encounter building guidelines adapted for tactical play.
    """

    # Base map sizes by tier
    BASE_MAP_SIZES = {
        1: (8, 8),    # Tier 1 (levels 1-4)
        2: (10, 10),  # Tier 2 (levels 5-10)
        3: (12, 12),  # Tier 3 (levels 11-16)
        4: (14, 14),  # Tier 4 (levels 17-20)
    }

    # Base enemy counts by party size
    BASE_ENEMY_COUNTS = {
        1: 2,
        2: 3,
        3: 4,
        4: 5,
        5: 6,
        6: 7,
    }

    def __init__(
        self,
        party_level: int = 1,
        party_size: int = 4,
        difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    ):
        """
        Initialize the difficulty scaler.

        Args:
            party_level: Average level of the party
            party_size: Number of party members
            difficulty: Desired difficulty level
        """
        self.party_level = max(1, min(20, party_level))
        self.party_size = max(1, min(8, party_size))
        self.difficulty = difficulty
        self.config = DIFFICULTY_CONFIGS[difficulty]

    @property
    def tier(self) -> int:
        """Get the party tier based on level."""
        if self.party_level <= 4:
            return 1
        elif self.party_level <= 10:
            return 2
        elif self.party_level <= 16:
            return 3
        else:
            return 4

    def get_base_map_size(self) -> Tuple[int, int]:
        """Get the base map size for current tier."""
        return self.BASE_MAP_SIZES.get(self.tier, (10, 10))

    def scale_map_size(self) -> Tuple[int, int]:
        """
        Calculate scaled map dimensions.

        Returns:
            Tuple of (width, height) in grid squares
        """
        base_w, base_h = self.get_base_map_size()

        # Apply difficulty multiplier
        scaled_w = int(base_w * self.config.map_size_multiplier)
        scaled_h = int(base_h * self.config.map_size_multiplier)

        # Add variation
        scaled_w += random.randint(-1, 2)
        scaled_h += random.randint(-1, 2)

        # Ensure minimum size
        scaled_w = max(6, scaled_w)
        scaled_h = max(6, scaled_h)

        return scaled_w, scaled_h

    def scale_enemy_count(self) -> int:
        """
        Calculate number of enemies for the encounter.

        Returns:
            Number of enemies
        """
        base_count = self.BASE_ENEMY_COUNTS.get(self.party_size, 5)

        # Apply difficulty multiplier
        scaled = base_count * self.config.enemy_count_multiplier

        # Add tier bonus
        scaled += (self.tier - 1) * 0.5

        # Add variation
        scaled += random.randint(-1, 1)

        return max(1, int(scaled))

    def get_enemy_cr(self) -> float:
        """
        Calculate appropriate enemy CR.

        Returns:
            Target CR for enemies
        """
        # Base CR roughly equals party level for a single challenging enemy
        base_cr = self.party_level / 4  # Adjusted for multiple enemies

        # Apply difficulty adjustment
        adjusted_cr = base_cr + self.config.enemy_cr_adjustment

        # Ensure minimum CR
        return max(0.125, adjusted_cr)

    def get_trap_dc(self) -> int:
        """
        Calculate trap DC for the encounter.

        Returns:
            Trap DC
        """
        # Base DC scales with tier
        base_dc = 10 + (self.tier * 2)

        # Apply difficulty bonus
        return base_dc + self.config.trap_dc_bonus

    def should_have_boss(self) -> bool:
        """
        Determine if encounter should have a boss enemy.

        Returns:
            True if encounter should include a boss
        """
        # Higher difficulty = higher chance of boss
        boss_chance = {
            DifficultyLevel.EASY: 0.1,
            DifficultyLevel.MEDIUM: 0.2,
            DifficultyLevel.HARD: 0.4,
            DifficultyLevel.DEADLY: 0.6,
        }

        return random.random() < boss_chance.get(self.difficulty, 0.2)

    def get_num_hazards(self) -> int:
        """
        Calculate number of hazards for the map.

        Returns:
            Number of hazard squares
        """
        base_hazards = 2 + self.tier

        # Apply difficulty multiplier
        scaled = base_hazards * self.config.hazard_multiplier

        return max(0, int(scaled))

    def calculate_encounter(self) -> ScaledEncounterParams:
        """
        Calculate all scaled parameters for an encounter.

        Returns:
            ScaledEncounterParams with all calculated values
        """
        width, height = self.scale_map_size()

        return ScaledEncounterParams(
            map_width=width,
            map_height=height,
            num_enemies=self.scale_enemy_count(),
            enemy_cr=self.get_enemy_cr(),
            num_hazards=self.get_num_hazards(),
            trap_dc=self.get_trap_dc(),
            has_boss=self.should_have_boss(),
            difficulty=self.difficulty,
        )

    def get_xp_budget(self) -> int:
        """
        Calculate XP budget for encounter building.

        Based on D&D 5e encounter building guidelines.

        Returns:
            XP budget for the encounter
        """
        # XP thresholds per character by level
        xp_thresholds = {
            1: {"easy": 25, "medium": 50, "hard": 75, "deadly": 100},
            2: {"easy": 50, "medium": 100, "hard": 150, "deadly": 200},
            3: {"easy": 75, "medium": 150, "hard": 225, "deadly": 400},
            4: {"easy": 125, "medium": 250, "hard": 375, "deadly": 500},
            5: {"easy": 250, "medium": 500, "hard": 750, "deadly": 1100},
            6: {"easy": 300, "medium": 600, "hard": 900, "deadly": 1400},
            7: {"easy": 350, "medium": 750, "hard": 1100, "deadly": 1700},
            8: {"easy": 450, "medium": 900, "hard": 1400, "deadly": 2100},
            9: {"easy": 550, "medium": 1100, "hard": 1600, "deadly": 2400},
            10: {"easy": 600, "medium": 1200, "hard": 1900, "deadly": 2800},
            11: {"easy": 800, "medium": 1600, "hard": 2400, "deadly": 3600},
            12: {"easy": 1000, "medium": 2000, "hard": 3000, "deadly": 4500},
            13: {"easy": 1100, "medium": 2200, "hard": 3400, "deadly": 5100},
            14: {"easy": 1250, "medium": 2500, "hard": 3800, "deadly": 5700},
            15: {"easy": 1400, "medium": 2800, "hard": 4300, "deadly": 6400},
            16: {"easy": 1600, "medium": 3200, "hard": 4800, "deadly": 7200},
            17: {"easy": 2000, "medium": 3900, "hard": 5900, "deadly": 8800},
            18: {"easy": 2100, "medium": 4200, "hard": 6300, "deadly": 9500},
            19: {"easy": 2400, "medium": 4900, "hard": 7300, "deadly": 10900},
            20: {"easy": 2800, "medium": 5700, "hard": 8500, "deadly": 12700},
        }

        level = max(1, min(20, self.party_level))
        thresholds = xp_thresholds.get(level, xp_thresholds[1])
        difficulty_key = self.difficulty.value

        per_player_xp = thresholds.get(difficulty_key, thresholds["medium"])

        return per_player_xp * self.party_size

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "party_level": self.party_level,
            "party_size": self.party_size,
            "difficulty": self.difficulty.value,
            "tier": self.tier,
            "xp_budget": self.get_xp_budget(),
        }
