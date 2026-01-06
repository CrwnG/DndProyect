"""
Procedural Battlemap Generation System.

Generates tactical battlemaps for D&D 5e encounters using:
- Binary Space Partitioning (BSP) for dungeon layouts
- Room templates for different encounter types
- Difficulty scaling based on party level
"""

from .dungeon_generator import DungeonGenerator, GeneratedMap, generate_battlemap
from .room_templates import RoomTemplate, RoomType, get_room_template
from .difficulty_scaler import DifficultyScaler, DifficultyLevel

__all__ = [
    "DungeonGenerator",
    "GeneratedMap",
    "generate_battlemap",
    "RoomTemplate",
    "RoomType",
    "get_room_template",
    "DifficultyScaler",
    "DifficultyLevel",
]
