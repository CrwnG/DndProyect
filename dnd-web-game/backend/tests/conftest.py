"""
D&D Combat Engine - Test Configuration and Fixtures
Shared test utilities and fixtures for pytest.
"""
import pytest
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==================== Event Loop Fixture ====================

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== Character Fixtures ====================

@pytest.fixture
def sample_player() -> Dict[str, Any]:
    """Create a sample player character."""
    return {
        "id": "player-1",
        "name": "Thorin Ironforge",
        "type": "player",
        "race": "Dwarf",
        "class": "Fighter",
        "level": 5,
        "hp": 45,
        "max_hp": 45,
        "temp_hp": 0,
        "ac": 18,
        "speed": 25,
        "dex_mod": 1,
        "str_mod": 3,
        "con_mod": 2,
        "int_mod": 0,
        "wis_mod": 1,
        "cha_mod": 0,
        "proficiency_bonus": 3,
        "abilities": {
            "strength": 16,
            "dexterity": 12,
            "constitution": 14,
            "intelligence": 10,
            "wisdom": 13,
            "charisma": 11
        },
        "saving_throws": {
            "strength": True,
            "constitution": True
        },
        "skills": ["athletics", "intimidation", "perception"],
        "weapons": [
            {
                "name": "Battleaxe",
                "damage": "1d8",
                "damage_type": "slashing",
                "properties": ["versatile"],
                "attack_bonus": 6
            }
        ],
        "armor": {"name": "Chain Mail", "base_ac": 16},
        "shield": {"name": "Shield", "ac_bonus": 2},
        "conditions": [],
        "features": ["Second Wind", "Action Surge", "Extra Attack"]
    }


@pytest.fixture
def sample_enemy() -> Dict[str, Any]:
    """Create a sample enemy creature."""
    return {
        "id": "enemy-1",
        "name": "Goblin",
        "type": "enemy",
        "creature_type": "humanoid",
        "cr": 0.25,
        "hp": 7,
        "max_hp": 7,
        "ac": 15,
        "speed": 30,
        "dex_mod": 2,
        "str_mod": -1,
        "con_mod": 0,
        "abilities": {
            "strength": 8,
            "dexterity": 14,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 8,
            "charisma": 8
        },
        "attacks": [
            {
                "name": "Scimitar",
                "attack_bonus": 4,
                "damage": "1d6+2",
                "damage_type": "slashing"
            },
            {
                "name": "Shortbow",
                "attack_bonus": 4,
                "damage": "1d6+2",
                "damage_type": "piercing",
                "range": "80/320"
            }
        ],
        "special_abilities": [
            {"name": "Nimble Escape", "description": "Disengage or Hide as bonus action"}
        ],
        "conditions": []
    }


@pytest.fixture
def sample_spellcaster() -> Dict[str, Any]:
    """Create a sample spellcasting character."""
    return {
        "id": "player-2",
        "name": "Elara Moonwhisper",
        "type": "player",
        "race": "Elf",
        "class": "Wizard",
        "level": 5,
        "hp": 28,
        "max_hp": 28,
        "ac": 12,
        "speed": 30,
        "dex_mod": 2,
        "str_mod": -1,
        "con_mod": 1,
        "int_mod": 4,
        "wis_mod": 1,
        "cha_mod": 0,
        "proficiency_bonus": 3,
        "spell_slots": {
            "1": 4,
            "2": 3,
            "3": 2
        },
        "spells_known": [
            "fire_bolt", "ray_of_frost", "mage_hand", "prestidigitation",
            "magic_missile", "shield", "misty_step", "scorching_ray",
            "fireball", "counterspell"
        ],
        "spell_save_dc": 15,
        "spell_attack_bonus": 7,
        "conditions": []
    }


@pytest.fixture
def party(sample_player, sample_spellcaster) -> List[Dict[str, Any]]:
    """Create a sample party of adventurers."""
    return [sample_player, sample_spellcaster]


@pytest.fixture
def enemy_group(sample_enemy) -> List[Dict[str, Any]]:
    """Create a group of enemies."""
    enemies = []
    for i in range(3):
        enemy = sample_enemy.copy()
        enemy["id"] = f"enemy-{i+1}"
        enemy["name"] = f"Goblin {i+1}"
        enemies.append(enemy)
    return enemies


# ==================== Combat Fixtures ====================

@pytest.fixture
def combat_state():
    """Create a fresh combat state."""
    from app.core.combat_engine import CombatState
    return CombatState()


@pytest.fixture
def combat_engine(combat_state):
    """Create a combat engine with fresh state."""
    from app.core.combat_engine import CombatEngine
    return CombatEngine(combat_state=combat_state)


@pytest.fixture
def active_combat(combat_engine, party, enemy_group):
    """Create an active combat with participants."""
    combat_engine.start_combat(party, enemy_group)
    return combat_engine


# ==================== Campaign Fixtures ====================

