"""Reliability fixes from the bug-hunt (see ROADMAP.md / reliability findings)."""


def test_dice_only_strips_flat_modifiers():
    """R15: crit doubling must double dice only, not the flat modifier."""
    from app.core.dice import dice_only

    assert dice_only("2d10+6") == "2d10"
    assert dice_only("1d8") == "1d8"
    assert dice_only("3d6+2d4+5") == "3d6+2d4"
    assert dice_only("7") == "0"          # flat-only -> no dice to double


def test_multiattack_name_matching_normalizes_plurals():
    """R12: multiattack pattern tokens ('claw') must match action keys ('claws')."""
    from app.core.combat_engine import CombatEngine

    attack_map = {"claws": "CLAW_ATK", "bite": "BITE_ATK"}
    assert CombatEngine._match_attack(attack_map, "claw") == "CLAW_ATK"
    assert CombatEngine._match_attack(attack_map, "claws") == "CLAW_ATK"
    assert CombatEngine._match_attack(attack_map, "bite") == "BITE_ATK"
    assert CombatEngine._match_attack(attack_map, "tail") is None


def test_shops_build_without_missing_module():
    """R2: shop factories imported a nonexistent app.data.items -> every shop 500'd."""
    from app.models.shop import create_general_store, create_potion_shop, create_weapon_shop

    for factory in (create_general_store, create_potion_shop, create_weapon_shop):
        shop = factory()
        assert len(shop.inventory) > 0
        for item in shop.inventory:
            assert item.price >= 0  # numeric value-derived price


async def test_dm_narration_falls_back_without_api_key():
    """R8: DM narration must return template content even with no API key (the
    routes used to short-circuit before reaching the service fallbacks)."""
    from app.services.ai_dm import get_ai_dm

    dm = get_ai_dm()
    content = await dm.generate_scene_description(
        {"name": "Goblin Cave", "story": {"intro_text": "A dark cave mouth."}}, [], {}
    )
    assert content is not None and len(str(content).strip()) > 0


def test_jwt_secret_warnings_flag_dev_defaults():
    """R6: dev/default/empty JWT secrets must be flagged (warning, not a crash)."""
    from app.config import check_jwt_secrets

    assert check_jwt_secrets("dev-secret-key-change-in-production", "strong")   # flagged
    assert check_jwt_secrets("strong", "")                                      # empty refresh flagged
    assert check_jwt_secrets("strong-secret", "strong-refresh") == []           # secure -> no warnings
