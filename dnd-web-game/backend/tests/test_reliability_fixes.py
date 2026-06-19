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


def test_aoe_cone_and_line_respect_direction():
    """R13: cones/lines must be directional, not omnidirectional spheres."""
    from app.core.combat_engine import CombatEngine

    f = CombatEngine._aoe_includes
    origin, direction = (0, 0), (10, 0)  # aimed east
    # Cone (30 ft = 6 squares): straight ahead and slightly off-axis are in;
    # behind, perpendicular, and beyond range are out.
    assert f("cone", origin, direction, (3, 0), 30)
    assert f("cone", origin, direction, (4, 1), 30)
    assert not f("cone", origin, direction, (-3, 0), 30)
    assert not f("cone", origin, direction, (0, 5), 30)
    assert not f("cone", origin, direction, (7, 0), 30)
    # Line (60 ft, 5 ft wide): on the ray is in; off-width / behind are out.
    assert f("line", origin, direction, (5, 0), 60, 5)
    assert not f("line", origin, direction, (5, 2), 60, 5)
    assert not f("line", origin, direction, (-1, 0), 60, 5)
    # Sphere is omnidirectional within range.
    assert f("sphere", origin, direction, (0, 4), 30)
    # QA-F5: with no aim direction a cone/line must NOT fall back to a sphere.
    assert not f("cone", origin, origin, (1, 0), 30)
    assert not f("line", origin, origin, (1, 0), 60, 5)


def _engine_with(reactor_id, **player_over):
    """A started combat with one player (the reactor) and a dummy enemy."""
    from app.core.combat_engine import CombatEngine, CombatState

    player = {
        "id": reactor_id, "name": reactor_id, "type": "player",
        "hp": 30, "max_hp": 30, "ac": 15, "speed": 30,
        "str_mod": 0, "dex_mod": 3, "con_mod": 2,
        "attack_bonus": 5, "damage_dice": "1d8", "damage_type": "piercing",
        "abilities": {"strength": 10, "dexterity": 16, "constitution": 14,
                      "intelligence": 10, "wisdom": 10, "charisma": 10},
        "class": "rogue", "level": 5, "conditions": [],
    }
    player.update(player_over)
    enemy = {
        "id": "enemy-1", "name": "Bandit", "type": "enemy",
        "hp": 16, "max_hp": 16, "ac": 12, "speed": 30,
        "str_mod": 2, "dex_mod": 1, "con_mod": 1,
        "attack_bonus": 4, "damage_dice": "1d6", "damage_type": "slashing",
        "abilities": {"strength": 14, "dexterity": 12, "constitution": 12,
                      "intelligence": 10, "wisdom": 10, "charisma": 10},
        "class": "fighter", "level": 2, "conditions": [],
    }
    engine = CombatEngine(combat_state=CombatState())
    engine.start_combat([player], [enemy])
    return engine


def test_uncanny_dodge_credits_half_damage_back():
    """R14: Uncanny Dodge must actually restore the prevented (halved) damage."""
    from app.api.routes.combat import apply_defensive_reaction
    from app.core.reactions import ReactionType, resolve_uncanny_dodge

    engine = _engine_with("rogue-1")
    engine.state.combatant_stats["rogue-1"]["current_hp"] = 10   # took 20 of 30
    result = resolve_uncanny_dodge("rogue-1", "Rogue", 20)

    info = apply_defensive_reaction(engine, "rogue-1", ReactionType.UNCANNY_DODGE, result, 20)

    assert info["hp_restored"] == 10
    assert engine.state.combatant_stats["rogue-1"]["current_hp"] == 20
    assert engine.state.initiative_tracker.get_combatant("rogue-1").current_hp == 20


