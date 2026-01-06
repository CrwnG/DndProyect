"""
Equipment and Inventory System.

D&D 5e equipment rules:
- Characters have equipment slots (main hand, off-hand, armor, etc.)
- Can carry items up to carrying capacity (STR × 15 lbs)
- Drawing/sheathing a weapon costs free object interaction (1 per turn)
- Switching weapons mid-combat requires planning
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class EquipmentSlot(str, Enum):
    """Equipment slot types - BG3-style paper doll layout."""
    # Weapons
    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    RANGED = "ranged"  # Quick-access ranged weapon

    # Protection
    ARMOR = "armor"
    SHIELD = "shield"
    HEAD = "head"  # Helmet, circlet, hat
    CLOAK = "cloak"  # Cloak, cape
    GLOVES = "gloves"  # Gauntlets, gloves
    BOOTS = "boots"  # Boots, shoes

    # Accessories
    AMULET = "amulet"  # Necklace, amulet
    BELT = "belt"  # Belt, girdle
    RING_1 = "ring_1"  # Ring slot 1
    RING_2 = "ring_2"  # Ring slot 2

    # Consumables
    AMMUNITION = "ammunition"


class ItemRarity(str, Enum):
    """D&D item rarity levels with associated colors."""
    COMMON = "common"          # Gray #9d9d9d
    UNCOMMON = "uncommon"      # Green #1eff00
    RARE = "rare"              # Blue #0070dd
    VERY_RARE = "very_rare"    # Purple #a335ee
    LEGENDARY = "legendary"    # Orange #ff8000
    ARTIFACT = "artifact"      # Gold #e6cc80


@dataclass
class InventoryItem:
    """A single item in inventory or equipment."""
    id: str
    name: str
    weight: float = 0.0  # in lbs
    quantity: int = 1
    item_type: str = "misc"  # weapon, armor, consumable, misc, accessory
    properties: List[str] = field(default_factory=list)
    icon: str = "📦"

    # Item metadata
    rarity: str = "common"  # ItemRarity value
    value: int = 0  # Gold piece value
    description: str = ""
    requires_attunement: bool = False
    is_attuned: bool = False
    valid_slots: List[str] = field(default_factory=list)  # Which slots this can equip to

    # Weapon-specific
    damage: Optional[str] = None
    damage_type: Optional[str] = None
    range: Optional[int] = None  # Normal range in feet
    long_range: Optional[int] = None  # Long range (disadvantage)
    mastery: Optional[str] = None  # 2024 weapon mastery type

    # Armor-specific
    ac_bonus: Optional[int] = None
    max_dex_bonus: Optional[int] = None
    strength_requirement: Optional[int] = None
    stealth_disadvantage: bool = False
    don_time: Optional[str] = None  # Time to put on armor (e.g., "1 minute", "10 minutes")
    doff_time: Optional[str] = None  # Time to remove armor

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "weight": self.weight,
            "quantity": self.quantity,
            "item_type": self.item_type,
            "properties": self.properties,
            "icon": self.icon,
            "rarity": self.rarity,
            "value": self.value,
            "description": self.description,
            "requires_attunement": self.requires_attunement,
            "is_attuned": self.is_attuned,
            "valid_slots": self.valid_slots,
            "damage": self.damage,
            "damage_type": self.damage_type,
            "range": self.range,
            "long_range": self.long_range,
            "mastery": self.mastery,
            "ac_bonus": self.ac_bonus,
            "max_dex_bonus": self.max_dex_bonus,
            "strength_requirement": self.strength_requirement,
            "stealth_disadvantage": self.stealth_disadvantage,
            "don_time": self.don_time,
            "doff_time": self.doff_time,
        }


@dataclass
class CharacterEquipment:
    """Full equipment and inventory tracking for a character - BG3-style paper doll."""

    # Weapons (equipped and ready)
    main_hand: Optional[InventoryItem] = None
    off_hand: Optional[InventoryItem] = None
    ranged: Optional[InventoryItem] = None  # Quick-draw ranged weapon

    # Protection gear
    armor: Optional[InventoryItem] = None
    head: Optional[InventoryItem] = None  # Helmet, circlet
    cloak: Optional[InventoryItem] = None  # Cloak, cape
    gloves: Optional[InventoryItem] = None  # Gauntlets, gloves
    boots: Optional[InventoryItem] = None  # Boots, shoes

    # Accessories
    amulet: Optional[InventoryItem] = None  # Necklace, amulet
    belt: Optional[InventoryItem] = None  # Belt, girdle
    ring_1: Optional[InventoryItem] = None  # Ring slot 1
    ring_2: Optional[InventoryItem] = None  # Ring slot 2

    # Inventory (backpack, belt pouches, etc.)
    inventory: List[InventoryItem] = field(default_factory=list)

    # Capacity tracking
    carrying_capacity: float = 150.0  # STR × 15
    current_weight: float = 0.0

    # Turn resource for weapon switching
    object_interaction_used: bool = False

    # Attunement tracking (D&D: max 3 attuned items)
    max_attunement_slots: int = 3

    def can_carry(self, item: InventoryItem) -> bool:
        """Check if character can carry an additional item."""
        return (self.current_weight + item.weight * item.quantity) <= self.carrying_capacity

    def get_encumbrance_status(self, strength: int = 10) -> Dict[str, Any]:
        """
        Calculate encumbrance status based on D&D 5e rules.

        Variant Encumbrance Rules:
        - Encumbered (>5×STR lbs): Speed -10ft
        - Heavily Encumbered (>10×STR lbs): Speed -20ft, disadvantage on ability checks,
          attack rolls, and saving throws using STR, DEX, or CON

        Args:
            strength: Character's Strength score

        Returns:
            Dict with status, speed_penalty, and other encumbrance info
        """
        encumbered_threshold = strength * 5
        heavily_threshold = strength * 10
        max_capacity = strength * 15

        self.calculate_weight()

        if self.current_weight > heavily_threshold:
            return {
                "status": "heavily_encumbered",
                "speed_penalty": 20,
                "disadvantage_on_physical": True,
                "current_weight": self.current_weight,
                "encumbered_threshold": encumbered_threshold,
                "heavily_threshold": heavily_threshold,
                "max_capacity": max_capacity,
                "description": "Heavily Encumbered: -20ft speed, disadvantage on physical checks"
            }
        elif self.current_weight > encumbered_threshold:
            return {
                "status": "encumbered",
                "speed_penalty": 10,
                "disadvantage_on_physical": False,
                "current_weight": self.current_weight,
                "encumbered_threshold": encumbered_threshold,
                "heavily_threshold": heavily_threshold,
                "max_capacity": max_capacity,
                "description": "Encumbered: -10ft speed"
            }
        else:
            return {
                "status": "normal",
                "speed_penalty": 0,
                "disadvantage_on_physical": False,
                "current_weight": self.current_weight,
                "encumbered_threshold": encumbered_threshold,
                "heavily_threshold": heavily_threshold,
                "max_capacity": max_capacity,
                "description": "Normal"
            }

    def check_armor_str_requirement(self, strength: int = 10) -> Dict[str, Any]:
        """
        Check if character meets armor strength requirements.

        D&D 5e: If you wear armor with a STR requirement you don't meet,
        your speed is reduced by 10ft.

        Args:
            strength: Character's Strength score

        Returns:
            Dict with requirement status and speed penalty
        """
        if not self.armor:
            return {"meets_requirement": True, "speed_penalty": 0}

        str_req = self.armor.strength_requirement
        if str_req and strength < str_req:
            return {
                "meets_requirement": False,
                "speed_penalty": 10,
                "required_strength": str_req,
                "current_strength": strength,
                "description": f"Heavy Armor requires {str_req} STR (you have {strength}). Speed -10ft."
            }

        return {"meets_requirement": True, "speed_penalty": 0}

    def get_available_weapons(self) -> List[InventoryItem]:
        """Get weapons that can be used this turn without switching."""
        weapons = []

        if self.main_hand and self.main_hand.damage:
            weapons.append(self.main_hand)

        if self.off_hand and self.off_hand.damage:
            weapons.append(self.off_hand)

        if self.ranged and self.ranged.damage:
            weapons.append(self.ranged)

        # Always have unarmed strike available
        weapons.append(InventoryItem(
            id="unarmed",
            name="Unarmed Strike",
            weight=0,
            item_type="weapon",
            damage="1",
            damage_type="bludgeoning",
            icon="✊"
        ))

        return weapons

    def get_inventory_weapons(self) -> List[InventoryItem]:
        """Get weapons in inventory that require drawing."""
        return [item for item in self.inventory if item.damage is not None]

    def can_switch_weapon(self) -> bool:
        """Check if object interaction is still available for weapon switching."""
        return not self.object_interaction_used

    def switch_weapon(self, to_item_id: str, slot: str = "main_hand") -> bool:
        """
        Switch a weapon using object interaction.

        Args:
            to_item_id: ID of weapon in inventory to draw
            slot: Which slot to equip to (main_hand, off_hand, ranged)

        Returns:
            True if switch successful, False otherwise
        """
        if self.object_interaction_used:
            return False

        # Find item in inventory
        item = next((i for i in self.inventory if i.id == to_item_id), None)
        if not item:
            return False

        # Get current item in slot
        current = getattr(self, slot, None)

        # Swap: put current back in inventory, equip new item
        if current:
            self.inventory.append(current)

        setattr(self, slot, item)
        self.inventory.remove(item)

        # Mark object interaction as used
        self.object_interaction_used = True
        return True

    def reset_turn(self):
        """Reset turn-based resources."""
        self.object_interaction_used = False

    def calculate_weight(self) -> float:
        """Calculate total weight of all equipment and inventory."""
        total = 0.0

        # All equipment slots
        equipped_items = [
            self.main_hand, self.off_hand, self.ranged,
            self.armor, self.head, self.cloak, self.gloves, self.boots,
            self.amulet, self.belt, self.ring_1, self.ring_2
        ]

        for item in equipped_items:
            if item:
                total += item.weight * item.quantity

        for item in self.inventory:
            total += item.weight * item.quantity

        self.current_weight = total
        return total

    def get_all_equipped(self) -> Dict[str, Optional[InventoryItem]]:
        """Get all equipped items as a dictionary."""
        return {
            "main_hand": self.main_hand,
            "off_hand": self.off_hand,
            "ranged": self.ranged,
            "armor": self.armor,
            "head": self.head,
            "cloak": self.cloak,
            "gloves": self.gloves,
            "boots": self.boots,
            "amulet": self.amulet,
            "belt": self.belt,
            "ring_1": self.ring_1,
            "ring_2": self.ring_2,
        }

    def get_attuned_count(self) -> int:
        """Count currently attuned items."""
        count = 0
        for item in self.get_all_equipped().values():
            if item and item.is_attuned:
                count += 1
        for item in self.inventory:
            if item.is_attuned:
                count += 1
        return count

    def can_attune(self) -> bool:
        """Check if character can attune to another item."""
        return self.get_attuned_count() < self.max_attunement_slots

    def equip_item(self, item_id: str, slot: str) -> bool:
        """
        Equip an item from inventory to a specific slot.

        Args:
            item_id: ID of item in inventory
            slot: Target equipment slot

        Returns:
            True if equipped successfully
        """
        # Find item in inventory
        item = next((i for i in self.inventory if i.id == item_id), None)
        if not item:
            return False

        # Check if slot is valid
        if not hasattr(self, slot):
            return False

        # Get current item in slot
        current = getattr(self, slot, None)

        # Swap: put current back in inventory, equip new item
        if current:
            self.inventory.append(current)

        setattr(self, slot, item)
        self.inventory.remove(item)
        self.calculate_weight()
        return True

    def unequip_item(self, slot: str) -> bool:
        """
        Unequip an item from a slot to inventory.

        Args:
            slot: Equipment slot to unequip

        Returns:
            True if unequipped successfully
        """
        if not hasattr(self, slot):
            return False

        current = getattr(self, slot, None)
        if not current:
            return False

        self.inventory.append(current)
        setattr(self, slot, None)
        self.calculate_weight()
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            # Weapons
            "main_hand": self.main_hand.to_dict() if self.main_hand else None,
            "off_hand": self.off_hand.to_dict() if self.off_hand else None,
            "ranged": self.ranged.to_dict() if self.ranged else None,
            # Protection
            "armor": self.armor.to_dict() if self.armor else None,
            "head": self.head.to_dict() if self.head else None,
            "cloak": self.cloak.to_dict() if self.cloak else None,
            "gloves": self.gloves.to_dict() if self.gloves else None,
            "boots": self.boots.to_dict() if self.boots else None,
            # Accessories
            "amulet": self.amulet.to_dict() if self.amulet else None,
            "belt": self.belt.to_dict() if self.belt else None,
            "ring_1": self.ring_1.to_dict() if self.ring_1 else None,
            "ring_2": self.ring_2.to_dict() if self.ring_2 else None,
            # Inventory
            "inventory": [item.to_dict() for item in self.inventory],
            "carrying_capacity": self.carrying_capacity,
            "current_weight": self.current_weight,
            "object_interaction_used": self.object_interaction_used,
            "max_attunement_slots": self.max_attunement_slots,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterEquipment":
        """Create CharacterEquipment from dictionary."""
        def item_from_dict(d):
            if d is None:
                return None

            # Parse armor_class string if present and ac_bonus not already set
            ac_bonus = d.get("ac_bonus")
            max_dex_bonus = d.get("max_dex_bonus")

            # If armor_class string exists and ac_bonus isn't set, parse it
            armor_class_str = d.get("armor_class")
            if armor_class_str and ac_bonus is None:
                from app.core.rules_engine import parse_armor_class_string
                parsed = parse_armor_class_string(armor_class_str)
                ac_bonus = parsed["base_ac"]
                # Only set max_dex_bonus from parsing if not already specified
                if max_dex_bonus is None:
                    max_dex_bonus = parsed["max_dex_bonus"]

            # Handle both old format (without new fields) and new format
            return InventoryItem(
                id=d.get("id", "unknown"),
                name=d.get("name", "Unknown Item"),
                weight=d.get("weight", 0.0),
                quantity=d.get("quantity", 1),
                item_type=d.get("item_type", "misc"),
                properties=d.get("properties", []),
                icon=d.get("icon", "📦"),
                rarity=d.get("rarity", "common"),
                value=d.get("value", 0),
                description=d.get("description", ""),
                requires_attunement=d.get("requires_attunement", False),
                is_attuned=d.get("is_attuned", False),
                valid_slots=d.get("valid_slots", []),
                damage=d.get("damage"),
                damage_type=d.get("damage_type"),
                range=d.get("range"),
                long_range=d.get("long_range"),
                mastery=d.get("mastery"),
                ac_bonus=ac_bonus,
                max_dex_bonus=max_dex_bonus,
                strength_requirement=d.get("strength_requirement"),
                stealth_disadvantage=d.get("stealth_disadvantage", False),
                don_time=d.get("don_time"),
                doff_time=d.get("doff_time"),
            )

        return cls(
            # Weapons
            main_hand=item_from_dict(data.get("main_hand")),
            off_hand=item_from_dict(data.get("off_hand")),
            ranged=item_from_dict(data.get("ranged")),
            # Protection
            armor=item_from_dict(data.get("armor")),
            head=item_from_dict(data.get("head")),
            cloak=item_from_dict(data.get("cloak")),
            gloves=item_from_dict(data.get("gloves")),
            boots=item_from_dict(data.get("boots")),
            # Accessories
            amulet=item_from_dict(data.get("amulet")),
            belt=item_from_dict(data.get("belt")),
            ring_1=item_from_dict(data.get("ring_1")),
            ring_2=item_from_dict(data.get("ring_2")),
            # Inventory
            inventory=[item_from_dict(i) for i in data.get("inventory", [])],
            carrying_capacity=data.get("carrying_capacity", 150.0),
            current_weight=data.get("current_weight", 0.0),
            object_interaction_used=data.get("object_interaction_used", False),
            max_attunement_slots=data.get("max_attunement_slots", 3),
        )

    def calculate_ac(self, dexterity: int = 10) -> Dict[str, Any]:
        """
        Calculate AC from equipped armor and shield.

        D&D 5e Armor Rules:
        - Unarmored: 10 + DEX mod
        - Light Armor: armor base + DEX mod
        - Medium Armor: armor base + DEX mod (max +2)
        - Heavy Armor: armor base only (no DEX)
        - Shield: +2 AC

        Args:
            dexterity: Character's dexterity score

        Returns:
            Dict with AC breakdown
        """
        dex_mod = (dexterity - 10) // 2
        base_ac = 10  # Unarmored
        armor_name = "Unarmored"
        effective_dex = dex_mod
        shield_bonus = 0
        magic_bonus = 0

        # Check for equipped armor
        if self.armor:
            if self.armor.ac_bonus is not None:
                base_ac = self.armor.ac_bonus
                armor_name = self.armor.name

                # Apply max DEX bonus based on armor type
                if self.armor.max_dex_bonus is not None:
                    effective_dex = min(dex_mod, self.armor.max_dex_bonus)
                elif self.armor.max_dex_bonus == 0:
                    # Heavy armor - no DEX bonus
                    effective_dex = 0

                # Check for magic armor bonus
                if "+1" in self.armor.name:
                    magic_bonus += 1
                elif "+2" in self.armor.name:
                    magic_bonus += 2
                elif "+3" in self.armor.name:
                    magic_bonus += 3

        # Check for shield in off-hand
        if self.off_hand and self.off_hand.item_type == "shield":
            shield_bonus = self.off_hand.ac_bonus or 2  # Default shield is +2

            # Magic shield bonus
            if "+1" in self.off_hand.name:
                magic_bonus += 1
            elif "+2" in self.off_hand.name:
                magic_bonus += 2
            elif "+3" in self.off_hand.name:
                magic_bonus += 3

        # Calculate total AC
        total_ac = base_ac + effective_dex + shield_bonus + magic_bonus

        # Check for other AC bonuses from accessories
        other_bonus = 0
        for item in [self.ring_1, self.ring_2, self.amulet, self.cloak]:
            if item and item.ac_bonus:
                other_bonus += item.ac_bonus

        total_ac += other_bonus

        return {
            "total_ac": total_ac,
            "base_ac": base_ac,
            "armor_name": armor_name,
            "dex_bonus": effective_dex,
            "dex_mod": dex_mod,
            "max_dex_bonus": self.armor.max_dex_bonus if self.armor else None,
            "shield_bonus": shield_bonus,
            "magic_bonus": magic_bonus,
            "other_bonus": other_bonus,
            "breakdown": f"{base_ac} (base) + {effective_dex} (DEX) + {shield_bonus} (shield) + {magic_bonus} (magic) + {other_bonus} (other) = {total_ac}",
        }

    def get_weapon_stats(self, weapon_slot: str = "main_hand") -> Optional[Dict[str, Any]]:
        """
        Get stats for a weapon in a specific slot.

        Args:
            weapon_slot: Which slot to get weapon from (main_hand, off_hand, ranged)

        Returns:
            Dict with weapon stats or None if no weapon
        """
        weapon = getattr(self, weapon_slot, None)
        if not weapon or not weapon.damage:
            return None

        # Check for magic weapon bonus
        magic_bonus = 0
        if "+1" in weapon.name:
            magic_bonus = 1
        elif "+2" in weapon.name:
            magic_bonus = 2
        elif "+3" in weapon.name:
            magic_bonus = 3

        return {
            "id": weapon.id,
            "name": weapon.name,
            "damage": weapon.damage,
            "damage_type": weapon.damage_type or "bludgeoning",
            "properties": weapon.properties,
            "range": weapon.range or 5,
            "long_range": weapon.long_range,
            "mastery": weapon.mastery,
            "magic_bonus": magic_bonus,
            "is_finesse": "finesse" in weapon.properties,
            "is_two_handed": "two-handed" in weapon.properties or "two_handed" in weapon.properties,
            "is_light": "light" in weapon.properties,
            "is_heavy": "heavy" in weapon.properties,
            "is_versatile": "versatile" in weapon.properties,
            "is_ranged": "ammunition" in weapon.properties or "thrown" in weapon.properties,
        }

    @property
    def total_weight(self) -> float:
        """Get total carried weight."""
        self.calculate_weight()
        return self.current_weight
