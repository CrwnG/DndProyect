"""
D&D 5e AI Multi-Enemy Coordination System.

Coordinates multiple enemies for tactical advantage:
- Focus fire on single targets
- Flanking positioning
- Target distribution (avoid overkill)
- Synchronized actions (buff/attack combos)
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, TYPE_CHECKING
from enum import Enum

from .targeting import TargetEvaluator, TargetPriority
from app.core.movement import find_path

if TYPE_CHECKING:
    from app.core.combat_engine import CombatEngine


class CoordinationStrategy(Enum):
    """Overall coordination strategies."""
    FOCUS_FIRE = "focus_fire"       # All attack same target
    DISTRIBUTE = "distribute"        # Spread attacks evenly
    PRIORITY_CHAIN = "priority_chain"  # Attack in priority order
    PROTECT_CASTER = "protect_caster"  # Frontline protects backline
    SURROUND = "surround"            # Surround and flank


@dataclass
class TargetAssignment:
    """Assignment of an enemy to a target."""
    enemy_id: str
    enemy_name: str
    target_id: str
    target_name: str
    role: str  # attack, support, flank, block
    priority: int  # Lower = higher priority
    reasoning: str


@dataclass
class CoordinationPlan:
    """Complete coordination plan for a group of enemies."""
    strategy: CoordinationStrategy
    primary_target: Optional[str]
    assignments: List[TargetAssignment]
    flank_positions: Dict[str, Tuple[int, int]]  # enemy_id -> position
    focus_target_hp: int  # HP of focus target (for kill tracking)
    expected_damage: int  # Estimated total damage this round
    notes: List[str] = field(default_factory=list)


class CombatCoordinator:
    """
    Coordinates multiple enemies for tactical advantage.

    Analyzes the battlefield and assigns optimal targets/positions
    to each enemy combatant for maximum effectiveness.
    """

    def __init__(self, engine: "CombatEngine"):
        """
        Initialize coordinator.

        Args:
            engine: The combat engine instance
        """
        self.engine = engine
        self._target_evaluator_cache = {}

    def get_target_evaluator(self, combatant_id: str) -> TargetEvaluator:
        """Get or create a target evaluator for a combatant."""
        if combatant_id not in self._target_evaluator_cache:
            self._target_evaluator_cache[combatant_id] = TargetEvaluator(
                self.engine, combatant_id
            )
        return self._target_evaluator_cache[combatant_id]

    def create_plan(
        self,
        enemy_ids: List[str],
        player_ids: List[str],
        strategy: CoordinationStrategy = CoordinationStrategy.PRIORITY_CHAIN,
    ) -> CoordinationPlan:
        """
        Create a coordinated attack plan for enemy combatants.

        Args:
            enemy_ids: List of enemy combatant IDs to coordinate
            player_ids: List of player/ally IDs (targets)
            strategy: Coordination strategy to use

        Returns:
            CoordinationPlan with target assignments
        """
        if strategy == CoordinationStrategy.FOCUS_FIRE:
            return self._plan_focus_fire(enemy_ids, player_ids)
        elif strategy == CoordinationStrategy.DISTRIBUTE:
            return self._plan_distribute(enemy_ids, player_ids)
        elif strategy == CoordinationStrategy.SURROUND:
            return self._plan_surround(enemy_ids, player_ids)
        elif strategy == CoordinationStrategy.PROTECT_CASTER:
            return self._plan_protect_caster(enemy_ids, player_ids)
        else:
            return self._plan_priority_chain(enemy_ids, player_ids)

    def _plan_focus_fire(
        self,
        enemy_ids: List[str],
        player_ids: List[str],
    ) -> CoordinationPlan:
        """
        All enemies focus on a single high-priority target.

        Best when:
        - One player is significantly more dangerous
        - Target can be killed this round
        - Enemies have similar capabilities
        """
        # Find best target for focus fire
        if not player_ids:
            return self._empty_plan(enemy_ids, CoordinationStrategy.FOCUS_FIRE)

        # Use first enemy's perspective (they share info)
        evaluator = self.get_target_evaluator(enemy_ids[0])
        targets = evaluator.evaluate_all_targets(player_ids, TargetPriority.HIGHEST_THREAT)

        if not targets:
            return self._empty_plan(enemy_ids, CoordinationStrategy.FOCUS_FIRE)

        primary = targets[0]
        primary_combatant = self.engine.state.initiative_tracker.get_combatant(
            primary.target_id
        )
        primary_stats = self.engine.state.combatant_stats.get(primary.target_id, {})
        primary_hp = primary_stats.get("current_hp", 1)

        # Assign all enemies to focus target
        assignments = []
        expected_damage = 0
        flank_positions = {}

        for i, eid in enumerate(enemy_ids):
            enemy = self.engine.state.initiative_tracker.get_combatant(eid)
            enemy_stats = self.engine.state.combatant_stats.get(eid, {})

            # Estimate damage this enemy can deal
            est_damage = self._estimate_damage(enemy_stats)
            expected_damage += est_damage

            # Determine role - first two melee, rest can be backup
            role = "attack" if i < 4 else "backup"

            assignments.append(TargetAssignment(
                enemy_id=eid,
                enemy_name=enemy.name if enemy else "enemy",
                target_id=primary.target_id,
                target_name=primary.target_name,
                role=role,
                priority=i,
                reasoning=f"Focus fire on {primary.target_name}"
            ))

            # Assign flank positions
            flank_pos = self._find_flank_position(eid, primary.target_id, flank_positions)
            if flank_pos:
                flank_positions[eid] = flank_pos

        notes = [f"Focus fire strategy on {primary.target_name}"]
        if expected_damage >= primary_hp:
            notes.append(f"Kill likely! (Est. {expected_damage} dmg vs {primary_hp} HP)")

        return CoordinationPlan(
            strategy=CoordinationStrategy.FOCUS_FIRE,
            primary_target=primary.target_id,
            assignments=assignments,
            flank_positions=flank_positions,
            focus_target_hp=primary_hp,
            expected_damage=expected_damage,
            notes=notes,
        )

    def _plan_distribute(
        self,
        enemy_ids: List[str],
        player_ids: List[str],
    ) -> CoordinationPlan:
        """
        Distribute attacks across targets to avoid overkill.

        Best when:
        - Multiple targets are equally threatening
        - Enemies significantly outnumber players
        - Want to pressure the whole party
        """
        if not player_ids:
            return self._empty_plan(enemy_ids, CoordinationStrategy.DISTRIBUTE)

        assignments = []
        target_assignment_count: Dict[str, int] = {pid: 0 for pid in player_ids}

        # Evaluate all targets once
        evaluator = self.get_target_evaluator(enemy_ids[0])
        all_targets = evaluator.evaluate_all_targets(player_ids, TargetPriority.HIGHEST_THREAT)
        target_scores = {t.target_id: t for t in all_targets}

        for eid in enemy_ids:
            enemy = self.engine.state.initiative_tracker.get_combatant(eid)

            # Find least-targeted player that's still valid
            best_target = None
            best_count = 999

            for pid in player_ids:
                count = target_assignment_count[pid]
                if count < best_count:
                    best_count = count
                    best_target = pid

            if best_target:
                target_assignment_count[best_target] += 1
                target_info = target_scores.get(best_target)

                assignments.append(TargetAssignment(
                    enemy_id=eid,
                    enemy_name=enemy.name if enemy else "enemy",
                    target_id=best_target,
                    target_name=target_info.target_name if target_info else "target",
                    role="attack",
                    priority=len(assignments),
                    reasoning=f"Distributed attack (target has {best_count} attackers)"
                ))

        return CoordinationPlan(
            strategy=CoordinationStrategy.DISTRIBUTE,
            primary_target=None,
            assignments=assignments,
            flank_positions={},
            focus_target_hp=0,
            expected_damage=0,
            notes=["Distributed attack strategy - pressuring multiple targets"],
        )

    def _plan_priority_chain(
        self,
        enemy_ids: List[str],
        player_ids: List[str],
    ) -> CoordinationPlan:
        """
        Attack targets in priority order, moving to next when one falls.

        Best when:
        - Mixed enemy capabilities
        - Want efficient target selection
        - Standard tactical approach
        """
        if not player_ids:
            return self._empty_plan(enemy_ids, CoordinationStrategy.PRIORITY_CHAIN)

        evaluator = self.get_target_evaluator(enemy_ids[0])
        priority_targets = evaluator.evaluate_all_targets(
            player_ids, TargetPriority.HIGHEST_THREAT
        )

        if not priority_targets:
            return self._empty_plan(enemy_ids, CoordinationStrategy.PRIORITY_CHAIN)

        assignments = []
        target_damage_assigned: Dict[str, int] = {}

        for eid in enemy_ids:
            enemy = self.engine.state.initiative_tracker.get_combatant(eid)
            enemy_stats = self.engine.state.combatant_stats.get(eid, {})
            est_damage = self._estimate_damage(enemy_stats)

            # Find best target that isn't "overkilled"
            assigned_target = None
            for target in priority_targets:
                target_stats = self.engine.state.combatant_stats.get(target.target_id, {})
                target_hp = target_stats.get("current_hp", 1)

                damage_so_far = target_damage_assigned.get(target.target_id, 0)

                # Don't overkill by more than 50%
                if damage_so_far < target_hp * 1.5:
                    assigned_target = target
                    target_damage_assigned[target.target_id] = damage_so_far + est_damage
                    break

            if not assigned_target:
                # All targets overkilled, pick the top priority
                assigned_target = priority_targets[0]

            assignments.append(TargetAssignment(
                enemy_id=eid,
                enemy_name=enemy.name if enemy else "enemy",
                target_id=assigned_target.target_id,
                target_name=assigned_target.target_name,
                role="attack",
                priority=len(assignments),
                reasoning=f"Priority chain: {assigned_target.target_name} ({', '.join(assigned_target.reasons[:1])})"
            ))

        return CoordinationPlan(
            strategy=CoordinationStrategy.PRIORITY_CHAIN,
            primary_target=priority_targets[0].target_id if priority_targets else None,
            assignments=assignments,
            flank_positions={},
            focus_target_hp=0,
            expected_damage=sum(target_damage_assigned.values()),
            notes=["Priority chain strategy - efficient target selection"],
        )

    def _plan_surround(
        self,
        enemy_ids: List[str],
        player_ids: List[str],
    ) -> CoordinationPlan:
        """
        Surround targets to maximize flanking.

        Best when:
        - Many melee enemies
        - Players are grouped
        - Want to prevent escape
        """
        if not player_ids:
            return self._empty_plan(enemy_ids, CoordinationStrategy.SURROUND)

        # Find center of players
        player_positions = []
        for pid in player_ids:
            pos = self.engine.state.positions.get(pid)
            if pos:
                if isinstance(pos, dict):
                    pos = (pos.get("x", 0), pos.get("y", 0))
                player_positions.append(pos)

        if not player_positions:
            return self._plan_priority_chain(enemy_ids, player_ids)

        # Calculate center
        center_x = sum(p[0] for p in player_positions) // len(player_positions)
        center_y = sum(p[1] for p in player_positions) // len(player_positions)

        # Assign enemies to surround positions
        assignments = []
        flank_positions = {}

        # Cardinal directions for surrounding
        directions = [
            (0, -2), (2, 0), (0, 2), (-2, 0),  # N, E, S, W
            (-1, -1), (1, -1), (1, 1), (-1, 1),  # Diagonals
        ]

        for i, eid in enumerate(enemy_ids):
            enemy = self.engine.state.initiative_tracker.get_combatant(eid)

            # Assign surround position
            dir_idx = i % len(directions)
            surround_pos = (
                center_x + directions[dir_idx][0],
                center_y + directions[dir_idx][1]
            )
            flank_positions[eid] = surround_pos

            # Find nearest player to attack
            nearest_player = None
            nearest_dist = 999
            for pid in player_ids:
                ppos = self.engine.state.positions.get(pid)
                if ppos:
                    if isinstance(ppos, dict):
                        ppos = (ppos.get("x", 0), ppos.get("y", 0))
                    dist = abs(surround_pos[0] - ppos[0]) + abs(surround_pos[1] - ppos[1])
                    if dist < nearest_dist:
                        nearest_dist = dist
                        nearest_player = pid

            if nearest_player:
                target = self.engine.state.initiative_tracker.get_combatant(nearest_player)
                assignments.append(TargetAssignment(
                    enemy_id=eid,
                    enemy_name=enemy.name if enemy else "enemy",
                    target_id=nearest_player,
                    target_name=target.name if target else "target",
                    role="flank",
                    priority=i,
                    reasoning=f"Surround and flank"
                ))

        return CoordinationPlan(
            strategy=CoordinationStrategy.SURROUND,
            primary_target=None,
            assignments=assignments,
            flank_positions=flank_positions,
            focus_target_hp=0,
            expected_damage=0,
            notes=["Surround strategy - maximizing flanking opportunities"],
        )

    def _plan_protect_caster(
        self,
        enemy_ids: List[str],
        player_ids: List[str],
    ) -> CoordinationPlan:
        """
        Front line protects back line casters.

        Best when:
        - Enemy group has casters
        - Melee enemies can act as wall
        - Need to protect key damage dealers
        """
        # Identify casters vs melee among enemies
        casters = []
        melee = []

        for eid in enemy_ids:
            enemy_stats = self.engine.state.combatant_stats.get(eid, {})
            enemy_class = enemy_stats.get("class", "").lower()

            if enemy_class in ["wizard", "sorcerer", "warlock", "cleric", "druid"]:
                casters.append(eid)
            else:
                melee.append(eid)

        # If no clear split, use priority chain
        if not casters or not melee:
            return self._plan_priority_chain(enemy_ids, player_ids)

        assignments = []

        # Melee form defensive line and attack nearest players
        evaluator = self.get_target_evaluator(melee[0]) if melee else None
        targets = evaluator.evaluate_all_targets(player_ids, TargetPriority.NEAREST) if evaluator else []

        for eid in melee:
            enemy = self.engine.state.initiative_tracker.get_combatant(eid)
            target = targets[0] if targets else None

            assignments.append(TargetAssignment(
                enemy_id=eid,
                enemy_name=enemy.name if enemy else "enemy",
                target_id=target.target_id if target else player_ids[0],
                target_name=target.target_name if target else "target",
                role="block",
                priority=len(assignments),
                reasoning="Frontline blocking"
            ))

        # Casters target high-priority enemies from safety
        if casters and player_ids:
            caster_evaluator = self.get_target_evaluator(casters[0])
            caster_targets = caster_evaluator.evaluate_all_targets(
                player_ids, TargetPriority.HIGHEST_THREAT
            )

            for eid in casters:
                enemy = self.engine.state.initiative_tracker.get_combatant(eid)
                target = caster_targets[0] if caster_targets else None

                assignments.append(TargetAssignment(
                    enemy_id=eid,
                    enemy_name=enemy.name if enemy else "enemy",
                    target_id=target.target_id if target else player_ids[0],
                    target_name=target.target_name if target else "target",
                    role="support",
                    priority=len(assignments),
                    reasoning="Protected caster"
                ))

        return CoordinationPlan(
            strategy=CoordinationStrategy.PROTECT_CASTER,
            primary_target=None,
            assignments=assignments,
            flank_positions={},
            focus_target_hp=0,
            expected_damage=0,
            notes=[
                f"Protect caster strategy",
                f"{len(melee)} melee blocking, {len(casters)} casters in back"
            ],
        )

    def _empty_plan(
        self,
        enemy_ids: List[str],
        strategy: CoordinationStrategy,
    ) -> CoordinationPlan:
        """Create empty plan when no valid targets."""
        return CoordinationPlan(
            strategy=strategy,
            primary_target=None,
            assignments=[],
            flank_positions={},
            focus_target_hp=0,
            expected_damage=0,
            notes=["No valid targets found"],
        )

    def _estimate_damage(self, enemy_stats: Dict) -> int:
        """Estimate damage an enemy can deal in one round."""
        damage = 0

        # Check equipped weapon
        equipment = enemy_stats.get("equipment", {})
        main_weapon = equipment.get("main_hand", {})

        if main_weapon:
            damage_dice = main_weapon.get("damage_dice", "1d6")
            damage = self._parse_avg_dice(damage_dice)

            # Add ability modifier (assume STR or DEX)
            str_mod = (enemy_stats.get("strength", 10) - 10) // 2
            dex_mod = (enemy_stats.get("dexterity", 10) - 10) // 2
            damage += max(str_mod, dex_mod)

        # Fallback estimate based on CR/level
        if damage == 0:
            level = enemy_stats.get("level", 1)
            damage = 5 + level  # Rough estimate

        return max(1, damage)

    def _parse_avg_dice(self, dice_str: str) -> int:
        """Parse average value from dice string."""
        try:
            if "d" not in dice_str.lower():
                return int(dice_str)

            parts = dice_str.lower().split("d")
            num_dice = int(parts[0]) if parts[0] else 1
            die_size = int(parts[1].split("+")[0].split("-")[0])

            avg = num_dice * (die_size + 1) // 2

            if "+" in dice_str:
                mod = int(dice_str.split("+")[1])
                avg += mod

            return avg
        except (ValueError, IndexError):
            return 4  # Default

    def _find_flank_position(
        self,
        enemy_id: str,
        target_id: str,
        existing_positions: Dict[str, Tuple[int, int]],
    ) -> Optional[Tuple[int, int]]:
        """Find optimal flanking position for an enemy."""
        target_pos = self.engine.state.positions.get(target_id)
        if not target_pos:
            return None

        if isinstance(target_pos, dict):
            target_pos = (target_pos.get("x", 0), target_pos.get("y", 0))

        # Adjacent positions
        adjacent = [
            (target_pos[0] - 1, target_pos[1]),
            (target_pos[0] + 1, target_pos[1]),
            (target_pos[0], target_pos[1] - 1),
            (target_pos[0], target_pos[1] + 1),
        ]

        taken_positions = set(existing_positions.values())

        for pos in adjacent:
            if pos not in taken_positions:
                # Check if position is valid
                if self._is_position_valid(pos):
                    return pos

        return None

    def _is_position_valid(self, pos: Tuple[int, int]) -> bool:
        """Check if a position is valid for movement."""
        # Check grid bounds
        if hasattr(self.engine.state, "grid") and self.engine.state.grid:
            grid = self.engine.state.grid
            if pos[0] < 0 or pos[0] >= grid.width:
                return False
            if pos[1] < 0 or pos[1] >= grid.height:
                return False

            cell = grid.get_cell(pos[0], pos[1])
            if cell and not cell.is_passable:
                return False

        # Check for other combatants
        for cid, cpos in self.engine.state.positions.items():
            if isinstance(cpos, dict):
                cpos = (cpos.get("x", 0), cpos.get("y", 0))
            if cpos[0] == pos[0] and cpos[1] == pos[1]:
                return False

        return True

    def get_recommended_strategy(
        self,
        enemy_ids: List[str],
        player_ids: List[str],
    ) -> CoordinationStrategy:
        """
        Determine the best coordination strategy for current situation.

        Args:
            enemy_ids: List of enemy combatants
            player_ids: List of player combatants

        Returns:
            Recommended CoordinationStrategy
        """
        num_enemies = len(enemy_ids)
        num_players = len(player_ids)

        if num_enemies == 0 or num_players == 0:
            return CoordinationStrategy.PRIORITY_CHAIN

        # Check if any player is low HP - focus fire opportunity
        for pid in player_ids:
            pstats = self.engine.state.combatant_stats.get(pid, {})
            current = pstats.get("current_hp", 1)
            max_hp = pstats.get("max_hp", 1)
            if current / max_hp < 0.3:
                return CoordinationStrategy.FOCUS_FIRE

        # Check if enemies include casters
        has_casters = any(
            self.engine.state.combatant_stats.get(eid, {}).get("class", "").lower()
            in ["wizard", "sorcerer", "warlock", "cleric", "druid"]
            for eid in enemy_ids
        )

        if has_casters and num_enemies > 2:
            return CoordinationStrategy.PROTECT_CASTER

        # Many enemies vs few players - surround
        if num_enemies >= num_players * 2:
            return CoordinationStrategy.SURROUND

        # More players than enemies - focus fire
        if num_players > num_enemies:
            return CoordinationStrategy.FOCUS_FIRE

        # Default to balanced distribution
        return CoordinationStrategy.PRIORITY_CHAIN

    def get_movement_for_plan(
        self,
        plan: CoordinationPlan,
    ) -> Dict[str, Dict]:
        """
        Generate movement decisions for enemies based on coordination plan.

        Calculates actual paths from each enemy's current position to their
        assigned flank position using A* pathfinding.

        Args:
            plan: The coordination plan with flank_positions

        Returns:
            Dict mapping enemy_id to movement info:
            {
                enemy_id: {
                    "target_position": (x, y),
                    "path": [(x1, y1), (x2, y2), ...],
                    "needs_movement": bool,
                    "can_reach": bool,
                    "distance": int (in feet)
                }
            }
        """
        movement_commands = {}

        for enemy_id, target_pos in plan.flank_positions.items():
            # Get enemy's current position
            current_pos = self.engine.state.positions.get(enemy_id)
            if not current_pos:
                continue

            if isinstance(current_pos, dict):
                current_pos = (current_pos.get("x", 0), current_pos.get("y", 0))

            # Check if already at target
            if current_pos == target_pos:
                movement_commands[enemy_id] = {
                    "target_position": target_pos,
                    "path": [],
                    "needs_movement": False,
                    "can_reach": True,
                    "distance": 0,
                }
                continue

            # Get enemy's available movement
            enemy_stats = self.engine.state.combatant_stats.get(enemy_id, {})
            speed = enemy_stats.get("speed", 30)  # Default 30ft
            movement_remaining = enemy_stats.get("movement_remaining", speed)

            # Calculate path using A* pathfinding
            path = None
            can_reach = False
            distance = 0

            if hasattr(self.engine.state, "grid") and self.engine.state.grid:
                # Get ally IDs (other enemies on same side)
                ally_ids = set()
                for assignment in plan.assignments:
                    if assignment.enemy_id != enemy_id:
                        ally_ids.add(assignment.enemy_id)

                path_result = find_path(
                    self.engine.state.grid,
                    current_pos[0], current_pos[1],
                    target_pos[0], target_pos[1],
                    max_movement=movement_remaining,
                    mover_id=enemy_id,
                    ally_ids=ally_ids
                )

                if path_result.success:
                    path = path_result.path
                    can_reach = True
                    distance = path_result.total_cost
                else:
                    # Path is blocked or too far, try to get as close as possible
                    # The path may still have partial progress
                    if path_result.path:
                        path = path_result.path
                        can_reach = False
                        distance = path_result.total_cost
            else:
                # No grid, use simple distance calculation
                dx = abs(target_pos[0] - current_pos[0])
                dy = abs(target_pos[1] - current_pos[1])
                distance = max(dx, dy) * 5  # Chebyshev distance in feet
                can_reach = distance <= movement_remaining
                # Simple straight-line path
                path = [current_pos, target_pos] if can_reach else None

            movement_commands[enemy_id] = {
                "target_position": target_pos,
                "path": path or [],
                "needs_movement": True,
                "can_reach": can_reach,
                "distance": distance,
            }

        return movement_commands


def coordinate_enemies(
    engine: "CombatEngine",
    enemy_ids: List[str],
    player_ids: List[str],
) -> CoordinationPlan:
    """
    Convenience function to coordinate enemies.

    Args:
        engine: Combat engine instance
        enemy_ids: List of enemy combatant IDs
        player_ids: List of player combatant IDs

    Returns:
        CoordinationPlan with optimal strategy and assignments
    """
    coordinator = CombatCoordinator(engine)
    strategy = coordinator.get_recommended_strategy(enemy_ids, player_ids)
    return coordinator.create_plan(enemy_ids, player_ids, strategy)