def test_shield_spends_slot_and_negates_damage_on_miss():
    """R14: Shield must spend a 1st-level slot and, when its +5 AC turns the hit
    into a miss, undo the damage the attack already applied."""
    from app.api.routes.combat import apply_defensive_reaction
    from app.core.reactions import ReactionType, resolve_shield_spell

    engine = _engine_with("wiz-1", spell_slots={1: 2})
    engine.state.combatant_stats["wiz-1"]["current_hp"] = 18     # took 12 of 30
    # roll 16 hits AC 15, but 16 < 15+5 -> Shield makes it miss
    result = resolve_shield_spell("wiz-1", "Wizard", attack_roll=16, current_ac=15, has_spell_slot=True)
    assert result.extra_data["attack_would_miss"] is True

    info = apply_defensive_reaction(engine, "wiz-1", ReactionType.SHIELD, result, 12)

    assert info["slot_spent"] is True
    assert info["hp_restored"] == 12
    assert engine.state.combatant_stats["wiz-1"]["current_hp"] == 30
    # Slot spent by decrementing spell_slots (matches the engine's accounting), 2 -> 1.
    assert engine.state.combatant_stats["wiz-1"]["spell_slots"][1] == 1


def test_shield_spends_slot_but_keeps_damage_when_attack_still_hits():
    """R14: a slot is still spent, but no HP is credited back if the attack hits anyway."""
    from app.api.routes.combat import apply_defensive_reaction
    from app.core.reactions import ReactionType, resolve_shield_spell

    engine = _engine_with("wiz-2", spell_slots={1: 1})
    engine.state.combatant_stats["wiz-2"]["current_hp"] = 18
    result = resolve_shield_spell("wiz-2", "Wizard", attack_roll=25, current_ac=15, has_spell_slot=True)
    assert result.extra_data["attack_would_miss"] is False

    info = apply_defensive_reaction(engine, "wiz-2", ReactionType.SHIELD, result, 12)

    assert info["slot_spent"] is True
    assert info["hp_restored"] == 0
    assert engine.state.combatant_stats["wiz-2"]["current_hp"] == 18
    assert engine.state.combatant_stats["wiz-2"]["spell_slots"][1] == 0     # 1 -> 0


def test_uncanny_dodge_does_not_overheal_on_lethal_hit():
    """R14/QA-F1: a hit that clamped HP to 0 must not let Uncanny Dodge restore
    above what the halved damage allows. Rogue at 10 HP hit for 20 -> takes 10 -> 0."""
    from app.api.routes.combat import apply_defensive_reaction
    from app.core.reactions import ReactionType, resolve_uncanny_dodge

    engine = _engine_with("rogue-2")
    engine.state.combatant_stats["rogue-2"]["current_hp"] = 0   # 10 HP, took 20 -> clamped
    result = resolve_uncanny_dodge("rogue-2", "Rogue", 20)

    info = apply_defensive_reaction(
        engine, "rogue-2", ReactionType.UNCANNY_DODGE, result, 20, pre_hit_hp=10
    )

    assert engine.state.combatant_stats["rogue-2"]["current_hp"] == 0   # 10 - 10, not 10
    assert info["hp_restored"] == 0


def test_shield_negation_uses_pre_hit_hp_on_lethal_hit():
    """R14/QA-F1: Shield turning a lethal hit into a miss restores to the pre-hit HP,
    not to current+incoming (which could exceed it)."""
    from app.api.routes.combat import apply_defensive_reaction
    from app.core.reactions import ReactionType, resolve_shield_spell

    engine = _engine_with("wiz-3", spell_slots={1: 1})
    engine.state.combatant_stats["wiz-3"]["current_hp"] = 0     # 8 HP, took 25 -> clamped
    result = resolve_shield_spell("wiz-3", "Wizard", attack_roll=16, current_ac=15, has_spell_slot=True)
    assert result.extra_data["attack_would_miss"] is True

    info = apply_defensive_reaction(
        engine, "wiz-3", ReactionType.SHIELD, result, 25, pre_hit_hp=8
    )

    assert engine.state.combatant_stats["wiz-3"]["current_hp"] == 8   # back to pre-hit, not 25
    assert info["hp_restored"] == 8


