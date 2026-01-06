"""
D&D 5e Tactical AI - Core Decision Framework.

Implements utility-based decision making for enemy combatants.
Each possible action is scored based on its expected value,
and the highest-scoring action is selected.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, TYPE_CHECKING
from enum import Enum
import random

if TYPE_CHECKING:
    from app.core.combat_engine import CombatEngine

from .targeting import TargetEvaluator, TargetPriority
from .environmental import EnvironmentalAnalyzer, get_environmental_analyzer


class ActionType(Enum):
    """Types of actions the AI can take."""
    ATTACK = "attack"
    RANGED_ATTACK = "ranged_attack"
    MOVE = "move"
    DASH = "dash"
    DISENGAGE = "disengage"
    DODGE = "dodge"
    HIDE = "hide"
    HELP = "help"
    SPELL = "spell"
    CANTRIP = "cantrip"
    ABILITY = "ability"
    MULTIATTACK = "multiattack"
    SHOVE = "shove"  # Added for environmental tactics
    NONE = "none"


@dataclass
class TacticalDecision:
    """Result of tactical AI decision-making process."""
    action_type: ActionType
    target_id: Optional[str] = None
    position: Optional[Tuple[int, int]] = None
    ability_id: Optional[str] = None
    spell_id: Optional[str] = None
    spell_level: Optional[int] = None
    weapon_id: Optional[str] = None
    score: float = 0.0
    reasoning: str = ""
    priority: int = 0  # Higher = more urgent
    is_bonus_action: bool = False
    movement_path: Optional[List[Tuple[int, int]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "action_type": self.action_type.value,
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


# Alias for backwards compatibility
AIDecision = TacticalDecision


class TacticalAI:
    """
    Advanced tactical AI for enemy combatants.

    Uses utility-based scoring to evaluate all possible actions
    and select the optimal one based on the current situation.
    """

    def __init__(self, engine: "CombatEngine", combatant_id: str):
        self.engine = engine
        self.combatant_id = combatant_id
        self._combatant = None
        self._stats = None
        self._ai_config = {}
        self._target_evaluator = TargetEvaluator(engine, combatant_id)
        self._env_analyzer = get_environmental_analyzer(engine)
        self._load_combatant_data()

    def _load_combatant_data(self):
        """Load combatant data from engine."""
        self._combatant = self.engine.state.initiative_tracker.get_combatant(self.combatant_id)
        self._stats = self.engine.state.combatant_stats.get(self.combatant_id, {})
        self._ai_config = self._stats.get("ai_behavior", {})

    @property
    def combatant(self):
        """Get the combatant object."""
        return self._combatant

    @property
    def stats(self) -> Dict[str, Any]:
        """Get combatant stats."""
        return self._stats

    @property
    def position(self) -> Tuple[int, int]:
        """Get current position."""
        pos = self.engine.state.positions.get(self.combatant_id, (0, 0))
        if isinstance(pos, (list, tuple)):
            return (pos[0], pos[1])
        return (pos.get("x", 0), pos.get("y", 0))

    def decide_action(self) -> AIDecision:
        """
        Main decision entry point.

        Evaluates the battlefield, generates candidate actions,
        scores them, and returns the best action.
        """
        # Refresh data
        self._load_combatant_data()

        # 1. Assess the battlefield
        situation = self._assess_battlefield()

        # 2. Check for critical conditions (flee, self-heal)
        critical = self._check_critical_conditions(situation)
        if critical:
            return critical

        # 3. Generate all possible actions
        candidates = self._generate_action_candidates(situation)

        if not candidates:
            return AIDecision(
                action_type=ActionType.NONE,
                reasoning="No valid actions available"
            )

        # 4. Score each candidate
        scored = []
        for candidate in candidates:
            score = self._score_action(candidate, situation)
            candidate.score = score
            scored.append(candidate)

        # 5. Select best action (with slight randomization for variety)
        scored.sort(key=lambda x: x.score, reverse=True)

        # Add small random factor to top choices to prevent predictability
        top_choices = [a for a in scored if a.score >= scored[0].score * 0.85]
        best_action = random.choice(top_choices) if len(top_choices) > 1 else scored[0]

        return best_action

    def decide_bonus_action(self) -> Optional[AIDecision]:
        """
        Decide on a bonus action if available.

        Returns None if no bonus action should be taken.
        """
        # Refresh data
        self._load_combatant_data()

        # Collect all possible bonus actions
        candidates = []

        # 1. Check explicit bonus action abilities
        abilities = self._stats.get("abilities", {})
        for name, data in abilities.items():
            if isinstance(data, dict) and data.get("action_type") == "bonus_action":
                candidates.append(self._create_bonus_action_candidate(name, data))

        # 2. Check for offhand attack (dual wielding)
        offhand = self._get_offhand_weapon()
        if offhand and self._has_attacked_this_turn():
            # Can make an offhand attack
            situation = self._assess_battlefield()
            for target in situation["can_reach"]:
                candidates.append(AIDecision(
                    action_type=ActionType.ATTACK,
                    target_id=target["id"],
                    weapon_id=offhand.get("id", "offhand"),
                    reasoning=f"Offhand attack on {target['name']}",
                    is_bonus_action=True,
                    score=0.0
                ))

        # 3. Check class-specific bonus actions
        char_class = self._stats.get("class", "").lower()

        # Rogue: Cunning Action
        if char_class == "rogue":
            candidates.extend(self._get_cunning_action_options())

        # Fighter: Second Wind (if hurt)
        if char_class == "fighter" and self._stats.get("current_hp", 0) < self._stats.get("max_hp", 1) * 0.5:
            resources = self._stats.get("class_resources", {})
            if resources.get("second_wind", 1) > 0:
                candidates.append(AIDecision(
                    action_type=ActionType.ABILITY,
                    ability_id="second_wind",
                    target_id=self.combatant_id,
                    reasoning="Using Second Wind to heal",
                    is_bonus_action=True,
                    score=0.0
                ))

        # Barbarian: Rage (if not already raging)
        if char_class == "barbarian":
            conditions = self._stats.get("conditions", [])
            resources = self._stats.get("class_resources", {})
            if "raging" not in conditions and resources.get("rages", 1) > 0:
                candidates.append(AIDecision(
                    action_type=ActionType.ABILITY,
                    ability_id="rage",
                    target_id=self.combatant_id,
                    reasoning="Entering rage",
                    is_bonus_action=True,
                    score=0.0
                ))

        # 4. Check for bonus action spells
        spellcasting = self._stats.get("spellcasting", {})
        if spellcasting:
            known_spells = spellcasting.get("known_spells", [])
            for spell_id in known_spells:
                if self._is_bonus_action_spell(spell_id):
                    candidates.extend(self._create_spell_candidates(spell_id, is_bonus=True))

        if not candidates:
            return None

        # Score each candidate and pick the best
        situation = self._assess_battlefield()
        for candidate in candidates:
            candidate.score = self._score_bonus_action(candidate, situation)

        candidates.sort(key=lambda x: x.score, reverse=True)

        # Only use bonus action if score is above threshold
        if candidates[0].score < 20:
            return None

        return candidates[0]

    def _create_bonus_action_candidate(self, name: str, data: Dict) -> AIDecision:
        """Create a decision candidate from an ability."""
        return AIDecision(
            action_type=ActionType.ABILITY,
            ability_id=name,
            target_id=data.get("target", self.combatant_id),
            reasoning=f"Using {name}",
            is_bonus_action=True,
            score=0.0
        )

    def _get_offhand_weapon(self) -> Optional[Dict]:
        """Get offhand weapon if dual wielding."""
        equipment = self._stats.get("equipment", {})
        offhand = equipment.get("offhand")
        if offhand and offhand.get("type") == "weapon":
            return offhand
        return None

    def _has_attacked_this_turn(self) -> bool:
        """Check if we've already made an attack this turn."""
        current_turn = self.engine.state.current_turn
        if current_turn and current_turn.combatant_id == self.combatant_id:
            return current_turn.action_used
        return False

    def _get_cunning_action_options(self) -> List[AIDecision]:
        """Get Rogue Cunning Action options (Dash, Disengage, Hide)."""
        options = []
        options.append(AIDecision(
            action_type=ActionType.DASH,
            reasoning="Cunning Action: Dash",
            is_bonus_action=True,
            score=0.0
        ))
        options.append(AIDecision(
            action_type=ActionType.DISENGAGE,
            reasoning="Cunning Action: Disengage",
            is_bonus_action=True,
            score=0.0
        ))
        options.append(AIDecision(
            action_type=ActionType.HIDE,
            reasoning="Cunning Action: Hide",
            is_bonus_action=True,
            score=0.0
        ))
        return options

    def _is_bonus_action_spell(self, spell_id: str) -> bool:
        """Check if a spell is cast as a bonus action."""
        bonus_action_spells = {
            "misty_step", "healing_word", "spiritual_weapon",
            "hex", "hunters_mark", "shield_of_faith",
            "sanctuary", "expeditious_retreat", "compelled_duel",
            "divine_favor", "searing_smite", "thunderous_smite",
            "wrathful_smite", "branding_smite", "magic_weapon"
        }
        return spell_id.lower().replace(" ", "_") in bonus_action_spells

    def _create_spell_candidates(self, spell_id: str, is_bonus: bool = False) -> List[AIDecision]:
        """Create spell casting candidates for a spell."""
        candidates = []
        situation = self._assess_battlefield()

        # Determine spell type and create appropriate targets
        offensive_keywords = ["smite", "hex", "mark", "weapon"]
        healing_keywords = ["healing", "word", "sanctuary"]

        spell_lower = spell_id.lower()

        if any(kw in spell_lower for kw in healing_keywords):
            # Self-target healing/buff
            candidates.append(AIDecision(
                action_type=ActionType.SPELL,
                spell_id=spell_id,
                target_id=self.combatant_id,
                reasoning=f"Casting {spell_id}",
                is_bonus_action=is_bonus,
                score=0.0
            ))
        else:
            # Offensive - target enemies
            for enemy in situation["enemies"][:3]:  # Top 3 enemies
                candidates.append(AIDecision(
                    action_type=ActionType.SPELL,
                    spell_id=spell_id,
                    target_id=enemy["id"],
                    reasoning=f"Casting {spell_id} on {enemy['name']}",
                    is_bonus_action=is_bonus,
                    score=0.0
                ))

        return candidates

    def _score_bonus_action(self, action: AIDecision, situation: Dict) -> float:
        """Score a bonus action."""
        score = 25.0  # Base score for using bonus action

        if action.action_type == ActionType.ATTACK:
            # Offhand attack
            target = next((t for t in situation["priority_targets"] if t["id"] == action.target_id), None)
            if target:
                score += target.get("priority_score", 0) * 0.5
                # Bonus for potential kill
                if target.get("hp", 100) <= self._estimate_damage() * 0.6:
                    score += 30

        elif action.action_type == ActionType.ABILITY:
            ability_id = action.ability_id or ""

            # Second Wind / healing
            if "heal" in ability_id.lower() or ability_id == "second_wind":
                hp_deficit = 1 - situation["my_hp_percent"]
                score += hp_deficit * 60

            # Rage
            elif ability_id == "rage":
                # Good if enemies nearby and not hurt badly
                if situation["can_reach"] and situation["my_hp_percent"] > 0.3:
                    score += 50

        elif action.action_type == ActionType.DASH:
            # Cunning Action Dash - good for repositioning
            if not situation["can_reach"]:
                score += 35

        elif action.action_type == ActionType.DISENGAGE:
            # Good when surrounded or hurt
            adjacent = len([e for e in situation["enemies"] if e.get("distance", 999) <= 5])
            if adjacent >= 1 and situation["my_hp_percent"] < 0.5:
                score += 40

        elif action.action_type == ActionType.HIDE:
            # Rogue - good for getting advantage
            score += 30

        elif action.action_type == ActionType.SPELL:
            # Bonus action spells
            spell_id = (action.spell_id or "").lower()
            if "hex" in spell_id or "mark" in spell_id:
                # Concentration spells for extra damage
                score += 45
            elif "healing" in spell_id:
                hp_deficit = 1 - situation["my_hp_percent"]
                score += hp_deficit * 50

        return score

    def _assess_battlefield(self) -> Dict[str, Any]:
        """
        Analyze the current combat situation.

        Returns a dictionary with key battlefield metrics.
        """
        my_hp = self._stats.get("current_hp", 0)
        my_max_hp = self._stats.get("max_hp", 1)
        hp_percent = my_hp / my_max_hp if my_max_hp > 0 else 0

        # Get allies and enemies
        allies = []
        enemies = []
        for c in self.engine.state.initiative_tracker.combatants:
            if not c.is_active:
                continue
            if c.id == self.combatant_id:
                continue

            c_stats = self.engine.state.combatant_stats.get(c.id, {})
            c_type = c_stats.get("type", "enemy")

            entry = {
                "id": c.id,
                "name": c.name,
                "hp": c_stats.get("current_hp", 0),
                "max_hp": c_stats.get("max_hp", 1),
                "ac": c_stats.get("ac", 10),
                "position": self.engine.state.positions.get(c.id, (0, 0)),
                "conditions": c_stats.get("conditions", []),
                "class": c_stats.get("class", ""),
            }

            if c_type == self._stats.get("type", "enemy"):
                allies.append(entry)
            else:
                enemies.append(entry)

        # Evaluate targets
        enemy_ids = [e["id"] for e in enemies]
        target_scores = self._target_evaluator.evaluate_all_targets(
            enemy_ids,
            TargetPriority.HIGHEST_THREAT
        )

        # Convert to dict format for backward compatibility
        priority_targets = []
        for score in target_scores:
            enemy_data = next((e for e in enemies if e["id"] == score.target_id), None)
            if enemy_data:
                priority_targets.append({
                    "id": score.target_id,
                    "name": score.target_name,
                    "priority_score": score.total_score,
                    "hp": enemy_data.get("hp", 1),
                    "max_hp": enemy_data.get("max_hp", 1),
                    "position": enemy_data.get("position"),
                    "reasons": score.reasons,
                })

        # Calculate reachable enemies
        can_reach = self._get_reachable_enemies(enemies)

        # Environmental awareness - check for push opportunities and hazards
        push_opportunities = []
        position_danger = 0.0
        should_move_from_hazard = False
        hazard_reason = ""

        try:
            # Check current position danger
            position_danger = self._env_analyzer.get_position_hazard_score(
                self.position, self._stats
            )
            should_move_from_hazard, hazard_reason = self._env_analyzer.should_avoid_current_position(
                self.position, self._stats
            )

            # Find push opportunities for adjacent enemies
            adjacent_enemy_ids = [e["id"] for e in can_reach if e.get("distance", 999) <= 5]
            if adjacent_enemy_ids:
                push_opportunities = self._env_analyzer.find_push_opportunities(
                    self.combatant_id,
                    self.position,
                    adjacent_enemy_ids
                )
        except Exception:
            # Environmental analysis failed, continue without it
            pass

        return {
            "my_hp_percent": hp_percent,
            "my_hp": my_hp,
            "my_max_hp": my_max_hp,
            "my_ac": self._stats.get("ac", 10),
            "my_position": self.position,
            "allies": allies,
            "enemies": enemies,
            "priority_targets": priority_targets,
            "can_reach": can_reach,
            "round_number": self.engine.state.initiative_tracker.current_round,
            "movement_remaining": self._get_movement_remaining(),
            # Environmental data
            "push_opportunities": push_opportunities,
            "position_danger": position_danger,
            "should_move_from_hazard": should_move_from_hazard,
            "hazard_reason": hazard_reason,
        }

    def _get_weapon_reach(self) -> int:
        """
        Get melee reach from equipped weapon or monster attacks.

        Returns reach in feet (default 5ft).
        """
        # Check equipped weapon for reach property
        equipment = self._stats.get("equipment", {})
        main_weapon = equipment.get("mainhand") or equipment.get("weapon")

        if main_weapon:
            properties = main_weapon.get("properties", [])
            if isinstance(properties, list) and "reach" in properties:
                return 10  # Reach weapons add 5ft (total 10ft)
            # Check for explicit reach value
            if main_weapon.get("reach"):
                return main_weapon["reach"]

        # Check monster actions for reach (e.g., "reach 10 ft.")
        actions = self._stats.get("actions", [])
        if isinstance(actions, list):
            for action in actions:
                if isinstance(action, dict):
                    # Check action description for reach
                    desc = action.get("desc", action.get("description", ""))
                    if "reach 10" in desc.lower():
                        return 10
                    elif "reach 15" in desc.lower():
                        return 15
                    elif "reach 20" in desc.lower():
                        return 20
                    # Check explicit reach field
                    if action.get("reach"):
                        return action["reach"]

        # Default 5ft reach
        return 5

    def _get_reachable_enemies(self, enemies: List[Dict]) -> List[Dict]:
        """Get enemies that can be reached this turn."""
        my_pos = self.position
        speed = self._stats.get("speed", 30)
        reach = self._get_weapon_reach()

        reachable = []
        for enemy in enemies:
            pos = enemy["position"]
            if isinstance(pos, dict):
                pos = (pos.get("x", 0), pos.get("y", 0))
            elif isinstance(pos, (list, tuple)):
                pos = (pos[0], pos[1])

            # Calculate distance (5ft per cell)
            dx = abs(my_pos[0] - pos[0])
            dy = abs(my_pos[1] - pos[1])
            distance = max(dx, dy) * 5  # Diagonal movement

            if distance <= speed + reach:
                enemy["distance"] = distance
                reachable.append(enemy)

        return reachable

    def _get_movement_remaining(self) -> int:
        """Get remaining movement for this turn."""
        speed = self._stats.get("speed", 30)
        used = self.engine.state.current_turn.movement_used if self.engine.state.current_turn else 0
        return max(0, speed - used)

    def _check_critical_conditions(self, situation: Dict) -> Optional[AIDecision]:
        """
        Check for conditions that override normal behavior.

        Returns an immediate action if a critical condition is detected.
        """
        hp_percent = situation["my_hp_percent"]

        # Flee if below threshold
        flee_threshold = self._ai_config.get("flee_threshold", 0.15)
        if hp_percent < flee_threshold and situation["movement_remaining"] > 0:
            # Find safest direction (away from enemies)
            escape_pos = self._find_escape_position(situation)
            if escape_pos:
                return AIDecision(
                    action_type=ActionType.DASH,
                    position=escape_pos,
                    reasoning=f"Fleeing - HP at {hp_percent*100:.0f}%",
                    priority=100
                )

        # Self-heal if possible and hurt
        if hp_percent < 0.5:
            heal = self._get_healing_ability()
            if heal:
                return AIDecision(
                    action_type=ActionType.ABILITY,
                    ability_id=heal["id"],
                    target_id=self.combatant_id,
                    reasoning="Self-healing - low HP",
                    priority=90
                )

        return None

    def _find_escape_position(self, situation: Dict) -> Optional[Tuple[int, int]]:
        """Find a position to flee to."""
        my_pos = situation["my_position"]
        enemies = situation["enemies"]

        if not enemies:
            return None

        # Calculate average enemy position
        avg_x = sum(e["position"][0] if isinstance(e["position"], (list, tuple)) else e["position"]["x"] for e in enemies) / len(enemies)
        avg_y = sum(e["position"][1] if isinstance(e["position"], (list, tuple)) else e["position"]["y"] for e in enemies) / len(enemies)

        # Move away from enemies
        dx = my_pos[0] - avg_x
        dy = my_pos[1] - avg_y

        # Normalize and multiply by movement
        length = max(1, (dx**2 + dy**2)**0.5)
        speed_cells = situation["movement_remaining"] // 5

        new_x = int(my_pos[0] + (dx / length) * speed_cells)
        new_y = int(my_pos[1] + (dy / length) * speed_cells)

        # Clamp to grid bounds
        grid_width = getattr(self.engine, 'grid_width', 20)
        grid_height = getattr(self.engine, 'grid_height', 20)
        new_x = max(0, min(grid_width - 1, new_x))
        new_y = max(0, min(grid_height - 1, new_y))

        return (new_x, new_y)

    def _get_healing_ability(self) -> Optional[Dict]:
        """Get a healing ability if available."""
        abilities = self._stats.get("abilities", {})
        for name, data in abilities.items():
            if "heal" in name.lower() or data.get("effect") == "heal":
                return {"id": name, **data}
        return None

    def _generate_action_candidates(self, situation: Dict) -> List[AIDecision]:
        """
        Generate all possible actions.

        Returns a list of potential actions to be scored.
        """
        candidates = []

        # Check for monster special abilities first (breath weapons, multiattack, etc.)
        monster_ability_candidates = self._generate_monster_ability_candidates(situation)
        candidates.extend(monster_ability_candidates)

        # Attack actions
        for target in situation["can_reach"]:
            candidates.append(AIDecision(
                action_type=ActionType.ATTACK,
                target_id=target["id"],
                reasoning=f"Melee attack on {target['name']}"
            ))

        # Ranged attack on any visible enemy
        ranged_weapon = self._get_ranged_weapon()
        if ranged_weapon:
            for enemy in situation["enemies"]:
                candidates.append(AIDecision(
                    action_type=ActionType.ATTACK,
                    target_id=enemy["id"],
                    weapon_id=ranged_weapon.get("id"),
                    reasoning=f"Ranged attack on {enemy['name']}"
                ))

        # Shove actions - push enemies into hazards (environmental awareness)
        push_opportunities = situation.get("push_opportunities", [])
        for push_opp in push_opportunities:
            candidates.append(AIDecision(
                action_type=ActionType.SHOVE,
                target_id=push_opp.target_id,
                ability_id="shove_push",
                score=push_opp.score_bonus,  # Pre-scored based on hazard damage
                reasoning=push_opp.reasoning
            ))

        # Movement to reach targets
        if not situation["can_reach"] and situation["movement_remaining"] > 0:
            best_target = situation["priority_targets"][0] if situation["priority_targets"] else None
            if best_target:
                # Move toward best target
                target_pos = best_target["position"]
                if isinstance(target_pos, dict):
                    target_pos = (target_pos.get("x", 0), target_pos.get("y", 0))

                candidates.append(AIDecision(
                    action_type=ActionType.DASH,
                    position=target_pos,
                    target_id=best_target["id"],
                    reasoning=f"Dashing toward {best_target['name']}"
                ))

                candidates.append(AIDecision(
                    action_type=ActionType.MOVE,
                    position=target_pos,
                    target_id=best_target["id"],
                    reasoning=f"Moving toward {best_target['name']}"
                ))

        # Defensive options
        if situation["my_hp_percent"] < 0.3:
            candidates.append(AIDecision(
                action_type=ActionType.DODGE,
                reasoning="Dodging - low HP"
            ))

        # Disengage if surrounded
        adjacent_enemies = [e for e in situation["enemies"] if e.get("distance", 999) <= 5]
        if len(adjacent_enemies) >= 2 and situation["my_hp_percent"] < 0.5:
            candidates.append(AIDecision(
                action_type=ActionType.DISENGAGE,
                reasoning="Disengaging from multiple enemies"
            ))

        return candidates

    def _generate_monster_ability_candidates(self, situation: Dict) -> List[AIDecision]:
        """
        Generate candidates for monster special abilities.

        Checks for breath weapons, multiattack, and other special actions.
        """
        import re
        candidates = []

        # Get monster's actions from stats
        actions = self._stats.get("actions", [])
        if not actions:
            return candidates

        # Get recharge state from combat engine
        recharge_state = {}
        if hasattr(self.engine, 'state') and hasattr(self.engine.state, 'monster_ability_recharge'):
            recharge_state = self.engine.state.monster_ability_recharge.get(self.combatant_id, {})

        # Check for multiattack first (usually the best option)
        has_multiattack = False
        for action in actions:
            action_name = action.get("name", "").lower()

            if "multiattack" in action_name:
                has_multiattack = True
                # Multiattack is almost always preferred
                best_target = situation["priority_targets"][0] if situation["priority_targets"] else None
                if best_target:
                    candidates.append(AIDecision(
                        action_type=ActionType.MULTIATTACK,
                        target_id=best_target["id"],
                        ability_id=f"{self.combatant_id}_multiattack",
                        reasoning=f"Multiattack on {best_target['name']}",
                        score=100.0  # High base score for multiattack
                    ))
                continue

            # Check for breath weapons (high value AOE)
            if "breath" in action_name:
                ability_id = f"{self.combatant_id}_{action_name.replace(' ', '_')}"

                # Check if recharged
                is_available = recharge_state.get(ability_id, True)
                if not is_available:
                    continue

                # Breath weapons are excellent when multiple enemies are clustered
                num_enemies = len(situation["enemies"])
                if num_enemies >= 2:
                    candidates.append(AIDecision(
                        action_type=ActionType.ABILITY,
                        target_id=situation["priority_targets"][0]["id"] if situation["priority_targets"] else None,
                        ability_id=ability_id,
                        reasoning=f"Use {action.get('name', 'Breath Weapon')} on {num_enemies} enemies",
                        score=80.0 + (num_enemies * 10)  # More enemies = higher value
                    ))
                elif num_enemies == 1:
                    # Still worth using on single target for high damage
                    candidates.append(AIDecision(
                        action_type=ActionType.ABILITY,
                        target_id=situation["priority_targets"][0]["id"] if situation["priority_targets"] else None,
                        ability_id=ability_id,
                        reasoning=f"Use {action.get('name', 'Breath Weapon')} on single target",
                        score=60.0
                    ))
                continue

            # Check for Frightful Presence
            if "frightful presence" in action_name:
                # Only use if enemies aren't already frightened
                unfr_enemies = [e for e in situation["enemies"]
                               if "frightened" not in e.get("conditions", [])]
                if len(unfr_enemies) >= 1:
                    candidates.append(AIDecision(
                        action_type=ActionType.ABILITY,
                        target_id=None,  # AOE, no specific target
                        ability_id=f"{self.combatant_id}_frightful_presence",
                        reasoning=f"Frighten {len(unfr_enemies)} enemies",
                        score=50.0 + (len(unfr_enemies) * 5)
                    ))
                continue

            # Check for other recharge abilities
            recharge_match = re.search(r'\(Recharge\s+(\d+)', action_name, re.IGNORECASE)
            if recharge_match:
                ability_id = f"{self.combatant_id}_{action_name.replace(' ', '_')}"
                is_available = recharge_state.get(ability_id, True)

                if is_available and situation["enemies"]:
                    candidates.append(AIDecision(
                        action_type=ActionType.ABILITY,
                        target_id=situation["priority_targets"][0]["id"] if situation["priority_targets"] else None,
                        ability_id=ability_id,
                        reasoning=f"Use special ability: {action.get('name', 'Unknown')}",
                        score=70.0
                    ))

        return candidates

    def _get_ranged_weapon(self) -> Optional[Dict]:
        """Get a ranged weapon if available."""
        equipment = self._stats.get("equipment", {})
        if equipment and equipment.get("ranged"):
            return equipment["ranged"]
        return None

    def _score_action(self, action: AIDecision, situation: Dict) -> float:
        """
        Score an action based on expected utility.

        Higher scores indicate better actions.
        """
        score = 0.0

        if action.action_type == ActionType.ATTACK:
            score = self._score_attack(action, situation)

        elif action.action_type == ActionType.DASH:
            score = self._score_dash(action, situation)

        elif action.action_type == ActionType.MOVE:
            score = self._score_move(action, situation)

        elif action.action_type == ActionType.DODGE:
            score = self._score_dodge(action, situation)

        elif action.action_type == ActionType.DISENGAGE:
            score = self._score_disengage(action, situation)

        elif action.action_type == ActionType.ABILITY:
            score = self._score_ability(action, situation)

        elif action.action_type == ActionType.MULTIATTACK:
            score = self._score_multiattack(action, situation)

        elif action.action_type == ActionType.SHOVE:
            score = self._score_shove(action, situation)

        return score

    def _score_shove(self, action: AIDecision, situation: Dict) -> float:
        """
        Score a shove action (pushing enemy into hazard).

        Shove is valuable when it can push enemy into pit, ledge, or harmful surface.
        The pre-calculated score_bonus from push opportunity is used as a base.
        """
        # Use the pre-calculated score from environmental analysis
        score = action.score if action.score > 0 else 30.0

        # Find the push opportunity for more context
        for push_opp in situation.get("push_opportunities", []):
            if push_opp.target_id == action.target_id:
                # Add bonus based on hazard damage potential
                score = max(score, push_opp.score_bonus)

                # Extra bonus if this would kill/incapacitate the target
                target_data = next(
                    (t for t in situation["priority_targets"] if t["id"] == action.target_id),
                    None
                )
                if target_data:
                    target_hp = target_data.get("hp", 100)
                    hazard_damage = push_opp.hazard.damage_potential
                    if target_hp <= hazard_damage:
                        score += 40  # Big bonus for potential environmental kill

                    # Bonus if hazard causes prone (advantage on attacks)
                    if push_opp.hazard.causes_condition == "prone":
                        score += 15

                break

        return score

    def _score_multiattack(self, action: AIDecision, situation: Dict) -> float:
        """Score a multiattack action."""
        # Multiattack is generally the best option for monsters with it
        score = 100.0  # High base score

        # Find target
        target = None
        for t in situation["priority_targets"]:
            if t["id"] == action.target_id:
                target = t
                break

        if not target:
            return score * 0.8  # Still good, just no specific target

        # Add priority score from target
        score += target.get("priority_score", 0)

        # Bonus for potential kill (multiple attacks increase chance)
        target_hp = target.get("hp", 100)
        estimated_damage = self._estimate_damage() * 2  # Assume 2+ attacks
        if target_hp <= estimated_damage:
            score += 30

        return score

    def _score_attack(self, action: AIDecision, situation: Dict) -> float:
        """Score an attack action."""
        score = 50.0  # Base score for attacking

        # Find target in priority list
        target = None
        for t in situation["priority_targets"]:
            if t["id"] == action.target_id:
                target = t
                break

        if not target:
            return 0

        # Add priority score from target evaluation
        score += target.get("priority_score", 0)

        # Bonus for potential kill
        target_hp = target.get("hp", 100)
        estimated_damage = self._estimate_damage()
        if target_hp <= estimated_damage:
            score += 40  # Big bonus for potential kill

        # Bonus for attacking low HP targets
        hp_percent = target_hp / max(1, target.get("max_hp", 1))
        score += (1 - hp_percent) * 20  # Up to 20 points for low HP targets

        # Ranged attacks on distant targets
        if action.weapon_id:
            distance = target.get("distance", 5)
            if distance > 5:
                score += 10  # Bonus for using ranged when appropriate

        return score

    def _score_dash(self, action: AIDecision, situation: Dict) -> float:
        """Score a dash action."""
        score = 20.0  # Base score

        # Higher if we can't reach anyone
        if not situation["can_reach"]:
            score += 30

        # Higher if moving toward high-priority target
        if action.target_id:
            for t in situation["priority_targets"]:
                if t["id"] == action.target_id:
                    score += t.get("priority_score", 0) * 0.5
                    break

        return score

    def _score_move(self, action: AIDecision, situation: Dict) -> float:
        """Score a move action."""
        return self._score_dash(action, situation) * 0.8  # Slightly prefer dash

    def _score_dodge(self, action: AIDecision, situation: Dict) -> float:
        """Score a dodge action."""
        score = 10.0

        # Much better when low HP
        if situation["my_hp_percent"] < 0.3:
            score += 40

        # Better when multiple enemies nearby
        adjacent = len([e for e in situation["enemies"] if e.get("distance", 999) <= 10])
        score += adjacent * 10

        return score

    def _score_disengage(self, action: AIDecision, situation: Dict) -> float:
        """Score a disengage action."""
        score = 15.0

        # Better when low HP and surrounded
        if situation["my_hp_percent"] < 0.5:
            score += 25

        adjacent = len([e for e in situation["enemies"] if e.get("distance", 999) <= 5])
        if adjacent >= 2:
            score += 30

        return score

    def _score_ability(self, action: AIDecision, situation: Dict) -> float:
        """Score using a special ability."""
        score = 30.0

        # Healing abilities are more valuable at low HP
        if "heal" in (action.ability_id or "").lower():
            hp_deficit = 1 - situation["my_hp_percent"]
            score += hp_deficit * 50

        return score

    def _estimate_damage(self) -> int:
        """Estimate damage output per attack."""
        damage_dice = self._stats.get("damage_dice", "1d6")
        attack_bonus = self._stats.get("attack_bonus", 0)

        # Parse damage dice (simple)
        if "d" in damage_dice:
            parts = damage_dice.split("d")
            num_dice = int(parts[0]) if parts[0] else 1
            die_size = int(parts[1].split("+")[0].split("-")[0])
            avg = num_dice * (die_size + 1) / 2
        else:
            avg = int(damage_dice)

        return int(avg)


