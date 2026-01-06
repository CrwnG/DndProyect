"""Tests for the movement and pathfinding system."""
import pytest

from app.core.movement import (
    TerrainType,
    GridCell,
    CombatGrid,
    PathNode,
    MovementResult,
    calculate_distance,
    find_path,
    get_reachable_cells,
    get_threatened_squares,
    check_opportunity_attack_triggers,
    get_line_of_sight,
    get_cover_between,
    create_grid_with_obstacles,
)


class TestGridCell:
    """Test GridCell class."""

    def test_default_cell(self):
        """Default cell should be normal terrain."""
        cell = GridCell(x=0, y=0)

        assert cell.terrain == TerrainType.NORMAL
        assert cell.occupied_by is None
        assert cell.is_passable is True
        assert cell.movement_cost == 5

    def test_difficult_terrain(self):
        """Difficult terrain should cost double."""
        cell = GridCell(x=0, y=0, terrain=TerrainType.DIFFICULT)

        assert cell.is_passable is True
        assert cell.movement_cost == 10

    def test_impassable_terrain(self):
        """Impassable terrain should not be passable."""
        cell = GridCell(x=0, y=0, terrain=TerrainType.IMPASSABLE)

        assert cell.is_passable is False
        assert cell.movement_cost == float('inf')

    def test_occupied_cell(self):
        """Occupied cell should not be passable."""
        cell = GridCell(x=0, y=0, occupied_by="player-1")

        assert cell.is_passable is False

    def test_water_terrain(self):
        """Water should be difficult terrain."""
        cell = GridCell(x=0, y=0, terrain=TerrainType.WATER)

        assert cell.is_passable is True
        assert cell.movement_cost == 10


class TestCombatGrid:
    """Test CombatGrid class."""

    def test_create_default_grid(self):
        """Should create 8x8 grid by default."""
        grid = CombatGrid()

        assert grid.width == 8
        assert grid.height == 8
        assert len(grid.cells) == 64

    def test_create_custom_size(self):
        """Should create custom size grid."""
        grid = CombatGrid(width=10, height=6)

        assert grid.width == 10
        assert grid.height == 6
        assert len(grid.cells) == 60

    def test_get_cell(self):
        """Should get cell by coordinates."""
        grid = CombatGrid()

        cell = grid.get_cell(3, 4)

        assert cell is not None
        assert cell.x == 3
        assert cell.y == 4

    def test_get_cell_out_of_bounds(self):
        """Out of bounds should return None."""
        grid = CombatGrid()

        assert grid.get_cell(-1, 0) is None
        assert grid.get_cell(0, -1) is None
        assert grid.get_cell(8, 0) is None
        assert grid.get_cell(0, 8) is None

    def test_is_valid_position(self):
        """Should validate positions correctly."""
        grid = CombatGrid()

        assert grid.is_valid_position(0, 0) is True
        assert grid.is_valid_position(7, 7) is True
        assert grid.is_valid_position(-1, 0) is False
        assert grid.is_valid_position(8, 0) is False

    def test_set_terrain(self):
        """Should set terrain type."""
        grid = CombatGrid()

        result = grid.set_terrain(2, 2, TerrainType.DIFFICULT)

        assert result is True
        assert grid.get_cell(2, 2).terrain == TerrainType.DIFFICULT

    def test_set_occupant(self):
        """Should set cell occupant."""
        grid = CombatGrid()

        result = grid.set_occupant(3, 3, "player-1")

        assert result is True
        assert grid.get_occupant(3, 3) == "player-1"

    def test_clear_occupant(self):
        """Should clear occupant."""
        grid = CombatGrid()
        grid.set_occupant(3, 3, "player-1")

        grid.set_occupant(3, 3, None)

        assert grid.get_occupant(3, 3) is None

    def test_find_combatant(self):
        """Should find combatant position."""
        grid = CombatGrid()
        grid.set_occupant(5, 3, "player-1")

        pos = grid.find_combatant("player-1")

        assert pos == (5, 3)

    def test_find_combatant_not_found(self):
        """Should return None if not found."""
        grid = CombatGrid()

        pos = grid.find_combatant("nonexistent")

        assert pos is None

    def test_get_adjacent_cells_with_diagonals(self):
        """Should get 8 adjacent cells in center."""
        grid = CombatGrid()

        adjacent = grid.get_adjacent_cells(3, 3, include_diagonals=True)

        assert len(adjacent) == 8
        assert (2, 2) in adjacent  # Diagonal
        assert (3, 4) in adjacent  # Cardinal

    def test_get_adjacent_cells_without_diagonals(self):
        """Should get 4 adjacent cells without diagonals."""
        grid = CombatGrid()

        adjacent = grid.get_adjacent_cells(3, 3, include_diagonals=False)

        assert len(adjacent) == 4
        assert (2, 2) not in adjacent

    def test_get_adjacent_cells_corner(self):
        """Corner should have fewer adjacent cells."""
        grid = CombatGrid()

        adjacent = grid.get_adjacent_cells(0, 0, include_diagonals=True)

        assert len(adjacent) == 3

    def test_get_cells_in_radius(self):
        """Should get all cells within radius."""
        grid = CombatGrid()

        cells = grid.get_cells_in_radius(4, 4, 10)  # 2 square radius

        # Should be a 5x5 area centered on (4,4)
        assert len(cells) == 25
        assert (4, 4) in cells
        assert (2, 2) in cells
        assert (6, 6) in cells

    def test_serialization(self):
        """Should serialize and deserialize correctly."""
        grid = CombatGrid()
        grid.set_terrain(2, 2, TerrainType.DIFFICULT)
        grid.set_occupant(3, 3, "player-1")

        data = grid.to_dict()
        restored = CombatGrid.from_dict(data)

        assert restored.width == 8
        assert restored.height == 8
        assert restored.get_cell(2, 2).terrain == TerrainType.DIFFICULT
        assert restored.get_occupant(3, 3) == "player-1"