async def test_leader_decides_vote_defaults_leader_when_unset():
    """R11: a leader/consensus vote with no leader_id could never resolve."""
    from app.core.multiplayer_choices import MultiplayerChoiceHandler, DecisionMode

    h = MultiplayerChoiceHandler()
    session = await h.initiate_choice(
        "game-1", "c1", "Pick", [{"id": "a"}, {"id": "b"}],
        ["p1", "p2"], mode=DecisionMode.LEADER_DECIDES, leader_id=None,
    )
    # With a defaulted leader (p1), p1's vote resolves immediately.
    result = await h.record_vote(session.id, "p1", "a")
    assert result.resolved
    assert result.winning_choice == "a"


async def test_disconnect_does_not_deadlock_vote():
    """R11: a player leaving an active vote must shrink the quorum, not deadlock it."""
    from app.core.multiplayer_choices import MultiplayerChoiceHandler, DecisionMode

    h = MultiplayerChoiceHandler()
    session = await h.initiate_choice(
        "game-2", "c1", "Pick", [{"id": "a"}, {"id": "b"}],
        ["p1", "p2", "p3"], mode=DecisionMode.VOTING,
    )
    await h.record_vote(session.id, "p1", "a")
    await h.record_vote(session.id, "p2", "a")          # 2/3 — not resolved yet
    assert h.get_active_for_game("game-2") is not None

    result = await h.remove_player("game-2", "p3")        # p3 never votes, leaves
    assert result is not None and result.resolved         # quorum now 2/2
    assert result.winning_choice == "a"


async def test_remove_last_player_cancels_vote():
    """R11: removing the final voter cancels the vote rather than resolving to nothing."""
    from app.core.multiplayer_choices import MultiplayerChoiceHandler, DecisionMode

    h = MultiplayerChoiceHandler()
    session = await h.initiate_choice(
        "game-3", "c1", "Pick", [{"id": "a"}], ["p1"], mode=DecisionMode.VOTING,
    )
    await h.remove_player("game-3", "p1")
    assert h.get_active_for_game("game-3") is None


# ---------------------------------------------------------------------------
# Next-tier reliability hunt (post-merge): bugs found auditing the play loop.
# ---------------------------------------------------------------------------

def test_single_class_level_up_does_not_crash_on_readonly_level():
    """N1: PartyMember.level is a read-only @property (alias for total_level), so
    `member.level = new_level` in apply_level_up raised AttributeError on EVERY
    single-class level-up. Must update the backing fields instead."""
    from app.models.game_session import PartyMember
    from app.core.level_up import apply_level_up

    member = PartyMember(
        id="p1", name="Hero", character_class="fighter",
        class_levels={"fighter": 4}, _level=4,
        constitution=14, max_hp=30, current_hp=30,
        hit_die_size=10, hit_dice_total=4, hit_dice_remaining=4,
        xp=6500,   # enough for level 5
    )
    result = apply_level_up(member, new_level=5, hp_choice="average")

    assert result.new_level == 5
    assert member.level == 5          # property reflects the new level, no crash
    assert member.class_levels["fighter"] == 5


def test_level_up_delta_does_not_corrupt_multiclass_totals():
    """QA-F1: advancing one class adds the level delta to THAT class, not the new
    total level, so a multiclass character's total isn't inflated."""
    from app.models.game_session import PartyMember
    from app.core.level_up import apply_level_up

    member = PartyMember(
        id="mc", name="Multi", character_class="wizard",
        class_levels={"wizard": 4, "fighter": 1}, _level=5,
        constitution=14, max_hp=40, current_hp=40,
        hit_die_size=6, hit_dice_total=5, hit_dice_remaining=5,
        xp=14000,   # enough for total level 6
    )
    apply_level_up(member, new_level=6, hp_choice="average")

    assert member.class_levels["wizard"] == 5     # 4 + delta(1)
    assert member.class_levels["fighter"] == 1    # untouched
    assert member.level == 6


