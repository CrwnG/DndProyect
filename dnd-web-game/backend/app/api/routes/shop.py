"""
Shop/Vendor API Routes

Handles buying and selling items from shops.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from app.models.shop import get_shop, Shop
from app.api.routes.loot import active_combats

router = APIRouter(prefix="/shop", tags=["shop"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ShopResponse(BaseModel):
    """Response containing shop data."""
    success: bool
    shop: Dict[str, Any]
    message: str = ""


class BuyRequest(BaseModel):
    """Request to buy an item from a shop."""
    shop_id: str
    item_id: str
    combat_id: Optional[str] = None
    combatant_id: Optional[str] = None
    quantity: int = 1


class SellRequest(BaseModel):
    """Request to sell an item to a shop."""
    shop_id: str
    item_id: str
    combat_id: str
    combatant_id: str
    quantity: int = 1


class TransactionResponse(BaseModel):
    """Response for buy/sell transactions."""
    success: bool
    message: str
    gold_change: int = 0
    new_gold: int = 0
    item: Optional[Dict[str, Any]] = None


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/{shop_id}", response_model=ShopResponse)
async def get_shop_inventory(shop_id: str):
    """
    Get a shop's inventory and details.

    Returns the shop's name, owner, inventory with prices, and buy/sell rates.
    """
    shop = get_shop(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail=f"Shop '{shop_id}' not found")

    return ShopResponse(
        success=True,
        shop=shop.to_dict(),
        message=f"Welcome to {shop.name}!"
    )


@router.get("/", response_model=Dict[str, Any])
async def list_available_shops():
    """
    List all available shop types.
    """
    from app.models.shop import SHOP_TEMPLATES

    shops = []
    for shop_id in SHOP_TEMPLATES:
        shop = get_shop(shop_id)
        if shop:
            shops.append({
                "id": shop.id,
                "name": shop.name,
                "owner_name": shop.owner_name,
                "shop_type": shop.shop_type,
                "description": shop.description,
            })

    return {
        "success": True,
        "shops": shops,
    }


@router.post("/buy", response_model=TransactionResponse)
async def buy_item(request: BuyRequest):
    """
    Buy an item from a shop.

    Deducts gold from the player and adds the item to their inventory.
    """
    shop = get_shop(request.shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail=f"Shop '{request.shop_id}' not found")

    # Check if item is available
    shop_item = shop.get_item(request.item_id)
    if not shop_item:
        raise HTTPException(status_code=404, detail=f"Item '{request.item_id}' not found in shop")

    if not shop.can_buy(request.item_id):
        raise HTTPException(status_code=400, detail="Item is out of stock")

    # Calculate price
    price = shop.get_buy_price(request.item_id)
    if price is None:
        raise HTTPException(status_code=400, detail="Could not determine item price")

    total_price = price * request.quantity

    # Get player gold - either from combat state or we need a session
    current_gold = 0
    combatant_stats = None

    if request.combat_id and request.combatant_id:
        engine = active_combats.get(request.combat_id)
        if engine:
            combatant_stats = engine.state.combatant_stats.get(request.combatant_id, {})
            current_gold = combatant_stats.get("gold", 0)

    if current_gold < total_price:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough gold. Need {total_price}gp, have {current_gold}gp"
        )

    # Process transaction
    new_gold = current_gold - total_price

    # Update gold
    if combatant_stats is not None:
        engine.state.combatant_stats[request.combatant_id]["gold"] = new_gold

        # Add item to inventory
        inventory = combatant_stats.get("inventory", [])
        for _ in range(request.quantity):
            # Create a copy of the item with a unique ID
            item_copy = dict(shop_item.item_data)
            item_copy["id"] = f"{request.item_id}_{len(inventory) + 1}"
            inventory.append(item_copy)
        engine.state.combatant_stats[request.combatant_id]["inventory"] = inventory

    # Reduce shop stock
    for _ in range(request.quantity):
        shop.purchase_item(request.item_id)

    return TransactionResponse(
        success=True,
        message=f"Purchased {request.quantity}x {shop_item.item_data.get('name', request.item_id)} for {total_price}gp",
        gold_change=-total_price,
        new_gold=new_gold,
        item=shop_item.item_data,
    )


@router.post("/sell", response_model=TransactionResponse)
async def sell_item(request: SellRequest):
    """
    Sell an item to a shop.

    Adds gold to the player and removes the item from their inventory.
    """
    shop = get_shop(request.shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail=f"Shop '{request.shop_id}' not found")

    # Get combat engine and combatant
    engine = active_combats.get(request.combat_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Combat not found")

    combatant_stats = engine.state.combatant_stats.get(request.combatant_id)
    if not combatant_stats:
        raise HTTPException(status_code=404, detail="Combatant not found")

    # Find item in inventory
    inventory = combatant_stats.get("inventory", [])
    item_index = None
    item_data = None

    for i, inv_item in enumerate(inventory):
        item_id = inv_item.get("id", inv_item.get("item_id", ""))
        # Match by exact ID or base ID (without suffix)
        if item_id == request.item_id or item_id.split("_")[0] == request.item_id.split("_")[0]:
            item_index = i
            item_data = inv_item
            break

    if item_index is None:
        raise HTTPException(status_code=404, detail="Item not found in inventory")

    # Calculate sell price
    sell_price = shop.get_sell_price(item_data)

    # Process transaction
    current_gold = combatant_stats.get("gold", 0)
    new_gold = current_gold + sell_price

    # Update gold
    engine.state.combatant_stats[request.combatant_id]["gold"] = new_gold

    # Remove item from inventory
    inventory.pop(item_index)
    engine.state.combatant_stats[request.combatant_id]["inventory"] = inventory

    return TransactionResponse(
        success=True,
        message=f"Sold {item_data.get('name', request.item_id)} for {sell_price}gp",
        gold_change=sell_price,
        new_gold=new_gold,
        item=item_data,
    )
