"""
Foundry VTT Export Module.

Provides tools to export D&D content to Foundry VTT compatible format.
Supports monsters, spells, items, and complete module packaging.
"""

from .monster_exporter import MonsterExporter
from .module_builder import build_module, build_monster_pack
from .utils import generate_foundry_id, convert_to_html, parse_damage_dice

__all__ = [
    'MonsterExporter',
    'build_module',
    'build_monster_pack',
    'generate_foundry_id',
    'convert_to_html',
    'parse_damage_dice',
]