def test_monster_actions_reach_combat_stats_cache():
    """N2: _cache_combatant_stats dropped monster actions/legendary, and the
    request schema lacked the fields, so multiattack/abilities/legendary never
    fired via the API even though the engine logic supports them."""
    from app.core.combat_engine import CombatEngine, CombatState

    monster = {
        "id": "drake", "name": "Drake", "type": "enemy",
        "hp": 50, "max_hp": 50, "ac": 15, "speed": 40,
        "str_mod": 4, "attack_bonus": 6, "damage_dice": "2d6", "damage_type": "slashing",
        "abilities": {"strength": 18, "dexterity": 12, "constitution": 16,
                      "intelligence": 6, "wisdom": 12, "charisma": 8},
        "actions": [{"name": "Multiattack", "description": "makes two claw attacks"},
                    {"name": "Claw", "attack_bonus": 6, "damage": "2d6"}],
        "legendary_actions": [{"name": "Tail Swipe"}],
        "legendary_actions_per_round": 3,
    }
    player = {
        "id": "hero", "name": "Hero", "type": "player",
        "hp": 30, "max_hp": 30, "ac": 16, "speed": 30,
        "str_mod": 3, "attack_bonus": 5, "damage_dice": "1d8", "damage_type": "slashing",
        "abilities": {"strength": 16, "dexterity": 12, "constitution": 14,
                      "intelligence": 10, "wisdom": 10, "charisma": 10},
        "class": "fighter", "level": 3, "conditions": [],
    }
    engine = CombatEngine(combat_state=CombatState())
    engine.start_combat([player], [monster])

    cached = engine.state.combatant_stats["drake"]
    assert cached.get("actions"), "monster actions were dropped by the cache"
    assert cached.get("legendary_actions")
    assert cached.get("legendary_actions_per_round") == 3


def test_combatant_data_schema_carries_monster_actions():
    """N2: the /combat/start request schema must keep monster action fields so
    model_dump() doesn't strip them before start_combat."""
    from app.api.routes.combat import CombatantData

    cd = CombatantData(
        name="Drake",
        actions=[{"name": "Multiattack"}],
        legendary_actions=[{"name": "Tail Swipe"}],
        legendary_actions_per_round=3,
    )
    dumped = cd.model_dump()
    assert dumped["actions"] and dumped["legendary_actions"]
    assert dumped["legendary_actions_per_round"] == 3


def test_healing_ability_mod_tolerates_abbreviated_ability():
    """N3 (B1): healing read stats[spellcasting.ability] without normalizing, so an
    abbreviated/uppercase ability ('CHA') missed the full-name stats key
    ('charisma') and healing silently lost the +ability bonus."""
    from app.core.spell_system import _ability_modifier_from_stats

    stats = {"charisma": 18, "wisdom": 16}
    assert _ability_modifier_from_stats(stats, "CHA") == 4
    assert _ability_modifier_from_stats(stats, "cha") == 4
    assert _ability_modifier_from_stats(stats, "charisma") == 4
    assert _ability_modifier_from_stats(stats, "wis") == 3
    assert _ability_modifier_from_stats(stats, "str") == 0   # absent -> 10 -> +0


def test_level_up_does_not_refill_expended_spell_slots():
    """N4 (C2): leveling a caster overwrote remaining slots with the new max,
    silently refilling slots already spent this adventuring day. Only the newly
    gained slots should be added; expended slots must stay expended."""
    from app.models.game_session import PartyMember
    from app.core.level_up import apply_level_up

    member = PartyMember(
        id="w1", name="Mage", character_class="wizard",
        class_levels={"wizard": 4}, _level=4,
        constitution=12, max_hp=22, current_hp=22,
        hit_die_size=6, hit_dice_total=4, hit_dice_remaining=4,
        spell_slots={1: 0, 2: 0}, spell_slots_max={1: 4, 2: 3},  # all expended
        xp=6500,
    )
    apply_level_up(member, new_level=5, hp_choice="average")

    # Previously-expended level-1/2 slots stay expended (not refilled to max)...
    assert member.spell_slots[1] == 0
    assert member.spell_slots[2] == 0
    # ...but a newly gained level-3 slot is granted.
    assert member.spell_slots.get(3, 0) > 0
    assert member.spell_slots_max.get(3, 0) > 0


