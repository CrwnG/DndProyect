"""
Room Templates for Battlemap Generation.

Defines different room types with terrain features and spawn points.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Tuple, Optional
import random


class RoomType(str, Enum):
    """Types of rooms that can be generated."""
    CORRIDOR = "corridor"
    CHAMBER = "chamber"
    ARENA = "arena"
    LAIR = "lair"
    TREASURY = "treasury"
    ENTRANCE = "entrance"
    SHRINE = "shrine"
    PRISON = "prison"


class TerrainFeature(str, Enum):
    """Terrain features that can be placed in rooms."""
    NORMAL = "normal"
    DIFFICULT = "difficult"
    WATER = "water"
    PIT = "pit"
    PILLAR = "pillar"           # Provides cover
    STATUE = "statue"           # Provides cover
    RUBBLE = "rubble"           # Difficult terrain
    BRAZIER = "brazier"         # Light source, can be hazard
    ALTAR = "altar"             # Cover, interaction point
    CRATE = "crate"             # Half cover
    TABLE = "table"             # Half cover
    TRAP = "trap"               # Hidden hazard
    LAVA = "lava"               # Hazardous terrain
    ICE = "ice"                 # Slippery, difficult terrain


@dataclass
class SpawnPoint:
    """A spawn point for enemies or players."""
    x: int
    y: int
    spawn_type: str  # "player", "enemy", "boss", "minion"
    priority: int = 0  # Higher priority = spawn first


@dataclass
class TerrainPlacement:
    """A terrain feature placement."""
    x: int
    y: int
    feature: TerrainFeature
    elevation: int = 0
    cover_value: int = 0  # 0=none, 2=half, 5=three-quarters
    is_hazard: bool = False
    hazard_damage: str = ""
    hazard_type: str = ""


@dataclass
class RoomTemplate:
    """Template for a room type with terrain and spawn info."""
    room_type: RoomType
    name: str
    min_width: int
    max_width: int
    min_height: int
    max_height: int
    description: str = ""

    # Terrain generation rules
    pillar_chance: float = 0.0        # Chance of pillars (0-1)
    difficult_terrain_chance: float = 0.0
    water_chance: float = 0.0
    pit_chance: float = 0.0
    cover_objects_chance: float = 0.0  # Crates, tables, etc.
    hazard_chance: float = 0.0        # Traps, braziers

    # Spawn configuration
    player_spawn_edge: str = "south"  # Which edge players spawn on
    enemy_spawn_edge: str = "north"   # Which edge enemies spawn on
    boss_spawn_center: bool = False   # Boss spawns in center

    # Special features
    has_altar: bool = False
    has_throne: bool = False
    has_treasure: bool = False

    def generate_terrain(
        self,
        width: int,
        height: int,
        seed: Optional[int] = None
    ) -> List[TerrainPlacement]:
        """
        Generate terrain features for a room of given size.

        Args:
            width: Room width in squares
            height: Room height in squares
            seed: Random seed for reproducibility

        Returns:
            List of terrain placements
        """
        if seed is not None:
            random.seed(seed)

        terrain = []

        # Generate pillars
        if self.pillar_chance > 0 and random.random() < self.pillar_chance:
            terrain.extend(self._generate_pillars(width, height))

        # Generate difficult terrain patches
        if self.difficult_terrain_chance > 0:
            terrain.extend(self._generate_difficult_terrain(width, height))

        # Generate water features
        if self.water_chance > 0 and random.random() < self.water_chance:
            terrain.extend(self._generate_water(width, height))

        # Generate pits
        if self.pit_chance > 0 and random.random() < self.pit_chance:
            terrain.extend(self._generate_pits(width, height))

        # Generate cover objects
        if self.cover_objects_chance > 0:
            terrain.extend(self._generate_cover_objects(width, height))

        # Generate hazards
        if self.hazard_chance > 0:
            terrain.extend(self._generate_hazards(width, height))

        # Special features
        if self.has_altar:
            cx, cy = width // 2, height // 2
            terrain.append(TerrainPlacement(
                x=cx, y=cy, feature=TerrainFeature.ALTAR,
                cover_value=2, elevation=0
            ))

        return terrain

    def _generate_pillars(self, width: int, height: int) -> List[TerrainPlacement]:
        """Generate pillar placements in a symmetric pattern."""
        pillars = []

        # Calculate pillar positions (typically at corners of inner area)
        margin = 2
        if width > 6 and height > 6:
            positions = [
                (margin, margin),
                (margin, height - margin - 1),
                (width - margin - 1, margin),
                (width - margin - 1, height - margin - 1),
            ]

            # Add middle pillars for larger rooms
            if width > 10 and height > 8:
                mid_x = width // 2
                positions.extend([
                    (mid_x, margin),
                    (mid_x, height - margin - 1),
                ])

            for x, y in positions:
                pillars.append(TerrainPlacement(
                    x=x, y=y, feature=TerrainFeature.PILLAR,
                    cover_value=5  # Three-quarters cover
                ))

        return pillars

    def _generate_difficult_terrain(self, width: int, height: int) -> List[TerrainPlacement]:
        """Generate patches of difficult terrain."""
        terrain = []
        num_patches = int(self.difficult_terrain_chance * 3) + 1

        for _ in range(num_patches):
            if random.random() > self.difficult_terrain_chance:
                continue

            # Random patch location
            cx = random.randint(1, width - 2)
            cy = random.randint(1, height - 2)

            # Random patch size (1-3 squares radius)
            radius = random.randint(1, min(2, width // 4, height // 4))

            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < width and 0 <= y < height:
                        if random.random() < 0.6:  # Not all squares in patch
                            terrain.append(TerrainPlacement(
                                x=x, y=y, feature=TerrainFeature.RUBBLE
                            ))

        return terrain

    def _generate_water(self, width: int, height: int) -> List[TerrainPlacement]:
        """Generate water features (stream or pool)."""
        water = []

        if random.random() < 0.5:
            # Stream running through room
            if random.random() < 0.5:
                # Horizontal stream
                y = height // 2
                for x in range(width):
                    water.append(TerrainPlacement(
                        x=x, y=y, feature=TerrainFeature.WATER
                    ))
            else:
                # Vertical stream
                x = width // 2
                for y in range(height):
                    water.append(TerrainPlacement(
                        x=x, y=y, feature=TerrainFeature.WATER
                    ))
        else:
            # Pool in corner or center
            cx = random.choice([2, width - 3, width // 2])
            cy = random.choice([2, height - 3, height // 2])
            radius = random.randint(1, 2)

            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < width and 0 <= y < height:
                        water.append(TerrainPlacement(
                            x=x, y=y, feature=TerrainFeature.WATER
                        ))

        return water

    def _generate_pits(self, width: int, height: int) -> List[TerrainPlacement]:
        """Generate pit hazards."""
        pits = []
        num_pits = random.randint(1, 3)

        for _ in range(num_pits):
            x = random.randint(2, width - 3)
            y = random.randint(2, height - 3)
            pits.append(TerrainPlacement(
                x=x, y=y, feature=TerrainFeature.PIT,
                is_hazard=True, hazard_damage="2d6", hazard_type="falling"
            ))

        return pits

    def _generate_cover_objects(self, width: int, height: int) -> List[TerrainPlacement]:
        """Generate cover objects (crates, tables)."""
        objects = []
        num_objects = int(self.cover_objects_chance * 5) + random.randint(0, 2)

        for _ in range(num_objects):
            x = random.randint(1, width - 2)
            y = random.randint(1, height - 2)
            feature = random.choice([TerrainFeature.CRATE, TerrainFeature.TABLE])
            objects.append(TerrainPlacement(
                x=x, y=y, feature=feature, cover_value=2
            ))

        return objects

    def _generate_hazards(self, width: int, height: int) -> List[TerrainPlacement]:
        """Generate hazard terrain (braziers, traps)."""
        hazards = []

        if random.random() < self.hazard_chance:
            # Braziers at edges
            if random.random() < 0.5:
                positions = [(0, 0), (0, height - 1), (width - 1, 0), (width - 1, height - 1)]
                for x, y in positions:
                    if random.random() < 0.5:
                        hazards.append(TerrainPlacement(
                            x=x, y=y, feature=TerrainFeature.BRAZIER,
                            is_hazard=True, hazard_damage="1d6", hazard_type="fire"
                        ))

            # Hidden traps
            if random.random() < self.hazard_chance:
                num_traps = random.randint(1, 2)
                for _ in range(num_traps):
                    x = random.randint(2, width - 3)
                    y = random.randint(2, height - 3)
                    hazards.append(TerrainPlacement(
                        x=x, y=y, feature=TerrainFeature.TRAP,
                        is_hazard=True, hazard_damage="2d6", hazard_type="piercing"
                    ))

        return hazards

    def generate_spawn_points(
        self,
        width: int,
        height: int,
        num_players: int = 4,
        num_enemies: int = 4,
        has_boss: bool = False
    ) -> List[SpawnPoint]:
        """
        Generate spawn points for players and enemies.

        Args:
            width: Room width
            height: Room height
            num_players: Number of player spawn points
            num_enemies: Number of enemy spawn points
            has_boss: Include a boss spawn point

        Returns:
            List of spawn points
        """
        spawns = []

        # Player spawns
        player_positions = self._get_edge_positions(
            width, height, self.player_spawn_edge, num_players
        )
        for i, (x, y) in enumerate(player_positions):
            spawns.append(SpawnPoint(x=x, y=y, spawn_type="player", priority=i))

        # Enemy spawns
        enemy_positions = self._get_edge_positions(
            width, height, self.enemy_spawn_edge, num_enemies
        )
        for i, (x, y) in enumerate(enemy_positions):
            spawns.append(SpawnPoint(x=x, y=y, spawn_type="enemy", priority=i))

        # Boss spawn
        if has_boss and self.boss_spawn_center:
            cx, cy = width // 2, height // 2
            spawns.append(SpawnPoint(x=cx, y=cy, spawn_type="boss", priority=0))

        return spawns

    def _get_edge_positions(
        self,
        width: int,
        height: int,
        edge: str,
        count: int
    ) -> List[Tuple[int, int]]:
        """Get evenly spaced positions along an edge."""
        positions = []

        if edge == "north":
            y = 1
            spacing = max(1, (width - 2) // max(1, count))
            for i in range(count):
                x = 1 + i * spacing
                if x < width - 1:
                    positions.append((x, y))
        elif edge == "south":
            y = height - 2
            spacing = max(1, (width - 2) // max(1, count))
            for i in range(count):
                x = 1 + i * spacing
                if x < width - 1:
                    positions.append((x, y))
        elif edge == "east":
            x = width - 2
            spacing = max(1, (height - 2) // max(1, count))
            for i in range(count):
                y = 1 + i * spacing
                if y < height - 1:
                    positions.append((x, y))
        elif edge == "west":
            x = 1
            spacing = max(1, (height - 2) // max(1, count))
            for i in range(count):
                y = 1 + i * spacing
                if y < height - 1:
                    positions.append((x, y))

        return positions


# Pre-defined room templates
ROOM_TEMPLATES: Dict[RoomType, RoomTemplate] = {
    RoomType.CORRIDOR: RoomTemplate(
        room_type=RoomType.CORRIDOR,
        name="Corridor",
        min_width=4, max_width=6,
        min_height=8, max_height=16,
        description="A narrow passage connecting areas",
        pillar_chance=0.0,
        difficult_terrain_chance=0.1,
        cover_objects_chance=0.2,
    ),
    RoomType.CHAMBER: RoomTemplate(
        room_type=RoomType.CHAMBER,
        name="Chamber",
        min_width=8, max_width=12,
        min_height=8, max_height=12,
        description="A standard room for encounters",
        pillar_chance=0.4,
        difficult_terrain_chance=0.2,
        cover_objects_chance=0.3,
        hazard_chance=0.1,
    ),
    RoomType.ARENA: RoomTemplate(
        room_type=RoomType.ARENA,
        name="Arena",
        min_width=12, max_width=16,
        min_height=12, max_height=16,
        description="A large open space for major battles",
        pillar_chance=0.6,
        difficult_terrain_chance=0.1,
        pit_chance=0.2,
        boss_spawn_center=True,
    ),
    RoomType.LAIR: RoomTemplate(
        room_type=RoomType.LAIR,
        name="Lair",
        min_width=10, max_width=14,
        min_height=10, max_height=14,
        description="A creature's den with hazards",
        pillar_chance=0.3,
        difficult_terrain_chance=0.4,
        water_chance=0.3,
        hazard_chance=0.3,
        boss_spawn_center=True,
    ),
    RoomType.TREASURY: RoomTemplate(
        room_type=RoomType.TREASURY,
        name="Treasury",
        min_width=6, max_width=10,
        min_height=6, max_height=10,
        description="A room filled with treasure and traps",
        cover_objects_chance=0.5,
        hazard_chance=0.5,
        has_treasure=True,
    ),
    RoomType.ENTRANCE: RoomTemplate(
        room_type=RoomType.ENTRANCE,
        name="Entrance",
        min_width=8, max_width=10,
        min_height=6, max_height=8,
        description="The entrance to a dungeon",
        pillar_chance=0.3,
        cover_objects_chance=0.2,
    ),
    RoomType.SHRINE: RoomTemplate(
        room_type=RoomType.SHRINE,
        name="Shrine",
        min_width=8, max_width=12,
        min_height=8, max_height=12,
        description="A sacred space with an altar",
        pillar_chance=0.5,
        has_altar=True,
        hazard_chance=0.2,
    ),
    RoomType.PRISON: RoomTemplate(
        room_type=RoomType.PRISON,
        name="Prison",
        min_width=10, max_width=14,
        min_height=8, max_height=12,
        description="A dungeon holding area",
        difficult_terrain_chance=0.2,
        cover_objects_chance=0.3,
    ),
}


def get_room_template(room_type: RoomType) -> RoomTemplate:
    """Get a room template by type."""
    return ROOM_TEMPLATES.get(room_type, ROOM_TEMPLATES[RoomType.CHAMBER])


def get_random_room_template(
    exclude: Optional[List[RoomType]] = None
) -> RoomTemplate:
    """Get a random room template, optionally excluding certain types."""
    available = list(ROOM_TEMPLATES.keys())
    if exclude:
        available = [rt for rt in available if rt not in exclude]

    if not available:
        return ROOM_TEMPLATES[RoomType.CHAMBER]

    return ROOM_TEMPLATES[random.choice(available)]
