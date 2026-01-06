"""
Equipment API Routes.

Provides endpoints for equipment management:
- GET equipment state
- POST equip/unequip items
- GET available items from rules data
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import json
from pathlib import Path

from app.models.equipment import CharacterEquipment, InventoryItem, EquipmentSlot, ItemRarity
from app.core.combat_storage import active_combats

router = APIRouter(prefix="/equipment", tags=["equipment"])


# ============================================================================
# Request/Response Models
# ============================================================================

class EquipItemRequest(BaseModel):
    """Request to equip an item."""
    item_id: str
    slot: str


class UnequipItemRequest(BaseModel):
    """Request to unequip an item."""
    slot: str


class SwapSlotsRequest(BaseModel):
    """Request to swap items between slots."""
    from_slot: str
    to_slot: str


class EquipmentResponse(BaseModel):
    """Equipment state response."""
    equipped: Dict[str, Any]
    inventory: List[Dict[str, Any]]
    carrying_capacity: float
    current_weight: float
    encumbrance_status: str  # "normal", "encumbered", "heavily_encumbered"


class ItemDataResponse(BaseModel):
    """Item data from rules."""
    weapons: List[Dict[str, Any]]
    armor: List[Dict[str, Any]]
    gear: List[Dict[str, Any]]


# ============================================================================
# Helper Functions
# ============================================================================

def get_equipment_from_combat(combat_id: str, combatant_id: str) -> Optional[CharacterEquipment]:
    """Get equipment for a combatant in an active combat."""
    if combat_id not in active_combats:
        return None

    # active_combats stores CombatEngine objects directly, not dicts
    engine = active_combats[combat_id]
    if not engine:
        return None

    # Get combatant stats which contains equipment
    stats = engine.state.combatant_stats.get(combatant_id, {})
    equipment_data = stats.get("equipment")

    if equipment_data:
        if isinstance(equipment_data, CharacterEquipment):
            return equipment_data
        elif isinstance(equipment_data, dict):
            return CharacterEquipment.from_dict(equipment_data)

    return CharacterEquipment()


def calculate_encumbrance_status(equipment: CharacterEquipment, strength: int = 10) -> str:
    """
    Calculate encumbrance status based on D&D 5e variant rules.

    Normal: up to STR × 5 lbs
    Encumbered: STR × 5 to STR × 10 lbs (-10 speed)
    Heavily Encumbered: STR × 10 to STR × 15 lbs (-20 speed, disadvantage)
    """
    weight = equipment.current_weight
    normal_limit = strength * 5
    encumbered_limit = strength * 10
    max_capacity = strength * 15

    if weight <= normal_limit:
        return "normal"
    elif weight <= encumbered_limit:
        return "encumbered"
    elif weight <= max_capacity:
        return "heavily_encumbered"
    else:
        return "over_capacity"


def load_item_data() -> ItemDataResponse:
    """Load all item data from JSON files."""
    data_path = Path(__file__).parent.parent.parent / "data" / "rules" / "2024" / "equipment"

    weapons = []
    armor = []
    gear = []

    # Load weapons
    weapons_file = data_path / "weapons.json"
    if weapons_file.exists():
        with open(weapons_file, "r", encoding="utf-8") as f:
            weapons_data = json.load(f)
            weapons = weapons_data.get("weapons", [])

    # Load armor
    armor_file = data_path / "armor.json"
    if armor_file.exists():
        with open(armor_file, "r", encoding="utf-8") as f:
            armor_data = json.load(f)
            armor = armor_data.get("armor", [])

    # Load adventuring gear
    gear_file = data_path / "adventuring_gear.json"
    if gear_file.exists():
        with open(gear_file, "r", encoding="utf-8") as f:
            gear_data = json.load(f)
            gear = gear_data.get("gear", gear_data.get("items", []))

    return ItemDataResponse(weapons=weapons, armor=armor, gear=gear)


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/items")
async def get_all_items() -> ItemDataResponse:
    """Get all available items from equipment data files."""
    return load_item_data()


@router.get("/items/weapons")
async def get_weapons() -> List[Dict[str, Any]]:
    """Get all weapons with mastery properties."""
    data = load_item_data()
    return data.weapons


@router.get("/items/armor")
async def get_armor() -> List[Dict[str, Any]]:
    """Get all armor types."""
    data = load_item_data()
    return data.armor


@router.get("/items/gear")
async def get_gear() -> List[Dict[str, Any]]:
    """Get all adventuring gear."""
    data = load_item_data()
    return data.gear


@router.get("/{combat_id}/{combatant_id}")
async def get_equipment(combat_id: str, combatant_id: str) -> EquipmentResponse:
    """
    Get full equipment state for a combatant.

    Returns equipped items, inventory, weight, and encumbrance status.
    """
    equipment = get_equipment_from_combat(combat_id, combatant_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="Combat or combatant not found")

    equipment.calculate_weight()

    # Get strength for encumbrance calculation
    if combat_id in active_combats:
        engine = active_combats[combat_id]
        stats = engine.state.combatant_stats.get(combatant_id, {}) if engine else {}
        strength = stats.get("strength", 10)
    else:
        strength = 10

    return EquipmentResponse(
        equipped={k: v.to_dict() if v else None for k, v in equipment.get_all_equipped().items()},
        inventory=[item.to_dict() for item in equipment.inventory],
        carrying_capacity=equipment.carrying_capacity,
        current_weight=equipment.current_weight,
        encumbrance_status=calculate_encumbrance_status(equipment, strength),
    )


@router.post("/{combat_id}/{combatant_id}/equip")
async def equip_item(
    combat_id: str,
    combatant_id: str,
    request: EquipItemRequest
) -> Dict[str, Any]:
    """
    Equip an item from inventory to a slot.

    Args:
        combat_id: Active combat ID
        combatant_id: Combatant ID
        request: Item ID and target slot

    Returns:
        Updated equipment state and success status
    """
    equipment = get_equipment_from_combat(combat_id, combatant_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="Combat or combatant not found")

    # Validate slot
    valid_slots = [slot.value for slot in EquipmentSlot]
    if request.slot not in valid_slots:
        raise HTTPException(status_code=400, detail=f"Invalid slot: {request.slot}")

    # Check combat restrictions for armor
    if request.slot == "armor":
        # In combat, armor changes are restricted (takes 1-10 minutes per D&D rules)
        if combat_id in active_combats:
            raise HTTPException(
                status_code=400,
                detail="Cannot change armor during combat (requires 1-10 minutes to don/doff)"
            )

    # Find the item in equipment.inventory OR combatant_stats.inventory
    # Equipment.inventory holds items unequipped from slots
    # combatant_stats.inventory holds items picked up from ground
    item = next((i for i in equipment.inventory if i.id == request.item_id), None)

    # If not in equipment.inventory, check combatant_stats.inventory
    if not item:
        engine = active_combats.get(combat_id)
        if engine:
            stats = engine.state.combatant_stats.get(combatant_id, {})
            stats_inventory = stats.get("inventory", [])
            for i, inv_item in enumerate(stats_inventory):
                # Handle both dicts and InventoryItem objects
                if isinstance(inv_item, dict):
                    item_id = inv_item.get("id")
                else:
                    item_id = getattr(inv_item, "id", None)

                if item_id == request.item_id:
                    # Found in combatant_stats.inventory - convert to InventoryItem
                    if isinstance(inv_item, dict):
                        # Construct InventoryItem from dict fields
                        item = InventoryItem(
                            id=inv_item.get("id", ""),
                            name=inv_item.get("name", "Unknown"),
                            weight=inv_item.get("weight", 0.0),
                            quantity=inv_item.get("quantity", 1),
                            item_type=inv_item.get("item_type", "misc"),
                            properties=inv_item.get("properties", []),
                            icon=inv_item.get("icon", "📦"),
                            rarity=inv_item.get("rarity", "common"),
                            value=inv_item.get("value", 0),
                            description=inv_item.get("description", ""),
                            requires_attunement=inv_item.get("requires_attunement", False),
                            is_attuned=inv_item.get("is_attuned", False),
                            valid_slots=inv_item.get("valid_slots", []),
                            damage=inv_item.get("damage"),
                            damage_type=inv_item.get("damage_type"),
                            range=inv_item.get("range"),
                            long_range=inv_item.get("long_range"),
                            mastery=inv_item.get("mastery"),
                            ac_bonus=inv_item.get("ac_bonus"),
                            max_dex_bonus=inv_item.get("max_dex_bonus"),
                            strength_requirement=inv_item.get("strength_requirement"),
                            stealth_disadvantage=inv_item.get("stealth_disadvantage", False),
                            don_time=inv_item.get("don_time"),
                            doff_time=inv_item.get("doff_time"),
                        )
                    else:
                        item = inv_item
                    # Remove from combatant_stats.inventory
                    stats_inventory.pop(i)
                    engine.state.combatant_stats[combatant_id]["inventory"] = stats_inventory
                    # Add to equipment.inventory so equip_item() can find it
                    equipment.inventory.append(item)
                    break

    if not item:
        raise HTTPException(status_code=400, detail=f"Item '{request.item_id}' not found in inventory")

    # Validate weapon properties for slot restrictions
    if item.item_type == "weapon" and item.properties:
        properties = [p.lower() for p in item.properties]

        # Two-handed weapons can ONLY go in main_hand
        if "two-handed" in properties or "two_handed" in properties:
            if request.slot not in ["main_hand"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Two-handed weapons like {item.name} can only be equipped in main hand"
                )
            # Auto-unequip off_hand if equipping a two-handed weapon
            if equipment.off_hand:
                off_hand_item = equipment.off_hand
                equipment.inventory.append(off_hand_item)
                equipment.off_hand = None

        # Light weapons are required for off-hand (two-weapon fighting)
        if request.slot == "off_hand" and "light" not in properties:
            # Check if main hand is also light (or empty)
            main_weapon = equipment.main_hand
            if main_weapon and main_weapon.properties:
                main_properties = [p.lower() for p in main_weapon.properties]
                # Two-weapon fighting requires both weapons to be light
                # (unless you have the Dual Wielder feat, which we don't track here)
                if "light" not in main_properties:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Off-hand weapon must have 'Light' property for two-weapon fighting. {item.name} is not Light."
                    )

    # Attempt to equip
    success = equipment.equip_item(request.item_id, request.slot)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to equip item - item not found or invalid slot")

    # Update combat state
    if combat_id in active_combats:
        engine = active_combats[combat_id]
        if engine:
            engine.state.combatant_stats[combatant_id]["equipment"] = equipment.to_dict()

    # Get the updated combatant_stats inventory to return to frontend
    combat_inventory = []
    if combat_id in active_combats:
        engine = active_combats[combat_id]
        if engine:
            stats = engine.state.combatant_stats.get(combatant_id, {})
            combat_inventory = stats.get("inventory", [])
            # Convert to dicts if needed
            combat_inventory = [
                item if isinstance(item, dict) else item.to_dict() if hasattr(item, 'to_dict') else {"id": str(item)}
                for item in combat_inventory
            ]

    return {
        "success": True,
        "message": f"Equipped {request.item_id} to {request.slot}",
        "equipped": equipment.get_all_equipped()[request.slot].to_dict() if equipment.get_all_equipped()[request.slot] else None,
        "inventory": [item.to_dict() for item in equipment.inventory],
        "combat_inventory": combat_inventory,  # Also return combatant_stats.inventory
        "current_weight": equipment.current_weight,
    }


@router.post("/{combat_id}/{combatant_id}/unequip")
async def unequip_item(
    combat_id: str,
    combatant_id: str,
    request: UnequipItemRequest
) -> Dict[str, Any]:
    """
    Unequip an item from a slot to inventory.

    Args:
        combat_id: Active combat ID
        combatant_id: Combatant ID
        request: Slot to unequip

    Returns:
        Updated equipment state and success status
    """
    # Validate slot name
    valid_slots = ['main_hand', 'off_hand', 'ranged', 'armor', 'head', 'cloak',
                   'gloves', 'boots', 'amulet', 'belt', 'ring_1', 'ring_2']
    if request.slot not in valid_slots:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid slot '{request.slot}'. Valid slots: {', '.join(valid_slots)}"
        )

    equipment = get_equipment_from_combat(combat_id, combatant_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="Combat or combatant not found")

    # Check if slot has an item
    current_item = getattr(equipment, request.slot, None)
    if not current_item:
        # Slot is already empty - return success silently
        # This prevents errors from duplicate unequip calls
        return {
            "success": True,
            "message": f"Slot {request.slot} is already empty",
            "current_weight": equipment.current_weight,
        }

    item_name = current_item.name

    # Attempt to unequip
    success = equipment.unequip_item(request.slot)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to unequip '{item_name}' from {request.slot}"
        )

    # Update combat state
    if combat_id in active_combats:
        engine = active_combats[combat_id]
        if engine:
            engine.state.combatant_stats[combatant_id]["equipment"] = equipment.to_dict()

    return {
        "success": True,
        "message": f"Unequipped {item_name} from {request.slot}",
        "current_weight": equipment.current_weight,
    }


@router.post("/{combat_id}/{combatant_id}/swap")
async def swap_slots(
    combat_id: str,
    combatant_id: str,
    request: SwapSlotsRequest
) -> Dict[str, Any]:
    """
    Swap items between two equipment slots.

    Useful for swapping rings, switching main/off hand, etc.
    """
    equipment = get_equipment_from_combat(combat_id, combatant_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="Combat or combatant not found")

    # Get items from both slots
    from_item = getattr(equipment, request.from_slot, None)
    to_item = getattr(equipment, request.to_slot, None)

    # Perform swap
    setattr(equipment, request.from_slot, to_item)
    setattr(equipment, request.to_slot, from_item)

    # Update combat state
    if combat_id in active_combats:
        engine = active_combats[combat_id]
        if engine:
            engine.state.combatant_stats[combatant_id]["equipment"] = equipment.to_dict()

    return {
        "success": True,
        "message": f"Swapped {request.from_slot} and {request.to_slot}",
        "from_slot": equipment.get_all_equipped()[request.from_slot].to_dict() if equipment.get_all_equipped()[request.from_slot] else None,
        "to_slot": equipment.get_all_equipped()[request.to_slot].to_dict() if equipment.get_all_equipped()[request.to_slot] else None,
    }


@router.get("/slots")
async def get_equipment_slots() -> Dict[str, List[str]]:
    """Get all available equipment slots organized by category."""
    return {
        "weapons": ["main_hand", "off_hand", "ranged"],
        "protection": ["armor", "head", "cloak", "gloves", "boots"],
        "accessories": ["amulet", "belt", "ring_1", "ring_2"],
        "consumables": ["ammunition"],
    }


@router.get("/rarities")
async def get_item_rarities() -> List[Dict[str, str]]:
    """Get item rarity levels with their display colors."""
    return [
        {"id": "common", "name": "Common", "color": "#9d9d9d"},
        {"id": "uncommon", "name": "Uncommon", "color": "#1eff00"},
        {"id": "rare", "name": "Rare", "color": "#0070dd"},
        {"id": "very_rare", "name": "Very Rare", "color": "#a335ee"},
        {"id": "legendary", "name": "Legendary", "color": "#ff8000"},
        {"id": "artifact", "name": "Artifact", "color": "#e6cc80"},
    ]
