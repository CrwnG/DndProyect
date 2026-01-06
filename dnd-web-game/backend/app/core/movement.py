"""
Movement System.

Handles grid-based movement, pathfinding, and terrain for tactical combat.
Uses A* pathfinding for movement validation and path calculation.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Set, Tuple, Any
import heapq


class TerrainType(Enum):
    """Types of terrain that affect movement."""
    NORMAL = "normal"
    DIFFICULT = "difficult"
    IMPASSABLE = "impassable"
    WATER = "water"  # Difficult terrain, may have other effects
    WATER_DEEP = "water_deep"  # Requires swimming
    PIT = "pit"  # May cause damage if entered
    CLIMBING = "climbing"  # Vertical surface, requires climbing


class MovementMode(Enum):
    """Types of movement modes."""
    WALK = "walk"
    CLIMB = "climb"
    SWIM = "swim"
    FLY = "fly"
    JUMP = "jump"


@dataclass
class GridCell:
    """A single cell in the combat grid."""
    x: int
    y: int
    terrain: TerrainType = TerrainType.NORMAL
    occupied_by: Optional[str] = None  # Combatant ID
    elevation: int = 0  # Height in 5ft increments (0 = ground level)
    cover_value: int = 0  # 0=none, 2=half, 5=three-quarters
    is_hazard: bool = False  # Environmental hazard (fire, acid, etc.)
    hazard_damage: str = ""  # Damage dice if hazard (e.g., "1d6")
    hazard_type: str = ""  # Damage type (e.g., "fire", "acid")

    @property
    def is_passable(self) -> bool:
        """Check if this cell can be entered."""
        return self.terrain != TerrainType.IMPASSABLE and self.occupied_by is None

    @property
    def movement_cost(self) -> int:
        """Get the base movement cost to enter this cell (in feet)."""
        if self.terrain == TerrainType.IMPASSABLE:
            return float('inf')
        elif self.terrain in [TerrainType.DIFFICULT, TerrainType.WATER]:
            return 10  # Difficult terrain costs double
        elif self.terrain == TerrainType.CLIMBING:
            return 10  # Climbing costs double (without climb speed)
        elif self.terrain == TerrainType.WATER_DEEP:
            return 10  # Swimming costs double (without swim speed)
        return 5  # Normal 5ft per square

    def get_movement_cost(
        self,
        climb_speed: int = 0,
        swim_speed: int = 0,
        fly_speed: int = 0,
        from_elevation: int = 0
    ) -> int:
        """
        Get movement cost considering special movement speeds.

        Args:
            climb_speed: Creature's climbing speed (0 = no climb speed)
            swim_speed: Creature's swimming speed (0 = no swim speed)
            fly_speed: Creature's flying speed (0 = no fly speed)
            from_elevation: Elevation of the cell moving from

        Returns:
            Movement cost in feet
        """
        if self.terrain == TerrainType.IMPASSABLE:
            return float('inf')

        base_cost = 5

        # Climbing terrain - reduced cost if has climb speed
        if self.terrain == TerrainType.CLIMBING:
            if climb_speed > 0 or fly_speed > 0:
                base_cost = 5  # Normal cost with climb/fly speed
            else:
                base_cost = 10  # Double cost without

        # Deep water - reduced cost if has swim speed
        elif self.terrain == TerrainType.WATER_DEEP:
            if swim_speed > 0 or fly_speed > 0:
                base_cost = 5  # Normal cost with swim/fly speed
            else:
                base_cost = 10  # Double cost without

        # Shallow water or difficult terrain
        elif self.terrain in [TerrainType.DIFFICULT, TerrainType.WATER]:
            if fly_speed > 0:
                base_cost = 5  # Flying ignores difficult terrain
            else:
                base_cost = 10  # Double cost

        # Elevation change cost (climbing up costs extra unless flying)
        elevation_diff = self.elevation - from_elevation
        if elevation_diff > 0 and fly_speed == 0:
            # Climbing up - costs extra per 5ft of elevation
            # Each 5ft up costs an additional 5ft (total 10ft per square when climbing)
            if climb_speed > 0:
                base_cost += elevation_diff * 5  # Normal climb speed
            else:
                base_cost += elevation_diff * 10  # Double without climb speed

        return base_cost


@dataclass
class CombatGrid:
    """
    The tactical combat grid.

    Standard D&D uses 5-foot squares on an 8x8 or larger grid.
    """
    width: int = 8
    height: int = 8
    cells: Dict[Tuple[int, int], GridCell] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize all cells if not already done."""
        if not self.cells:
            for x in range(self.width):
                for y in range(self.height):
                    self.cells[(x, y)] = GridCell(x=x, y=y)

    def get_cell(self, x: int, y: int) -> Optional[GridCell]:
        """Get a cell by coordinates."""
        return self.cells.get((x, y))

    def is_valid_position(self, x: int, y: int) -> bool:
        """Check if coordinates are within the grid."""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_passable(self, x: int, y: int) -> bool:
        """Check if a position can be moved into."""
        if not self.is_valid_position(x, y):
            return False
        cell = self.get_cell(x, y)
        return cell is not None and cell.is_passable

    def set_terrain(self, x: int, y: int, terrain: TerrainType) -> bool:
        """Set the terrain type for a cell."""
        cell = self.get_cell(x, y)
        if cell:
            cell.terrain = terrain
            return True
        return False

    def set_occupant(self, x: int, y: int, combatant_id: Optional[str]) -> bool:
        """Set or clear the occupant of a cell."""
        cell = self.get_cell(x, y)
        if cell:
            cell.occupied_by = combatant_id
            return True
        return False

    def get_occupant(self, x: int, y: int) -> Optional[str]:
        """Get the ID of the combatant occupying a cell."""
        cell = self.get_cell(x, y)
        return cell.occupied_by if cell else None

    def find_combatant(self, combatant_id: str) -> Optional[Tuple[int, int]]:
        """Find the position of a combatant on the grid."""
        for pos, cell in self.cells.items():
            if cell.occupied_by == combatant_id:
                return pos
        return None

    def get_adjacent_cells(
        self,
        x: int,
        y: int,
        include_diagonals: bool = True
    ) -> List[Tuple[int, int]]:
        """Get all adjacent cell positions."""
        adjacent = []

        # Cardinal directions
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if self.is_valid_position(nx, ny):
                adjacent.append((nx, ny))

        # Diagonal directions
        if include_diagonals:
            for dx, dy in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                nx, ny = x + dx, y + dy
                if self.is_valid_position(nx, ny):
                    adjacent.append((nx, ny))

        return adjacent

    def get_cells_in_radius(
        self,
        x: int,
        y: int,
        radius_ft: int
    ) -> List[Tuple[int, int]]:
        """Get all cells within a radius (in feet)."""
        radius_squares = radius_ft // 5
        cells = []

        for dx in range(-radius_squares, radius_squares + 1):
            for dy in range(-radius_squares, radius_squares + 1):
                nx, ny = x + dx, y + dy
                if self.is_valid_position(nx, ny):
                    # Use Chebyshev distance (max of |dx| or |dy|)
                    distance = max(abs(dx), abs(dy))
                    if distance <= radius_squares:
                        cells.append((nx, ny))

        return cells

    def to_dict(self) -> Dict:
        """Serialize the grid for transmission."""
        return {
            "width": self.width,
            "height": self.height,
            "cells": {
                f"{x},{y}": {
                    "terrain": cell.terrain.value,
                    "occupied_by": cell.occupied_by,
                    "elevation": cell.elevation,
                    "cover_value": cell.cover_value
                }
                for (x, y), cell in self.cells.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CombatGrid":
        """Deserialize a grid from dictionary."""
        grid = cls(width=data["width"], height=data["height"])

        for key, cell_data in data.get("cells", {}).items():
            x, y = map(int, key.split(","))
            cell = grid.get_cell(x, y)
            if cell:
                cell.terrain = TerrainType(cell_data["terrain"])
                cell.occupied_by = cell_data.get("occupied_by")
                cell.elevation = cell_data.get("elevation", 0)
                cell.cover_value = cell_data.get("cover_value", 0)

        return grid


@dataclass
class PathNode:
    """A node in the pathfinding graph."""
    x: int
    y: int
    g_cost: int = 0  # Cost from start
    h_cost: int = 0  # Heuristic (estimated cost to goal)
    parent: Optional["PathNode"] = None

    @property
    def f_cost(self) -> int:
        """Total estimated cost."""
        return self.g_cost + self.h_cost

    def __lt__(self, other: "PathNode") -> bool:
        """For heap comparison."""
        return self.f_cost < other.f_cost

    def __eq__(self, other: object) -> bool:
        """Position equality."""
        if not isinstance(other, PathNode):
            return False
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        """Hash by position."""
        return hash((self.x, self.y))


@dataclass
class MovementResult:
    """Result of a movement attempt."""
    success: bool
    path: List[Tuple[int, int]]
    total_cost: int
    description: str
    blocked_by: Optional[str] = None  # Combatant ID if blocked
    opportunity_attacks_from: List[str] = field(default_factory=list)


def calculate_distance(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    diagonal_rule: str = "chebyshev"
) -> int:
    """
    Calculate distance between two points in feet.

    Args:
        x1, y1: Start position
        x2, y2: End position
        diagonal_rule: "chebyshev" (5ft diagonals) or "alternating" (5-10-5-10)

    Returns:
        Distance in feet
    """
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)

    if diagonal_rule == "chebyshev":
        # Simplified: all squares cost 5ft
        return max(dx, dy) * 5
    else:
        # Alternating: first diagonal 5ft, second 10ft, etc.
        straight = abs(dx - dy)
        diagonals = min(dx, dy)
        # Diagonals cost 5ft on odd moves, 10ft on even
        diagonal_cost = (diagonals // 2) * 15 + (diagonals % 2) * 5
        return straight * 5 + diagonal_cost


def heuristic(x1: int, y1: int, x2: int, y2: int) -> int:
    """Heuristic for A* (Chebyshev distance in feet)."""
    return max(abs(x2 - x1), abs(y2 - y1)) * 5


def find_path(
    grid: CombatGrid,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    max_movement: int = 30,
    ignore_occupants: bool = False,
    mover_id: Optional[str] = None,
    ally_ids: Optional[Set[str]] = None
) -> MovementResult:
    """
    Find a path between two points using A*.

    Args:
        grid: The combat grid
        start_x, start_y: Starting position
        end_x, end_y: Target position
        max_movement: Maximum movement in feet
        ignore_occupants: If True, path through occupied squares
        mover_id: ID of the moving combatant (for ally detection)
        ally_ids: Set of ally combatant IDs (can pass through but not end on)

    Returns:
        MovementResult with the path if successful
    """
    # Default to empty set if not provided
    if ally_ids is None:
        ally_ids = set()
    # Validate positions
    if not grid.is_valid_position(start_x, start_y):
        return MovementResult(
            success=False,
            path=[],
            total_cost=0,
            description="Invalid start position"
        )

    if not grid.is_valid_position(end_x, end_y):
        return MovementResult(
            success=False,
            path=[],
            total_cost=0,
            description="Invalid end position"
        )

    # Check if end is passable
    end_cell = grid.get_cell(end_x, end_y)
    if end_cell and end_cell.terrain == TerrainType.IMPASSABLE:
        return MovementResult(
            success=False,
            path=[],
            total_cost=0,
            description="Destination is impassable"
        )

    # D&D rules: Can't end turn on any occupied cell (ally or enemy)
    if end_cell and end_cell.occupied_by and not ignore_occupants:
        occupant_id = end_cell.occupied_by
        # Even allies block the destination (can pass through, not end on)
        return MovementResult(
            success=False,
            path=[],
            total_cost=0,
            description="Destination is occupied" + (" by an ally" if occupant_id in ally_ids else ""),
            blocked_by=occupant_id
        )

    # Already there
    if start_x == end_x and start_y == end_y:
        return MovementResult(
            success=True,
            path=[(start_x, start_y)],
            total_cost=0,
            description="Already at destination"
        )

    # A* pathfinding
    start_node = PathNode(x=start_x, y=start_y)
    start_node.h_cost = heuristic(start_x, start_y, end_x, end_y)

    open_set: List[PathNode] = [start_node]
    closed_set: Set[Tuple[int, int]] = set()
    node_map: Dict[Tuple[int, int], PathNode] = {(start_x, start_y): start_node}

    while open_set:
        # Get node with lowest f_cost
        current = heapq.heappop(open_set)
        current_pos = (current.x, current.y)

        if current_pos in closed_set:
            continue

        closed_set.add(current_pos)

        # Found the goal
        if current.x == end_x and current.y == end_y:
            # Reconstruct path
            path = []
            node = current
            while node:
                path.append((node.x, node.y))
                node = node.parent
            path.reverse()

            # Check if path is within movement range
            if current.g_cost > max_movement:
                # Find the furthest point we can reach
                trimmed_path = []
                cost = 0
                for i, (px, py) in enumerate(path):
                    if i == 0:
                        trimmed_path.append((px, py))
                        continue
                    cell = grid.get_cell(px, py)
                    move_cost = cell.movement_cost if cell else 5
                    if cost + move_cost <= max_movement:
                        cost += move_cost
                        trimmed_path.append((px, py))
                    else:
                        break

                return MovementResult(
                    success=True,
                    path=trimmed_path,
                    total_cost=cost,
                    description=f"Path found but limited to {cost}ft of movement"
                )

            return MovementResult(
                success=True,
                path=path,
                total_cost=current.g_cost,
                description=f"Path found: {current.g_cost}ft"
            )

        # Explore neighbors
        for nx, ny in grid.get_adjacent_cells(current.x, current.y):
            if (nx, ny) in closed_set:
                continue

            cell = grid.get_cell(nx, ny)
            if not cell:
                continue

            # Check passability
            if cell.terrain == TerrainType.IMPASSABLE:
                continue

            if cell.occupied_by and not ignore_occupants:
                occupant_id = cell.occupied_by
                # D&D rules: Can pass through allies, but not enemies
                if occupant_id not in ally_ids:
                    # It's an enemy - can't pass through
                    continue
                # It's an ally - can pass through but can't end here
                # (the destination check above handles the "can't end" part)

            # Calculate movement cost
            move_cost = cell.movement_cost
            # Add extra cost for diagonal movement if using alternating rule
            new_g_cost = current.g_cost + move_cost

            neighbor_pos = (nx, ny)
            existing = node_map.get(neighbor_pos)

            if existing and new_g_cost >= existing.g_cost:
                continue

            neighbor = PathNode(
                x=nx,
                y=ny,
                g_cost=new_g_cost,
                h_cost=heuristic(nx, ny, end_x, end_y),
                parent=current
            )

            node_map[neighbor_pos] = neighbor
            heapq.heappush(open_set, neighbor)

    return MovementResult(
        success=False,
        path=[],
        total_cost=0,
        description="No path found"
    )


def get_reachable_cells(
    grid: CombatGrid,
    start_x: int,
    start_y: int,
    movement: int,
    include_occupied: bool = False,
    mover_id: Optional[str] = None,
    ally_ids: Optional[Set[str]] = None
) -> List[Tuple[int, int, int]]:
    """
    Get all cells reachable with the given movement.

    Args:
        grid: The combat grid
        start_x, start_y: Starting position
        movement: Available movement in feet
        include_occupied: Include cells that are occupied
        mover_id: ID of the moving combatant
        ally_ids: Set of ally IDs (can pass through but not end on)

    Returns:
        List of (x, y, cost) tuples for reachable cells (valid destinations only)
    """
    if ally_ids is None:
        ally_ids = set()

    reachable = []
    visited: Dict[Tuple[int, int], int] = {(start_x, start_y): 0}
    queue = [(0, start_x, start_y)]
    # Track cells we can pass through but not end on
    passable_but_blocked: Set[Tuple[int, int]] = set()

    while queue:
        cost, x, y = heapq.heappop(queue)

        if cost > movement:
            continue

        for nx, ny in grid.get_adjacent_cells(x, y):
            cell = grid.get_cell(nx, ny)
            if not cell:
                continue

            if cell.terrain == TerrainType.IMPASSABLE:
                continue

            # Handle occupied cells
            if cell.occupied_by and not include_occupied:
                occupant_id = cell.occupied_by
                # D&D rules: Can pass through allies, block on enemies
                if occupant_id in ally_ids:
                    # Ally: can pass through but not end here
                    passable_but_blocked.add((nx, ny))
                else:
                    # Enemy: can't pass through at all
                    continue

            move_cost = cell.movement_cost
            new_cost = cost + move_cost

            if new_cost > movement:
                continue

            if (nx, ny) in visited and visited[(nx, ny)] <= new_cost:
                continue

            visited[(nx, ny)] = new_cost
            heapq.heappush(queue, (new_cost, nx, ny))

            # Only add to reachable if it's a valid destination (not occupied)
            if (nx, ny) not in passable_but_blocked and not cell.occupied_by:
                reachable.append((nx, ny, new_cost))

    return reachable


def get_threatened_squares(
    grid: CombatGrid,
    combatant_id: str,
    reach: int = 5
) -> List[Tuple[int, int]]:
    """
    Get squares threatened by a combatant (for opportunity attacks).

    Args:
        grid: The combat grid
        combatant_id: ID of the threatening combatant
        reach: Weapon reach in feet

    Returns:
        List of (x, y) positions within reach
    """
    pos = grid.find_combatant(combatant_id)
    if not pos:
        return []

    return grid.get_cells_in_radius(pos[0], pos[1], reach)


def check_opportunity_attack_triggers(
    grid: CombatGrid,
    mover_id: str,
    from_pos: Tuple[int, int],
    to_pos: Tuple[int, int],
    enemy_ids: List[str],
    mover_conditions: Optional[List[str]] = None,
    enemy_data: Optional[Dict[str, Dict[str, Any]]] = None,
    mover_attacked_this_turn: Optional[List[str]] = None
) -> List[str]:
    """
    Check if movement triggers opportunity attacks.

    An opportunity attack is triggered when leaving a threatened square.
    D&D Rules:
    - Disengage action prevents opportunity attacks (unless Sentinel)
    - Mobile feat: after attacking a creature, no OA from that creature
    - Extended reach weapons (10ft) can trigger OA from further away

    Args:
        grid: The combat grid
        mover_id: ID of the moving combatant
        from_pos: Starting position
        to_pos: Ending position
        enemy_ids: List of enemy combatant IDs
        mover_conditions: List of conditions on the mover (check for "disengaged")
        enemy_data: Dict mapping enemy_id to their stats (for reach, sentinel, etc.)
        mover_attacked_this_turn: List of enemy IDs the mover attacked this turn (for Mobile)

    Returns:
        List of enemy IDs that can make opportunity attacks
    """
    enemy_data = enemy_data or {}
    mover_attacked_this_turn = mover_attacked_this_turn or []

    # Check if mover has disengaged
    has_disengaged = mover_conditions and "disengaged" in mover_conditions

    # Check if mover has Mobile feat
    mover_has_mobile = mover_conditions and "mobile" in mover_conditions

    opportunity_attackers = []

    for enemy_id in enemy_ids:
        enemy_pos = grid.find_combatant(enemy_id)
        if not enemy_pos:
            continue

        # Get enemy's stats
        enemy_stats = enemy_data.get(enemy_id, {})

        # Get enemy's reach (default 5ft = 1 square, some have 10ft = 2 squares)
        reach_ft = enemy_stats.get("reach", 5)
        reach_squares = max(1, reach_ft // 5)

        # Check if enemy has Sentinel (ignores Disengage)
        has_sentinel = enemy_stats.get("sentinel", False)

        # If mover disengaged and enemy doesn't have Sentinel, skip
        if has_disengaged and not has_sentinel:
            continue

        # If mover has Mobile feat and attacked this enemy, skip
        if mover_has_mobile and enemy_id in mover_attacked_this_turn:
            continue

        # Check if mover was in reach and is leaving reach
        from_distance = max(abs(from_pos[0] - enemy_pos[0]),
                           abs(from_pos[1] - enemy_pos[1]))
        to_distance = max(abs(to_pos[0] - enemy_pos[0]),
                         abs(to_pos[1] - enemy_pos[1]))

        # Was in reach and is leaving
        if from_distance <= reach_squares and to_distance > reach_squares:
            opportunity_attackers.append(enemy_id)

    return opportunity_attackers


def check_polearm_master_triggers(
    grid: CombatGrid,
    mover_id: str,
    from_pos: Tuple[int, int],
    to_pos: Tuple[int, int],
    enemy_ids: List[str],
    enemy_data: Optional[Dict[str, Dict[str, Any]]] = None
) -> List[str]:
    """
    Check if movement triggers Polearm Master opportunity attacks.

    Polearm Master feat allows OA when a creature ENTERS your reach.

    Args:
        grid: The combat grid
        mover_id: ID of the moving combatant
        from_pos: Starting position
        to_pos: Ending position
        enemy_ids: List of enemy combatant IDs with Polearm Master
        enemy_data: Dict mapping enemy_id to their stats

    Returns:
        List of enemy IDs with Polearm Master that can make OA
    """
    enemy_data = enemy_data or {}
    polearm_attackers = []

    for enemy_id in enemy_ids:
        enemy_stats = enemy_data.get(enemy_id, {})

        # Only check if enemy has Polearm Master feat
        if not enemy_stats.get("polearm_master", False):
            continue

        enemy_pos = grid.find_combatant(enemy_id)
        if not enemy_pos:
            continue

        # Polearm Master works with reach weapons (10ft = 2 squares)
        reach_squares = 2

        # Check if mover was outside reach and is entering reach
        from_distance = max(abs(from_pos[0] - enemy_pos[0]),
                           abs(from_pos[1] - enemy_pos[1]))
        to_distance = max(abs(to_pos[0] - enemy_pos[0]),
                         abs(to_pos[1] - enemy_pos[1]))

        # Was outside reach and is entering
        if from_distance > reach_squares and to_distance <= reach_squares:
            polearm_attackers.append(enemy_id)

    return polearm_attackers


def get_line_of_sight(
    grid: CombatGrid,
    x1: int,
    y1: int,
    x2: int,
    y2: int
) -> Tuple[bool, List[Tuple[int, int]]]:
    """
    Check line of sight between two points.

    Uses Bresenham's line algorithm to trace the line.

    Args:
        grid: The combat grid
        x1, y1: Start position
        x2, y2: End position

    Returns:
        Tuple of (has_line_of_sight, cells_in_path)
    """
    cells = []
    has_los = True

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy

    x, y = x1, y1

    while True:
        cells.append((x, y))

        cell = grid.get_cell(x, y)
        if cell and cell.terrain == TerrainType.IMPASSABLE:
            # Skip the starting cell
            if (x, y) != (x1, y1):
                has_los = False

        if x == x2 and y == y2:
            break

        e2 = 2 * err

        if e2 > -dy:
            err -= dy
            x += sx

        if e2 < dx:
            err += dx
            y += sy

    return has_los, cells


def get_cover_between(
    grid: CombatGrid,
    attacker_x: int,
    attacker_y: int,
    target_x: int,
    target_y: int
) -> int:
    """
    Calculate cover bonus between attacker and target.

    Args:
        grid: The combat grid
        attacker_x, attacker_y: Attacker position
        target_x, target_y: Target position

    Returns:
        Cover bonus to AC (0, 2, or 5)
    """
    has_los, cells = get_line_of_sight(
        grid, attacker_x, attacker_y, target_x, target_y
    )

    if not has_los:
        return 5  # Full cover

    max_cover = 0
    for x, y in cells:
        if (x, y) == (attacker_x, attacker_y):
            continue
        if (x, y) == (target_x, target_y):
            continue

        cell = grid.get_cell(x, y)
        if cell and cell.cover_value > max_cover:
            max_cover = cell.cover_value

    return max_cover


def create_grid_with_obstacles(
    width: int = 8,
    height: int = 8,
    obstacles: Optional[List[Tuple[int, int]]] = None,
    difficult_terrain: Optional[List[Tuple[int, int]]] = None
) -> CombatGrid:
    """
    Create a combat grid with predefined obstacles.

    Args:
        width: Grid width
        height: Grid height
        obstacles: List of (x, y) positions for impassable terrain
        difficult_terrain: List of (x, y) positions for difficult terrain

    Returns:
        Configured CombatGrid
    """
    grid = CombatGrid(width=width, height=height)

    if obstacles:
        for x, y in obstacles:
            grid.set_terrain(x, y, TerrainType.IMPASSABLE)

    if difficult_terrain:
        for x, y in difficult_terrain:
            grid.set_terrain(x, y, TerrainType.DIFFICULT)

    return grid


# ============================================================================
# ELEVATION SYSTEM
# ============================================================================

def get_elevation_attack_modifier(
    grid: CombatGrid,
    attacker_x: int,
    attacker_y: int,
    target_x: int,
    target_y: int
) -> Tuple[int, str]:
    """
    Calculate attack modifier based on elevation difference.

    D&D 5e / BG3 Rule: High ground provides +2 to attack rolls.
    Low ground provides -2 (optional, used in BG3).

    Args:
        grid: The combat grid
        attacker_x, attacker_y: Attacker position
        target_x, target_y: Target position

    Returns:
        Tuple of (attack_modifier, reason_description)
    """
    attacker_cell = grid.get_cell(attacker_x, attacker_y)
    target_cell = grid.get_cell(target_x, target_y)

    if not attacker_cell or not target_cell:
        return (0, "")

    elevation_diff = attacker_cell.elevation - target_cell.elevation

    # High ground advantage (+2 attack)
    if elevation_diff >= 1:
        return (2, f"High ground (+2 attack, {elevation_diff * 5}ft above)")

    # Low ground penalty (-2 attack) - Optional BG3 rule
    # Uncomment to enable: if elevation_diff <= -1:
    #     return (-2, f"Low ground (-2 attack, {abs(elevation_diff) * 5}ft below)")

    return (0, "")


def get_elevation_ranged_bonus(
    grid: CombatGrid,
    attacker_x: int,
    attacker_y: int,
    target_x: int,
    target_y: int
) -> int:
    """
    Calculate bonus range for ranged attacks from elevation.

    Firing from high ground can extend effective range.
    Each 10ft of elevation adds 5ft of effective range.

    Args:
        grid: The combat grid
        attacker_x, attacker_y: Attacker position
        target_x, target_y: Target position

    Returns:
        Bonus range in feet (0 or positive)
    """
    attacker_cell = grid.get_cell(attacker_x, attacker_y)
    target_cell = grid.get_cell(target_x, target_y)

    if not attacker_cell or not target_cell:
        return 0

    elevation_diff = attacker_cell.elevation - target_cell.elevation

    if elevation_diff > 0:
        # Each 2 elevation units (10ft) grants 5ft bonus range
        return (elevation_diff // 2) * 5

    return 0


# ============================================================================
# JUMPING SYSTEM
# ============================================================================

@dataclass
class JumpResult:
    """Result of a jump attempt."""
    success: bool
    distance_ft: int
    movement_cost: int
    description: str
    cleared_hazards: List[Tuple[int, int]] = field(default_factory=list)


def calculate_long_jump_distance(
    strength_score: int,
    running_start: bool = True
) -> int:
    """
    Calculate long jump distance.

    D&D 5e Rule:
    - With running start (10ft): Jump distance = Strength score (in feet)
    - Standing jump: Half that distance

    Args:
        strength_score: Character's Strength score (not modifier)
        running_start: Whether the character has a 10ft running start

    Returns:
        Jump distance in feet
    """
    if running_start:
        return strength_score  # Full STR score in feet
    else:
        return strength_score // 2  # Half for standing jump


def calculate_high_jump_distance(
    strength_modifier: int,
    running_start: bool = True
) -> int:
    """
    Calculate high jump height.

    D&D 5e Rule:
    - With running start: Jump height = 3 + STR modifier (in feet)
    - Standing jump: Half that distance
    - Minimum of 0 feet

    Args:
        strength_modifier: Character's Strength modifier
        running_start: Whether the character has a 10ft running start

    Returns:
        Jump height in feet
    """
    base_height = max(0, 3 + strength_modifier)

    if running_start:
        return base_height
    else:
        return base_height // 2


def attempt_jump(
    grid: CombatGrid,
    jumper_id: str,
    from_x: int,
    from_y: int,
    to_x: int,
    to_y: int,
    strength_score: int,
    strength_modifier: int,
    running_start: bool = True,
    jump_type: str = "long"
) -> JumpResult:
    """
    Attempt a jump from one position to another.

    Args:
        grid: The combat grid
        jumper_id: ID of the jumping combatant
        from_x, from_y: Starting position
        to_x, to_y: Target position
        strength_score: Jumper's Strength score
        strength_modifier: Jumper's Strength modifier
        running_start: Whether jumper has 10ft running start
        jump_type: "long" for horizontal, "high" for vertical

    Returns:
        JumpResult with success/failure and details
    """
    # Calculate distance
    dx = abs(to_x - from_x)
    dy = abs(to_y - from_y)
    distance_ft = max(dx, dy) * 5

    # Get start and end cells
    start_cell = grid.get_cell(from_x, from_y)
    end_cell = grid.get_cell(to_x, to_y)

    if not end_cell:
        return JumpResult(
            success=False,
            distance_ft=0,
            movement_cost=0,
            description="Invalid destination"
        )

    if end_cell.terrain == TerrainType.IMPASSABLE:
        return JumpResult(
            success=False,
            distance_ft=0,
            movement_cost=0,
            description="Cannot land on impassable terrain"
        )

    if end_cell.occupied_by and end_cell.occupied_by != jumper_id:
        return JumpResult(
            success=False,
            distance_ft=0,
            movement_cost=0,
            description="Cannot land on occupied space"
        )

    # Calculate elevation change
    elevation_diff = 0
    if start_cell and end_cell:
        elevation_diff = end_cell.elevation - start_cell.elevation

    # Determine if jump is possible
    if jump_type == "long":
        max_distance = calculate_long_jump_distance(strength_score, running_start)

        # Jumping up requires clearing the height too
        if elevation_diff > 0:
            max_height = calculate_high_jump_distance(strength_modifier, running_start)
            height_needed = elevation_diff * 5  # Convert elevation to feet
            if height_needed > max_height:
                return JumpResult(
                    success=False,
                    distance_ft=0,
                    movement_cost=0,
                    description=f"Cannot jump high enough ({height_needed}ft needed, {max_height}ft max)"
                )

        if distance_ft > max_distance:
            return JumpResult(
                success=False,
                distance_ft=0,
                movement_cost=0,
                description=f"Distance too far ({distance_ft}ft, max {max_distance}ft)"
            )

    else:  # high jump
        max_height = calculate_high_jump_distance(strength_modifier, running_start)
        height_needed = max(0, elevation_diff) * 5

        if height_needed > max_height:
            return JumpResult(
                success=False,
                distance_ft=0,
                movement_cost=0,
                description=f"Cannot jump high enough ({height_needed}ft needed, {max_height}ft max)"
            )

    # Calculate movement cost (jump distance counts against movement)
    # Running start requires 10ft of movement before the jump
    movement_cost = distance_ft
    if running_start:
        movement_cost += 10

    # Check for hazards jumped over
    cleared_hazards = []
    has_los, cells_in_path = get_line_of_sight(grid, from_x, from_y, to_x, to_y)

    for x, y in cells_in_path:
        if (x, y) == (from_x, from_y) or (x, y) == (to_x, to_y):
            continue
        cell = grid.get_cell(x, y)
        if cell and (cell.is_hazard or cell.terrain == TerrainType.PIT):
            cleared_hazards.append((x, y))

    return JumpResult(
        success=True,
        distance_ft=distance_ft,
        movement_cost=movement_cost,
        description=f"Jumped {distance_ft}ft" + (f", cleared {len(cleared_hazards)} hazards" if cleared_hazards else ""),
        cleared_hazards=cleared_hazards
    )


# ============================================================================
# HAZARD SYSTEM
# ============================================================================

@dataclass
class HazardResult:
    """Result of entering a hazard."""
    took_damage: bool
    damage_dice: str
    damage_type: str
    description: str


def check_hazard_damage(
    grid: CombatGrid,
    x: int,
    y: int
) -> Optional[HazardResult]:
    """
    Check if a cell has a hazard and return damage info.

    Args:
        grid: The combat grid
        x, y: Position to check

    Returns:
        HazardResult if hazard present, None otherwise
    """
    cell = grid.get_cell(x, y)

    if not cell:
        return None

    if cell.is_hazard and cell.hazard_damage:
        return HazardResult(
            took_damage=True,
            damage_dice=cell.hazard_damage,
            damage_type=cell.hazard_type,
            description=f"Entered hazardous terrain ({cell.hazard_type})"
        )

    if cell.terrain == TerrainType.PIT:
        return HazardResult(
            took_damage=True,
            damage_dice="1d6",
            damage_type="bludgeoning",
            description="Fell into pit"
        )

    return None


def set_cell_hazard(
    grid: CombatGrid,
    x: int,
    y: int,
    damage_dice: str,
    damage_type: str
) -> bool:
    """
    Set a cell as a hazard.

    Args:
        grid: The combat grid
        x, y: Cell position
        damage_dice: Damage dice (e.g., "2d6")
        damage_type: Damage type (e.g., "fire")

    Returns:
        True if hazard was set, False if cell not found
    """
    cell = grid.get_cell(x, y)
    if cell:
        cell.is_hazard = True
        cell.hazard_damage = damage_dice
        cell.hazard_type = damage_type
        return True
    return False


def set_cell_elevation(
    grid: CombatGrid,
    x: int,
    y: int,
    elevation: int
) -> bool:
    """
    Set a cell's elevation.

    Args:
        grid: The combat grid
        x, y: Cell position
        elevation: Elevation in 5ft increments (0 = ground)

    Returns:
        True if elevation was set, False if cell not found
    """
    cell = grid.get_cell(x, y)
    if cell:
        cell.elevation = elevation
        return True
    return False


def set_cell_cover(
    grid: CombatGrid,
    x: int,
    y: int,
    cover_value: int
) -> bool:
    """
    Set a cell's cover value.

    Args:
        grid: The combat grid
        x, y: Cell position
        cover_value: 0=none, 2=half cover, 5=three-quarters cover

    Returns:
        True if cover was set, False if cell not found
    """
    if cover_value not in [0, 2, 5]:
        return False

    cell = grid.get_cell(x, y)
    if cell:
        cell.cover_value = cover_value
        return True
    return False
