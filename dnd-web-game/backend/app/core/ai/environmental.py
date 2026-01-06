"""
D&D 5e AI Environmental Awareness Module.

Provides tactical analysis of environmental features for AI decision-making:
- Surface hazards (fire, acid, poison, etc.)
- Pits and elevation drops (falling damage opportunities)
- Elemental combo opportunities (lightning + water)
- Cover positions
- Throwable objects
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING, Set
from enum import Enum

if TYPE_CHECKING:
    from app.core.combat_engine import CombatEngine


class HazardType(Enum):
    """Types of environmental hazards."""
    PIT = "pit"
    LEDGE = "ledge"
    FIRE = "fire"
    ACID = "acid"
    POISON = "poison"
    ELECTRIFIED_WATER = "electrified_water"
    ICE = "ice"
    GREASE = "grease"


@dataclass
class EnvironmentalHazard:
    """Represents a hazard at a position."""
    position: Tuple[int, int]
    hazard_type: HazardType
    damage_potential: int  # Expected damage if pushed into
    causes_condition: Optional[str] = None  # e.g., "prone", "restrained"
    description: str = ""


@dataclass
class PushOpportunity:
    """Represents an opportunity to push enemy into hazard."""
    target_id: str
    target_name: str
    push_direction: Tuple[int, int]
    hazard: EnvironmentalHazard
    score_bonus: float  # Additional score to add to shove action
    reasoning: str


@dataclass
class ElementalCombo:
    """Represents an elemental combination opportunity."""
    spell_id: str
    target_position: Tuple[int, int]
    affected_enemy_ids: List[str]
    combo_type: str  # e.g., "lightning_water", "fire_grease"
    bonus_damage: int
    reasoning: str


class EnvironmentalAnalyzer:
    """
    Analyzes the battlefield for environmental tactical opportunities.

    Used by AI to make smarter decisions about:
    - Positioning (avoid hazards)
    - Pushing enemies into hazards
    - Exploiting elemental combinations
    - Using throwable objects
    """

    # Damage surfaces that AI should avoid standing in
    HARMFUL_SURFACES = {"fire", "acid", "poison", "electrified_water"}

    # Difficult terrain surfaces (less priority to avoid)
    DIFFICULT_SURFACES = {"ice", "grease", "web"}

    # Surface + spell combinations for bonus damage
    ELEMENTAL_COMBOS = {
        ("water", "lightning"): {"bonus_damage": 6, "name": "electrocution"},
        ("grease", "fire"): {"bonus_damage": 8, "name": "grease fire"},
        ("oil", "fire"): {"bonus_damage": 10, "name": "oil ignition"},
        ("ice", "fire"): {"remove_surface": True, "name": "melt"},
        ("water", "cold"): {"create_surface": "ice", "name": "freeze"},
    }

    def __init__(self, engine: "CombatEngine"):
        self.engine = engine

    def get_position_hazard_score(
        self,
        position: Tuple[int, int],
        combatant_stats: Dict
    ) -> float:
        """
        Get a danger score for a position (higher = more dangerous).

        Used by AI to evaluate whether to stand on a cell.

        Args:
            position: Grid position to evaluate
            combatant_stats: Stats of combatant considering the position

        Returns:
            Danger score (0 = safe, higher = more dangerous)
        """
        danger = 0.0

        # Check for surface effects
        surface_manager = getattr(self.engine.state, 'surface_manager', None)
        if surface_manager:
            surfaces = surface_manager.get_surfaces_at(position[0], position[1])
            for surface in surfaces:
                surface_type = surface.surface_type.value if hasattr(surface.surface_type, 'value') else str(surface.surface_type)

                if surface_type in self.HARMFUL_SURFACES:
                    # High danger for damaging surfaces
                    danger += 50.0

                    # Check for resistance/immunity
                    resistances = combatant_stats.get("resistances", [])
                    immunities = combatant_stats.get("immunities", [])

                    damage_type = self._get_surface_damage_type(surface_type)
                    if damage_type in immunities:
                        danger -= 50.0  # Safe if immune
                    elif damage_type in resistances:
                        danger -= 25.0  # Less dangerous if resistant

                elif surface_type in self.DIFFICULT_SURFACES:
                    # Moderate danger for difficult terrain
                    danger += 15.0

                    # Ice/grease are dangerous if enemy could push us
                    if surface_type in ("ice", "grease"):
                        danger += 10.0  # Prone risk

        # Check for pit
        grid = getattr(self.engine.state, 'grid', None)
        if grid:
            try:
                from app.core.falling import check_pit_fall
                is_pit, depth = check_pit_fall(grid, position[0], position[1])
                if is_pit:
                    damage = (depth // 10) * 3.5  # Average d6 damage per 10ft
                    danger += damage + 20  # Extra penalty for pit
            except (ImportError, AttributeError):
                pass

        return danger

    def _get_surface_damage_type(self, surface_type: str) -> str:
        """Get the damage type for a surface."""
        damage_map = {
            "fire": "fire",
            "acid": "acid",
            "poison": "poison",
            "electrified_water": "lightning",
        }
        return damage_map.get(surface_type, "")

    def find_push_opportunities(
        self,
        pusher_id: str,
        pusher_position: Tuple[int, int],
        potential_targets: List[str]
    ) -> List[PushOpportunity]:
        """
        Find opportunities to push enemies into hazards.

        Checks adjacent enemies and determines if pushing them would
        result in extra damage from pits, ledges, or surfaces.

        Args:
            pusher_id: ID of the combatant doing the pushing
            pusher_position: Position of the pusher
            potential_targets: List of enemy IDs to consider pushing

        Returns:
            List of push opportunities sorted by value
        """
        opportunities = []

        for target_id in potential_targets:
            target_pos = self.engine.state.positions.get(target_id)
            if not target_pos:
                continue

            if isinstance(target_pos, dict):
                target_pos = (target_pos.get("x", 0), target_pos.get("y", 0))

            # Check if target is adjacent (can be shoved)
            dx = target_pos[0] - pusher_position[0]
            dy = target_pos[1] - pusher_position[1]

            if abs(dx) > 1 or abs(dy) > 1:
                continue  # Not adjacent

            if dx == 0 and dy == 0:
                continue  # Same position (shouldn't happen)

            # Determine push direction (away from pusher)
            push_dx = 1 if dx > 0 else (-1 if dx < 0 else 0)
            push_dy = 1 if dy > 0 else (-1 if dy < 0 else 0)

            # Check destination cell for hazards
            dest_x = target_pos[0] + push_dx
            dest_y = target_pos[1] + push_dy

            hazard = self._check_hazard_at(dest_x, dest_y, target_pos)
            if hazard:
                target = self.engine.state.initiative_tracker.get_combatant(target_id)
                target_name = target.name if target else "enemy"

                opportunities.append(PushOpportunity(
                    target_id=target_id,
                    target_name=target_name,
                    push_direction=(push_dx, push_dy),
                    hazard=hazard,
                    score_bonus=hazard.damage_potential * 2 + 20,  # Bonus based on damage
                    reasoning=f"Push {target_name} into {hazard.description}"
                ))

        # Sort by score bonus (best opportunities first)
        opportunities.sort(key=lambda x: x.score_bonus, reverse=True)
        return opportunities

    def _check_hazard_at(
        self,
        x: int,
        y: int,
        from_pos: Tuple[int, int]
    ) -> Optional[EnvironmentalHazard]:
        """Check for hazards at a position."""
        grid = getattr(self.engine.state, 'grid', None)

        # Check for pit
        try:
            from app.core.falling import check_pit_fall, check_fall_from_position

            if grid:
                # Check for pit
                is_pit, depth = check_pit_fall(grid, x, y)
                if is_pit and depth >= 10:
                    avg_damage = (depth // 10) * 3.5
                    return EnvironmentalHazard(
                        position=(x, y),
                        hazard_type=HazardType.PIT,
                        damage_potential=int(avg_damage),
                        causes_condition="prone",
                        description=f"{depth}ft pit"
                    )

                # Check for elevation drop (ledge)
                fall_distance = check_fall_from_position(
                    grid, from_pos[0], from_pos[1], x, y
                )
                if fall_distance >= 10:
                    avg_damage = (fall_distance // 10) * 3.5
                    return EnvironmentalHazard(
                        position=(x, y),
                        hazard_type=HazardType.LEDGE,
                        damage_potential=int(avg_damage),
                        causes_condition="prone",
                        description=f"{fall_distance}ft drop"
                    )
        except (ImportError, AttributeError):
            pass

        # Check for harmful surfaces
        surface_manager = getattr(self.engine.state, 'surface_manager', None)
        if surface_manager:
            surfaces = surface_manager.get_surfaces_at(x, y)
            for surface in surfaces:
                surface_type = surface.surface_type.value if hasattr(surface.surface_type, 'value') else str(surface.surface_type)

                if surface_type == "fire":
                    return EnvironmentalHazard(
                        position=(x, y),
                        hazard_type=HazardType.FIRE,
                        damage_potential=3,  # 1d4 avg
                        description="fire"
                    )
                elif surface_type == "acid":
                    return EnvironmentalHazard(
                        position=(x, y),
                        hazard_type=HazardType.ACID,
                        damage_potential=7,  # 2d4 avg
                        description="acid pool"
                    )
                elif surface_type == "poison":
                    return EnvironmentalHazard(
                        position=(x, y),
                        hazard_type=HazardType.POISON,
                        damage_potential=3,
                        causes_condition="poisoned",
                        description="poison cloud"
                    )
                elif surface_type == "electrified_water":
                    return EnvironmentalHazard(
                        position=(x, y),
                        hazard_type=HazardType.ELECTRIFIED_WATER,
                        damage_potential=7,  # 2d6 avg
                        description="electrified water"
                    )

        return None

    def find_elemental_combos(
        self,
        caster_position: Tuple[int, int],
        enemy_positions: Dict[str, Tuple[int, int]],
        available_spells: List[str]
    ) -> List[ElementalCombo]:
        """
        Find opportunities for elemental combination attacks.

        Checks for enemies standing in water (for lightning),
        near grease (for fire), etc.

        Args:
            caster_position: Position of the spellcaster
            enemy_positions: Dict of enemy_id -> position
            available_spells: List of spell IDs the caster knows

        Returns:
            List of combo opportunities
        """
        combos = []
        surface_manager = getattr(self.engine.state, 'surface_manager', None)

        if not surface_manager:
            return combos

        # Spell to damage type mapping
        lightning_spells = {"lightning_bolt", "witch_bolt", "shocking_grasp", "call_lightning"}
        fire_spells = {"fireball", "fire_bolt", "burning_hands", "scorching_ray", "flame_strike"}
        cold_spells = {"ray_of_frost", "cone_of_cold", "ice_storm"}

        for enemy_id, enemy_pos in enemy_positions.items():
            if isinstance(enemy_pos, dict):
                enemy_pos = (enemy_pos.get("x", 0), enemy_pos.get("y", 0))

            surfaces = surface_manager.get_surfaces_at(enemy_pos[0], enemy_pos[1])

            for surface in surfaces:
                surface_type = surface.surface_type.value if hasattr(surface.surface_type, 'value') else str(surface.surface_type)

                # Lightning + Water combo
                if surface_type == "water":
                    for spell in available_spells:
                        if spell.lower().replace(" ", "_") in lightning_spells:
                            # Find all enemies in connected water
                            affected = self._find_enemies_in_water(enemy_positions, enemy_pos)
                            combos.append(ElementalCombo(
                                spell_id=spell,
                                target_position=enemy_pos,
                                affected_enemy_ids=affected,
                                combo_type="lightning_water",
                                bonus_damage=6,  # Electrocution bonus
                                reasoning=f"Cast {spell} on water - electrocute {len(affected)} enemies!"
                            ))
                            break  # Only need one lightning spell

                # Fire + Grease/Oil combo
                if surface_type in ("grease", "oil"):
                    for spell in available_spells:
                        if spell.lower().replace(" ", "_") in fire_spells:
                            combos.append(ElementalCombo(
                                spell_id=spell,
                                target_position=enemy_pos,
                                affected_enemy_ids=[enemy_id],
                                combo_type="fire_grease",
                                bonus_damage=8,  # Fire spread bonus
                                reasoning=f"Cast {spell} to ignite {surface_type} - fire spreads!"
                            ))
                            break

        # Sort by affected enemies and bonus damage
        combos.sort(key=lambda x: len(x.affected_enemy_ids) * 10 + x.bonus_damage, reverse=True)
        return combos

    def _find_enemies_in_water(
        self,
        enemy_positions: Dict[str, Tuple[int, int]],
        water_pos: Tuple[int, int]
    ) -> List[str]:
        """Find all enemies standing in water near a position."""
        affected = []
        surface_manager = getattr(self.engine.state, 'surface_manager', None)

        if not surface_manager:
            return affected

        for enemy_id, pos in enemy_positions.items():
            if isinstance(pos, dict):
                pos = (pos.get("x", 0), pos.get("y", 0))

            surfaces = surface_manager.get_surfaces_at(pos[0], pos[1])
            for surface in surfaces:
                surface_type = surface.surface_type.value if hasattr(surface.surface_type, 'value') else str(surface.surface_type)
                if surface_type == "water":
                    affected.append(enemy_id)
                    break

        return affected

    def get_safe_positions(
        self,
        current_position: Tuple[int, int],
        movement_range: int,
        combatant_stats: Dict
    ) -> List[Tuple[Tuple[int, int], float]]:
        """
        Get list of safe positions within movement range.

        Returns positions sorted by safety (lowest danger first).

        Args:
            current_position: Current position
            movement_range: Available movement in cells
            combatant_stats: Stats for resistance/immunity checks

        Returns:
            List of (position, danger_score) tuples, sorted by safety
        """
        safe_positions = []
        grid = getattr(self.engine.state, 'grid', None)

        # Check positions within movement range
        for dx in range(-movement_range, movement_range + 1):
            for dy in range(-movement_range, movement_range + 1):
                # Manhattan distance check
                if abs(dx) + abs(dy) > movement_range:
                    continue

                test_pos = (current_position[0] + dx, current_position[1] + dy)

                # Check grid bounds
                if grid:
                    if test_pos[0] < 0 or test_pos[0] >= grid.width:
                        continue
                    if test_pos[1] < 0 or test_pos[1] >= grid.height:
                        continue

                    # Check if passable
                    cell = grid.get_cell(test_pos[0], test_pos[1])
                    if cell and not getattr(cell, 'is_passable', True):
                        continue

                # Check for other combatants
                occupied = False
                for cid, cpos in self.engine.state.positions.items():
                    if isinstance(cpos, dict):
                        cpos = (cpos.get("x", 0), cpos.get("y", 0))
                    if cpos[0] == test_pos[0] and cpos[1] == test_pos[1]:
                        occupied = True
                        break

                if occupied:
                    continue

                # Calculate danger score
                danger = self.get_position_hazard_score(test_pos, combatant_stats)
                safe_positions.append((test_pos, danger))

        # Sort by danger (safest first)
        safe_positions.sort(key=lambda x: x[1])
        return safe_positions

    def should_avoid_current_position(
        self,
        position: Tuple[int, int],
        combatant_stats: Dict
    ) -> Tuple[bool, str]:
        """
        Check if combatant should move away from current position.

        Args:
            position: Current position
            combatant_stats: Combatant's stats

        Returns:
            Tuple of (should_move, reason)
        """
        danger = self.get_position_hazard_score(position, combatant_stats)

        if danger >= 50:
            return True, "Standing in harmful surface"
        elif danger >= 25:
            return True, "Standing in dangerous terrain"

        return False, ""

    def find_throwable_objects(
        self,
        position: Tuple[int, int],
        search_radius: int = 2
    ) -> List[Dict]:
        """
        Find throwable objects near a position.

        Args:
            position: Position to search from
            search_radius: Radius in cells to search

        Returns:
            List of throwable objects with position and type
        """
        # This would integrate with the throwing system
        # For now, return empty - objects would need to be tracked in combat state
        throwables = []

        # Check combat state for objects
        objects = getattr(self.engine.state, 'objects', {})
        for obj_id, obj_data in objects.items():
            obj_pos = obj_data.get("position")
            if not obj_pos:
                continue

            if isinstance(obj_pos, dict):
                obj_pos = (obj_pos.get("x", 0), obj_pos.get("y", 0))

            dx = abs(position[0] - obj_pos[0])
            dy = abs(position[1] - obj_pos[1])

            if dx <= search_radius and dy <= search_radius:
                if obj_data.get("throwable", False):
                    throwables.append({
                        "id": obj_id,
                        "position": obj_pos,
                        "type": obj_data.get("type", "object"),
                        "weight": obj_data.get("weight", 10),
                        "is_explosive": obj_data.get("explosive", False),
                    })

        return throwables


def get_environmental_analyzer(engine: "CombatEngine") -> EnvironmentalAnalyzer:
    """Get an environmental analyzer for the combat engine."""
    return EnvironmentalAnalyzer(engine)
