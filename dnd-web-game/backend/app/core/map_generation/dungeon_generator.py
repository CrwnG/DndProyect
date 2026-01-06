"""
Procedural Dungeon Generator using Binary Space Partitioning (BSP).

Generates tactical battlemaps for D&D 5e encounters.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import random
import uuid

from .room_templates import (
    RoomTemplate,
    RoomType,
    TerrainPlacement,
    TerrainFeature,
    SpawnPoint,
    get_room_template,
    get_random_room_template,
)
from .difficulty_scaler import DifficultyScaler, DifficultyLevel, ScaledEncounterParams


@dataclass
class Room:
    """A generated room in the dungeon."""
    id: str
    x: int
    y: int
    width: int
    height: int
    room_type: RoomType
    terrain: List[TerrainPlacement] = field(default_factory=list)
    spawn_points: List[SpawnPoint] = field(default_factory=list)
    connected_to: List[str] = field(default_factory=list)

    def contains(self, px: int, py: int) -> bool:
        """Check if a point is inside this room."""
        return (self.x <= px < self.x + self.width and
                self.y <= py < self.y + self.height)

    def center(self) -> Tuple[int, int]:
        """Get the center point of the room."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "room_type": self.room_type.value,
            "terrain": [
                {
                    "x": t.x,
                    "y": t.y,
                    "feature": t.feature.value,
                    "elevation": t.elevation,
                    "cover_value": t.cover_value,
                    "is_hazard": t.is_hazard,
                    "hazard_damage": t.hazard_damage,
                    "hazard_type": t.hazard_type,
                }
                for t in self.terrain
            ],
            "spawn_points": [
                {
                    "x": s.x,
                    "y": s.y,
                    "spawn_type": s.spawn_type,
                    "priority": s.priority,
                }
                for s in self.spawn_points
            ],
            "connected_to": self.connected_to,
        }


@dataclass
class Corridor:
    """A corridor connecting two rooms."""
    id: str
    points: List[Tuple[int, int]]
    room_a_id: str
    room_b_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "points": self.points,
            "room_a_id": self.room_a_id,
            "room_b_id": self.room_b_id,
        }


@dataclass
class BSPNode:
    """A node in the BSP tree."""
    x: int
    y: int
    width: int
    height: int
    left: Optional["BSPNode"] = None
    right: Optional["BSPNode"] = None
    room: Optional[Room] = None

    def is_leaf(self) -> bool:
        """Check if this is a leaf node."""
        return self.left is None and self.right is None

    def split(self, min_size: int = 6) -> bool:
        """
        Split this node into two children.

        Args:
            min_size: Minimum size for child nodes

        Returns:
            True if split was successful
        """
        if not self.is_leaf():
            return False

        # Determine split direction
        # Split horizontally if wide, vertically if tall
        split_h = random.random() < 0.5

        if self.width > self.height and self.width / self.height >= 1.25:
            split_h = False
        elif self.height > self.width and self.height / self.width >= 1.25:
            split_h = True

        max_size = (self.height if split_h else self.width) - min_size
        if max_size <= min_size:
            return False

        # Random split position
        split_pos = random.randint(min_size, max_size)

        if split_h:
            self.left = BSPNode(self.x, self.y, self.width, split_pos)
            self.right = BSPNode(self.x, self.y + split_pos, self.width, self.height - split_pos)
        else:
            self.left = BSPNode(self.x, self.y, split_pos, self.height)
            self.right = BSPNode(self.x + split_pos, self.y, self.width - split_pos, self.height)

        return True

    def get_room(self) -> Optional[Room]:
        """Get the room in this node or its children."""
        if self.room:
            return self.room

        if self.left:
            left_room = self.left.get_room()
            if left_room:
                return left_room

        if self.right:
            right_room = self.right.get_room()
            if right_room:
                return right_room

        return None


