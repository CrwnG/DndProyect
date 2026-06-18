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