def get_ai_for_role(role: str, engine: "CombatEngine", combatant_id: str):
    """
    Get the appropriate AI class for a given role.

    Args:
        role: AI role string (melee_brute, ranged_striker, spellcaster, etc.)
        engine: Combat engine instance
        combatant_id: ID of the combatant

    Returns:
        AI behavior instance for the specified role
    """
    from .behaviors import (
        MeleeBruteAI,
        RangedStrikerAI,
        SpellcasterAI,
        SupportAI,
        ControllerAI,
        SkirmisherAI,
        MinionAI,
        BossAI,
        BaseBehavior,
    )

    role_map = {
        "melee_brute": MeleeBruteAI,
        "ranged_striker": RangedStrikerAI,
        "spellcaster": SpellcasterAI,
        "support": SupportAI,
        "controller": ControllerAI,
        "skirmisher": SkirmisherAI,
        "minion": MinionAI,
        "boss": BossAI,
        # Class-based defaults
        "barbarian": MeleeBruteAI,
        "fighter": MeleeBruteAI,
        "paladin": MeleeBruteAI,
        "ranger": RangedStrikerAI,
        "rogue": SkirmisherAI,
        "wizard": SpellcasterAI,
        "sorcerer": SpellcasterAI,
        "warlock": SpellcasterAI,
        "cleric": SupportAI,
        "druid": SupportAI,
        "bard": SupportAI,
        "monk": SkirmisherAI,
    }

    ai_class = role_map.get(role.lower(), MeleeBruteAI)
    return ai_class(engine, combatant_id)


def get_ai_for_combatant(engine: "CombatEngine", combatant_id: str):
    """
    Get the best AI for a combatant based on their stats.

    Automatically determines the role from combatant data.

    Args:
        engine: Combat engine instance
        combatant_id: ID of the combatant

    Returns:
        AI behavior instance
    """
    stats = engine.state.combatant_stats.get(combatant_id, {})

    # Check for explicit AI role in config
    ai_config = stats.get("ai_behavior", {})
    if ai_config.get("role"):
        return get_ai_for_role(ai_config["role"], engine, combatant_id)

    # Infer from class
    char_class = stats.get("class", "").lower()
    if char_class:
        return get_ai_for_role(char_class, engine, combatant_id)

    # Check for spellcasting
    if stats.get("spellcasting"):
        return get_ai_for_role("spellcaster", engine, combatant_id)

    # Check for ranged weapon
    equipment = stats.get("equipment", {})
    if equipment.get("ranged"):
        return get_ai_for_role("ranged_striker", engine, combatant_id)

    # Default to melee brute
    return get_ai_for_role("melee_brute", engine, combatant_id)
