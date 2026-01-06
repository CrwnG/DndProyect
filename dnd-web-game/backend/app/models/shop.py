"""
Shop/Vendor System Models

Defines shop inventory, pricing, and transaction logic.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ShopItem:
    """An item available for purchase in a shop."""
    item_id: str
    item_data: Dict[str, Any]
    price: int  # Price in gold pieces
    quantity: int = -1  # -1 means unlimited stock

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_data": self.item_data,
            "price": self.price,
            "quantity": self.quantity,
        }


@dataclass
class Shop:
    """A vendor shop with inventory and pricing."""
    id: str
    name: str
    owner_name: str
    shop_type: str  # "general", "weapons", "armor", "magic", "potions", "blacksmith"
    inventory: List[ShopItem] = field(default_factory=list)
    buy_rate: float = 1.0   # Multiplier for selling prices (1.0 = base price)
    sell_rate: float = 0.5  # Multiplier for buying from player (0.5 = 50% of base)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner_name": self.owner_name,
            "shop_type": self.shop_type,
            "inventory": [item.to_dict() for item in self.inventory],
            "buy_rate": self.buy_rate,
            "sell_rate": self.sell_rate,
            "description": self.description,
        }

    def get_item(self, item_id: str) -> Optional[ShopItem]:
        """Get a shop item by ID."""
        for item in self.inventory:
            if item.item_id == item_id:
                return item
        return None

    def get_buy_price(self, item_id: str) -> Optional[int]:
        """Get the price to buy an item from this shop."""
        item = self.get_item(item_id)
        if item:
            return int(item.price * self.buy_rate)
        return None

    def get_sell_price(self, item_data: Dict[str, Any]) -> int:
        """Get the price the shop will pay for an item."""
        base_value = item_data.get("value", 0)
        return int(base_value * self.sell_rate)

    def can_buy(self, item_id: str) -> bool:
        """Check if an item is available for purchase."""
        item = self.get_item(item_id)
        if not item:
            return False
        return item.quantity == -1 or item.quantity > 0

    def purchase_item(self, item_id: str) -> bool:
        """Reduce stock after purchase. Returns True if successful."""
        item = self.get_item(item_id)
        if not item or not self.can_buy(item_id):
            return False
        if item.quantity > 0:
            item.quantity -= 1
        return True


# Default shop templates
def create_general_store() -> Shop:
    """Create a standard general goods store."""
    from app.data.items import CONSUMABLES

    inventory = []

    # Add common potions
    potion_items = ["potion_of_healing", "antitoxin", "potion_of_climbing"]
    for item_id in potion_items:
        if item_id in CONSUMABLES:
            item_data = CONSUMABLES[item_id]
            inventory.append(ShopItem(
                item_id=item_id,
                item_data=item_data,
                price=item_data.get("value", 50),
                quantity=-1  # Unlimited
            ))

    return Shop(
        id="general_store",
        name="General Store",
        owner_name="Marcus the Merchant",
        shop_type="general",
        inventory=inventory,
        buy_rate=1.0,
        sell_rate=0.5,
        description="A well-stocked general store with adventuring supplies."
    )


def create_potion_shop() -> Shop:
    """Create a potion/alchemy shop."""
    from app.data.items import CONSUMABLES

    inventory = []

    # Add all potions
    for item_id, item_data in CONSUMABLES.items():
        if item_data.get("type") == "potion":
            inventory.append(ShopItem(
                item_id=item_id,
                item_data=item_data,
                price=item_data.get("value", 50),
                quantity=-1
            ))

    return Shop(
        id="potion_shop",
        name="The Bubbling Cauldron",
        owner_name="Alara the Alchemist",
        shop_type="potions",
        inventory=inventory,
        buy_rate=0.9,  # Slight discount
        sell_rate=0.6,  # Better buyback for potions
        description="Potions, elixirs, and alchemical supplies."
    )


def create_weapon_shop() -> Shop:
    """Create a weapons shop."""
    from app.data.items import WEAPONS

    inventory = []

    # Add weapons
    for item_id, item_data in WEAPONS.items():
        inventory.append(ShopItem(
            item_id=item_id,
            item_data=item_data,
            price=item_data.get("value", 100),
            quantity=-1
        ))

    return Shop(
        id="weapon_shop",
        name="Steel & Blade",
        owner_name="Grimjaw the Smith",
        shop_type="weapons",
        inventory=inventory,
        buy_rate=1.0,
        sell_rate=0.4,  # Lower buyback for weapons
        description="Quality weapons for adventurers of all kinds."
    )


# Shop registry
SHOP_TEMPLATES = {
    "general_store": create_general_store,
    "potion_shop": create_potion_shop,
    "weapon_shop": create_weapon_shop,
}


def get_shop(shop_id: str) -> Optional[Shop]:
    """Get a shop by ID, creating from template if needed."""
    if shop_id in SHOP_TEMPLATES:
        return SHOP_TEMPLATES[shop_id]()
    return None