class TestPathNode:
    """Test PathNode class."""

    def test_f_cost_calculation(self):
        """F cost should be g + h."""
        node = PathNode(x=0, y=0, g_cost=10, h_cost=20)

        assert node.f_cost == 30

    def test_node_comparison(self):
        """Nodes should compare by f_cost."""
        node1 = PathNode(x=0, y=0, g_cost=10, h_cost=10)
        node2 = PathNode(x=1, y=1, g_cost=5, h_cost=30)

        assert node1 < node2  # 20 < 35

    def test_node_equality(self):
        """Nodes should be equal if same position."""
        node1 = PathNode(x=3, y=4, g_cost=10)
        node2 = PathNode(x=3, y=4, g_cost=20)

        assert node1 == node2


class TestDistanceCalculation:
    """Test distance calculation."""

    def test_cardinal_distance(self):
        """Cardinal movement distance."""
        assert calculate_distance(0, 0, 3, 0) == 15  # 3 squares = 15ft
        assert calculate_distance(0, 0, 0, 4) == 20  # 4 squares = 20ft

    def test_diagonal_distance_chebyshev(self):
        """Diagonal distance with Chebyshev (5ft diagonals)."""
        assert calculate_distance(0, 0, 3, 3) == 15  # max(3,3) = 3 squares = 15ft
        assert calculate_distance(0, 0, 2, 4) == 20  # max(2,4) = 4 squares = 20ft

    def test_diagonal_distance_alternating(self):
        """Diagonal distance with alternating rule."""
        # 3 diagonals = 5 + 10 + 5 = 20ft
        assert calculate_distance(0, 0, 3, 3, "alternating") == 20

    def test_same_position(self):
        """Distance to self is 0."""
        assert calculate_distance(5, 5, 5, 5) == 0


