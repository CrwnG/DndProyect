"""
D&D 5e AI Role-Based Behaviors.

Implements specific AI behaviors for different combat roles:
- MeleeBruteAI: Aggressive melee fighters
- RangedStrikerAI: Distance-keeping ranged attackers
- SpellcasterAI: Tactical spell usage
- SupportAI: Healing and buffing allies
- ControllerAI: Crowd control and zone denial
- SkirmisherAI: Hit-and-run tactics
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from enum import Enum

import re

from .targeting import TargetEvaluator, TargetPriority
from app.core.movement import find_path

if TYPE_CHECKING:
    from app.core.combat_engine import CombatEngine


def _parse_spellcasting_trait(description: str) -> Dict:
    """
    Parse spellcasting information from a monster trait description.

    Extracts spell save DC, spell attack bonus, and known spells
    from text like:
    "The acolyte is a 1st-level spellcaster. Its spellcasting ability is Wisdom
    (spell save DC 12, +4 to hit with spell attacks). The acolyte has the following
    cleric spells prepared: Cantrips: Light, Sacred Flame, Thaumaturgy.
    1st Level (3 slots): Bless, Cure Wounds, Sanctuary."

    Returns:
        Dict with spell_save_dc, spell_attack_bonus, spell_slots, known_spells
    """
    result = {
        "spell_save_dc": 10,
        "spell_attack_bonus": 0,
        "spell_slots": {},
        "known_spells": [],
        "cantrips": [],
    }

    # Extract spell save DC
    dc_match = re.search(r'spell save DC (\d+)', description, re.IGNORECASE)
    if dc_match:
        result["spell_save_dc"] = int(dc_match.group(1))

    # Extract spell attack bonus
    attack_match = re.search(r'\+(\d+) to hit with spell attacks', description, re.IGNORECASE)
    if attack_match:
        result["spell_attack_bonus"] = int(attack_match.group(1))

    # Extract cantrips
    cantrip_match = re.search(r'Cantrips[^:]*:\s*([^.]+)', description, re.IGNORECASE)
    if cantrip_match:
        cantrip_str = cantrip_match.group(1).strip()
        cantrips = [s.strip().lower().replace(" ", "_") for s in cantrip_str.split(",")]
        result["cantrips"] = [c for c in cantrips if c]

    # Extract spell slots and spells by level
    # Pattern: "1st Level (3 slots): Bless, Cure Wounds, Sanctuary"
    level_pattern = r'(\d+)(?:st|nd|rd|th)\s+Level\s*\((\d+)\s*slots?\)\s*:\s*([^.]+)'
    for match in re.finditer(level_pattern, description, re.IGNORECASE):
        level = int(match.group(1))
        slots = int(match.group(2))
        spell_str = match.group(3).strip()

        result["spell_slots"][str(level)] = slots

        # Parse spells at this level
        spells = [s.strip().lower().replace(" ", "_") for s in spell_str.split(",")]
        result["known_spells"].extend([(spell, level) for spell in spells if spell])

    return result


class AIRole(Enum):
    """Combat roles that determine AI behavior."""
    MELEE_BRUTE = "melee_brute"
    RANGED_STRIKER = "ranged_striker"
    SPELLCASTER = "spellcaster"
    SUPPORT = "support"
    CONTROLLER = "controller"
    SKIRMISHER = "skirmisher"
    MINION = "minion"
    BOSS = "boss"


@dataclass
class AIDecision:
    """Result of AI decision-making."""
    action_type: str  # "attack", "spell", "dash", etc.
    target_id: Optional[str] = None
    position: Optional[Tuple[int, int]] = None
    ability_id: Optional[str] = None
    spell_id: Optional[str] = None
    spell_level: Optional[int] = None
    weapon_id: Optional[str] = None
    score: float = 0.0
    reasoning: str = ""
    is_bonus_action: bool = False
    movement_path: Optional[List[Tuple[int, int]]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "action_type": self.action_type,
            "target_id": self.target_id,
            "position": self.position,
            "ability_id": self.ability_id,
            "spell_id": self.spell_id,
            "spell_level": self.spell_level,
            "weapon_id": self.weapon_id,
            "score": self.score,
            "reasoning": self.reasoning,
            "is_bonus_action": self.is_bonus_action,
        }


class BaseBehavior:
    """Base class for AI behaviors."""

    ROLE = AIRole.MELEE_BRUTE

    def __init__(self, engine: "CombatEngine", combatant_id: str):
        """
        Initialize behavior.

        Args:
            engine: The combat engine instance
            combatant_id: ID of the AI combatant
        """
        self.engine = engine
        self.combatant_id = combatant_id
        self.combatant = engine.state.initiative_tracker.get_combatant(combatant_id)
        self.stats = engine.state.combatant_stats.get(combatant_id, {})
        self.target_evaluator = TargetEvaluator(engine, combatant_id)

    def get_position(self) -> Optional[Tuple[int, int]]:
        """Get current position."""
        pos = self.engine.state.positions.get(self.combatant_id)
        if pos:
            if isinstance(pos, dict):
                return (pos.get("x", 0), pos.get("y", 0))
            return tuple(pos)
        return None

    def get_enemies(self) -> List[str]:
        """Get list of enemy combatant IDs."""
        enemies = []
        my_type = self.combatant.combatant_type if self.combatant else None

        for cid in self.engine.state.positions.keys():
            c = self.engine.state.initiative_tracker.get_combatant(cid)
            if c and c.is_active and c.combatant_type != my_type:
                enemies.append(cid)

        return enemies

    def get_allies(self) -> List[str]:
        """Get list of allied combatant IDs."""
        allies = []
        my_type = self.combatant.combatant_type if self.combatant else None

        for cid in self.engine.state.positions.keys():
            if cid == self.combatant_id:
                continue
            c = self.engine.state.initiative_tracker.get_combatant(cid)
            if c and c.is_active and c.combatant_type == my_type:
                allies.append(cid)

        return allies

    def get_distance_to(self, target_id: str) -> int:
        """Get distance to another combatant."""
        my_pos = self.get_position()
        target_pos = self.engine.state.positions.get(target_id)

        if not my_pos or not target_pos:
            return 999

        if isinstance(target_pos, dict):
            target_pos = (target_pos.get("x", 0), target_pos.get("y", 0))

        return abs(my_pos[0] - target_pos[0]) + abs(my_pos[1] - target_pos[1])

    def can_reach_melee(self, target_id: str) -> bool:
        """Check if target is in melee range."""
        return self.get_distance_to(target_id) <= 1

    def can_reach_with_movement(self, target_id: str, movement: int) -> bool:
        """Check if target is reachable with available movement."""
        # Distance - 1 because we need to be adjacent, not on top
        return self.get_distance_to(target_id) <= movement + 1

    def get_available_movement(self) -> int:
        """Get remaining movement for this turn."""
        speed = self.stats.get("speed", 30)
        turn_data = self.engine.state.current_turn
        if turn_data:
            used = getattr(turn_data, "movement_used", 0)
            return max(0, speed - used)
        return speed

    def get_hp_percent(self) -> float:
        """Get current HP as percentage."""
        current = self.stats.get("current_hp", 1)
        max_hp = self.stats.get("max_hp", 1)
        return current / max_hp if max_hp > 0 else 0.0

    def decide_action(self) -> AIDecision:
        """Main decision entry point. Override in subclasses."""
        raise NotImplementedError

    def decide_bonus_action(self) -> Optional[AIDecision]:
        """Decide bonus action. Override in subclasses that use bonus actions."""
        return None

    def decide_movement(self) -> Optional[AIDecision]:
        """Decide movement before action. Override in subclasses."""
        return None


class MeleeBruteAI(BaseBehavior):
    """
    Aggressive melee combatant - charge and overwhelm.

    Priorities:
    1. Rush to nearest enemy
    2. Attack whoever is in range
    3. Use Rage/Power Attack if available
    4. Never retreat unless critically wounded
    """

    ROLE = AIRole.MELEE_BRUTE

    def decide_action(self) -> AIDecision:
        """Decide the best action for a melee brute."""
        enemies = self.get_enemies()
        if not enemies:
            return AIDecision(
                action_type="dodge",
                reasoning="No enemies visible, taking defensive stance"
            )

        # Find targets in melee range
        melee_targets = [e for e in enemies if self.can_reach_melee(e)]

        if melee_targets:
            # Environmental awareness - check for push opportunities first
            push_opportunity = self._check_push_opportunity(melee_targets)
            if push_opportunity:
                return push_opportunity

            # Evaluate targets for attack
            best = self.target_evaluator.get_best_target(
                melee_targets,
                TargetPriority.LOWEST_HP  # Brutes finish off wounded
            )

            if best:
                return AIDecision(
                    action_type="attack",
                    target_id=best.target_id,
                    score=best.total_score,
                    reasoning=f"Attacking {best.target_name}: {', '.join(best.reasons[:2])}"
                )

        # No one in melee range - check if we can reach someone
        movement = self.get_available_movement()
        reachable = [e for e in enemies if self.can_reach_with_movement(e, movement)]

        if reachable:
            best = self.target_evaluator.get_best_target(
                reachable,
                TargetPriority.NEAREST
            )

            if best:
                return AIDecision(
                    action_type="attack",
                    target_id=best.target_id,
                    score=best.total_score,
                    reasoning=f"Moving to attack {best.target_name}"
                )

        # Can't reach anyone - dash to get closer
        best = self.target_evaluator.get_best_target(
            enemies,
            TargetPriority.HIGHEST_THREAT
        )

        if best:
            return AIDecision(
                action_type="dash",
                target_id=best.target_id,
                reasoning=f"Dashing toward {best.target_name}"
            )

        # Fallback
        return AIDecision(
            action_type="dash",
            reasoning="Closing distance with enemies"
        )

    def decide_bonus_action(self) -> Optional[AIDecision]:
        """Check for Rage or other bonus action abilities."""
        # Check for Rage
        if self.stats.get("class", "").lower() == "barbarian":
            if not self.stats.get("is_raging") and self.stats.get("rage_uses_remaining", 0) > 0:
                return AIDecision(
                    action_type="rage",
                    is_bonus_action=True,
                    reasoning="Entering rage for damage bonus",
                    score=80.0
                )

        return None

    def _check_push_opportunity(self, melee_targets: List[str]) -> Optional[AIDecision]:
        """
        Check for opportunities to push enemies into hazards.

        Returns a shove action if a valuable push opportunity exists.
        """
        try:
            from .environmental import get_environmental_analyzer
            env_analyzer = get_environmental_analyzer(self.engine)

            my_pos = self.get_position()
            if not my_pos:
                return None

            # Find push opportunities for adjacent enemies
            push_opportunities = env_analyzer.find_push_opportunities(
                self.combatant_id,
                my_pos,
                melee_targets
            )

            if push_opportunities:
                best_push = push_opportunities[0]  # Already sorted by value

                # Only shove if it's clearly better than just attacking
                # Pits/ledges worth 20+ damage are always worth it
                if best_push.hazard.damage_potential >= 15:
                    return AIDecision(
                        action_type="shove",
                        target_id=best_push.target_id,
                        ability_id="shove_push",
                        score=best_push.score_bonus,
                        reasoning=best_push.reasoning
                    )

                # For lower damage hazards, consider target HP
                target_stats = self.engine.state.combatant_stats.get(best_push.target_id, {})
                target_hp = target_stats.get("current_hp", 100)

                # If push damage would kill/significantly hurt target, do it
                if best_push.hazard.damage_potential >= target_hp * 0.5:
                    return AIDecision(
                        action_type="shove",
                        target_id=best_push.target_id,
                        ability_id="shove_push",
                        score=best_push.score_bonus + 20,  # Bonus for near-kill
                        reasoning=best_push.reasoning
                    )

        except (ImportError, Exception):
            # Environmental analysis not available
            pass

        return None


class RangedStrikerAI(BaseBehavior):
    """
    Ranged attacker - maintain distance, pick off priority targets.

    Priorities:
    1. Stay at optimal range (30-60ft)
    2. Target wounded or high-priority enemies
    3. Disengage if enemies get close
    4. Use cover when available
    """

    ROLE = AIRole.RANGED_STRIKER

    OPTIMAL_MIN_RANGE = 4  # 20ft minimum
    OPTIMAL_MAX_RANGE = 12  # 60ft maximum

    def decide_action(self) -> AIDecision:
        """Decide the best action for a ranged striker."""
        enemies = self.get_enemies()
        if not enemies:
            return AIDecision(
                action_type="dodge",
                reasoning="No enemies visible"
            )

        # Check if any enemies are too close
        adjacent_enemies = [e for e in enemies if self.get_distance_to(e) <= 1]

        if adjacent_enemies:
            # Disengage and move away
            return AIDecision(
                action_type="disengage",
                reasoning="Disengaging from melee threats"
            )

        # Find targets in optimal range
        in_range = [
            e for e in enemies
            if self.OPTIMAL_MIN_RANGE <= self.get_distance_to(e) <= self.OPTIMAL_MAX_RANGE
        ]

        if in_range:
            # Prioritize wounded targets for ranged
            best = self.target_evaluator.get_best_target(
                in_range,
                TargetPriority.LOWEST_HP
            )

            if best:
                return AIDecision(
                    action_type="ranged_attack",
                    target_id=best.target_id,
                    score=best.total_score,
                    reasoning=f"Ranged attack on {best.target_name}: {', '.join(best.reasons[:2])}"
                )

        # Targets too far - move closer but maintain distance
        # Or targets too close - already handled by disengage

        # Attack nearest valid target
        best = self.target_evaluator.get_best_target(
            enemies,
            TargetPriority.NEAREST
        )

        if best:
            return AIDecision(
                action_type="ranged_attack",
                target_id=best.target_id,
                score=best.total_score,
                reasoning=f"Ranged attack on {best.target_name}"
            )

        return AIDecision(
            action_type="dodge",
            reasoning="No valid targets for ranged attack"
        )

    def decide_movement(self) -> Optional[AIDecision]:
        """Decide optimal positioning."""
        enemies = self.get_enemies()
        if not enemies:
            return None

        my_pos = self.get_position()
        if not my_pos:
            return None

        # Find nearest enemy
        nearest_dist = min(self.get_distance_to(e) for e in enemies)

        # Too close - move away
        if nearest_dist < self.OPTIMAL_MIN_RANGE:
            # Find best retreat position
            best_pos = self._find_retreat_position(enemies)
            if best_pos:
                # Calculate actual path to retreat position
                movement_path = None
                if hasattr(self.engine.state, "grid") and self.engine.state.grid:
                    # Get ally IDs for pathfinding (can move through allies)
                    ally_ids = set(self.get_allies())
                    path_result = find_path(
                        self.engine.state.grid,
                        my_pos[0], my_pos[1],
                        best_pos[0], best_pos[1],
                        max_movement=self.get_available_movement() * 5,  # Convert squares to feet
                        mover_id=self.combatant_id,
                        ally_ids=ally_ids
                    )
                    if path_result.success:
                        movement_path = path_result.path
                    else:
                        # Path blocked, try to find partial path
                        # Just use the position without a calculated path
                        pass

                return AIDecision(
                    action_type="move",
                    position=best_pos,
                    movement_path=movement_path,
                    reasoning="Retreating to optimal range"
                )

        return None

    def _find_retreat_position(
        self,
        enemies: List[str],
    ) -> Optional[Tuple[int, int]]:
        """Find best position to retreat to."""
        my_pos = self.get_position()
        if not my_pos:
            return None

        movement = self.get_available_movement()
        best_pos = None
        best_score = -999

        # Check positions within movement range
        for dx in range(-movement, movement + 1):
            for dy in range(-movement, movement + 1):
                if abs(dx) + abs(dy) > movement:
                    continue

                test_pos = (my_pos[0] + dx, my_pos[1] + dy)

                # Check if position is valid
                if not self._is_valid_position(test_pos):
                    continue

                # Score position based on enemy distances
                min_enemy_dist = 999
                for eid in enemies:
                    epos = self.engine.state.positions.get(eid)
                    if epos:
                        if isinstance(epos, dict):
                            epos = (epos.get("x", 0), epos.get("y", 0))
                        dist = abs(test_pos[0] - epos[0]) + abs(test_pos[1] - epos[1])
                        min_enemy_dist = min(min_enemy_dist, dist)

                # Prefer positions at optimal range
                if self.OPTIMAL_MIN_RANGE <= min_enemy_dist <= self.OPTIMAL_MAX_RANGE:
                    score = 100
                elif min_enemy_dist > self.OPTIMAL_MAX_RANGE:
                    score = 50 - (min_enemy_dist - self.OPTIMAL_MAX_RANGE)
                else:
                    score = min_enemy_dist * 10

                if score > best_score:
                    best_score = score
                    best_pos = test_pos

        return best_pos

    def _is_valid_position(self, pos: Tuple[int, int]) -> bool:
        """Check if position is valid for movement."""
        # Check grid bounds
        if hasattr(self.engine.state, "grid") and self.engine.state.grid:
            grid = self.engine.state.grid
            if pos[0] < 0 or pos[0] >= grid.width:
                return False
            if pos[1] < 0 or pos[1] >= grid.height:
                return False

            # Check for obstacles
            cell = grid.get_cell(pos[0], pos[1])
            if cell and not cell.is_passable:
                return False

        # Check for other combatants
        for cid, cpos in self.engine.state.positions.items():
            if cid == self.combatant_id:
                continue
            if isinstance(cpos, dict):
                cpos = (cpos.get("x", 0), cpos.get("y", 0))
            if cpos[0] == pos[0] and cpos[1] == pos[1]:
                return False

        # Environmental awareness - avoid harmful surfaces
        surface_manager = getattr(self.engine.state, 'surface_manager', None)
        if surface_manager:
            surfaces = surface_manager.get_surfaces_at(pos[0], pos[1])
            harmful_surfaces = {"fire", "acid", "poison", "electrified_water"}
            for surface in surfaces:
                surface_type = surface.surface_type.value if hasattr(surface.surface_type, 'value') else str(surface.surface_type)
                if surface_type in harmful_surfaces:
                    # Check for resistance/immunity before rejecting
                    resistances = self.stats.get("resistances", [])
                    immunities = self.stats.get("immunities", [])
                    damage_type_map = {"fire": "fire", "acid": "acid", "poison": "poison", "electrified_water": "lightning"}
                    damage_type = damage_type_map.get(surface_type, "")
                    if damage_type not in immunities and damage_type not in resistances:
                        return False  # Avoid harmful surface

        # Check for pits
        try:
            from app.core.falling import check_pit_fall
            if hasattr(self.engine.state, "grid") and self.engine.state.grid:
                is_pit, depth = check_pit_fall(self.engine.state.grid, pos[0], pos[1])
                if is_pit and depth >= 10:
                    return False  # Avoid pits
        except (ImportError, AttributeError):
            pass

        return True


class SpellcasterAI(BaseBehavior):
    """
    Tactical spellcaster - prioritize impactful spells.

    Priorities:
    1. AoE when 3+ targets clustered
    2. Control spells on high-threat targets
    3. Buffs on allies early in combat
    4. Single-target damage spells
    5. Cantrips as fallback
    """

    ROLE = AIRole.SPELLCASTER

    # Default fallback spells when dynamic selection fails
    DEFAULT_AOE_SPELL = "fireball"
    DEFAULT_CONTROL_SPELL = "hold_person"
    DEFAULT_DAMAGE_SPELL = "magic_missile"
    DEFAULT_CANTRIP = "fire_bolt"

    # Spell categories for classification
    AOE_KEYWORDS = ["cone", "sphere", "cube", "line", "radius", "area", "each creature"]
    CONTROL_KEYWORDS = ["paralyzed", "stunned", "restrained", "incapacitated", "charmed", "frightened", "prone"]
    DAMAGE_KEYWORDS = ["damage", "hit points"]

    def __init__(self, engine: "CombatEngine", combatant_id: str):
        super().__init__(engine, combatant_id)

        # Try structured spellcasting data first
        self.spellcasting = self.stats.get("spellcasting", {})
        self.spell_slots = self.spellcasting.get("spell_slots", {})
        self.spell_slots_used = self.spellcasting.get("spell_slots_used", {})

        # Parse spellcasting from traits if not structured
        self.known_spells: List[Tuple[str, int]] = []  # [(spell_id, level), ...]
        self.cantrips: List[str] = []
        self._parse_spellcasting_from_traits()

        # Cache spell info from registry
        self._spell_cache: Dict[str, Dict] = {}
        self._categorized_spells: Dict[str, List[str]] = {
            "aoe": [],
            "control": [],
            "damage": [],
            "healing": [],
            "buff": [],
        }
        self._categorize_known_spells()

    def _parse_spellcasting_from_traits(self) -> None:
        """Parse spellcasting information from monster traits if needed."""
        # Check if we already have structured known_spells
        if self.spellcasting.get("known_spells"):
            spells = self.spellcasting["known_spells"]
            for spell in spells:
                if isinstance(spell, tuple):
                    self.known_spells.append(spell)
                elif isinstance(spell, str):
                    self.known_spells.append((spell, 1))  # Default to level 1
            return

        # Parse from traits
        traits = self.stats.get("traits", [])
        for trait in traits:
            if isinstance(trait, dict) and "spellcasting" in trait.get("name", "").lower():
                description = trait.get("description", "")
                parsed = _parse_spellcasting_trait(description)

                # Update spell slots if we don't have them
                if not self.spell_slots and parsed["spell_slots"]:
                    self.spell_slots = parsed["spell_slots"]

                # Add parsed spells
                self.known_spells.extend(parsed["known_spells"])
                self.cantrips.extend(parsed["cantrips"])
                break

    def _categorize_known_spells(self) -> None:
        """Categorize known spells by type using spell registry."""
        try:
            from app.core.spell_system import SpellRegistry
            registry = SpellRegistry.get_instance()

            all_spell_ids = [s[0] for s in self.known_spells] + self.cantrips

            for spell_id in all_spell_ids:
                spell = registry.get_spell(spell_id)
                if not spell:
                    continue

                # Cache spell info
                self._spell_cache[spell_id] = {
                    "id": spell_id,
                    "level": spell.level,
                    "effect_type": spell.effect_type,
                    "target_type": spell.target_type,
                    "damage_dice": spell.damage_dice,
                    "save_type": spell.save_type,
                    "description": spell.description,
                }

                # Categorize by effect_type if available
                if spell.effect_type:
                    effect = str(spell.effect_type).lower()
                    if "damage" in effect:
                        self._categorized_spells["damage"].append(spell_id)
                    elif "control" in effect or "debuff" in effect:
                        self._categorized_spells["control"].append(spell_id)
                    elif "healing" in effect:
                        self._categorized_spells["healing"].append(spell_id)
                    elif "buff" in effect:
                        self._categorized_spells["buff"].append(spell_id)

                # Check for AoE by target_type
                if spell.target_type:
                    target = str(spell.target_type).lower()
                    if any(aoe in target for aoe in ["sphere", "cone", "line", "cube", "cylinder"]):
                        self._categorized_spells["aoe"].append(spell_id)

                # Fallback: categorize by description keywords
                if spell_id not in self._categorized_spells["aoe"]:
                    desc = spell.description.lower()
                    if any(kw in desc for kw in self.AOE_KEYWORDS):
                        self._categorized_spells["aoe"].append(spell_id)
                    elif any(kw in desc for kw in self.CONTROL_KEYWORDS):
                        if spell_id not in self._categorized_spells["control"]:
                            self._categorized_spells["control"].append(spell_id)
                    elif any(kw in desc for kw in self.DAMAGE_KEYWORDS):
                        if spell_id not in self._categorized_spells["damage"]:
                            self._categorized_spells["damage"].append(spell_id)
        except (ImportError, Exception):
            # Registry not available, use defaults
            pass

    def _get_best_spell_of_type(self, spell_type: str, max_level: int = 9) -> Optional[str]:
        """Get the best available spell of a given type."""
        spells = self._categorized_spells.get(spell_type, [])
        if not spells:
            return None

        # Filter by available spell level
        available = []
        for spell_id in spells:
            spell_info = self._spell_cache.get(spell_id, {})
            spell_level = spell_info.get("level", 1)
            if spell_level == 0:  # Cantrip
                available.append((spell_id, 0))
            elif spell_level <= max_level and self.has_spell_slots(min_level=spell_level):
                available.append((spell_id, spell_level))

        if not available:
            return None

        # Prefer higher level spells for more impact
        available.sort(key=lambda x: x[1], reverse=True)
        return available[0][0]

    def _get_damage_cantrip(self) -> str:
        """Get an available damage cantrip."""
        # Check parsed cantrips for damage ones
        damage_cantrips = ["fire_bolt", "eldritch_blast", "sacred_flame", "toll_the_dead",
                          "chill_touch", "ray_of_frost", "shocking_grasp", "produce_flame"]
        for cantrip in self.cantrips:
            if cantrip in damage_cantrips:
                return cantrip
            # Check if it's in our damage category
            if cantrip in self._categorized_spells.get("damage", []):
                return cantrip

        # Return first cantrip or default
        if self.cantrips:
            return self.cantrips[0]
        return self.DEFAULT_CANTRIP

    def has_spell_slots(self, min_level: int = 1) -> bool:
        """Check if any spell slots of min level or higher are available."""
        for level, total in self.spell_slots.items():
            if int(level) >= min_level:
                used = self.spell_slots_used.get(level, 0)
                if total - used > 0:
                    return True
        return False

    def get_highest_slot_level(self) -> int:
        """Get highest available spell slot level."""
        highest = 0
        for level, total in self.spell_slots.items():
            level_int = int(level)
            used = self.spell_slots_used.get(level, 0)
            if total - used > 0 and level_int > highest:
                highest = level_int
        return highest

    def decide_action(self) -> AIDecision:
        """Decide the best spell or action."""
        enemies = self.get_enemies()
        allies = self.get_allies()
        max_slot = self.get_highest_slot_level()

        # Environmental awareness - check for elemental combo opportunities
        combo_action = self._check_elemental_combos(enemies)
        if combo_action:
            return combo_action

        # Check for AoE opportunity
        if self.has_spell_slots(min_level=1) and len(enemies) >= 3:
            aoe_result = self.target_evaluator.get_targets_for_aoe(
                self.get_position() or (0, 0),
                radius=4,  # 20ft radius
                enemy_ids=enemies,
                min_targets=3
            )

            if aoe_result:
                # Try to find an actual AoE spell
                aoe_spell = self._get_best_spell_of_type("aoe", max_slot)
                spell_id = aoe_spell or self.DEFAULT_AOE_SPELL

                return AIDecision(
                    action_type="spell",
                    spell_id=spell_id,
                    position=aoe_result["position"],
                    spell_level=max_slot,
                    score=90.0,
                    reasoning=f"AoE spell ({spell_id}) hitting {aoe_result['count']} targets"
                )

        # Check for control spell on high-threat target
        if self.has_spell_slots(min_level=1):
            threat_targets = self.target_evaluator.evaluate_all_targets(
                enemies,
                TargetPriority.HIGHEST_THREAT
            )

            if threat_targets and threat_targets[0].total_score >= 60:
                target = threat_targets[0]
                # Check for weak save
                weak_save_targets = self.target_evaluator.get_weak_save_targets(
                    [target.target_id],
                    "wisdom"  # Common control spell save
                )

                if weak_save_targets:
                    # Try to find an actual control spell
                    control_spell = self._get_best_spell_of_type("control", max_slot)
                    spell_id = control_spell or self.DEFAULT_CONTROL_SPELL

                    return AIDecision(
                        action_type="spell",
                        spell_id=spell_id,
                        target_id=target.target_id,
                        spell_level=max_slot,
                        score=85.0,
                        reasoning=f"Control spell ({spell_id}) on high-threat {target.target_name}"
                    )

        # Single target damage if enemies present
        if enemies and self.has_spell_slots(min_level=1):
            best = self.target_evaluator.get_best_target(
                enemies,
                TargetPriority.LOWEST_HP
            )

            if best:
                # Try to find an actual damage spell
                damage_spell = self._get_best_spell_of_type("damage", max_slot)
                spell_id = damage_spell or self.DEFAULT_DAMAGE_SPELL

                return AIDecision(
                    action_type="spell",
                    spell_id=spell_id,
                    target_id=best.target_id,
                    spell_level=max_slot,
                    score=70.0,
                    reasoning=f"Damage spell ({spell_id}) on {best.target_name}"
                )

        # Fallback to cantrip
        if enemies:
            best = self.target_evaluator.get_best_target(
                enemies,
                TargetPriority.NEAREST
            )

            if best:
                cantrip = self._get_damage_cantrip()
                return AIDecision(
                    action_type="cantrip",
                    spell_id=cantrip,
                    target_id=best.target_id,
                    score=50.0,
                    reasoning=f"Cantrip ({cantrip}) on {best.target_name}"
                )

        # No valid targets - dodge
        return AIDecision(
            action_type="dodge",
            reasoning="No valid spell targets"
        )

    def _check_elemental_combos(self, enemies: List[str]) -> Optional[AIDecision]:
        """
        Check for elemental combination opportunities.

        Looks for enemies standing in water (lightning combo),
        near grease/oil (fire combo), etc.

        Returns:
            AIDecision if a good combo is found, None otherwise
        """
        try:
            from .environmental import get_environmental_analyzer
            env_analyzer = get_environmental_analyzer(self.engine)

            # Get enemy positions
            enemy_positions = {}
            for eid in enemies:
                pos = self.engine.state.positions.get(eid)
                if pos:
                    if isinstance(pos, dict):
                        pos = (pos.get("x", 0), pos.get("y", 0))
                    enemy_positions[eid] = pos

            if not enemy_positions:
                return None

            # Get available spells
            available_spells = [s[0] for s in self.known_spells] + self.cantrips

            # Find combos
            combos = env_analyzer.find_elemental_combos(
                self.get_position() or (0, 0),
                enemy_positions,
                available_spells
            )

            if combos:
                best_combo = combos[0]  # Already sorted by value

                # Very high priority for elemental combos
                if len(best_combo.affected_enemy_ids) >= 2:
                    return AIDecision(
                        action_type="spell",
                        spell_id=best_combo.spell_id,
                        position=best_combo.target_position,
                        score=100.0 + best_combo.bonus_damage,
                        reasoning=best_combo.reasoning
                    )
                elif len(best_combo.affected_enemy_ids) == 1:
                    # Still good for single target
                    target_id = best_combo.affected_enemy_ids[0]
                    return AIDecision(
                        action_type="spell",
                        spell_id=best_combo.spell_id,
                        target_id=target_id,
                        score=80.0 + best_combo.bonus_damage,
                        reasoning=best_combo.reasoning
                    )

        except (ImportError, Exception):
            # Environmental analysis not available or failed
            pass

        return None


class SupportAI(BaseBehavior):
    """
    Support/healer - prioritize keeping allies alive.

    Priorities:
    1. Heal critically wounded allies (<25% HP)
    2. Remove dangerous conditions
    3. Buff allies at fight start
    4. Damage enemies if allies are healthy
    """

    ROLE = AIRole.SUPPORT

    def decide_action(self) -> AIDecision:
        """Decide the best supportive action."""
        allies = self.get_allies()
        enemies = self.get_enemies()

        # Check for critically wounded allies
        critical_allies = []
        for ally_id in allies:
            ally_stats = self.engine.state.combatant_stats.get(ally_id, {})
            current = ally_stats.get("current_hp", 1)
            max_hp = ally_stats.get("max_hp", 1)
            if current / max_hp < 0.25:
                critical_allies.append((ally_id, current / max_hp))

        if critical_allies:
            # Sort by lowest HP%
            critical_allies.sort(key=lambda x: x[1])
            target_id = critical_allies[0][0]
            target = self.engine.state.initiative_tracker.get_combatant(target_id)

            return AIDecision(
                action_type="spell",
                spell_id="cure_wounds",
                target_id=target_id,
                spell_level=1,
                score=95.0,
                reasoning=f"Emergency healing for {target.name if target else 'ally'}"
            )

        # Check for wounded allies (<50%)
        wounded_allies = []
        for ally_id in allies:
            ally_stats = self.engine.state.combatant_stats.get(ally_id, {})
            current = ally_stats.get("current_hp", 1)
            max_hp = ally_stats.get("max_hp", 1)
            hp_pct = current / max_hp
            if 0.25 <= hp_pct < 0.5:
                wounded_allies.append((ally_id, hp_pct))

        if wounded_allies:
            wounded_allies.sort(key=lambda x: x[1])
            target_id = wounded_allies[0][0]
            target = self.engine.state.initiative_tracker.get_combatant(target_id)

            return AIDecision(
                action_type="spell",
                spell_id="healing_word",
                target_id=target_id,
                spell_level=1,
                score=80.0,
                is_bonus_action=True,
                reasoning=f"Healing {target.name if target else 'wounded ally'}"
            )

        # Allies are healthy - attack enemies
        if enemies:
            best = self.target_evaluator.get_best_target(
                enemies,
                TargetPriority.SPELLCASTER
            )

            if best:
                return AIDecision(
                    action_type="spell",
                    spell_id="sacred_flame",  # Cantrip
                    target_id=best.target_id,
                    score=50.0,
                    reasoning=f"Attacking {best.target_name} (allies healthy)"
                )

        return AIDecision(
            action_type="dodge",
            reasoning="No valid targets"
        )


class ControllerAI(BaseBehavior):
    """
    Controller - crowd control and zone denial.

    Priorities:
    1. Lock down multiple enemies with AoE control
    2. Disable high-threat single targets
    3. Create difficult terrain/zones
    4. Fall back to damage if control isn't useful
    """

    ROLE = AIRole.CONTROLLER

    def decide_action(self) -> AIDecision:
        """Decide best control action."""
        enemies = self.get_enemies()

        if not enemies:
            return AIDecision(action_type="dodge", reasoning="No enemies")

        # Check for clustered enemies for AoE control
        if len(enemies) >= 2:
            aoe_result = self.target_evaluator.get_targets_for_aoe(
                self.get_position() or (0, 0),
                radius=3,  # 15ft radius
                enemy_ids=enemies,
                min_targets=2
            )

            if aoe_result:
                return AIDecision(
                    action_type="spell",
                    spell_id="web",  # AoE control
                    position=aoe_result["position"],
                    score=85.0,
                    reasoning=f"AoE control on {aoe_result['count']} enemies"
                )

        # Single-target control on most dangerous enemy
        threat_targets = self.target_evaluator.evaluate_all_targets(
            enemies,
            TargetPriority.HIGHEST_THREAT
        )

        if threat_targets:
            target = threat_targets[0]
            # Find best save to target
            weak_targets = self.target_evaluator.get_weak_save_targets(
                [target.target_id],
                "wisdom"
            )

            return AIDecision(
                action_type="spell",
                spell_id="command",  # Single-target control
                target_id=target.target_id,
                score=70.0,
                reasoning=f"Control spell on {target.target_name}"
            )

        # Fallback to damage cantrip
        return AIDecision(
            action_type="cantrip",
            spell_id="ray_of_frost",
            target_id=enemies[0],
            score=40.0,
            reasoning="Cantrip damage"
        )


class SkirmisherAI(BaseBehavior):
    """
    Skirmisher - hit and run tactics.

    Priorities:
    1. Strike vulnerable targets
    2. Disengage after attacking
    3. Never stay in melee if possible
    4. Use Cunning Action for mobility
    """

    ROLE = AIRole.SKIRMISHER

    def decide_action(self) -> AIDecision:
        """Decide best hit-and-run action."""
        enemies = self.get_enemies()

        if not enemies:
            return AIDecision(action_type="hide", reasoning="No enemies, hiding")

        # Check for flanking opportunities (enemy with ally adjacent)
        flank_targets = self._find_flank_targets(enemies)

        if flank_targets:
            best = flank_targets[0]
            return AIDecision(
                action_type="attack",
                target_id=best["target_id"],
                score=90.0,
                reasoning=f"Flanking attack on {best['target_name']} (Sneak Attack!)"
            )

        # Find wounded target
        best = self.target_evaluator.get_best_target(
            enemies,
            TargetPriority.LOWEST_HP
        )

        if best and self.can_reach_melee(best.target_id):
            return AIDecision(
                action_type="attack",
                target_id=best.target_id,
                score=best.total_score,
                reasoning=f"Strike on wounded {best.target_name}"
            )

        # Need to get in position
        if best:
            return AIDecision(
                action_type="attack",
                target_id=best.target_id,
                score=best.total_score,
                reasoning=f"Moving to attack {best.target_name}"
            )

        return AIDecision(
            action_type="hide",
            reasoning="Finding opportunity to strike"
        )

    def decide_bonus_action(self) -> Optional[AIDecision]:
        """Rogue Cunning Action - disengage or hide after attacking."""
        # Check if we just attacked and are adjacent to enemies
        enemies = self.get_enemies()
        adjacent = [e for e in enemies if self.can_reach_melee(e)]

        if adjacent:
            return AIDecision(
                action_type="cunning_action",
                ability_id="disengage",
                is_bonus_action=True,
                score=80.0,
                reasoning="Disengaging after strike"
            )

        # Otherwise try to hide
        return AIDecision(
            action_type="cunning_action",
            ability_id="hide",
            is_bonus_action=True,
            score=60.0,
            reasoning="Hiding for next ambush"
        )

    def _find_flank_targets(self, enemies: List[str]) -> List[Dict]:
        """Find enemies that can be flanked (ally adjacent)."""
        flank_targets = []
        allies = self.get_allies()

        for eid in enemies:
            epos = self.engine.state.positions.get(eid)
            if not epos:
                continue

            if isinstance(epos, dict):
                epos = (epos.get("x", 0), epos.get("y", 0))

            # Check if any ally is adjacent
            for ally_id in allies:
                apos = self.engine.state.positions.get(ally_id)
                if not apos:
                    continue

                if isinstance(apos, dict):
                    apos = (apos.get("x", 0), apos.get("y", 0))

                dist = abs(epos[0] - apos[0]) + abs(epos[1] - apos[1])
                if dist <= 1:
                    target = self.engine.state.initiative_tracker.get_combatant(eid)
                    flank_targets.append({
                        "target_id": eid,
                        "target_name": target.name if target else "enemy",
                        "ally_id": ally_id
                    })
                    break

        return flank_targets


class MinionAI(BaseBehavior):
    """
    Minion - simple, aggressive behavior.

    Just attacks nearest enemy, no complex tactics.
    Used for swarm-type creatures.
    """

    ROLE = AIRole.MINION

    def decide_action(self) -> AIDecision:
        """Simple attack nearest."""
        enemies = self.get_enemies()

        if not enemies:
            return AIDecision(action_type="dodge", reasoning="No enemies")

        # Find nearest
        nearest_id = None
        nearest_dist = 999

        for eid in enemies:
            dist = self.get_distance_to(eid)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_id = eid

        if nearest_id:
            if nearest_dist <= 1:
                return AIDecision(
                    action_type="attack",
                    target_id=nearest_id,
                    reasoning="Attacking nearest"
                )
            else:
                return AIDecision(
                    action_type="attack",  # Will move then attack
                    target_id=nearest_id,
                    reasoning="Moving to attack nearest"
                )

        return AIDecision(action_type="dash", reasoning="Searching for enemies")


class BossAI(BaseBehavior):
    """
    Boss - complex multi-action behavior.

    Uses legendary actions, targets threats,
    manages resources for long fights.
    """

    ROLE = AIRole.BOSS

    def decide_action(self) -> AIDecision:
        """Boss decision - balance offense and defense."""
        enemies = self.get_enemies()
        hp_percent = self.get_hp_percent()

        # Critical HP - defensive
        if hp_percent < 0.25:
            return AIDecision(
                action_type="multiattack",  # Use powerful ability
                reasoning="Critical HP - maximum damage output"
            )

        # Healthy - target priority threats
        if enemies:
            best = self.target_evaluator.get_best_target(
                enemies,
                TargetPriority.HEALER  # Bosses prioritize healers
            )

            if best:
                return AIDecision(
                    action_type="multiattack",
                    target_id=best.target_id,
                    score=best.total_score,
                    reasoning=f"Multiattack on {best.target_name}"
                )

        return AIDecision(
            action_type="multiattack",
            reasoning="Multiattack on any target"
        )


def get_behavior_for_role(
    role: AIRole,
    engine: "CombatEngine",
    combatant_id: str,
) -> BaseBehavior:
    """
    Factory function to get behavior class for a role.

    Args:
        role: The AI role
        engine: Combat engine instance
        combatant_id: ID of the combatant

    Returns:
        Appropriate behavior instance
    """
    role_to_class = {
        AIRole.MELEE_BRUTE: MeleeBruteAI,
        AIRole.RANGED_STRIKER: RangedStrikerAI,
        AIRole.SPELLCASTER: SpellcasterAI,
        AIRole.SUPPORT: SupportAI,
        AIRole.CONTROLLER: ControllerAI,
        AIRole.SKIRMISHER: SkirmisherAI,
        AIRole.MINION: MinionAI,
        AIRole.BOSS: BossAI,
    }

    behavior_class = role_to_class.get(role, MeleeBruteAI)
    return behavior_class(engine, combatant_id)