def test_distance_ft_between_combatants():
    """N5 (A4): 5e grid distance — 5 ft/square, diagonals count as one square
    (Chebyshev), and unknown positions return inf (no fabricated adjacency)."""
    import math
    from app.core.combat_engine import CombatEngine, CombatState

    engine = CombatEngine(combat_state=CombatState())
    engine.state.positions["a"] = (0, 0)
    engine.state.positions["b"] = (3, 4)        # max(3,4)=4 squares
    assert engine._distance_ft("a", "b") == 20.0
    engine.state.positions["c"] = {"x": 1, "y": 1}   # diagonally adjacent
    assert engine._distance_ft("a", "c") == 5.0
    assert engine._distance_ft("a", "missing") == math.inf


def test_condition_registry_includes_core_conditions():
    """N5-root: load_conditions only loaded conditions.json (7 entries), so
    paralyzed/unconscious/blinded/etc. (defined only in the built-in defaults)
    were absent and their attack effects silently never applied."""
    from app.core.condition_effects import load_conditions, get_attack_modifiers

    conds = load_conditions()
    for cid in ("paralyzed", "unconscious", "blinded", "incapacitated", "prone"):
        assert cid in conds, f"{cid} missing from condition registry"

    # The effect is actually wired: a paralyzed target attacked in melee within
    # 5 ft grants advantage and auto-crit.
    m = get_attack_modifiers(
        attacker_conditions=[], target_conditions=["paralyzed"],
        is_melee=True, distance_ft=5,
    )
    assert m.advantage and m.auto_critical


def test_monster_attack_auto_crits_paralyzed_adjacent_target():
    """N5 (A4): monster attacks ignored target conditions — a hit on a paralyzed
    target within 5 ft must be a critical (and the attack has advantage)."""
    from app.core.combat_engine import CombatEngine, CombatState
    from app.core.monster_abilities import MonsterAbility, AbilityType

    monster = {
        "id": "ogre", "name": "Ogre", "type": "enemy",
        "hp": 59, "max_hp": 59, "ac": 11, "speed": 40,
        "str_mod": 4, "attack_bonus": 6, "damage_dice": "2d8", "damage_type": "bludgeoning",
        "abilities": {"strength": 19, "dexterity": 8, "constitution": 16,
                      "intelligence": 5, "wisdom": 7, "charisma": 7},
        "class": "monster", "level": 1, "conditions": [],
    }
    player = {
        "id": "victim", "name": "Victim", "type": "player",
        "hp": 40, "max_hp": 40, "ac": 1, "speed": 30,   # AC 1 so any non-nat1 roll hits
        "str_mod": 0, "attack_bonus": 2, "damage_dice": "1d6", "damage_type": "slashing",
        "abilities": {"strength": 10, "dexterity": 10, "constitution": 10,
                      "intelligence": 10, "wisdom": 10, "charisma": 10},
        "class": "fighter", "level": 1, "conditions": ["paralyzed"],
    }
    engine = CombatEngine(combat_state=CombatState())
    engine.start_combat([player], [monster])
    # Place them adjacent (within 5 ft).
    engine.state.positions["ogre"] = (0, 0)
    engine.state.positions["victim"] = (1, 0)

    attack = MonsterAbility(
        id="slam", name="Slam", original_description="Melee Weapon Attack",
        ability_type=AbilityType.MELEE_ATTACK,
        attack_bonus=6, damage_dice="2d8", damage_type="bludgeoning",
    )
    ogre = engine.state.initiative_tracker.get_combatant("ogre")
    ogre_stats = engine.state.combatant_stats["ogre"]

    hit_seen = False
    for _ in range(40):
        # reset victim HP so repeated hits don't end combat / go to 0
        engine.state.combatant_stats["victim"]["current_hp"] = 40
        res = engine._execute_single_monster_attack(ogre, ogre_stats, attack, "victim")
        if res["hit"]:
            hit_seen = True
            assert res["critical"], "hit on a paralyzed adjacent target must be a crit"
    assert hit_seen, "expected at least one hit across 40 attacks"
