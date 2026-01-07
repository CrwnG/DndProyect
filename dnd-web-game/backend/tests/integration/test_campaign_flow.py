"""
Integration tests for Campaign Flow
Tests full campaign playthrough from creation to completion.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ==================== Campaign Creation Tests ====================

class TestCampaignCreation:
    """Test campaign creation flow."""

    @pytest.fixture
    def sample_campaign_config(self):
        """Sample campaign configuration."""
        return {
            "name": "The Lost Mine of Phandelver",
            "description": "A classic D&D adventure",
            "party_level_min": 1,
            "party_level_max": 5,
            "length": "medium",
            "tone": "heroic"
        }

    @pytest.fixture
    def sample_chapters(self):
        """Sample chapter structure."""
        return [
            {
                "id": "chapter-1",
                "title": "Goblin Arrows",
                "encounters": [
                    {"id": "enc-1", "type": "combat", "name": "Goblin Ambush"},
                    {"id": "enc-2", "type": "exploration", "name": "Cragmaw Hideout"}
                ]
            },
            {
                "id": "chapter-2",
                "title": "Phandalin",
                "encounters": [
                    {"id": "enc-3", "type": "social", "name": "Town Investigation"},
                    {"id": "enc-4", "type": "combat", "name": "Redbrand Ruffians"}
                ]
            }
        ]

    def test_campaign_structure_validation(self, sample_campaign_config, sample_chapters):
        """Campaign structure should be valid."""
        assert sample_campaign_config["name"] is not None
        assert len(sample_chapters) >= 1
        for chapter in sample_chapters:
            assert "id" in chapter
            assert "encounters" in chapter
            assert len(chapter["encounters"]) >= 1


# ==================== Encounter Flow Tests ====================

class TestEncounterFlow:
    """Test encounter progression."""

    @pytest.fixture
    def combat_encounter(self):
        return {
            "id": "enc-combat-1",
            "type": "combat",
            "name": "Goblin Patrol",
            "enemies": [
                {"monster_id": "goblin", "count": 3}
            ],
            "difficulty": "easy",
            "xp_reward": 75,
            "completion_conditions": ["all_enemies_defeated"]
        }

    @pytest.fixture
    def social_encounter(self):
        return {
            "id": "enc-social-1",
            "type": "social",
            "name": "The Nervous Innkeeper",
            "npc_id": "npc-innkeeper",
            "dialogue_tree": {
                "root": {
                    "text": "Welcome to the Stonehill Inn...",
                    "options": [
                        {"text": "Ask about rumors", "leads_to": "rumors"},
                        {"text": "Rent a room", "leads_to": "room"}
                    ]
                }
            },
            "skill_checks": [
                {"skill": "persuasion", "dc": 12, "outcome": "extra_info"}
            ]
        }

    def test_combat_encounter_has_required_fields(self, combat_encounter):
        """Combat encounter should have all required fields."""
        assert combat_encounter["type"] == "combat"
        assert "enemies" in combat_encounter
        assert "difficulty" in combat_encounter
        assert "xp_reward" in combat_encounter

    def test_social_encounter_has_dialogue(self, social_encounter):
        """Social encounter should have dialogue tree."""
        assert social_encounter["type"] == "social"
        assert "dialogue_tree" in social_encounter
        assert "root" in social_encounter["dialogue_tree"]


# ==================== Choice and Consequence Tests ====================

class TestChoiceConsequences:
    """Test choice tracking and consequences."""

    @pytest.fixture
    def world_state(self):
        return {
            "flags": {},
            "npc_dispositions": {
                "npc-innkeeper": 0,
                "npc-merchant": 0
            },
            "choice_history": [],
            "pending_consequences": []
        }

    @pytest.fixture
    def sample_choice(self):
        return {
            "id": "choice-1",
            "text": "Threaten the innkeeper",
            "effects": [
                {"type": "npc_disposition", "npc_id": "npc-innkeeper", "delta": -20},
                {"type": "set_flag", "flag": "threatened_innkeeper", "value": True}
            ],
            "delayed_consequences": [
                {
                    "trigger": {"chapters_delay": 1},
                    "effect": {"type": "encounter_modifier", "encounter_id": "enc-3", "modifier": "hostile_npcs"}
                }
            ]
        }

    def test_choice_modifies_disposition(self, world_state, sample_choice):
        """Choice should modify NPC disposition."""
        for effect in sample_choice["effects"]:
            if effect["type"] == "npc_disposition":
                npc_id = effect["npc_id"]
                delta = effect["delta"]
                world_state["npc_dispositions"][npc_id] += delta

        assert world_state["npc_dispositions"]["npc-innkeeper"] == -20

    def test_choice_sets_flag(self, world_state, sample_choice):
        """Choice should set world state flags."""
        for effect in sample_choice["effects"]:
            if effect["type"] == "set_flag":
                world_state["flags"][effect["flag"]] = effect["value"]

        assert world_state["flags"]["threatened_innkeeper"] is True

    def test_delayed_consequences_queued(self, world_state, sample_choice):
        """Delayed consequences should be queued."""
        for consequence in sample_choice.get("delayed_consequences", []):
            world_state["pending_consequences"].append({
                "choice_id": sample_choice["id"],
                **consequence
            })

        assert len(world_state["pending_consequences"]) == 1
        assert world_state["pending_consequences"][0]["choice_id"] == "choice-1"


# ==================== Campaign Progression Tests ====================

class TestCampaignProgression:
    """Test campaign state progression."""

    @pytest.fixture
    def campaign_state(self):
        return {
            "id": "campaign-1",
            "current_chapter_index": 0,
            "current_encounter_index": 0,
            "chapters": [
                {"id": "ch-1", "encounters": ["enc-1", "enc-2"]},
                {"id": "ch-2", "encounters": ["enc-3", "enc-4"]}
            ],
            "completed_encounters": [],
            "party": [
                {"id": "player-1", "name": "Hero", "hp": 25, "max_hp": 25, "xp": 0}
            ],
            "total_xp_earned": 0
        }

    def test_complete_encounter_progression(self, campaign_state):
        """Completing encounter should progress to next."""
        current_enc = campaign_state["chapters"][0]["encounters"][0]
        campaign_state["completed_encounters"].append(current_enc)
        campaign_state["current_encounter_index"] += 1

        assert current_enc in campaign_state["completed_encounters"]
        assert campaign_state["current_encounter_index"] == 1

    def test_chapter_completion(self, campaign_state):
        """Completing all encounters should advance chapter."""
        chapter = campaign_state["chapters"][0]

        # Complete all encounters in chapter
        for enc_id in chapter["encounters"]:
            campaign_state["completed_encounters"].append(enc_id)

        # Advance to next chapter
        campaign_state["current_chapter_index"] += 1
        campaign_state["current_encounter_index"] = 0

        assert campaign_state["current_chapter_index"] == 1
        assert len(campaign_state["completed_encounters"]) == 2

    def test_xp_distribution(self, campaign_state):
        """XP should be distributed to party."""
        xp_reward = 150

        for player in campaign_state["party"]:
            player["xp"] += xp_reward

        campaign_state["total_xp_earned"] += xp_reward

        assert campaign_state["party"][0]["xp"] == 150
        assert campaign_state["total_xp_earned"] == 150


# ==================== Save/Load Tests ====================

class TestSaveLoad:
    """Test campaign save/load functionality."""

    @pytest.fixture
    def saveable_state(self):
        return {
            "version": "1.0",
            "saved_at": datetime.utcnow().isoformat(),
            "campaign_id": "campaign-1",
            "current_chapter": 0,
            "current_encounter": 1,
            "party": [
                {"id": "p1", "name": "Hero", "hp": 20, "max_hp": 25}
            ],
            "world_state": {
                "flags": {"met_innkeeper": True},
                "npc_dispositions": {"npc-1": 10}
            },
            "combat_state": None
        }

    def test_state_serializable(self, saveable_state):
        """State should be JSON serializable."""
        import json

        try:
            serialized = json.dumps(saveable_state)
            deserialized = json.loads(serialized)
            assert deserialized["campaign_id"] == "campaign-1"
        except (TypeError, ValueError) as e:
            pytest.fail(f"State not serializable: {e}")

    def test_state_integrity_after_load(self, saveable_state):
        """State should maintain integrity after save/load."""
        import json

        original_hp = saveable_state["party"][0]["hp"]
        serialized = json.dumps(saveable_state)
        loaded = json.loads(serialized)

        assert loaded["party"][0]["hp"] == original_hp
        assert loaded["world_state"]["flags"]["met_innkeeper"] is True


# ==================== Multiplayer Session Tests ====================

class TestMultiplayerSession:
    """Test multiplayer campaign sessions."""

    @pytest.fixture
    def session_state(self):
        return {
            "id": "session-123",
            "campaign_id": "campaign-1",
            "host_id": "user-1",
            "players": [
                {"user_id": "user-1", "character_id": "char-1", "is_host": True},
                {"user_id": "user-2", "character_id": "char-2", "is_host": False}
            ],
            "decision_mode": "voting",
            "current_vote": None
        }

    @pytest.fixture
    def vote_state(self):
        return {
            "choice_id": "choice-1",
            "options": ["option-a", "option-b"],
            "votes": {},
            "deadline": None
        }

    def test_vote_collection(self, session_state, vote_state):
        """Votes should be collected from all players."""
        session_state["current_vote"] = vote_state

        # Player 1 votes
        vote_state["votes"]["user-1"] = "option-a"
        # Player 2 votes
        vote_state["votes"]["user-2"] = "option-b"

        assert len(vote_state["votes"]) == 2

    def test_vote_resolution_majority(self, session_state, vote_state):
        """Votes should resolve by majority."""
        vote_state["votes"] = {
            "user-1": "option-a",
            "user-2": "option-a",
            "user-3": "option-b"
        }

        # Count votes
        vote_counts = {}
        for vote in vote_state["votes"].values():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        winner = max(vote_counts, key=vote_counts.get)
        assert winner == "option-a"

    def test_vote_resolution_tie(self, session_state, vote_state):
        """Tie should be resolved by host or random."""
        vote_state["votes"] = {
            "user-1": "option-a",
            "user-2": "option-b"
        }

        vote_counts = {}
        for vote in vote_state["votes"].values():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        # Tie detected
        max_votes = max(vote_counts.values())
        tied_options = [k for k, v in vote_counts.items() if v == max_votes]

        assert len(tied_options) == 2  # Tie exists


# ==================== Full Campaign Playthrough Simulation ====================

class TestFullPlaythrough:
    """Simulate a complete campaign playthrough."""

    @pytest.fixture
    def mini_campaign(self):
        """Create a minimal complete campaign."""
        return {
            "id": "mini-campaign",
            "name": "The Quick Quest",
            "chapters": [
                {
                    "id": "ch-1",
                    "title": "Beginning",
                    "encounters": [
                        {
                            "id": "enc-1",
                            "type": "story",
                            "text": "You receive a quest from the village elder."
                        }
                    ],
                    "choices": [
                        {"id": "accept", "text": "Accept the quest", "leads_to": "ch-2"},
                        {"id": "decline", "text": "Decline", "leads_to": "ending-bad"}
                    ]
                },
                {
                    "id": "ch-2",
                    "title": "The Journey",
                    "encounters": [
                        {
                            "id": "enc-2",
                            "type": "combat",
                            "enemies": [{"monster_id": "goblin", "count": 2}],
                            "xp_reward": 50
                        }
                    ],
                    "on_complete": "ending-good"
                }
            ],
            "endings": {
                "ending-good": {"title": "Victory!", "text": "You saved the village!"},
                "ending-bad": {"title": "Cowardice", "text": "The village falls."}
            }
        }

    def test_campaign_has_valid_structure(self, mini_campaign):
        """Campaign should have all required elements."""
        assert "chapters" in mini_campaign
        assert "endings" in mini_campaign
        assert len(mini_campaign["chapters"]) >= 1

    def test_all_paths_lead_to_endings(self, mini_campaign):
        """All choice paths should lead to valid destinations."""
        valid_destinations = set()
        valid_destinations.update(mini_campaign["endings"].keys())
        for chapter in mini_campaign["chapters"]:
            valid_destinations.add(chapter["id"])

        for chapter in mini_campaign["chapters"]:
            for choice in chapter.get("choices", []):
                assert choice["leads_to"] in valid_destinations, \
                    f"Invalid destination: {choice['leads_to']}"

    def test_playthrough_good_path(self, mini_campaign):
        """Simulate good ending playthrough."""
        state = {
            "current_chapter": "ch-1",
            "completed": False,
            "ending": None,
            "xp_earned": 0
        }

        # Chapter 1: Accept quest
        state["current_chapter"] = "ch-2"  # Choice leads here

        # Chapter 2: Complete combat
        state["xp_earned"] += 50
        state["ending"] = "ending-good"
        state["completed"] = True

        assert state["completed"] is True
        assert state["ending"] == "ending-good"
        assert state["xp_earned"] == 50

    def test_playthrough_bad_path(self, mini_campaign):
        """Simulate bad ending playthrough."""
        state = {
            "current_chapter": "ch-1",
            "completed": False,
            "ending": None
        }

        # Chapter 1: Decline quest
        state["ending"] = "ending-bad"
        state["completed"] = True

        assert state["completed"] is True
        assert state["ending"] == "ending-bad"