class TestPathfinding:
    """Test A* pathfinding."""

    def test_simple_path(self):
        """Should find path to adjacent cell."""
        grid = CombatGrid()

        result = find_path(grid, 0, 0, 1, 0)

        assert result.success is True
        assert result.total_cost == 5
        assert len(result.path) == 2
        assert result.path[0] == (0, 0)
        assert result.path[1] == (1, 0)

    def test_diagonal_path(self):
        """Should find diagonal path."""
        grid = CombatGrid()

        result = find_path(grid, 0, 0, 2, 2)

        assert result.success is True
        assert result.total_cost == 10  # 2 diagonal moves = 10ft

    def test_path_around_obstacle(self):
        """Should path around obstacles."""
        grid = CombatGrid()
        grid.set_terrain(1, 0, TerrainType.IMPASSABLE)
        grid.set_terrain(1, 1, TerrainType.IMPASSABLE)

        result = find_path(grid, 0, 0, 2, 0)

        assert result.success is True
        # Path should go around
        assert (1, 0) not in result.path

    def test_no_path_blocked(self):
        """Should fail if completely blocked."""
        grid = CombatGrid()
        # Block all exits from (0,0)
        grid.set_terrain(1, 0, TerrainType.IMPASSABLE)
        grid.set_terrain(0, 1, TerrainType.IMPASSABLE)
        grid.set_terrain(1, 1, TerrainType.IMPASSABLE)

        result = find_path(grid, 0, 0, 5, 5)

        assert result.success is False
        assert "No path found" in result.description

    def test_path_limited_by_movement(self):
        """Should limit path to available movement."""
        grid = CombatGrid()

        result = find_path(grid, 0, 0, 7, 0, max_movement=20)

        assert result.success is True
        assert result.total_cost <= 20
        # Should only go 4 squares (20ft)
        assert len(result.path) <= 5

    def test_same_position(self):
        """Should handle already at destination."""
        grid = CombatGrid()

        result = find_path(grid, 3, 3, 3, 3)

        assert result.success is True
        assert result.total_cost == 0
        assert result.path == [(3, 3)]

    def test_occupied_destination(self):
        """Should fail if destination is occupied."""
        grid = CombatGrid()
        grid.set_occupant(5, 5, "enemy-1")

        result = find_path(grid, 0, 0, 5, 5)

        assert result.success is False
        assert result.blocked_by == "enemy-1"

    def test_difficult_terrain_cost(self):
        """Difficult terrain should cost more."""
        grid = CombatGrid()
        grid.set_terrain(1, 0, TerrainType.DIFFICULT)

        result = find_path(grid, 0, 0, 2, 0)

        # 5ft + 10ft (difficult) + 5ft = 20ft if going through
        # But pathfinder might go around (diagonal)
        assert result.success is True
        assert result.total_cost >= 10


class TestReachableCells:
    """Test getting reachable cells."""

    def test_reachable_from_center(self):
        """Should find all reachable cells."""
        grid = CombatGrid()

        reachable = get_reachable_cells(grid, 4, 4, 30)

        # With 30ft movement, can reach 6 squares in any direction
        # Should be substantial area
        assert len(reachable) > 30

    def test_reachable_limited_movement(self):
        """Should limit to available movement."""
        grid = CombatGrid()

        reachable = get_reachable_cells(grid, 4, 4, 10)

        # With 10ft, can reach 2 squares
        for x, y, cost in reachable:
            assert cost <= 10

    def test_reachable_avoids_obstacles(self):
        """Should not include cells behind obstacles."""
        grid = CombatGrid()
        # Create a wall
        for y in range(8):
            grid.set_terrain(3, y, TerrainType.IMPASSABLE)

        reachable = get_reachable_cells(grid, 0, 4, 30)

        # Should not be able to reach past the wall directly
        positions = [(x, y) for x, y, _ in reachable]
        # Wall cells should not be reachable
        assert (3, 4) not in positions


class TestThreatenedSquares:
    """Test threatened square detection."""

    def test_threatened_squares(self):
        """Should get squares in melee range."""
        grid = CombatGrid()
        grid.set_occupant(4, 4, "fighter-1")

        threatened = get_threatened_squares(grid, "fighter-1", reach=5)

        # Should include adjacent squares
        assert (3, 3) in threatened
        assert (4, 3) in threatened
        assert (5, 5) in threatened
        # Center
        assert (4, 4) in threatened

    def test_reach_weapon(self):
        """Reach weapon should threaten more squares."""
        grid = CombatGrid()
        grid.set_occupant(4, 4, "pikeman-1")

        threatened = get_threatened_squares(grid, "pikeman-1", reach=10)

        # Should include 2 squares out
        assert (2, 4) in threatened
        assert (6, 6) in threatened


