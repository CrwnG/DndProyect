"""
D&D 5e Loot & Treasure API Routes.

Endpoints for generating and distributing treasure from combat encounters.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.core.loot_system import (
    get_loot_generator,
    TreasureResult,
    TreasureType,
)
from app.core.combat_storage import active_combats
from app.database.dependencies import get_character_repo
from app.database.repositories import CharacterRepository
from app.database.models import CharacterUpdate


router = APIRouter(prefix="/loot", tags=["Loot & Treasure"])


# ============================================================================
# Request/Response Models
# ============================================================================

class GenerateLootRequest(BaseModel):
    """Request to generate loot from defeated enemies."""
    enemies: List[Dict[str, Any]] = Field(
        ...,
        description="List of defeated enemies with 'cr' or 'challenge_rating'"
    )
    difficulty: str = Field(
        default="medium",
        description="Encounter difficulty: easy, medium, hard, deadly"
    )
    is_boss: bool = Field(
        default=False,
        description="Whether this is a boss encounter (generates hoard treasure)"
    )


class CollectLootRequest(BaseModel):
    """Request to collect loot items."""
    character_id: str = Field(..., description="Character collecting the loot (gets items)")
    item_ids: List[str] = Field(
        default=[],
        description="Specific item IDs to collect (empty = all)"
    )
    take_coins: bool = Field(default=True, description="Whether to take coins")
    # Party gold division - gold is split equally among these characters
    party_character_ids: List[str] = Field(
        default=[],
        description="Character IDs to divide gold among (empty = all gold to collector)"
    )


class DistributeLootRequest(BaseModel):
    """Request to distribute loot among party members."""
    distribution: Dict[str, List[str]] = Field(
        ...,
        description="Map of character_id -> list of item IDs"
    )
    coin_split: Dict[str, float] = Field(
        default={},
        description="Map of character_id -> percentage of coins (0-1)"
    )


class LootResponse(BaseModel):
    """Loot generation response."""
    success: bool = True
    loot: Dict[str, Any]
    message: str = ""


class PreviewLootResponse(BaseModel):
    """Preview of possible loot for a CR."""
    cr: float
    treasure_type: str
    sample_loot: Dict[str, Any]
    avg_gold_value: float


# ============================================================================
# In-memory storage for pending loot
# ============================================================================

# Maps combat_id -> TreasureResult (loot waiting to be collected)
pending_loot: Dict[str, Dict[str, Any]] = {}

# Maps combat_id -> {"x,y": [items]} - items dropped on the ground
ground_items: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}


def _coins_to_gold(coins: Dict[str, int]) -> int:
    """Convert coin breakdown to gold pieces value."""
    # D&D coin conversion: 10cp = 1sp, 10sp = 1gp, 2ep = 1gp, 1pp = 10gp
    cp = coins.get("cp", 0)
    sp = coins.get("sp", 0)
    ep = coins.get("ep", 0)
    gp = coins.get("gp", 0)
    pp = coins.get("pp", 0)
    # Convert everything to gold (truncating fractions)
    total_gp = (cp // 100) + (sp // 10) + (ep // 2) + gp + (pp * 10)
    return total_gp


def _item_to_inventory_format(item: Dict[str, Any], item_type: str) -> Dict[str, Any]:
    """Convert loot item to inventory storage format."""
    return {
        "id": item.get("id", ""),
        "name": item.get("name", "Unknown Item"),
        "type": item_type,
        "rarity": item.get("rarity", "common"),
        "value_gp": item.get("value", item.get("value_gp", 0)),
        "description": item.get("description", ""),
        "requires_attunement": item.get("requires_attunement", False),
        "source": "loot",
    }


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/generate", response_model=LootResponse)
async def generate_loot(request: GenerateLootRequest):
    """
    Generate loot for defeated enemies.

    Call this when combat ends in victory to generate treasure.
    The generated loot is stored and can be retrieved/collected later.
    """
    generator = get_loot_generator()

    loot = generator.generate_encounter_loot(
        defeated_enemies=request.enemies,
        encounter_difficulty=request.difficulty,
        is_boss_encounter=request.is_boss
    )

    return LootResponse(
        success=True,
        loot=loot.to_dict(),
        message=f"Generated {'hoard' if request.is_boss else 'individual'} treasure (CR {loot.source_cr:.1f})"
    )


@router.get("/combat/{combat_id}", response_model=LootResponse)
async def get_combat_loot(combat_id: str):
    """
    Get loot from a completed combat encounter.

    Returns the pending loot for the combat, or generates it if not yet created.
    """
    # Check if loot was already generated
    if combat_id in pending_loot:
        return LootResponse(
            success=True,
            loot=pending_loot[combat_id],
            message="Loot retrieved from completed combat"
        )

    # Try to get combat engine directly (active_combats stores CombatEngine objects)
    engine = active_combats.get(combat_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Combat not found")

    # Get combat state with proper error handling
    try:
        if hasattr(engine, 'get_combat_state'):
            state = engine.get_combat_state()
        else:
            print(f"[LOOT ERROR] Engine has no get_combat_state, type: {type(engine)}")
            raise HTTPException(status_code=500, detail="Invalid combat engine")

        # Ensure state is a dict
        if not isinstance(state, dict):
            print(f"[LOOT ERROR] state is not a dict, type: {type(state)}")
            raise HTTPException(status_code=500, detail="Invalid combat state type")

    except AttributeError as e:
        print(f"[LOOT ERROR] Failed to get combat state: {e}")
        raise HTTPException(status_code=500, detail=f"Combat state error: {str(e)}")

    if not state.get("is_combat_over"):
        raise HTTPException(status_code=400, detail="Combat is not yet over")

    # Get defeated enemies from combat state
    defeated_enemies = []
    combatants = state.get("combatants", [])
    combatant_stats = state.get("combatant_stats", {})

    for c in combatants:
        cid = c.get("id", "")
        stats = combatant_stats.get(cid, {})

        # Enemy is defeated if type is enemy and is_active is False
        if stats.get("type") == "enemy" and not c.get("is_active", True):
            defeated_enemies.append({
                "id": cid,
                "name": c.get("name", "Unknown"),
                "cr": stats.get("cr", stats.get("challenge_rating", 0.25)),
            })

    if not defeated_enemies:
        return LootResponse(
            success=True,
            loot={"coins": {"cp": 0, "sp": 0, "ep": 0, "gp": 0, "pp": 0}},
            message="No defeated enemies - no loot generated"
        )

    # Generate loot
    generator = get_loot_generator()
    loot = generator.generate_encounter_loot(
        defeated_enemies=defeated_enemies,
        encounter_difficulty="medium",  # Default
        is_boss_encounter=len(defeated_enemies) == 1 and defeated_enemies[0].get("cr", 0) >= 5
    )

    # Store for later collection
    loot_dict = loot.to_dict()
    pending_loot[combat_id] = loot_dict

    return LootResponse(
        success=True,
        loot=loot_dict,
        message=f"Generated loot from {len(defeated_enemies)} defeated enemies"
    )


@router.post("/combat/{combat_id}/collect", response_model=LootResponse)
async def collect_loot(
    combat_id: str,
    request: CollectLootRequest,
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Collect loot from a completed combat.

    Transfers loot to the character's inventory and persists to database.
    """
    if combat_id not in pending_loot:
        # Try to generate loot first
        await get_combat_loot(combat_id)

    if combat_id not in pending_loot:
        raise HTTPException(status_code=404, detail="No loot available for this combat")

    loot = pending_loot[combat_id]

    # Get character from database
    character = await char_repo.get_by_id(request.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    # Build collected items list
    collected = {
        "character_id": request.character_id,
        "coins_collected": loot.get("coins", {}) if request.take_coins else {},
        "items_collected": [],
        "gems_collected": [],
        "art_collected": [],
        "total_value": loot.get("total_gold_value", 0),
    }

    # Prepare inventory additions
    new_inventory_items = []

    # Collect specific items or all
    if request.item_ids:
        # Collect specific items
        for item in loot.get("magic_items", []):
            if item.get("id") in request.item_ids:
                collected["items_collected"].append(item)
                new_inventory_items.append(_item_to_inventory_format(item, "magic_item"))
    else:
        # Collect all magic items
        for item in loot.get("magic_items", []):
            collected["items_collected"].append(item)
            new_inventory_items.append(_item_to_inventory_format(item, "magic_item"))

        # Collect gems (valuable, can be sold)
        for gem in loot.get("gems", []):
            collected["gems_collected"].append(gem)
            new_inventory_items.append(_item_to_inventory_format(gem, "gem"))

        # Collect art objects (valuable, can be sold)
        for art in loot.get("art_objects", []):
            collected["art_collected"].append(art)
            new_inventory_items.append(_item_to_inventory_format(art, "art_object"))

        # Collect mundane/consumable items (potions, scrolls, gear)
        for item in loot.get("mundane_items", []):
            collected["items_collected"].append(item)
            # Add directly to inventory with its existing format
            new_inventory_items.append({
                "id": item.get("id", ""),
                "name": item.get("name", "Unknown Item"),
                "type": item.get("type", "consumable"),
                "rarity": item.get("rarity", "common"),
                "value_gp": item.get("value_gp", 0),
                "description": item.get("description", ""),
                "source": "loot",
            })

    # Calculate gold from coins
    total_gold = 0
    if request.take_coins:
        total_gold = _coins_to_gold(loot.get("coins", {}))

    # Update collector's inventory (items go to the collector only)
    current_inventory = character.inventory or []
    updated_inventory = current_inventory + new_inventory_items

    # Gold division among party members
    gold_distribution = {}
    if request.party_character_ids and len(request.party_character_ids) > 0 and total_gold > 0:
        # Divide gold equally among party members
        party_size = len(request.party_character_ids)
        gold_per_member = total_gold // party_size
        remainder = total_gold % party_size

        print(f"[LOOT] Dividing {total_gold} gold among {party_size} party members ({gold_per_member} each)", flush=True)

        for i, char_id in enumerate(request.party_character_ids):
            # First member gets the remainder (if any)
            member_gold = gold_per_member + (remainder if i == 0 else 0)

            try:
                member_char = await char_repo.get_by_id(char_id)
                if member_char:
                    new_gold = (member_char.gold or 0) + member_gold
                    await char_repo.update(char_id, CharacterUpdate(gold=new_gold))
                    gold_distribution[char_id] = {
                        "name": member_char.name,
                        "gold_gained": member_gold,
                        "new_total": new_gold,
                    }
                    print(f"[LOOT] {member_char.name} gained {member_gold} gold (now {new_gold})", flush=True)
            except Exception as e:
                print(f"[LOOT ERROR] Failed to update gold for {char_id}: {e}", flush=True)

        # Update collector's inventory only (gold was distributed above)
        update_data = CharacterUpdate(inventory=updated_inventory)
        await char_repo.update(request.character_id, update_data)

        collected["gold_gained"] = total_gold
        collected["gold_per_member"] = gold_per_member
        collected["gold_distribution"] = gold_distribution
    else:
        # No party division - all gold goes to collector
        updated_gold = (character.gold or 0) + total_gold

        update_data = CharacterUpdate(
            inventory=updated_inventory,
            gold=updated_gold,
        )
        await char_repo.update(request.character_id, update_data)

        collected["gold_gained"] = total_gold
        collected["new_gold_total"] = updated_gold

    collected["items_added_to_inventory"] = len(new_inventory_items)

    # Clear pending loot after collection
    del pending_loot[combat_id]

    return LootResponse(
        success=True,
        loot=collected,
        message=f"Loot collected by {character.name}: {len(new_inventory_items)} items, {gold_gained} gp"
    )


@router.post("/combat/{combat_id}/distribute", response_model=LootResponse)
async def distribute_loot(
    combat_id: str,
    request: DistributeLootRequest,
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Distribute loot among multiple party members.

    Splits items and coins according to the distribution map.
    Persists all distributions to the database.
    """
    if combat_id not in pending_loot:
        raise HTTPException(status_code=404, detail="No loot available for this combat")

    loot = pending_loot[combat_id]
    coins = loot.get("coins", {})

    distribution_result = {}

    # Build item type lookup
    magic_item_ids = {item.get("id") for item in loot.get("magic_items", [])}
    gem_ids = {item.get("id") for item in loot.get("gems", [])}
    mundane_item_ids = {item.get("id") for item in loot.get("mundane_items", [])}

    # Distribute coins based on percentages
    for char_id, percentage in request.coin_split.items():
        if char_id not in distribution_result:
            distribution_result[char_id] = {"coins": {}, "items": [], "gold_gained": 0}

        char_coins = {
            coin_type: int(amount * percentage)
            for coin_type, amount in coins.items()
        }
        distribution_result[char_id]["coins"] = char_coins
        distribution_result[char_id]["gold_gained"] = _coins_to_gold(char_coins)

    # Distribute items based on assignment (include mundane items like consumables)
    all_items = (
        loot.get("magic_items", []) +
        loot.get("gems", []) +
        loot.get("art_objects", []) +
        loot.get("mundane_items", [])
    )
    item_map = {item.get("id", str(i)): item for i, item in enumerate(all_items)}

    for char_id, item_ids in request.distribution.items():
        if char_id not in distribution_result:
            distribution_result[char_id] = {"coins": {}, "items": [], "gold_gained": 0}

        for item_id in item_ids:
            if item_id in item_map:
                distribution_result[char_id]["items"].append(item_map[item_id])

    # Persist to database for each character
    for char_id, char_loot in distribution_result.items():
        character = await char_repo.get_by_id(char_id)
        if not character:
            continue  # Skip invalid character IDs

        # Convert items to inventory format
        new_inventory_items = []
        for item in char_loot["items"]:
            item_id = item.get("id", "")
            if item_id in magic_item_ids:
                item_type = "magic_item"
            elif item_id in gem_ids:
                item_type = "gem"
            elif item_id in mundane_item_ids:
                # Mundane/consumable items - add directly with their format
                new_inventory_items.append({
                    "id": item.get("id", ""),
                    "name": item.get("name", "Unknown Item"),
                    "type": item.get("type", "consumable"),
                    "rarity": item.get("rarity", "common"),
                    "value_gp": item.get("value_gp", 0),
                    "description": item.get("description", ""),
                    "source": "loot",
                })
                continue  # Skip the _item_to_inventory_format call
            else:
                item_type = "art_object"
            new_inventory_items.append(_item_to_inventory_format(item, item_type))

        # Update character inventory and gold
        current_inventory = character.inventory or []
        updated_inventory = current_inventory + new_inventory_items
        updated_gold = (character.gold or 0) + char_loot["gold_gained"]

        update_data = CharacterUpdate(
            inventory=updated_inventory,
            gold=updated_gold,
        )
        await char_repo.update(char_id, update_data)

        char_loot["new_gold_total"] = updated_gold
        char_loot["items_added"] = len(new_inventory_items)

    # Clear pending loot
    del pending_loot[combat_id]

    return LootResponse(
        success=True,
        loot={"distribution": distribution_result},
        message=f"Loot distributed to {len(distribution_result)} characters"
    )


@router.get("/preview/{cr}", response_model=PreviewLootResponse)
async def preview_loot(
    cr: float,
    treasure_type: str = Query(default="individual", description="individual or hoard")
):
    """
    Preview possible loot for a given CR.

    Useful for DM tools to see what treasure might be generated.
    Generates a sample and estimates average value.
    """
    generator = get_loot_generator()

    # Generate multiple samples to estimate average
    samples = []
    for _ in range(10):
        if treasure_type == "hoard":
            loot = generator.generate_hoard_loot(cr)
        else:
            loot = generator.generate_individual_loot(cr)
        samples.append(loot.total_gold_value)

    avg_value = sum(samples) / len(samples)

    # Generate one sample to return
    if treasure_type == "hoard":
        sample = generator.generate_hoard_loot(cr)
    else:
        sample = generator.generate_individual_loot(cr)

    return PreviewLootResponse(
        cr=cr,
        treasure_type=treasure_type,
        sample_loot=sample.to_dict(),
        avg_gold_value=round(avg_value, 2)
    )


@router.get("/tables")
async def get_treasure_tables():
    """
    Get the treasure table structure for reference.

    Returns information about how treasure is generated at different CRs.
    """
    return {
        "cr_tiers": {
            "cr_0_4": "Challenge Rating 0-4",
            "cr_5_10": "Challenge Rating 5-10",
            "cr_11_16": "Challenge Rating 11-16",
            "cr_17_plus": "Challenge Rating 17+",
        },
        "treasure_types": {
            "individual": "Per-creature loot (coins only)",
            "hoard": "Boss/lair treasure (coins, gems, art, magic items)",
        },
        "difficulty_multipliers": {
            "easy": 0.5,
            "medium": 1.0,
            "hard": 1.5,
            "deadly": 2.0,
        },
    }


# ============================================================================
# Item Management & Consumables
# ============================================================================

class GiveItemRequest(BaseModel):
    """Request to give an item to a character."""
    character_id: str
    item_id: str
    quantity: int = 1


class UseItemRequest(BaseModel):
    """Request to use a consumable item in combat."""
    combat_id: str
    combatant_id: str
    item_id: str
    target_id: Optional[str] = None  # For items that target others


class UseItemResponse(BaseModel):
    """Response from using an item."""
    success: bool
    message: str
    effect: Dict[str, Any] = {}
    combat_state: Optional[Dict[str, Any]] = None


# Consumable item definitions
CONSUMABLES = {
    "potion_of_healing": {
        "name": "Potion of Healing",
        "type": "potion",
        "action_type": "bonus_action",  # D&D 2024: drinking is a bonus action
        "effect": {"heal": "2d4+2"},
        "description": "Regain 2d4+2 HP"
    },
    "potion_of_greater_healing": {
        "name": "Potion of Greater Healing",
        "type": "potion",
        "action_type": "bonus_action",
        "effect": {"heal": "4d4+4"},
        "description": "Regain 4d4+4 HP"
    },
    "potion_of_superior_healing": {
        "name": "Potion of Superior Healing",
        "type": "potion",
        "action_type": "bonus_action",
        "effect": {"heal": "8d4+8"},
        "description": "Regain 8d4+8 HP"
    },
    "antitoxin": {
        "name": "Antitoxin",
        "type": "potion",
        "action_type": "action",
        "effect": {"advantage_poison_saves": True, "duration": "1 hour"},
        "description": "Advantage on saves vs poison for 1 hour"
    },
    # New consumables from loot drops
    "alchemists_fire": {
        "name": "Alchemist's Fire",
        "type": "thrown",
        "action_type": "action",
        "effect": {"damage": "1d4", "damage_type": "fire", "ongoing": True},
        "description": "Thrown weapon dealing 1d4 fire damage. Target takes damage at start of each turn until extinguished (action)."
    },
    "holy_water": {
        "name": "Holy Water",
        "type": "thrown",
        "action_type": "action",
        "effect": {"damage": "2d6", "damage_type": "radiant", "target_type": ["fiend", "undead"]},
        "description": "Thrown weapon dealing 2d6 radiant damage to fiends and undead."
    },
    "oil_of_slipperiness": {
        "name": "Oil of Slipperiness",
        "type": "oil",
        "action_type": "action",
        "effect": {"freedom_of_movement": True, "duration": "8 hours"},
        "description": "Apply to self. Gain effects of Freedom of Movement for 8 hours."
    },
    "potion_of_climbing": {
        "name": "Potion of Climbing",
        "type": "potion",
        "action_type": "bonus_action",
        "effect": {"climbing_speed": True, "advantage_climb": True, "duration": "1 hour"},
        "description": "Gain climbing speed equal to walking speed for 1 hour."
    },
    "scroll_of_cure_wounds": {
        "name": "Scroll of Cure Wounds",
        "type": "scroll",
        "action_type": "action",
        "effect": {"heal": "1d8+3"},  # 1d8 + spellcasting mod (assume +3)
        "description": "Cast Cure Wounds (1st level) - heals 1d8+3 HP."
    },
    "torch": {
        "name": "Torch",
        "type": "tool",
        "action_type": "action",
        "effect": {"light": True, "radius": 20, "damage": "1", "damage_type": "fire"},
        "description": "Provides bright light in 20ft radius. Can be used as improvised weapon (1 fire damage)."
    },
}


@router.post("/give-item", response_model=LootResponse)
async def give_item_to_character(
    request: GiveItemRequest,
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Give an item to a character (GM tool or for testing).

    Adds the specified item to the character's inventory.
    """
    # Get character
    character = await char_repo.get(request.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    # Look up item in consumables first, then gear
    item_data = CONSUMABLES.get(request.item_id)
    item_type = "consumable"

    if not item_data:
        # Try adventuring gear
        import json
        from pathlib import Path
        gear_path = Path(__file__).parent.parent.parent / "data" / "rules" / "2024" / "equipment" / "adventuring_gear.json"
        if gear_path.exists():
            with open(gear_path) as f:
                gear_list = json.load(f)
                for item in gear_list:
                    if item.get("id") == request.item_id:
                        item_data = item
                        item_type = "gear"
                        break

    if not item_data:
        raise HTTPException(status_code=404, detail=f"Item '{request.item_id}' not found")

    # Add to inventory
    current_inventory = character.inventory or []
    for _ in range(request.quantity):
        current_inventory.append({
            "id": request.item_id,
            "name": item_data.get("name", request.item_id),
            "type": item_type,
            "description": item_data.get("description", ""),
        })

    update_data = CharacterUpdate(inventory=current_inventory)
    await char_repo.update(request.character_id, update_data)

    return LootResponse(
        success=True,
        loot={"item": item_data, "quantity": request.quantity},
        message=f"Gave {request.quantity}x {item_data.get('name', request.item_id)} to {character.name}"
    )


@router.post("/use-item", response_model=UseItemResponse)
async def use_item_in_combat(request: UseItemRequest):
    """
    Use a consumable item during combat.

    Supports multiple item types:
    - Potions: Bonus action healing (D&D 2024 rules)
    - Thrown weapons: Action to throw at a target (alchemist's fire, holy water)
    - Buff items: Apply status effects (oil of slipperiness, antitoxin)
    - Scrolls: Cast the spell contained in the scroll

    Removes the item from inventory after use.
    """
    from app.core.dice import roll_damage

    # Get combat
    engine = active_combats.get(request.combat_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Combat not found")

    # Get combatant data
    combatant = engine.state.initiative_tracker.get_combatant(request.combatant_id)
    stats = engine.state.combatant_stats.get(request.combatant_id, {})

    if not combatant:
        raise HTTPException(status_code=404, detail="Combatant not found")

    # Check if item exists in inventory
    inventory = stats.get("inventory", [])
    item_index = None
    item_data = None

    for i, inv_item in enumerate(inventory):
        if inv_item.get("id") == request.item_id:
            item_index = i
            # Try exact match first, then try stripping numeric suffix (e.g., "potion_of_healing_1" -> "potion_of_healing")
            item_data = CONSUMABLES.get(request.item_id)
            if not item_data:
                # Strip numeric suffix like "_1", "_2", etc.
                import re
                base_id = re.sub(r'_\d+$', '', request.item_id)
                item_data = CONSUMABLES.get(base_id)
            break

    if item_index is None or item_data is None:
        raise HTTPException(
            status_code=400,
            detail=f"Item '{request.item_id}' not found in inventory or is not usable"
        )

    # Process the effect based on item type
    effect_result = {}
    item_type = item_data.get("type", "unknown")
    effect = item_data.get("effect", {})
    message_suffix = ""

    # === HEALING ITEMS (potions, scrolls with heal) ===
    if "heal" in effect:
        heal_dice = effect["heal"]
        heal_roll = roll_damage(heal_dice)
        heal_amount = heal_roll.total

        # Apply healing
        max_hp = stats.get("max_hp", combatant.max_hp)
        current_hp = stats.get("current_hp", combatant.current_hp)
        new_hp = min(max_hp, current_hp + heal_amount)

        # Update stats
        engine.state.combatant_stats[request.combatant_id]["current_hp"] = new_hp
        combatant.current_hp = new_hp

        effect_result = {
            "type": "heal",
            "dice": heal_dice,
            "rolled": heal_amount,
            "old_hp": current_hp,
            "new_hp": new_hp,
            "max_hp": max_hp
        }
        message_suffix = f" Healed for {heal_amount} HP!"

    # === THROWN DAMAGE ITEMS (alchemist's fire, holy water) ===
    elif item_type == "thrown" and "damage" in effect:
        if not request.target_id:
            raise HTTPException(
                status_code=400,
                detail="Thrown items require a target_id"
            )

        # Get target
        target = engine.state.initiative_tracker.get_combatant(request.target_id)
        target_stats = engine.state.combatant_stats.get(request.target_id, {})

        if not target:
            raise HTTPException(status_code=404, detail="Target not found")

        # Check target type restriction (e.g., holy water only affects undead/fiends)
        target_type_restriction = effect.get("target_type", [])
        target_creature_type = target_stats.get("creature_type", "humanoid").lower()

        if target_type_restriction and target_creature_type not in target_type_restriction:
            # Holy water doesn't affect non-undead/non-fiends but still consumed
            effect_result = {
                "type": "no_effect",
                "reason": f"{item_data['name']} has no effect on {target_creature_type} creatures"
            }
            message_suffix = f" The {item_data['name']} has no effect on {target.name}!"
        else:
            # Roll damage
            damage_dice = effect["damage"]
            damage_roll = roll_damage(damage_dice)
            damage_amount = damage_roll.total
            damage_type = effect.get("damage_type", "fire")

            # Apply damage to target
            target_current_hp = target_stats.get("current_hp", target.current_hp)
            target_new_hp = max(0, target_current_hp - damage_amount)

            engine.state.combatant_stats[request.target_id]["current_hp"] = target_new_hp
            target.current_hp = target_new_hp

            effect_result = {
                "type": "damage",
                "target_id": request.target_id,
                "target_name": target.name,
                "dice": damage_dice,
                "damage": damage_amount,
                "damage_type": damage_type,
                "target_old_hp": target_current_hp,
                "target_new_hp": target_new_hp,
                "ongoing": effect.get("ongoing", False)
            }
            message_suffix = f" {target.name} takes {damage_amount} {damage_type} damage!"

            # Check if target is defeated
            if target_new_hp <= 0:
                target.is_active = False
                effect_result["target_defeated"] = True
                message_suffix += f" {target.name} is defeated!"

            # Handle ongoing damage (alchemist's fire)
            if effect.get("ongoing", False):
                # Add a condition to track ongoing fire damage
                conditions = target_stats.get("conditions", [])
                conditions.append({
                    "type": "burning",
                    "source": request.item_id,
                    "damage": damage_dice,
                    "damage_type": damage_type,
                    "save_dc": 10,  # DC 10 Dex save to extinguish as action
                })
                engine.state.combatant_stats[request.target_id]["conditions"] = conditions
                effect_result["applied_condition"] = "burning"
                message_suffix += " Target is burning!"

    # === BUFF ITEMS (oil of slipperiness, potion of climbing, antitoxin) ===
    elif item_type in ["potion", "oil"] and "heal" not in effect:
        # Apply buff effects
        buffs = stats.get("buffs", [])

        buff_entry = {
            "source": request.item_id,
            "name": item_data["name"],
            "duration": effect.get("duration", "1 hour"),
            "effects": {}
        }

        if effect.get("advantage_poison_saves"):
            buff_entry["effects"]["advantage_poison_saves"] = True
            message_suffix = " Gained advantage on poison saving throws!"

        if effect.get("freedom_of_movement"):
            buff_entry["effects"]["freedom_of_movement"] = True
            message_suffix = " Gained Freedom of Movement effect!"

        if effect.get("climbing_speed"):
            buff_entry["effects"]["climbing_speed"] = True
            buff_entry["effects"]["advantage_climb"] = effect.get("advantage_climb", False)
            message_suffix = " Gained climbing speed!"

        buffs.append(buff_entry)
        engine.state.combatant_stats[request.combatant_id]["buffs"] = buffs

        effect_result = {
            "type": "buff",
            "buff_applied": buff_entry,
            "duration": effect.get("duration", "1 hour")
        }

    # === UNKNOWN ITEM TYPE ===
    else:
        effect_result = {
            "type": "generic",
            "description": item_data.get("description", "Item used")
        }
        message_suffix = f" {item_data.get('description', '')}"

    # Remove item from inventory
    inventory.pop(item_index)
    engine.state.combatant_stats[request.combatant_id]["inventory"] = inventory

    # Log the action
    engine.state.add_event(
        "use_item",
        f"{combatant.name} uses {item_data['name']}!{message_suffix}",
        combatant_id=request.combatant_id,
        data={"item": request.item_id, "effect": effect_result}
    )

    return UseItemResponse(
        success=True,
        message=f"{combatant.name} uses {item_data['name']}!{message_suffix}",
        effect=effect_result,
        combat_state=engine.get_combat_state()
    )


# ============================================================================
# Drop/Pickup Item Endpoints
# ============================================================================

class DropItemRequest(BaseModel):
    """Request to drop an item on the ground."""
    combatant_id: str = Field(..., description="Combatant dropping the item")
    item_id: str = Field(..., description="Item ID to drop")
    position: Optional[List[int]] = Field(
        default=None,
        description="Position to drop at [x, y]. If not provided, uses combatant's position"
    )


class DropItemResponse(BaseModel):
    """Response for drop item action."""
    success: bool
    message: str
    ground_items: Dict[str, List[Dict[str, Any]]] = Field(
        default={},
        description="Current ground items for this combat"
    )


class PickupItemRequest(BaseModel):
    """Request to pick up an item from the ground."""
    combatant_id: str = Field(..., description="Combatant picking up the item")
    position: Optional[List[int]] = Field(
        default=None,
        description="Position to pick up from [x, y]. If not provided, uses combatant's position"
    )
    item_id: Optional[str] = Field(
        default=None,
        description="Specific item ID to pick up. If not provided, picks up all items"
    )


class PickupItemResponse(BaseModel):
    """Response for pickup item action."""
    success: bool
    message: str
    items_picked_up: List[Dict[str, Any]] = []
    ground_items: Dict[str, List[Dict[str, Any]]] = Field(
        default={},
        description="Remaining ground items for this combat"
    )


@router.post("/{combat_id}/drop", response_model=DropItemResponse)
async def drop_item(combat_id: str, request: DropItemRequest):
    """
    Drop an item from inventory onto the ground at a position.

    The item is removed from the combatant's inventory and placed on the ground
    where it can be picked up later by any combatant.
    """
    # Get combat
    engine = active_combats.get(combat_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Combat not found")

    # Get combatant data
    combatant = engine.state.initiative_tracker.get_combatant(request.combatant_id)
    stats = engine.state.combatant_stats.get(request.combatant_id, {})

    if not combatant:
        raise HTTPException(status_code=404, detail="Combatant not found")

    # Get position (from request or combatant's current position)
    if request.position:
        position = tuple(request.position)
    else:
        position = engine.state.positions.get(request.combatant_id)
        if not position:
            raise HTTPException(status_code=400, detail="Could not determine drop position")

    # Find item in inventory OR equipment slots
    inventory = stats.get("inventory", [])
    item_index = None
    item_data = None
    item_source = None  # 'inventory' or 'equipment'
    equipment_slot = None

    # Check inventory first
    for i, inv_item in enumerate(inventory):
        if inv_item.get("id") == request.item_id:
            item_index = i
            item_data = inv_item.copy()
            item_source = 'inventory'
            break

    # If not in inventory, check equipment (slots AND equipment.inventory)
    if item_data is None:
        equipment = stats.get("equipment", {})
        # Handle CharacterEquipment object - convert to dict
        if hasattr(equipment, 'to_dict'):
            equipment_dict = equipment.to_dict()
        else:
            equipment_dict = equipment if isinstance(equipment, dict) else {}

        # First check equipped slots
        for slot in ['main_hand', 'off_hand', 'ranged', 'armor', 'shield', 'head', 'cloak', 'gloves', 'boots', 'amulet', 'belt', 'ring_1', 'ring_2']:
            slot_item = equipment_dict.get(slot)
            if slot_item:
                # Handle both dicts and InventoryItem objects
                if isinstance(slot_item, dict):
                    item_id = slot_item.get("id")
                else:
                    # It's an InventoryItem object - access attribute directly
                    item_id = getattr(slot_item, "id", None)

                if item_id == request.item_id:
                    # Convert to dict for ground items
                    if isinstance(slot_item, dict):
                        item_data = slot_item.copy()
                    else:
                        # Convert InventoryItem object to dict
                        item_data = slot_item.to_dict() if hasattr(slot_item, 'to_dict') else {
                            "id": item_id,
                            "name": getattr(slot_item, "name", "Unknown"),
                            "item_type": getattr(slot_item, "item_type", "misc"),
                        }
                    item_source = 'equipment_slot'
                    equipment_slot = slot
                    break

        # If not in equipped slots, check equipment.inventory (where unequipped items go)
        if item_data is None:
            equipment_inventory = equipment_dict.get("inventory", [])
            for i, eq_inv_item in enumerate(equipment_inventory):
                # Handle both dicts and InventoryItem objects
                if isinstance(eq_inv_item, dict):
                    item_id = eq_inv_item.get("id")
                else:
                    item_id = getattr(eq_inv_item, "id", None)

                if item_id == request.item_id:
                    if isinstance(eq_inv_item, dict):
                        item_data = eq_inv_item.copy()
                    else:
                        item_data = eq_inv_item.to_dict() if hasattr(eq_inv_item, 'to_dict') else {
                            "id": item_id,
                            "name": getattr(eq_inv_item, "name", "Unknown"),
                            "item_type": getattr(eq_inv_item, "item_type", "misc"),
                        }
                    item_source = 'equipment_inventory'
                    item_index = i
                    break

    if item_data is None:
        raise HTTPException(status_code=400, detail=f"Item '{request.item_id}' not found in inventory or equipment")

    # Remove from appropriate location
    if item_source == 'inventory':
        # Remove from top-level inventory (potions, consumables)
        inventory.pop(item_index)
        engine.state.combatant_stats[request.combatant_id]["inventory"] = inventory
    elif item_source == 'equipment_slot':
        # Remove from equipped slot (main_hand, off_hand, etc.)
        equipment = stats.get("equipment", {})
        if hasattr(equipment, equipment_slot):
            # It's a CharacterEquipment object - set the slot attribute to None
            setattr(equipment, equipment_slot, None)
            engine.state.combatant_stats[request.combatant_id]["equipment"] = equipment
        elif isinstance(equipment, dict):
            # It's a dict
            equipment[equipment_slot] = None
            engine.state.combatant_stats[request.combatant_id]["equipment"] = equipment
    elif item_source == 'equipment_inventory':
        # Remove from equipment.inventory (where unequipped items go)
        equipment = stats.get("equipment", {})
        if hasattr(equipment, 'inventory'):
            # It's a CharacterEquipment object
            equipment.inventory.pop(item_index)
            engine.state.combatant_stats[request.combatant_id]["equipment"] = equipment
        elif isinstance(equipment, dict) and "inventory" in equipment:
            # It's a dict with inventory key
            equipment["inventory"].pop(item_index)
            engine.state.combatant_stats[request.combatant_id]["equipment"] = equipment

    # Add to ground items
    if combat_id not in ground_items:
        ground_items[combat_id] = {}

    pos_key = f"{position[0]},{position[1]}"
    if pos_key not in ground_items[combat_id]:
        ground_items[combat_id][pos_key] = []

    ground_items[combat_id][pos_key].append(item_data)

    # Log the action
    engine.state.add_event(
        "drop_item",
        f"{combatant.name} drops {item_data.get('name', 'an item')} on the ground.",
        combatant_id=request.combatant_id,
        data={"item": item_data, "position": list(position)}
    )

    return DropItemResponse(
        success=True,
        message=f"Dropped {item_data.get('name', 'item')} at position ({position[0]}, {position[1]})",
        ground_items=ground_items.get(combat_id, {})
    )


@router.post("/{combat_id}/pickup", response_model=PickupItemResponse)
async def pickup_item(combat_id: str, request: PickupItemRequest):
    """
    Pick up item(s) from the ground at a position.

    The combatant must be at or adjacent to the position to pick up items.
    Items are added to the combatant's inventory.
    """
    # Get combat
    engine = active_combats.get(combat_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Combat not found")

    # Get combatant data
    combatant = engine.state.initiative_tracker.get_combatant(request.combatant_id)
    stats = engine.state.combatant_stats.get(request.combatant_id, {})

    if not combatant:
        raise HTTPException(status_code=404, detail="Combatant not found")

    # Get position (from request or combatant's current position)
    if request.position:
        position = tuple(request.position)
    else:
        position = engine.state.positions.get(request.combatant_id)
        if not position:
            raise HTTPException(status_code=400, detail="Could not determine pickup position")

    # Check if there are items at this position
    pos_key = f"{position[0]},{position[1]}"
    combat_ground = ground_items.get(combat_id, {})
    items_at_pos = combat_ground.get(pos_key, [])

    if not items_at_pos:
        raise HTTPException(status_code=400, detail=f"No items at position ({position[0]}, {position[1]})")

    # Pick up specific item or all items
    picked_up = []
    if request.item_id:
        # Find and pick up specific item
        for i, item in enumerate(items_at_pos):
            if item.get("id") == request.item_id:
                picked_up.append(items_at_pos.pop(i))
                break
        if not picked_up:
            raise HTTPException(status_code=400, detail=f"Item '{request.item_id}' not found at position")
    else:
        # Pick up all items
        picked_up = items_at_pos.copy()
        items_at_pos.clear()

    # Update ground items (remove empty positions)
    if not items_at_pos:
        combat_ground.pop(pos_key, None)

    # Add to inventory
    inventory = stats.get("inventory", [])
    inventory.extend(picked_up)
    engine.state.combatant_stats[request.combatant_id]["inventory"] = inventory

    # Log the action
    item_names = ", ".join(item.get("name", "item") for item in picked_up)
    engine.state.add_event(
        "pickup_item",
        f"{combatant.name} picks up {item_names}.",
        combatant_id=request.combatant_id,
        data={"items": picked_up, "position": list(position)}
    )

    return PickupItemResponse(
        success=True,
        message=f"Picked up {len(picked_up)} item(s)",
        items_picked_up=picked_up,
        ground_items=ground_items.get(combat_id, {})
    )


@router.get("/{combat_id}/ground-items")
async def get_ground_items(combat_id: str):
    """
    Get all items on the ground for a combat.

    Returns a dictionary mapping position strings ("x,y") to lists of items.
    """
    return {
        "success": True,
        "ground_items": ground_items.get(combat_id, {})
    }