@dataclass
class GeneratedMap:
    """A complete generated battlemap."""
    id: str
    width: int
    height: int
    rooms: List[Room]
    corridors: List[Corridor]
    grid: List[List[str]]  # 2D grid of cell types
    difficulty: DifficultyLevel
    party_level: int
    seed: Optional[int] = None

    def get_cell(self, x: int, y: int) -> str:
        """Get the cell type at a position."""
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[0]):
            return self.grid[y][x]
        return "wall"

    def get_spawn_points(self, spawn_type: str) -> List[SpawnPoint]:
        """Get all spawn points of a specific type."""
        points = []
        for room in self.rooms:
            points.extend([s for s in room.spawn_points if s.spawn_type == spawn_type])
        return sorted(points, key=lambda s: s.priority)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "width": self.width,
            "height": self.height,
            "rooms": [r.to_dict() for r in self.rooms],
            "corridors": [c.to_dict() for c in self.corridors],
            "grid": self.grid,
            "difficulty": self.difficulty.value,
            "party_level": self.party_level,
            "seed": self.seed,
            "player_spawns": [
                {"x": s.x, "y": s.y, "priority": s.priority}
                for s in self.get_spawn_points("player")
            ],
            "enemy_spawns": [
                {"x": s.x, "y": s.y, "priority": s.priority}
                for s in self.get_spawn_points("enemy")
            ],
            "boss_spawns": [
                {"x": s.x, "y": s.y, "priority": s.priority}
                for s in self.get_spawn_points("boss")
            ],
        }

    def to_combat_grid_format(self) -> Dict[str, Any]:
        """
        Convert to the format expected by CombatGrid.

        Returns:
            Dict compatible with CombatGrid.from_dict()
        """
        cells = {}

        for y, row in enumerate(self.grid):
            for x, cell_type in enumerate(row):
                terrain = "normal"
                elevation = 0
                cover_value = 0

                if cell_type == "wall":
                    terrain = "impassable"
                elif cell_type == "difficult":
                    terrain = "difficult"
                elif cell_type == "water":
                    terrain = "water"
                elif cell_type == "pit":
                    terrain = "pit"

                cells[f"{x},{y}"] = {
                    "terrain": terrain,
                    "occupied_by": None,
                    "elevation": elevation,
                    "cover_value": cover_value,
                }

        # Add terrain features from rooms
        for room in self.rooms:
            for t in room.terrain:
                key = f"{t.x},{t.y}"
                if key in cells:
                    if t.feature == TerrainFeature.PILLAR:
                        cells[key]["terrain"] = "impassable"
                        cells[key]["cover_value"] = t.cover_value
                    elif t.feature == TerrainFeature.RUBBLE:
                        cells[key]["terrain"] = "difficult"
                    elif t.feature == TerrainFeature.WATER:
                        cells[key]["terrain"] = "water"
                    elif t.feature == TerrainFeature.PIT:
                        cells[key]["terrain"] = "pit"
                    elif t.feature in [TerrainFeature.CRATE, TerrainFeature.TABLE]:
                        cells[key]["cover_value"] = t.cover_value
                    elif t.feature == TerrainFeature.STATUE:
                        cells[key]["cover_value"] = 5

                    cells[key]["elevation"] = t.elevation

        return {
            "width": self.width,
            "height": self.height,
            "cells": cells,
        }