@pytest.fixture
def sample_encounter() -> Dict[str, Any]:
    """Create a sample encounter."""
    return {
        "id": "encounter-1",
        "name": "Goblin Ambush",
        "type": "combat",
        "description": "A group of goblins springs from the underbrush!",
        "enemies": [
            {"monster_id": "goblin", "count": 3},
            {"monster_id": "goblin_boss", "count": 1}
        ],
        "difficulty": "medium",
        "xp_reward": 150,
        "terrain": "forest",
        "environmental_effects": [],
        "loot": [
            {"item": "gold", "amount": "2d6"},
            {"item": "shortbow", "chance": 0.3}
        ]
    }


@pytest.fixture
def sample_chapter(sample_encounter) -> Dict[str, Any]:
    """Create a sample chapter."""
    return {
        "id": "chapter-1",
        "title": "The Forest Road",
        "summary": "The party travels through dangerous wilderness.",
        "encounters": [sample_encounter["id"]],
        "opening_narration": "The forest path grows dark as the canopy thickens...",
        "completion_text": "With the goblins defeated, the road ahead is clear.",
        "choices": [
            {
                "id": "choice-1",
                "text": "Follow the goblin tracks",
                "leads_to": "chapter-2a",
                "requirements": {"skill_check": {"skill": "survival", "dc": 12}}
            },
            {
                "id": "choice-2",
                "text": "Continue to the town",
                "leads_to": "chapter-2b"
            }
        ]
    }


@pytest.fixture
def sample_campaign(sample_chapter) -> Dict[str, Any]:
    """Create a sample campaign."""
    return {
        "id": "campaign-1",
        "name": "The Lost Mine",
        "description": "An adventure to reclaim a lost dwarven mine.",
        "party_level_min": 1,
        "party_level_max": 5,
        "chapters": [sample_chapter],
        "current_chapter": "chapter-1",
        "world_state": {
            "flags": {},
            "npc_dispositions": {},
            "inventory": []
        }
    }


# ==================== Authentication Fixtures ====================

@pytest.fixture
def sample_user() -> Dict[str, Any]:
    """Create a sample user."""
    return {
        "id": "user-123",
        "username": "adventurer",
        "email": "adventurer@example.com",
        "display_name": "The Adventurer",
        "is_active": True,
        "created_at": datetime.utcnow()
    }


@pytest.fixture
def auth_tokens() -> Dict[str, str]:
    """Create sample auth tokens."""
    return {
        "access_token": "test-access-token-123",
        "refresh_token": "test-refresh-token-456",
        "token_type": "bearer"
    }


# ==================== Mock Fixtures ====================

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    mock = AsyncMock()
    mock.execute = AsyncMock(return_value=MagicMock())
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_ai_client():
    """Create a mock AI client."""
    mock = AsyncMock()
    mock.generate = AsyncMock(return_value={
        "content": "The goblin snarls and raises its scimitar...",
        "tokens_used": 50
    })
    return mock


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    mock = AsyncMock()
    mock.accept = AsyncMock()
    mock.send_json = AsyncMock()
    mock.receive_json = AsyncMock(return_value={"type": "ping"})
    mock.close = AsyncMock()
    return mock


# ==================== Grid/Map Fixtures ====================

@pytest.fixture
def sample_grid() -> Dict[str, Any]:
    """Create a sample combat grid."""
    return {
        "width": 20,
        "height": 15,
        "cell_size": 5,  # feet
        "terrain": [
            {"x": 5, "y": 5, "type": "difficult"},
            {"x": 6, "y": 5, "type": "difficult"},
            {"x": 10, "y": 8, "type": "obstacle"}
        ],
        "tokens": []
    }


# ==================== Utility Functions ====================

@pytest.fixture
def roll_result():
    """Factory for creating roll results."""
    def _roll_result(total: int, dice: str = "1d20", natural: int = None):
        return {
            "total": total,
            "dice": dice,
            "rolls": [natural or total],
            "modifier": total - (natural or total),
            "critical": natural == 20,
            "fumble": natural == 1
        }
    return _roll_result


# ==================== Test Data Helpers ====================

@pytest.fixture
def generate_combatants():
    """Factory for generating multiple combatants."""
    def _generate(count: int, base_name: str = "Combatant", is_enemy: bool = False):
        combatants = []
        for i in range(count):
            combatants.append({
                "id": f"{'enemy' if is_enemy else 'player'}-{i+1}",
                "name": f"{base_name} {i+1}",
                "type": "enemy" if is_enemy else "player",
                "hp": 20 + (i * 5),
                "max_hp": 20 + (i * 5),
                "ac": 12 + i,
                "dex_mod": i,
                "speed": 30
            })
        return combatants
    return _generate


# ==================== Cleanup Fixtures ====================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Run cleanup after each test."""
    yield
    # Cleanup code here if needed


# ==================== Test Categories ====================

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "combat: Combat system tests")
    config.addinivalue_line("markers", "auth: Authentication tests")
    config.addinivalue_line("markers", "campaign: Campaign system tests")
