"""
D&D Combat Engine - Surface Effects System
BG3-style environmental surfaces: fire, water, ice, grease, poison, acid, etc.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from app.core.dice import roll_dice


class SurfaceType(str, Enum):
    """Types of surfaces that can exist on the battlefield."""
    FIRE = "fire"
    WATER = "water"
    ICE = "ice"
    GREASE = "grease"
    POISON = "poison"
    ACID = "acid"
    BLOOD = "blood"
    ELECTRIFIED_WATER = "electrified_water"
    OIL = "oil"  # Flammable, slippery
    WEB = "web"  # Difficult terrain, flammable
    STEAM = "steam"  # Obscured area
    SMOKE = "smoke"  # Obscured area


@dataclass
class Surface:
    """Represents a surface effect on a grid cell."""
    surface_type: SurfaceType
    duration_rounds: int = -1  # -1 = permanent until removed
    damage_dice: str = ""
    damage_type: str = ""
    dc: int = 10  # Save DC for effects
    save_type: str = "dex"  # Type of save
    creator_id: Optional[str] = None
    spell_id: Optional[str] = None
    intensity: int = 1  # For stacking/spreading

    def to_dict(self) -> Dict[str, Any]:
        return {
            "surface_type": self.surface_type.value,
            "duration_rounds": self.duration_rounds,
            "damage_dice": self.damage_dice,
            "damage_type": self.damage_type,
            "dc": self.dc,
            "save_type": self.save_type,
            "creator_id": self.creator_id,
            "spell_id": self.spell_id,
            "intensity": self.intensity
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Surface":
        return cls(
            surface_type=SurfaceType(data["surface_type"]),
            duration_rounds=data.get("duration_rounds", -1),
            damage_dice=data.get("damage_dice", ""),
            damage_type=data.get("damage_type", ""),
            dc=data.get("dc", 10),
            save_type=data.get("save_type", "dex"),
            creator_id=data.get("creator_id"),
            spell_id=data.get("spell_id"),
            intensity=data.get("intensity", 1)
        )


# Surface effect definitions
SURFACE_EFFECTS: Dict[SurfaceType, Dict[str, Any]] = {
    SurfaceType.FIRE: {
        "damage_dice": "1d4",
        "damage_type": "fire",
        "dc": 10,
        "save_type": "dex",
        "difficult_terrain": False,
        "condition": None,
        "description": "Burning flames",
        "light_level": "bright",
        "can_spread": True
    },
    SurfaceType.WATER: {
        "damage_dice": "",
        "damage_type": "",
        "dc": 0,
        "save_type": "",
        "difficult_terrain": False,
        "condition": None,
        "description": "Shallow water",
        "conductible": True,  # Conducts lightning
        "extinguishes_fire": True
    },
    SurfaceType.ICE: {
        "damage_dice": "",
        "damage_type": "",
        "dc": 12,
        "save_type": "dex",
        "difficult_terrain": True,
        "condition": "prone",  # On failed save
        "description": "Slippery ice",
        "meltable": True
    },
    SurfaceType.GREASE: {
        "damage_dice": "",
        "damage_type": "",
        "dc": 12,
        "save_type": "dex",
        "difficult_terrain": True,
        "condition": "prone",  # On failed save
        "description": "Slippery grease",
        "flammable": True
    },
    SurfaceType.POISON: {
        "damage_dice": "1d4",
        "damage_type": "poison",
        "dc": 12,
        "save_type": "con",
        "difficult_terrain": False,
        "condition": "poisoned",
        "description": "Toxic fumes"
    },
    SurfaceType.ACID: {
        "damage_dice": "2d4",
        "damage_type": "acid",
        "dc": 12,
        "save_type": "dex",
        "difficult_terrain": False,
        "condition": None,
        "description": "Corrosive acid"
    },
    SurfaceType.BLOOD: {
        "damage_dice": "",
        "damage_type": "",
        "dc": 10,
        "save_type": "dex",
        "difficult_terrain": False,
        "condition": None,  # Disadvantage on DEX saves
        "description": "Slippery blood",
        "slip_penalty": True
    },
    SurfaceType.ELECTRIFIED_WATER: {
        "damage_dice": "1d6",
        "damage_type": "lightning",
        "dc": 12,
        "save_type": "con",
        "difficult_terrain": False,
        "condition": None,
        "description": "Electrified water",
        "chains": True  # Affects all in connected water
    },
    SurfaceType.OIL: {
        "damage_dice": "",
        "damage_type": "",
        "dc": 12,
        "save_type": "dex",
        "difficult_terrain": True,
        "condition": "prone",
        "description": "Slippery oil",
        "flammable": True
    },
    SurfaceType.WEB: {
        "damage_dice": "",
        "damage_type": "",
        "dc": 12,
        "save_type": "dex",
        "difficult_terrain": True,
        "condition": "restrained",
        "description": "Sticky webs",
        "flammable": True
    },
    SurfaceType.STEAM: {
        "damage_dice": "",
        "damage_type": "",
        "dc": 0,
        "save_type": "",
        "difficult_terrain": False,
        "condition": None,
        "description": "Obscuring steam",
        "obscured": "heavily"
    },
    SurfaceType.SMOKE: {
        "damage_dice": "",
        "damage_type": "",
        "dc": 0,
        "save_type": "",
        "difficult_terrain": False,
        "condition": None,
        "description": "Obscuring smoke",
        "obscured": "lightly"
    }
}

# Surface interaction rules
SURFACE_INTERACTIONS: Dict[Tuple[str, str], Dict[str, Any]] = {
    # Fire interactions
    ("fire", "water"): {"result": "steam", "removes": ["fire", "water"], "description": "Fire and water create steam"},
    ("fire", "ice"): {"result": "water", "removes": ["fire", "ice"], "description": "Fire melts ice to water"},
    ("fire", "grease"): {"result": "fire", "removes": ["grease"], "spreads": True, "description": "Grease ignites!"},
    ("fire", "oil"): {"result": "fire", "removes": ["oil"], "spreads": True, "damage_bonus": "1d4", "description": "Oil ignites!"},
    ("fire", "web"): {"result": "fire", "removes": ["web"], "spreads": True, "description": "Webs burn away"},
    ("fire", "poison"): {"result": None, "removes": ["fire", "poison"], "description": "Fire burns away poison"},

    # Lightning interactions
    ("lightning", "water"): {"result": "electrified_water", "removes": ["water"], "description": "Water becomes electrified!"},
    ("lightning", "blood"): {"result": "electrified_water", "removes": ["blood"], "description": "Blood conducts electricity!"},

    # Cold interactions
    ("cold", "water"): {"result": "ice", "removes": ["water"], "description": "Water freezes to ice"},
    ("cold", "electrified_water"): {"result": "ice", "removes": ["electrified_water"], "description": "Electrified water freezes"},

    # Water interactions
    ("water", "fire"): {"result": "steam", "removes": ["fire", "water"], "description": "Water extinguishes fire"},
    ("water", "acid"): {"result": None, "removes": ["acid"], "dilutes": True, "description": "Water dilutes acid"},

    # Acid interactions
    ("acid", "web"): {"result": None, "removes": ["web"], "description": "Acid dissolves webs"},
}


class SurfaceManager:
    """Manages surfaces on the combat grid."""

    def __init__(self, grid: Any = None):
        """
        Initialize the surface manager.

        Args:
            grid: The combat grid
        """
        self.grid = grid
        self.surfaces: Dict[Tuple[int, int], List[Surface]] = {}

    def add_surface(
        self,
        x: int,
        y: int,
        surface_type: SurfaceType,
        duration_rounds: int = -1,
        dc: int = None,
        creator_id: str = None,
        spell_id: str = None,
        intensity: int = 1
    ) -> Dict[str, Any]:
        """
        Add a surface to a grid cell.

        Args:
            x, y: Grid coordinates
            surface_type: Type of surface
            duration_rounds: How long surface lasts (-1 = permanent)
            dc: Save DC (uses default if None)
            creator_id: ID of creature that created it
            spell_id: ID of spell that created it
            intensity: Surface intensity for stacking

        Returns:
            Result dictionary with interaction effects
        """
        pos = (x, y)
        effects = SURFACE_EFFECTS.get(surface_type, {})

        surface = Surface(
            surface_type=surface_type,
            duration_rounds=duration_rounds,
            damage_dice=effects.get("damage_dice", ""),
            damage_type=effects.get("damage_type", ""),
            dc=dc if dc is not None else effects.get("dc", 10),
            save_type=effects.get("save_type", "dex"),
            creator_id=creator_id,
            spell_id=spell_id,
            intensity=intensity
        )

        # Check for interactions with existing surfaces
        interaction_results = []
        if pos in self.surfaces:
            for existing in self.surfaces[pos][:]:  # Copy to allow modification
                interaction = self._check_interaction(surface_type, existing.surface_type)
                if interaction:
                    interaction_results.append(interaction)
                    # Handle the interaction
                    self._apply_interaction(pos, surface_type, existing.surface_type, interaction)

        # Add the surface if it wasn't consumed by interaction
        if not any(ir.get("removes_new", False) for ir in interaction_results):
            if pos not in self.surfaces:
                self.surfaces[pos] = []

            # Replace or stack with same type
            existing_same = [s for s in self.surfaces[pos] if s.surface_type == surface_type]
            if existing_same:
                # Increase intensity instead of stacking
                existing_same[0].intensity = min(existing_same[0].intensity + intensity, 3)
                existing_same[0].duration_rounds = max(existing_same[0].duration_rounds, duration_rounds)
            else:
                self.surfaces[pos].append(surface)

        return {
            "success": True,
            "position": pos,
            "surface_type": surface_type.value,
            "interactions": interaction_results,
            "surfaces_at_position": [s.to_dict() for s in self.surfaces.get(pos, [])]
        }

    def remove_surface(self, x: int, y: int, surface_type: SurfaceType = None) -> bool:
        """
        Remove a surface from a grid cell.

        Args:
            x, y: Grid coordinates
            surface_type: Specific type to remove, or None for all

        Returns:
            True if surface was removed
        """
        pos = (x, y)
        if pos not in self.surfaces:
            return False

        if surface_type is None:
            del self.surfaces[pos]
            return True

        initial_count = len(self.surfaces[pos])
        self.surfaces[pos] = [s for s in self.surfaces[pos] if s.surface_type != surface_type]

        if not self.surfaces[pos]:
            del self.surfaces[pos]

        return len(self.surfaces.get(pos, [])) < initial_count

    def get_surfaces_at(self, x: int, y: int) -> List[Surface]:
        """Get all surfaces at a position."""
        return self.surfaces.get((x, y), [])

    def has_surface(self, x: int, y: int, surface_type: SurfaceType = None) -> bool:
        """Check if position has a surface (optionally of specific type)."""
        surfaces = self.get_surfaces_at(x, y)
        if surface_type is None:
            return len(surfaces) > 0
        return any(s.surface_type == surface_type for s in surfaces)

    def _check_interaction(
        self,
        new_type: SurfaceType,
        existing_type: SurfaceType
    ) -> Optional[Dict[str, Any]]:
        """Check if two surface types interact."""
        key1 = (new_type.value, existing_type.value)
        key2 = (existing_type.value, new_type.value)

        return SURFACE_INTERACTIONS.get(key1) or SURFACE_INTERACTIONS.get(key2)

    def _apply_interaction(
        self,
        pos: Tuple[int, int],
        new_type: SurfaceType,
        existing_type: SurfaceType,
        interaction: Dict[str, Any]
    ):
        """Apply a surface interaction."""
        removes = interaction.get("removes", [])
        result_type = interaction.get("result")

        # Remove surfaces marked for removal
        if existing_type.value in removes:
            self.surfaces[pos] = [s for s in self.surfaces[pos] if s.surface_type != existing_type]

        # Create result surface if specified
        if result_type:
            try:
                result_surface_type = SurfaceType(result_type)
                effects = SURFACE_EFFECTS.get(result_surface_type, {})

                result_surface = Surface(
                    surface_type=result_surface_type,
                    duration_rounds=3,  # Interaction results are temporary
                    damage_dice=effects.get("damage_dice", ""),
                    damage_type=effects.get("damage_type", ""),
                    dc=effects.get("dc", 10),
                    save_type=effects.get("save_type", "dex")
                )

                # Add bonus damage if specified
                if interaction.get("damage_bonus"):
                    result_surface.damage_dice = f"{result_surface.damage_dice}+{interaction['damage_bonus']}"

                if pos not in self.surfaces:
                    self.surfaces[pos] = []
                self.surfaces[pos].append(result_surface)

                # Spread fire if indicated
                if interaction.get("spreads"):
                    self._spread_surface(pos, result_surface_type)
            except ValueError:
                pass  # Invalid surface type

    def _spread_surface(self, pos: Tuple[int, int], surface_type: SurfaceType, radius: int = 1):
        """Spread a surface to adjacent cells that have flammable surfaces."""
        x, y = pos
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue

                new_pos = (x + dx, y + dy)
                if new_pos in self.surfaces:
                    for surface in self.surfaces[new_pos][:]:
                        effects = SURFACE_EFFECTS.get(surface.surface_type, {})
                        if effects.get("flammable") and surface_type == SurfaceType.FIRE:
                            # Ignite flammable surface
                            self.add_surface(
                                new_pos[0], new_pos[1],
                                SurfaceType.FIRE,
                                duration_rounds=3
                            )

    def apply_damage_effect(
        self,
        damage_type: str,
        x: int,
        y: int,
        damage_amount: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Apply a damage type to surfaces at a position.
        Used when spells/attacks hit an area.

        Args:
            damage_type: Type of damage (fire, cold, lightning, etc.)
            x, y: Position
            damage_amount: Amount of damage (for intensity)

        Returns:
            List of interaction results
        """
        results = []
        surfaces = self.get_surfaces_at(x, y)

        for surface in surfaces[:]:  # Copy to allow modification
            interaction = SURFACE_INTERACTIONS.get((damage_type, surface.surface_type.value))
            if interaction:
                results.append({
                    "position": (x, y),
                    "damage_type": damage_type,
                    "surface": surface.surface_type.value,
                    "interaction": interaction
                })
                self._apply_interaction((x, y), SurfaceType(damage_type) if damage_type in [s.value for s in SurfaceType] else surface.surface_type, surface.surface_type, interaction)

        return results

    def process_turn_start(self, combatant_id: str, x: int, y: int, combatant_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process surface effects when a combatant starts their turn on a surface.

        Args:
            combatant_id: ID of the combatant
            x, y: Combatant's position
            combatant_stats: Combatant's stats for saves

        Returns:
            List of effect results
        """
        results = []
        surfaces = self.get_surfaces_at(x, y)

        for surface in surfaces:
            effect = self._apply_surface_effect(surface, combatant_id, combatant_stats)
            if effect:
                results.append(effect)

        return results

    def process_movement_enter(
        self,
        combatant_id: str,
        x: int,
        y: int,
        combatant_stats: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Process surface effects when a combatant enters a surface.

        Args:
            combatant_id: ID of the combatant
            x, y: Position entered
            combatant_stats: Combatant's stats for saves

        Returns:
            List of effect results
        """
        results = []
        surfaces = self.get_surfaces_at(x, y)

        for surface in surfaces:
            effect = self._apply_surface_effect(surface, combatant_id, combatant_stats, on_enter=True)
            if effect:
                results.append(effect)

        return results

    def _apply_surface_effect(
        self,
        surface: Surface,
        combatant_id: str,
        combatant_stats: Dict[str, Any],
        on_enter: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Apply a single surface's effect to a combatant."""
        effects = SURFACE_EFFECTS.get(surface.surface_type, {})
        result = {
            "surface_type": surface.surface_type.value,
            "combatant_id": combatant_id,
            "damage": 0,
            "condition": None,
            "save_made": None,
            "description": effects.get("description", "")
        }

        # Apply damage if surface deals damage
        if surface.damage_dice:
            damage = roll_dice(surface.damage_dice)
            # Apply intensity multiplier
            damage = int(damage * surface.intensity)
            result["damage"] = damage
            result["damage_type"] = surface.damage_type

        # Check for save-based effects
        if surface.dc > 0 and surface.save_type:
            save_mod = combatant_stats.get(f"{surface.save_type}_save", 0)
            if save_mod == 0:
                # Calculate from ability score
                ability_mod = combatant_stats.get(f"{surface.save_type}_mod", 0)
                save_mod = ability_mod

            save_roll = roll_dice("1d20") + save_mod
            result["save_roll"] = save_roll
            result["save_dc"] = surface.dc
            result["save_made"] = save_roll >= surface.dc

            if not result["save_made"]:
                # Apply condition on failed save
                condition = effects.get("condition")
                if condition:
                    result["condition"] = condition
            else:
                # Some surfaces deal half damage on save
                if result["damage"] > 0:
                    result["damage"] = result["damage"] // 2

        return result if result["damage"] > 0 or result["condition"] else None

    def is_difficult_terrain(self, x: int, y: int) -> bool:
        """Check if surfaces at position create difficult terrain."""
        for surface in self.get_surfaces_at(x, y):
            effects = SURFACE_EFFECTS.get(surface.surface_type, {})
            if effects.get("difficult_terrain"):
                return True
        return False

    def is_obscured(self, x: int, y: int) -> Optional[str]:
        """Check if surfaces at position create obscurement."""
        for surface in self.get_surfaces_at(x, y):
            effects = SURFACE_EFFECTS.get(surface.surface_type, {})
            obscured = effects.get("obscured")
            if obscured:
                return obscured  # "lightly" or "heavily"
        return None

    def advance_round(self):
        """Process surfaces at the end of a round (decay durations)."""
        positions_to_clear = []

        for pos, surfaces in self.surfaces.items():
            remaining = []
            for surface in surfaces:
                if surface.duration_rounds > 0:
                    surface.duration_rounds -= 1
                    if surface.duration_rounds > 0:
                        remaining.append(surface)
                elif surface.duration_rounds == -1:
                    remaining.append(surface)  # Permanent surface

            if remaining:
                self.surfaces[pos] = remaining
            else:
                positions_to_clear.append(pos)

        for pos in positions_to_clear:
            del self.surfaces[pos]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize surface manager to dictionary."""
        return {
            "surfaces": {
                f"{x},{y}": [s.to_dict() for s in surfaces]
                for (x, y), surfaces in self.surfaces.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], grid: Any = None) -> "SurfaceManager":
        """Deserialize surface manager from dictionary."""
        manager = cls(grid)
        for pos_str, surface_list in data.get("surfaces", {}).items():
            x, y = map(int, pos_str.split(","))
            manager.surfaces[(x, y)] = [Surface.from_dict(s) for s in surface_list]
        return manager


# Spell-to-surface mapping
SPELL_SURFACES: Dict[str, Dict[str, Any]] = {
    "grease": {
        "surface_type": SurfaceType.GREASE,
        "duration_rounds": 10,  # 1 minute
        "radius": 2
    },
    "create_bonfire": {
        "surface_type": SurfaceType.FIRE,
        "duration_rounds": 10,
        "radius": 0  # Single square
    },
    "web": {
        "surface_type": SurfaceType.WEB,
        "duration_rounds": 60,  # 1 hour
        "radius": 4
    },
    "fog_cloud": {
        "surface_type": SurfaceType.STEAM,
        "duration_rounds": 60,
        "radius": 4
    },
    "cloudkill": {
        "surface_type": SurfaceType.POISON,
        "duration_rounds": 10,
        "radius": 4,
        "damage_dice": "5d8"
    },
    "acid_splash": {
        "surface_type": SurfaceType.ACID,
        "duration_rounds": 1,
        "radius": 0
    },
    "burning_hands": {
        "surface_type": SurfaceType.FIRE,
        "duration_rounds": 1,
        "radius": 0
    },
    "fireball": {
        "surface_type": SurfaceType.FIRE,
        "duration_rounds": 1,
        "radius": 4
    },
    "ice_storm": {
        "surface_type": SurfaceType.ICE,
        "duration_rounds": 10,
        "radius": 4
    },
    "sleet_storm": {
        "surface_type": SurfaceType.ICE,
        "duration_rounds": 10,
        "radius": 8
    }
}


def create_surface_from_spell(
    spell_id: str,
    x: int,
    y: int,
    surface_manager: SurfaceManager,
    caster_id: str = None,
    spell_dc: int = None
) -> Dict[str, Any]:
    """
    Create surfaces from a spell cast.

    Args:
        spell_id: ID of the spell
        x, y: Center position
        surface_manager: The surface manager
        caster_id: ID of the caster
        spell_dc: Spell save DC

    Returns:
        Result dictionary
    """
    spell_data = SPELL_SURFACES.get(spell_id.lower().replace(" ", "_"))
    if not spell_data:
        return {"success": False, "reason": "Spell does not create surfaces"}

    surface_type = spell_data["surface_type"]
    duration = spell_data["duration_rounds"]
    radius = spell_data.get("radius", 0)

    results = []

    # Create surfaces in area
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            # Check if within circular radius
            if dx * dx + dy * dy <= radius * radius:
                result = surface_manager.add_surface(
                    x + dx, y + dy,
                    surface_type,
                    duration_rounds=duration,
                    dc=spell_dc,
                    creator_id=caster_id,
                    spell_id=spell_id
                )
                results.append(result)

    return {
        "success": True,
        "spell_id": spell_id,
        "surface_type": surface_type.value,
        "center": (x, y),
        "radius": radius,
        "cells_affected": len(results),
        "results": results
    }
