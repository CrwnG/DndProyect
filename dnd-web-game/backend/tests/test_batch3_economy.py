"""Batch 3: economy reward loop.

- Looted items sell for 0 gp because the shop reads `value` but loot writes
  `value_gp` (audit: shop.py:67 vs loot.py:117).
- Selling matched on `id.split("_")[0]`, so "potion_of_climbing" collides with
  "potion_of_healing" (both -> "potion") and the wrong item is removed
  (audit: shop route :200).
"""
from app.models.shop import Shop


def _shop():
    # sell_rate defaults to 0.5; build a minimal shop to exercise pricing.
    return Shop(id="s1", name="Test Shop", owner_name="Keeper", shop_type="general")


def test_get_sell_price_reads_value_gp_for_looted_items():
    """A looted item carries `value_gp`, not `value` — it must still sell for gp."""
    shop = _shop()
    looted = {"name": "Ruby", "value_gp": 100}
    assert shop.get_sell_price(looted) == int(100 * shop.sell_rate)
    assert shop.get_sell_price(looted) > 0

    # Shop-stocked items still use `value`.
    stocked = {"name": "Potion", "value": 50}
    assert shop.get_sell_price(stocked) == int(50 * shop.sell_rate)


def test_sell_item_matching_does_not_collide_on_first_token():
    """Selling must match the full base id, not just the first `_`-token, so a
    cheap potion can't pop a different (valuable) one."""
    from app.api.routes.shop import _inventory_item_matches

    # Same base id (inventory ids carry a numeric suffix from buy_item) -> match.
    assert _inventory_item_matches("potion_of_healing_1", "potion_of_healing")
    assert _inventory_item_matches("longsword", "longsword")
    # Different items that share only the first token -> NO match.
    assert not _inventory_item_matches("potion_of_climbing_1", "potion_of_healing")
    assert not _inventory_item_matches("potion_of_climbing", "potion_of_healing")