class TestOpportunityAttacks:
    """Test opportunity attack triggering."""

    def test_leaving_reach_triggers(self):
        """Moving away should trigger opportunity attack."""
        grid = CombatGrid()
        grid.set_occupant(0, 0, "player-1")
        grid.set_occupant(1, 0, "enemy-1")

        triggers = check_opportunity_attack_triggers(
            grid,
            mover_id="player-1",
            from_pos=(0, 0),
            to_pos=(0, 2),  # Moving away from enemy
            enemy_ids=["enemy-1"]
        )

        assert "enemy-1" in triggers

    def test_not_in_reach_no_trigger(self):
        """Moving when not in reach shouldn't trigger."""
        grid = CombatGrid()
        grid.set_occupant(0, 0, "player-1")
        grid.set_occupant(5, 5, "enemy-1")

        triggers = check_opportunity_attack_triggers(
            grid,
            mover_id="player-1",
            from_pos=(0, 0),
            to_pos=(0, 2),
            enemy_ids=["enemy-1"]
        )

        assert len(triggers) == 0

    def test_staying_in_reach_no_trigger(self):
        """Moving within reach shouldn't trigger."""
        grid = CombatGrid()
        grid.set_occupant(0, 0, "player-1")
        grid.set_occupant(1, 1, "enemy-1")

        triggers = check_opportunity_attack_triggers(
            grid,
            mover_id="player-1",
            from_pos=(0, 0),
            to_pos=(1, 0),  # Still adjacent to enemy
            enemy_ids=["enemy-1"]
        )

        assert len(triggers) == 0


class TestLineOfSight:
    """Test line of sight calculations."""

    def test_clear_los(self):
        """Clear line should have LoS."""
        grid = CombatGrid()

        has_los, cells = get_line_of_sight(grid, 0, 0, 5, 5)

        assert has_los is True
        assert len(cells) > 0

    def test_blocked_los(self):
        """Obstacle should block LoS."""
        grid = CombatGrid()
        grid.set_terrain(2, 2, TerrainType.IMPASSABLE)

        has_los, cells = get_line_of_sight(grid, 0, 0, 5, 5)

        assert has_los is False

    def test_los_path(self):
        """Should return cells in path."""
        grid = CombatGrid()

        has_los, cells = get_line_of_sight(grid, 0, 0, 3, 0)

        assert cells == [(0, 0), (1, 0), (2, 0), (3, 0)]


class TestCover:
    """Test cover calculations."""

    def test_no_cover(self):
        """Clear line should have no cover."""
        grid = CombatGrid()

        cover = get_cover_between(grid, 0, 0, 5, 0)

        assert cover == 0

    def test_full_cover(self):
        """Blocked LoS should give full cover."""
        grid = CombatGrid()
        grid.set_terrain(2, 0, TerrainType.IMPASSABLE)

        cover = get_cover_between(grid, 0, 0, 5, 0)

        assert cover == 5

    def test_half_cover(self):
        """Cell with cover value should provide it."""
        grid = CombatGrid()
        cell = grid.get_cell(2, 0)
        cell.cover_value = 2  # Half cover

        cover = get_cover_between(grid, 0, 0, 5, 0)

        assert cover == 2


class TestGridCreation:
    """Test convenience grid creation."""

    def test_create_with_obstacles(self):
        """Should create grid with obstacles."""
        grid = create_grid_with_obstacles(
            obstacles=[(2, 2), (3, 3)],
            difficult_terrain=[(1, 1)]
        )

        assert grid.get_cell(2, 2).terrain == TerrainType.IMPASSABLE
        assert grid.get_cell(3, 3).terrain == TerrainType.IMPASSABLE
        assert grid.get_cell(1, 1).terrain == TerrainType.DIFFICULT
        assert grid.get_cell(0, 0).terrain == TerrainType.NORMAL

    def test_create_custom_size(self):
        """Should create custom size with obstacles."""
        grid = create_grid_with_obstacles(
            width=10,
            height=10,
            obstacles=[(5, 5)]
        )

        assert grid.width == 10
        assert grid.height == 10
        assert grid.get_cell(5, 5).terrain == TerrainType.IMPASSABLE


class TestEdgeCases:
    """Test edge cases."""

    def test_invalid_start_position(self):
        """Should handle invalid start."""
        grid = CombatGrid()

        result = find_path(grid, -1, 0, 5, 5)

        assert result.success is False

    def test_invalid_end_position(self):
        """Should handle invalid end."""
        grid = CombatGrid()

        result = find_path(grid, 0, 0, 10, 10)

        assert result.success is False

    def test_empty_grid_pathfinding(self):
        """Should work on empty grid."""
        grid = CombatGrid()

        result = find_path(grid, 0, 0, 7, 7)

        assert result.success is True

    def test_reachable_from_corner(self):
        """Should work from corner."""
        grid = CombatGrid()

        reachable = get_reachable_cells(grid, 0, 0, 30)

        assert len(reachable) > 0
