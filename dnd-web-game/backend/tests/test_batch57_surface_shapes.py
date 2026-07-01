"""Batch 57 (A3-tail): surfaces cover their real spell areas, not a single tile.

A3b placed one surface per targeted tile. Per the 2024 spell areas: Grease covers a
10-ft square (2x2 tiles), Web a 20-ft cube (4x4), Cloudkill a 20-ft-radius sphere,
and the walls (Wall of Fire/Ice) are lines — oriented perpendicular to the
caster->target axis (a wall between you and them), centered on the target tile.
Tiles off the grid are clipped (existing guard).
"""
from app.core.combat_engine import CombatEngine, CombatState, CombatPhase, TurnState
from app.core.surfaces import spell_surface_tiles


def test_grease_covers_2x2_square():
    tiles = spell_surface_tiles("grease", (3, 3))
    assert set(tiles) == {(3, 3), (4, 3), (3, 4), (4, 4)}


def test_web_covers_4x4_cube():
    tiles = spell_surface_tiles("web", (2, 2))
    assert len(set(tiles)) == 16
    assert (2, 2) in tiles and (5, 5) in tiles and (6, 6) not in tiles


def test_cloudkill_covers_sphere_radius_4():
    tiles = set(spell_surface_tiles("cloudkill", (0, 0)))
    assert (4, 0) in tiles          # 20 ft away: inside
    assert (2, 2) in tiles          # sqrt(8) tiles ~ 14 ft: inside
    assert (4, 3) not in tiles      # sqrt(25)=5 tiles = 25 ft: outside


def test_wall_is_a_line_perpendicular_to_the_caster():
    # Caster west of the anchor -> the wall runs north-south (constant x).
    tiles = spell_surface_tiles("wall_of_fire", (4, 4), caster_pos=(0, 4))
    assert len(tiles) > 4
    assert all(x == 4 for x, y in tiles)
    assert (4, 4) in tiles
    # Caster north of the anchor -> the wall runs east-west (constant y).
    tiles2 = spell_surface_tiles("wall_of_ice", (4, 4), caster_pos=(4, 0))
    assert all(y == 4 for x, y in tiles2)


def test_unknown_spell_returns_none():
    assert spell_surface_tiles("magic_missile", (0, 0)) is None


def _engine():
    def _mk(cid, ctype):
        return {"id": cid, "name": cid, "type": ctype, "hp": 30, "max_hp": 30, "ac": 12,
                "speed": 30, "abilities": {"strength": 12, "dexterity": 12, "constitution": 14,
                                           "intelligence": 10, "wisdom": 10, "charisma": 10},
                "class": "wizard", "level": 5, "conditions": []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([_mk("wiz", "player")], [_mk("gob", "enemy")],
                     positions={"wiz": (0, 0), "gob": (5, 5)})
    eng.state.phase = CombatPhase.COMBAT_ACTIVE
    eng.state.current_turn = TurnState(combatant_id="wiz")
    return eng


def test_engine_places_full_grease_area():
    eng = _engine()
    placed = eng.apply_spell_surfaces(["grease"], [(3, 3)], caster_id="wiz", spell_id="grease")
    assert placed == 4
    for tile in [(3, 3), (4, 3), (3, 4), (4, 4)]:
        assert eng.state.surface_manager.get_surfaces_at(*tile)


def test_engine_clips_area_to_grid():
    eng = _engine()
    placed = eng.apply_spell_surfaces(["grease"], [(7, 7)], caster_id="wiz", spell_id="grease")
    assert placed == 1              # 2x2 from (7,7) has 3 tiles off an 8x8 grid
    assert eng.state.surface_manager.get_surfaces_at(7, 7)


def test_engine_single_tile_fallback_for_unmapped_spell():
    eng = _engine()
    placed = eng.apply_spell_surfaces(["fire"], [(2, 2)], caster_id="wiz", spell_id="some_homebrew")
    assert placed == 1
    assert eng.state.surface_manager.get_surfaces_at(2, 2)
