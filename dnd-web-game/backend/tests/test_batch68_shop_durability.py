"""Batch 68 (F2): shop transactions survive a server restart.

The buy/sell routes read only the in-memory active_combats dict — no DB rehydrate on a
cache miss (buy even soft-failed to gold=0, reporting a misleading "Not enough gold")
— and never persisted the mutated gold/inventory back, so a restart undid purchases
(gold restored, items duped or lost). Both violate golden rule #3. Now they resolve
the engine like the combat routes do and persist after every transaction.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.loot import active_combats

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _init_db():
    """TestClient doesn't run the app lifespan, so the DB tables the shop persistence
    writes to don't exist in a fresh environment (CI) — create them explicitly."""
    from app.database.engine import init_db
    asyncio.run(init_db())


def _start_combat_with_gold():
    r = client.post("/api/combat/start", json={
        "players": [{
            "id": "hero", "name": "Hero", "type": "player", "hp": 30, "max_hp": 30,
            "ac": 15, "speed": 30, "gold": 500,
            "abilities": {"strength": 14, "dexterity": 12, "constitution": 14,
                          "intelligence": 10, "wisdom": 10, "charisma": 10},
            "class": "fighter", "level": 3,
        }],
        "enemies": [{
            "id": "gob", "name": "Goblin", "type": "enemy", "hp": 7, "max_hp": 7,
            "ac": 13, "speed": 30,
            "abilities": {"strength": 8, "dexterity": 14, "constitution": 10,
                          "intelligence": 8, "wisdom": 8, "charisma": 8},
            "class": "goblin", "level": 1,
        }],
        "grid_width": 8, "grid_height": 8,
    })
    assert r.status_code == 200, r.text
    return r.json()["combat_id"]


def _first_shop_item():
    shop = client.get("/api/shop/general_store").json()["shop"]
    return shop["inventory"][0]["item_id"]


@pytest.fixture()
def combat_id():
    cid = _start_combat_with_gold()
    yield cid
    active_combats.pop(cid, None)


def test_buy_persists_and_survives_restart(combat_id):
    item_id = _first_shop_item()
    r = client.post("/api/shop/buy", json={
        "shop_id": "general_store", "item_id": item_id, "quantity": 1,
        "combat_id": combat_id, "combatant_id": "hero",
    })
    assert r.status_code == 200, r.text
    gold_after_buy = r.json()["new_gold"]
    assert gold_after_buy < 500

    # Simulate a restart: drop the in-memory engine. The purchase must still exist —
    # a second buy through the rehydrated engine starts from the persisted gold.
    active_combats.pop(combat_id, None)
    r2 = client.post("/api/shop/buy", json={
        "shop_id": "general_store", "item_id": item_id, "quantity": 1,
        "combat_id": combat_id, "combatant_id": "hero",
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["new_gold"] < gold_after_buy, \
        "restart refunded the first purchase (transaction was not persisted)"


def test_sell_works_after_restart(combat_id):
    item_id = _first_shop_item()
    buy = client.post("/api/shop/buy", json={
        "shop_id": "general_store", "item_id": item_id, "quantity": 1,
        "combat_id": combat_id, "combatant_id": "hero",
    })
    assert buy.status_code == 200
    gold_after_buy = buy.json()["new_gold"]

    # Restart, then sell the item back — the route must rehydrate, not 404.
    active_combats.pop(combat_id, None)
    sell = client.post("/api/shop/sell", json={
        "shop_id": "general_store", "item_id": item_id,
        "combat_id": combat_id, "combatant_id": "hero",
    })
    assert sell.status_code == 200, sell.text
    assert sell.json()["new_gold"] > gold_after_buy


def test_buy_with_unknown_combat_404s_instead_of_lying_about_gold(combat_id):
    item_id = _first_shop_item()
    r = client.post("/api/shop/buy", json={
        "shop_id": "general_store", "item_id": item_id, "quantity": 1,
        "combat_id": "no-such-combat", "combatant_id": "hero",
    })
    assert r.status_code == 404   # was: 400 "Not enough gold. Need Xgp, have 0gp"
