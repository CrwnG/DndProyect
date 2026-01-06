"""
Ammunition Tracking System.

D&D 5e ammunition rules:
- Ranged weapons with the Ammunition property require ammunition
- After combat, you can recover half your expended ammunition (rounded down)
- Drawing ammunition is free as part of the attack
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from enum import Enum


class AmmunitionType(str, Enum):
    """Types of ammunition in D&D 5e."""
    ARROW = "arrow"
    BOLT = "bolt"          # Crossbow bolts
    BULLET = "bullet"      # Sling bullets
    NEEDLE = "needle"      # Blowgun needles
    DART = "dart"          # Throwing darts (not really ammunition, but tracked)


# Weapon to ammunition type mapping
WEAPON_AMMUNITION = {
    # Bows
    "shortbow": AmmunitionType.ARROW,
    "longbow": AmmunitionType.ARROW,
    # Crossbows
    "light_crossbow": AmmunitionType.BOLT,
    "hand_crossbow": AmmunitionType.BOLT,
    "heavy_crossbow": AmmunitionType.BOLT,
    # Other
    "sling": AmmunitionType.BULLET,
    "blowgun": AmmunitionType.NEEDLE,
}

# Default ammunition costs and weights (per 20 units)
AMMUNITION_COSTS = {
    AmmunitionType.ARROW: {"cost": 1, "weight": 1.0},     # 1gp per 20, 1 lb per 20
    AmmunitionType.BOLT: {"cost": 1, "weight": 1.5},      # 1gp per 20, 1.5 lb per 20
    AmmunitionType.BULLET: {"cost": 0.04, "weight": 1.5}, # 4cp per 20, 1.5 lb per 20
    AmmunitionType.NEEDLE: {"cost": 1, "weight": 1.0},    # 1gp per 50, 1 lb per 50
    AmmunitionType.DART: {"cost": 0.05, "weight": 0.25},  # 5cp each, 0.25 lb each
}


@dataclass
class AmmunitionTracker:
    """Tracks ammunition for a character."""

    # Ammunition counts by type
    ammunition: Dict[str, int] = field(default_factory=dict)

    # Ammunition used during current combat (for recovery)
    combat_used: Dict[str, int] = field(default_factory=dict)

    def get_ammunition_count(self, ammo_type: str) -> int:
        """Get current count of a specific ammunition type."""
        return self.ammunition.get(ammo_type, 0)

    def has_ammunition(self, ammo_type: str, count: int = 1) -> bool:
        """Check if character has enough ammunition."""
        return self.get_ammunition_count(ammo_type) >= count

    def use_ammunition(self, ammo_type: str, count: int = 1) -> bool:
        """
        Use ammunition for an attack.

        Args:
            ammo_type: Type of ammunition to use
            count: Number of ammunition to use

        Returns:
            True if ammunition was used, False if not enough
        """
        current = self.get_ammunition_count(ammo_type)
        if current < count:
            return False

        self.ammunition[ammo_type] = current - count

        # Track for recovery
        used = self.combat_used.get(ammo_type, 0)
        self.combat_used[ammo_type] = used + count

        return True

    def add_ammunition(self, ammo_type: str, count: int) -> None:
        """Add ammunition to inventory."""
        current = self.get_ammunition_count(ammo_type)
        self.ammunition[ammo_type] = current + count

    def recover_ammunition(self) -> Dict[str, int]:
        """
        Recover half of expended ammunition after combat.

        D&D 5e Rule: After combat, you can spend a minute to recover
        half your expended ammunition (rounded down).

        Returns:
            Dict of recovered ammunition by type
        """
        recovered = {}

        for ammo_type, used in self.combat_used.items():
            # Recover half, rounded down
            recovery_amount = used // 2
            if recovery_amount > 0:
                self.add_ammunition(ammo_type, recovery_amount)
                recovered[ammo_type] = recovery_amount

        # Clear combat tracking
        self.combat_used.clear()

        return recovered

    def start_combat(self) -> None:
        """Reset combat tracking for a new combat."""
        self.combat_used.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "ammunition": dict(self.ammunition),
            "combat_used": dict(self.combat_used),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AmmunitionTracker":
        """Create from dictionary."""
        return cls(
            ammunition=data.get("ammunition", {}),
            combat_used=data.get("combat_used", {}),
        )


def get_weapon_ammunition_type(weapon_name: str) -> Optional[str]:
    """
    Get the ammunition type required by a weapon.

    Args:
        weapon_name: Name of the weapon (normalized to lowercase with underscores)

    Returns:
        Ammunition type string or None if weapon doesn't use ammunition
    """
    # Normalize weapon name
    normalized = weapon_name.lower().replace(" ", "_").replace("-", "_")

    ammo_type = WEAPON_AMMUNITION.get(normalized)
    if ammo_type:
        return ammo_type.value

    return None


def check_ammunition_for_attack(
    ammunition_tracker: Optional[AmmunitionTracker],
    weapon_name: str,
    weapon_properties: list
) -> Dict[str, Any]:
    """
    Check if character has ammunition for a ranged attack.

    Args:
        ammunition_tracker: Character's ammunition tracker (can be None)
        weapon_name: Name of the weapon being used
        weapon_properties: List of weapon properties

    Returns:
        Dict with:
        - has_ammunition: True if attack can proceed
        - ammo_type: Type of ammunition needed (or None)
        - remaining: Count remaining after this attack
        - message: Descriptive message
    """
    # Check if weapon requires ammunition
    if "ammunition" not in [p.lower() for p in weapon_properties]:
        return {
            "has_ammunition": True,
            "ammo_type": None,
            "remaining": None,
            "message": "Weapon does not require ammunition"
        }

    # Get ammunition type for this weapon
    ammo_type = get_weapon_ammunition_type(weapon_name)

    if not ammo_type:
        # Weapon requires ammo but we don't know the type - assume generic
        ammo_type = "arrow"  # Default fallback

    # Check if tracker exists
    if ammunition_tracker is None:
        # No tracking - assume infinite ammunition
        return {
            "has_ammunition": True,
            "ammo_type": ammo_type,
            "remaining": None,
            "message": "Ammunition not tracked"
        }

    # Check ammunition count
    current = ammunition_tracker.get_ammunition_count(ammo_type)

    if current <= 0:
        return {
            "has_ammunition": False,
            "ammo_type": ammo_type,
            "remaining": 0,
            "message": f"Out of {ammo_type}s!"
        }

    return {
        "has_ammunition": True,
        "ammo_type": ammo_type,
        "remaining": current,
        "message": f"{current} {ammo_type}s remaining"
    }


def consume_ammunition_for_attack(
    ammunition_tracker: AmmunitionTracker,
    weapon_name: str,
    weapon_properties: list
) -> Dict[str, Any]:
    """
    Consume ammunition for a ranged attack.

    Args:
        ammunition_tracker: Character's ammunition tracker
        weapon_name: Name of the weapon being used
        weapon_properties: List of weapon properties

    Returns:
        Dict with:
        - consumed: True if ammunition was consumed
        - ammo_type: Type of ammunition consumed
        - remaining: Count remaining after consumption
        - message: Descriptive message
    """
    if "ammunition" not in [p.lower() for p in weapon_properties]:
        return {
            "consumed": False,
            "ammo_type": None,
            "remaining": None,
            "message": "Weapon does not require ammunition"
        }

    ammo_type = get_weapon_ammunition_type(weapon_name)
    if not ammo_type:
        ammo_type = "arrow"

    success = ammunition_tracker.use_ammunition(ammo_type)
    remaining = ammunition_tracker.get_ammunition_count(ammo_type)

    if success:
        return {
            "consumed": True,
            "ammo_type": ammo_type,
            "remaining": remaining,
            "message": f"Used 1 {ammo_type}. {remaining} remaining."
        }
    else:
        return {
            "consumed": False,
            "ammo_type": ammo_type,
            "remaining": 0,
            "message": f"Out of {ammo_type}s!"
        }