class DungeonGenerator:
    """
    Generates procedural dungeons using BSP algorithm.

    The generator creates interconnected rooms with terrain features
    and spawn points for tactical D&D 5e encounters.
    """

    def __init__(
        self,
        party_level: int = 1,
        party_size: int = 4,
        difficulty: DifficultyLevel = DifficultyLevel.MEDIUM,
        seed: Optional[int] = None
    ):
        """
        Initialize the dungeon generator.

        Args:
            party_level: Average level of the party
            party_size: Number of party members
            difficulty: Desired difficulty level
            seed: Random seed for reproducibility
        """
        self.party_level = party_level
        self.party_size = party_size
        self.difficulty = difficulty
        self.seed = seed

        if seed is not None:
            random.seed(seed)

        self.scaler = DifficultyScaler(party_level, party_size, difficulty)

    def generate(
        self,
        room_type: Optional[RoomType] = None,
        num_rooms: int = 1
    ) -> GeneratedMap:
        """
        Generate a battlemap.

        Args:
            room_type: Specific room type to generate (None for random)
            num_rooms: Number of rooms to generate (1 for single room)

        Returns:
            GeneratedMap with the generated dungeon
        """
        if num_rooms == 1:
            return self._generate_single_room(room_type)
        else:
            return self._generate_dungeon(num_rooms)

    def _generate_single_room(self, room_type: Optional[RoomType] = None) -> GeneratedMap:
        """Generate a single-room battlemap."""
        # Get encounter parameters
        params = self.scaler.calculate_encounter()

        # Get room template
        if room_type:
            template = get_room_template(room_type)
        else:
            template = get_random_room_template()

        # Calculate room size
        width = max(template.min_width, min(template.max_width, params.map_width))
        height = max(template.min_height, min(template.max_height, params.map_height))

        # Generate terrain
        terrain = template.generate_terrain(width, height, self.seed)

        # Generate spawn points
        spawn_points = template.generate_spawn_points(
            width, height,
            num_players=self.party_size,
            num_enemies=params.num_enemies,
            has_boss=params.has_boss
        )

        # Create room
        room = Room(
            id=str(uuid.uuid4())[:8],
            x=0,
            y=0,
            width=width,
            height=height,
            room_type=template.room_type,
            terrain=terrain,
            spawn_points=spawn_points,
        )

        # Create grid
        grid = self._create_grid(width, height, [room], [])

        return GeneratedMap(
            id=str(uuid.uuid4())[:8],
            width=width,
            height=height,
            rooms=[room],
            corridors=[],
            grid=grid,
            difficulty=self.difficulty,
            party_level=self.party_level,
            seed=self.seed,
        )

    def _generate_dungeon(self, num_rooms: int) -> GeneratedMap:
        """Generate a multi-room dungeon using BSP."""
        # Get encounter parameters
        params = self.scaler.calculate_encounter()

        # Calculate total dungeon size
        base_size = max(params.map_width, params.map_height)
        dungeon_width = base_size * 2 + 4
        dungeon_height = base_size * 2 + 4

        # Create BSP tree
        root = BSPNode(0, 0, dungeon_width, dungeon_height)

        # Split the tree
        nodes = [root]
        for _ in range(min(num_rooms - 1, 4)):  # Max 5 splits
            new_nodes = []
            for node in nodes:
                if node.is_leaf() and node.split():
                    new_nodes.extend([node.left, node.right])
                else:
                    new_nodes.append(node)
            nodes = new_nodes

        # Get leaf nodes
        leaf_nodes = [n for n in self._get_leaves(root)]

        # Create rooms in leaves
        rooms = []
        for i, leaf in enumerate(leaf_nodes[:num_rooms]):
            # Determine room type
            if i == 0:
                room_type = RoomType.ENTRANCE
            elif i == len(leaf_nodes) - 1:
                room_type = RoomType.LAIR if params.has_boss else RoomType.TREASURY
            else:
                room_type = random.choice([RoomType.CHAMBER, RoomType.SHRINE, RoomType.PRISON])

            room = self._create_room_in_node(leaf, room_type, i == len(leaf_nodes) - 1)
            rooms.append(room)
            leaf.room = room

        # Connect rooms with corridors
        corridors = self._connect_rooms(root, rooms)

        # Create grid
        grid = self._create_grid(dungeon_width, dungeon_height, rooms, corridors)

        return GeneratedMap(
            id=str(uuid.uuid4())[:8],
            width=dungeon_width,
            height=dungeon_height,
            rooms=rooms,
            corridors=corridors,
            grid=grid,
            difficulty=self.difficulty,
            party_level=self.party_level,
            seed=self.seed,
        )

    def _get_leaves(self, node: BSPNode) -> List[BSPNode]:
        """Get all leaf nodes in the BSP tree."""
        if node.is_leaf():
            return [node]

        leaves = []
        if node.left:
            leaves.extend(self._get_leaves(node.left))
        if node.right:
            leaves.extend(self._get_leaves(node.right))
        return leaves

    def _create_room_in_node(
        self,
        node: BSPNode,
        room_type: RoomType,
        is_boss_room: bool
    ) -> Room:
        """Create a room within a BSP node."""
        template = get_room_template(room_type)

        # Room size with margin
        margin = 2
        max_width = min(template.max_width, node.width - margin * 2)
        max_height = min(template.max_height, node.height - margin * 2)

        width = max(template.min_width, random.randint(template.min_width, max(template.min_width, max_width)))
        height = max(template.min_height, random.randint(template.min_height, max(template.min_height, max_height)))

        # Position with margin
        x = node.x + margin + random.randint(0, max(0, node.width - width - margin * 2))
        y = node.y + margin + random.randint(0, max(0, node.height - height - margin * 2))

        # Generate terrain
        terrain = template.generate_terrain(width, height, self.seed)

        # Generate spawn points (only for entrance and boss rooms)
        spawn_points = []
        if room_type == RoomType.ENTRANCE:
            spawn_points = template.generate_spawn_points(
                width, height,
                num_players=self.party_size,
                num_enemies=0,
                has_boss=False
            )
        elif is_boss_room:
            params = self.scaler.calculate_encounter()
            spawn_points = template.generate_spawn_points(
                width, height,
                num_players=0,
                num_enemies=params.num_enemies,
                has_boss=True
            )

        # Offset spawn points to room position
        for sp in spawn_points:
            sp.x += x
            sp.y += y

        # Offset terrain to room position
        for t in terrain:
            t.x += x
            t.y += y

        return Room(
            id=str(uuid.uuid4())[:8],
            x=x,
            y=y,
            width=width,
            height=height,
            room_type=room_type,
            terrain=terrain,
            spawn_points=spawn_points,
        )

    def _connect_rooms(self, root: BSPNode, rooms: List[Room]) -> List[Corridor]:
        """Connect rooms with corridors using the BSP tree structure."""
        corridors = []
        self._connect_node(root, corridors)
        return corridors

    def _connect_node(self, node: BSPNode, corridors: List[Corridor]) -> None:
        """Recursively connect rooms in the BSP tree."""
        if node.is_leaf():
            return

        if node.left and node.right:
            left_room = node.left.get_room()
            right_room = node.right.get_room()

            if left_room and right_room:
                corridor = self._create_corridor(left_room, right_room)
                corridors.append(corridor)

                left_room.connected_to.append(right_room.id)
                right_room.connected_to.append(left_room.id)

            self._connect_node(node.left, corridors)
            self._connect_node(node.right, corridors)

    def _create_corridor(self, room_a: Room, room_b: Room) -> Corridor:
        """Create a corridor between two rooms."""
        ax, ay = room_a.center()
        bx, by = room_b.center()

        points = []

        # L-shaped corridor
        if random.random() < 0.5:
            # Horizontal then vertical
            for x in range(min(ax, bx), max(ax, bx) + 1):
                points.append((x, ay))
            for y in range(min(ay, by), max(ay, by) + 1):
                points.append((bx, y))
        else:
            # Vertical then horizontal
            for y in range(min(ay, by), max(ay, by) + 1):
                points.append((ax, y))
            for x in range(min(ax, bx), max(ax, bx) + 1):
                points.append((x, by))

        return Corridor(
            id=str(uuid.uuid4())[:8],
            points=list(set(points)),  # Remove duplicates
            room_a_id=room_a.id,
            room_b_id=room_b.id,
        )

    def _create_grid(
        self,
        width: int,
        height: int,
        rooms: List[Room],
        corridors: List[Corridor]
    ) -> List[List[str]]:
        """Create the 2D grid representation."""
        # Initialize with walls
        grid = [["wall" for _ in range(width)] for _ in range(height)]

        # Carve out rooms
        for room in rooms:
            for y in range(room.y, room.y + room.height):
                for x in range(room.x, room.x + room.width):
                    if 0 <= y < height and 0 <= x < width:
                        grid[y][x] = "floor"

            # Apply terrain features
            for t in room.terrain:
                if 0 <= t.y < height and 0 <= t.x < width:
                    if t.feature == TerrainFeature.PILLAR:
                        grid[t.y][t.x] = "pillar"
                    elif t.feature == TerrainFeature.RUBBLE:
                        grid[t.y][t.x] = "difficult"
                    elif t.feature == TerrainFeature.WATER:
                        grid[t.y][t.x] = "water"
                    elif t.feature == TerrainFeature.PIT:
                        grid[t.y][t.x] = "pit"
                    elif t.feature == TerrainFeature.LAVA:
                        grid[t.y][t.x] = "lava"
                    elif t.feature in [TerrainFeature.CRATE, TerrainFeature.TABLE]:
                        grid[t.y][t.x] = "cover"
                    elif t.feature == TerrainFeature.ALTAR:
                        grid[t.y][t.x] = "altar"
                    elif t.feature == TerrainFeature.TRAP:
                        grid[t.y][t.x] = "trap"

        # Carve out corridors
        for corridor in corridors:
            for x, y in corridor.points:
                if 0 <= y < height and 0 <= x < width:
                    if grid[y][x] == "wall":
                        grid[y][x] = "floor"

        return grid


def generate_battlemap(
    party_level: int = 1,
    party_size: int = 4,
    difficulty: str = "medium",
    room_type: Optional[str] = None,
    num_rooms: int = 1,
    seed: Optional[int] = None
) -> GeneratedMap:
    """
    Convenience function to generate a battlemap.

    Args:
        party_level: Average level of the party (1-20)
        party_size: Number of party members (1-8)
        difficulty: "easy", "medium", "hard", or "deadly"
        room_type: Specific room type or None for random
        num_rooms: Number of rooms (1 for single room)
        seed: Random seed for reproducibility

    Returns:
        GeneratedMap with the complete battlemap
    """
    diff_level = DifficultyLevel(difficulty.lower())

    rt = None
    if room_type:
        rt = RoomType(room_type.lower())

    generator = DungeonGenerator(
        party_level=party_level,
        party_size=party_size,
        difficulty=diff_level,
        seed=seed
    )

    return generator.generate(room_type=rt, num_rooms=num_rooms)
