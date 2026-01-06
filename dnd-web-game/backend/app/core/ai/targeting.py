"""
D&D 5e AI Target Evaluation System.

Evaluates and prioritizes targets based on threat level,
vulnerability, tactical value, and positioning.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from app.core.combat_engine import CombatEngine


class TargetPriority(Enum):
    """Target selection priorities."""
    LOWEST_HP = "lowest_hp"
    HIGHEST_THREAT = "highest_threat"
    SPELLCASTER = "spellcaster"
    HEALER = "healer"
    NEAREST = "nearest"
    CONCENTRATING = "concentrating"
    WEAKEST_SAVE = "weakest_save"
    HIGHEST_DAMAGE = "highest_damage"


@dataclass
class TargetScore:
    """Evaluation score for a potential target."""
    target_id: str
    target_name: str
    total_score: float
    hp_score: float = 0.0
    threat_score: float = 0.0
    class_score: float = 0.0
    condition_score: float = 0.0
    position_score: float = 0.0
    tactical_score: float = 0.0
    reasons: List[str] = field(default_factory=list)

    @property
    def is_priority(self) -> bool:
        """Check if this is a high-priority target."""
        return self.total_score >= 50.0


class TargetEvaluator:
    """
    Evaluates potential targets for AI combatants.

    Uses a weighted scoring system to determine the best targets
    based on multiple factors including:
    - Current HP percentage (finish off wounded)
    - Class threat level (prioritize healers/casters)
    - Active conditions (target concentrating enemies)
    - Positioning (prefer reachable targets)
    - Tactical value (consider team coordination)
    """

    # Class threat weights - higher = more dangerous
    CLASS_THREAT_WEIGHTS = {
        "cleric": 90,      # Healing is very dangerous
        "druid": 85,       # Healing + control
        "bard": 80,        # Support/healing
        "wizard": 75,      # High damage potential
        "sorcerer": 70,    # Damage dealer
        "warlock": 65,     # Consistent damage
        "paladin": 60,     # Tanky but dangerous smites
        "ranger": 55,      # Ranged threat
        "monk": 50,        # Mobile striker
        "rogue": 45,       # Sneak attack threat
        "fighter": 40,     # Consistent damage
        "barbarian": 35,   # High HP, lower priority
    }

    # Save type weaknesses by class (for spell targeting)
    CLASS_WEAK_SAVES = {
        "barbarian": ["intelligence", "wisdom"],
        "fighter": ["intelligence", "wisdom", "charisma"],
        "rogue": ["strength", "constitution"],
        "wizard": ["strength", "constitution"],
        "sorcerer": ["strength", "constitution"],
        "cleric": ["dexterity"],
        "druid": ["strength"],
        "warlock": ["strength", "constitution"],
        "paladin": ["dexterity"],
        "ranger": ["charisma"],
        "monk": ["charisma"],
        "bard": ["strength"],
    }

    def __init__(self, engine: "CombatEngine", evaluator_id: str):
        """
        Initialize target evaluator.

        Args:
            engine: The combat engine instance
            evaluator_id: ID of the combatant doing the evaluating
        """
        self.engine = engine
        self.evaluator_id = evaluator_id
        self._cache = {}

    def get_evaluator_position(self) -> Optional[Tuple[int, int]]:
        """Get the position of the evaluating combatant."""
        pos = self.engine.state.positions.get(self.evaluator_id)
        if pos:
            if isinstance(pos, dict):
                return (pos.get("x", 0), pos.get("y", 0))
            return tuple(pos)
        return None

    def evaluate_all_targets(
        self,
        enemy_ids: List[str],
        priority: TargetPriority = TargetPriority.HIGHEST_THREAT,
    ) -> List[TargetScore]:
        """
        Evaluate all potential targets and return sorted scores.

        Args:
            enemy_ids: List of potential target IDs
            priority: Primary factor to weight highest

        Returns:
            List of TargetScore sorted by total_score descending
        """
        scores = []

        for target_id in enemy_ids:
            score = self.evaluate_target(target_id, priority)
            if score:
                scores.append(score)

        # Sort by total score descending
        scores.sort(key=lambda s: s.total_score, reverse=True)
        return scores

    def evaluate_target(
        self,
        target_id: str,
        priority: TargetPriority = TargetPriority.HIGHEST_THREAT,
    ) -> Optional[TargetScore]:
        """
        Evaluate a single target's priority score.

        Args:
            target_id: ID of target to evaluate
            priority: Primary factor to weight highest

        Returns:
            TargetScore with breakdown of scoring factors
        """
        target = self.engine.state.initiative_tracker.get_combatant(target_id)
        if not target or not target.is_active:
            return None

        target_stats = self.engine.state.combatant_stats.get(target_id, {})
        reasons = []

        # Calculate individual scores
        hp_score = self._calculate_hp_score(target, target_stats, reasons)
        threat_score = self._calculate_threat_score(target_stats, reasons)
        class_score = self._calculate_class_score(target_stats, reasons)
        condition_score = self._calculate_condition_score(target, reasons)
        position_score = self._calculate_position_score(target_id, reasons)
        tactical_score = self._calculate_tactical_score(target_id, target_stats, reasons)

        # Weight scores based on priority
        weights = self._get_priority_weights(priority)

        total_score = (
            hp_score * weights["hp"] +
            threat_score * weights["threat"] +
            class_score * weights["class"] +
            condition_score * weights["condition"] +
            position_score * weights["position"] +
            tactical_score * weights["tactical"]
        )

        return TargetScore(
            target_id=target_id,
            target_name=target.name,
            total_score=total_score,
            hp_score=hp_score,
            threat_score=threat_score,
            class_score=class_score,
            condition_score=condition_score,
            position_score=position_score,
            tactical_score=tactical_score,
            reasons=reasons,
        )

    def _calculate_hp_score(
        self,
        target,
        target_stats: Dict,
        reasons: List[str],
    ) -> float:
        """
        Score based on target's HP percentage.
        Lower HP = higher score (finish them off).
        """
        current_hp = target_stats.get("current_hp", target.hp)
        max_hp = target_stats.get("max_hp", getattr(target, "max_hp", current_hp))

        if max_hp <= 0:
            return 0.0

        hp_percent = current_hp / max_hp

        # Heavily wounded (< 25%) - high priority
        if hp_percent < 0.25:
            reasons.append(f"Heavily wounded ({int(hp_percent * 100)}% HP)")
            return 100.0

        # Wounded (< 50%) - medium priority
        if hp_percent < 0.5:
            reasons.append(f"Wounded ({int(hp_percent * 100)}% HP)")
            return 70.0

        # Damaged (< 75%) - slight priority
        if hp_percent < 0.75:
            reasons.append(f"Damaged ({int(hp_percent * 100)}% HP)")
            return 40.0

        # Full/near full HP - lowest priority
        return 20.0

    def _calculate_threat_score(
        self,
        target_stats: Dict,
        reasons: List[str],
    ) -> float:
        """
        Score based on target's damage output potential.
        """
        score = 0.0

        # Check for equipped weapons
        equipment = target_stats.get("equipment", {})
        main_weapon = equipment.get("main_hand")
        if main_weapon:
            damage_dice = main_weapon.get("damage_dice", "1d6")
            # Parse average damage from dice
            avg_damage = self._estimate_dice_average(damage_dice)
            score += avg_damage * 2

            if avg_damage >= 10:
                reasons.append(f"High damage weapon ({damage_dice})")

        # Check for spellcasting
        spellcasting = target_stats.get("spellcasting")
        if spellcasting:
            spell_slots = spellcasting.get("spell_slots", {})
            total_slots = sum(spell_slots.values())
            if total_slots > 0:
                score += total_slots * 5
                reasons.append(f"Has {total_slots} spell slots")

        # Check level
        level = target_stats.get("level", 1)
        score += level * 3

        return min(score, 100.0)

    def _calculate_class_score(
        self,
        target_stats: Dict,
        reasons: List[str],
    ) -> float:
        """
        Score based on target's class priority.
        Healers and casters are high priority.
        """
        char_class = target_stats.get("class", "").lower()

        if char_class in self.CLASS_THREAT_WEIGHTS:
            weight = self.CLASS_THREAT_WEIGHTS[char_class]
            if weight >= 80:
                reasons.append(f"High-priority class: {char_class.title()}")
            elif weight >= 60:
                reasons.append(f"Medium-priority class: {char_class.title()}")
            return float(weight)

        return 30.0  # Unknown class, moderate priority

    def _calculate_condition_score(
        self,
        target,
        reasons: List[str],
    ) -> float:
        """
        Score based on target's conditions.
        Concentrating targets are high priority.
        """
        conditions = getattr(target, "conditions", []) or []
        score = 0.0

        # Concentration is very valuable to break
        if "concentrating" in conditions:
            score += 50.0
            reasons.append("Concentrating on a spell")

        # Already debuffed - might be easier to finish
        if "prone" in conditions:
            score += 20.0
            reasons.append("Prone (advantage on melee)")

        if "restrained" in conditions:
            score += 25.0
            reasons.append("Restrained (advantage)")

        if "frightened" in conditions:
            score += 15.0
            reasons.append("Frightened")

        if "poisoned" in conditions:
            score += 10.0
            reasons.append("Poisoned")

        # Negative conditions for us - lower priority
        if "invisible" in conditions:
            score -= 30.0
            reasons.append("Invisible (harder to hit)")

        if "heavily_obscured" in conditions:
            score -= 20.0

        return max(0.0, score)

    def _calculate_position_score(
        self,
        target_id: str,
        reasons: List[str],
    ) -> float:
        """
        Score based on target's position relative to evaluator.
        Closer targets are generally better.
        """
        my_pos = self.get_evaluator_position()
        target_pos = self.engine.state.positions.get(target_id)

        if not my_pos or not target_pos:
            return 50.0  # Default middle score

        if isinstance(target_pos, dict):
            target_pos = (target_pos.get("x", 0), target_pos.get("y", 0))

        distance = abs(my_pos[0] - target_pos[0]) + abs(my_pos[1] - target_pos[1])

        # Adjacent - highest priority
        if distance <= 1:
            reasons.append("Adjacent (melee range)")
            return 100.0

        # Close range (2-3 squares)
        if distance <= 3:
            reasons.append("Close range")
            return 80.0

        # Medium range (4-6 squares)
        if distance <= 6:
            return 60.0

        # Long range (7-12 squares)
        if distance <= 12:
            return 40.0

        # Very far
        reasons.append("Far away")
        return 20.0

    def _calculate_tactical_score(
        self,
        target_id: str,
        target_stats: Dict,
        reasons: List[str],
    ) -> float:
        """
        Score based on tactical considerations.
        """
        score = 0.0

        # Check if target has used their reaction
        turn_data = getattr(self.engine.state, "current_turn", None)
        if turn_data:
            reactions_used = getattr(turn_data, "reactions_used", set())
            if target_id in reactions_used:
                score += 20.0
                reasons.append("Reaction already used")

        # Check if target is isolated (no allies nearby)
        target_pos = self.engine.state.positions.get(target_id)
        if target_pos:
            if isinstance(target_pos, dict):
                target_pos = (target_pos.get("x", 0), target_pos.get("y", 0))

            # Count allies near target
            target_combatant = self.engine.state.initiative_tracker.get_combatant(target_id)
            ally_count = 0

            if target_combatant:
                for cid, cpos in self.engine.state.positions.items():
                    if cid == target_id:
                        continue
                    other = self.engine.state.initiative_tracker.get_combatant(cid)
                    if not other or not other.is_active:
                        continue
                    if other.combatant_type == target_combatant.combatant_type:
                        if isinstance(cpos, dict):
                            cpos = (cpos.get("x", 0), cpos.get("y", 0))
                        dist = abs(target_pos[0] - cpos[0]) + abs(target_pos[1] - cpos[1])
                        if dist <= 2:
                            ally_count += 1

            if ally_count == 0:
                score += 25.0
                reasons.append("Isolated target")
            elif ally_count >= 2:
                score -= 15.0  # Protected by allies

        return max(0.0, score)

    def _get_priority_weights(self, priority: TargetPriority) -> Dict[str, float]:
        """Get weight multipliers based on priority focus."""
        # Default balanced weights
        weights = {
            "hp": 1.0,
            "threat": 1.0,
            "class": 1.0,
            "condition": 1.0,
            "position": 1.0,
            "tactical": 1.0,
        }

        if priority == TargetPriority.LOWEST_HP:
            weights["hp"] = 2.0
            weights["position"] = 1.5
        elif priority == TargetPriority.HIGHEST_THREAT:
            weights["threat"] = 2.0
            weights["class"] = 1.5
        elif priority == TargetPriority.SPELLCASTER:
            weights["class"] = 2.5
            weights["threat"] = 1.5
        elif priority == TargetPriority.HEALER:
            weights["class"] = 3.0  # Healers specifically
        elif priority == TargetPriority.NEAREST:
            weights["position"] = 3.0
        elif priority == TargetPriority.CONCENTRATING:
            weights["condition"] = 3.0

        return weights

    def _estimate_dice_average(self, dice_str: str) -> float:
        """Estimate average roll from dice string like '2d6'."""
        try:
            if "d" not in dice_str.lower():
                return float(dice_str)

            parts = dice_str.lower().split("d")
            num_dice = int(parts[0]) if parts[0] else 1
            die_size = int(parts[1].split("+")[0].split("-")[0])

            avg = num_dice * (die_size + 1) / 2

            # Add modifier if present
            if "+" in dice_str:
                mod = int(dice_str.split("+")[1])
                avg += mod
            elif "-" in parts[1]:
                mod = int(parts[1].split("-")[1])
                avg -= mod

            return avg
        except (ValueError, IndexError):
            return 3.5  # Default to 1d6 average

    def get_best_target(
        self,
        enemy_ids: List[str],
        priority: TargetPriority = TargetPriority.HIGHEST_THREAT,
    ) -> Optional[TargetScore]:
        """
        Get the single best target from a list.

        Args:
            enemy_ids: List of potential target IDs
            priority: Primary factor to weight highest

        Returns:
            The highest-scored target, or None if no valid targets
        """
        scores = self.evaluate_all_targets(enemy_ids, priority)
        return scores[0] if scores else None

    def get_targets_for_aoe(
        self,
        center: Tuple[int, int],
        radius: int,
        enemy_ids: List[str],
        min_targets: int = 2,
    ) -> Optional[Dict]:
        """
        Find the best position for an AoE spell.

        Args:
            center: Starting point to search from
            radius: AoE radius in squares
            enemy_ids: List of enemy IDs to consider
            min_targets: Minimum targets needed to use AoE

        Returns:
            Dict with 'position', 'targets', 'count' or None if not viable
        """
        best_position = None
        best_targets = []
        best_count = 0

        # Search grid around center for best AoE position
        search_range = radius + 3
        for dx in range(-search_range, search_range + 1):
            for dy in range(-search_range, search_range + 1):
                test_pos = (center[0] + dx, center[1] + dy)

                # Check which enemies would be hit
                targets_hit = []
                for eid in enemy_ids:
                    epos = self.engine.state.positions.get(eid)
                    if not epos:
                        continue
                    if isinstance(epos, dict):
                        epos = (epos.get("x", 0), epos.get("y", 0))

                    dist = abs(test_pos[0] - epos[0]) + abs(test_pos[1] - epos[1])
                    if dist <= radius:
                        targets_hit.append(eid)

                if len(targets_hit) > best_count:
                    best_count = len(targets_hit)
                    best_position = test_pos
                    best_targets = targets_hit

        if best_count >= min_targets:
            return {
                "position": best_position,
                "targets": best_targets,
                "count": best_count,
            }

        return None

    def get_weak_save_targets(
        self,
        enemy_ids: List[str],
        save_type: str,
    ) -> List[TargetScore]:
        """
        Find targets most likely to fail a specific save type.

        Args:
            enemy_ids: List of potential targets
            save_type: Save type (strength, dexterity, etc.)

        Returns:
            List of targets sorted by likelihood to fail save
        """
        targets = []
        save_type_lower = save_type.lower()

        for eid in enemy_ids:
            target = self.engine.state.initiative_tracker.get_combatant(eid)
            if not target or not target.is_active:
                continue

            target_stats = self.engine.state.combatant_stats.get(eid, {})
            char_class = target_stats.get("class", "").lower()

            # Check if this is a weak save for the class
            weak_saves = self.CLASS_WEAK_SAVES.get(char_class, [])

            score = 50.0  # Base score
            reasons = []

            if save_type_lower in weak_saves:
                score += 40.0
                reasons.append(f"{char_class.title()} weak to {save_type} saves")

            # Check actual save modifier if available
            save_mod = target_stats.get(f"{save_type_lower}_save", None)
            if save_mod is not None:
                if save_mod <= 0:
                    score += 30.0
                    reasons.append(f"Low {save_type} save (+{save_mod})")
                elif save_mod <= 2:
                    score += 15.0

            # Add HP factor (wounded targets may have disadvantage)
            hp_score = self._calculate_hp_score(target, target_stats, reasons)
            score += hp_score * 0.3

            targets.append(TargetScore(
                target_id=eid,
                target_name=target.name,
                total_score=score,
                tactical_score=score,
                reasons=reasons,
            ))

        targets.sort(key=lambda t: t.total_score, reverse=True)
        return targets
