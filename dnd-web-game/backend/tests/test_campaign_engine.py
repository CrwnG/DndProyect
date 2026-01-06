"""Tests for the campaign engine state machine."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

from app.core.campaign_engine import (
    CampaignEngine,
    CampaignAction,
    CampaignState,
    load_campaign,
    list_campaigns,
)
from app.models.campaign import (
    Campaign,
    Encounter,
    EncounterType,
    RestType,
    CombatSetup,
    ChoiceSetup,
    Choice,
    SkillCheck,
    CheckType,
    StoryContent,
    EncounterTransitions,
    Rewards,
    WorldState,
    GridEnvironment,
)
from app.models.game_session import (
    GameSession,
    SessionPhase,
    PartyMember,
)


class TestCampaignAction:
    """Tests for CampaignAction enum."""

    def test_action_values(self):
        """CampaignAction should have correct string values."""
        assert CampaignAction.START_CAMPAIGN.value == "start_campaign"
        assert CampaignAction.CONTINUE.value == "continue"
        assert CampaignAction.START_COMBAT.value == "start_combat"
        assert CampaignAction.END_COMBAT.value == "end_combat"
        assert CampaignAction.MAKE_CHOICE.value == "make_choice"
        assert CampaignAction.REST.value == "rest"
        assert CampaignAction.SKIP_REST.value == "skip_rest"
        assert CampaignAction.RETRY.value == "retry"
        assert CampaignAction.QUIT.value == "quit"


class TestCampaignState:
    """Tests for CampaignState dataclass."""

    def test_to_dict(self):
        """to_dict should return correct dictionary."""
        state = CampaignState(
            session_id="test-session",
            phase=SessionPhase.STORY_INTRO,
            encounter_id="enc1",
            encounter_name="Test Encounter",
            encounter_type="combat",
            story_text="You enter a dark dungeon...",
            combat_id=None,
            round=1,
            party_summary=[{"name": "Hero", "hp": 20}],
            world_time={"day": 1, "hour": 8},
            available_actions=["start_combat"],
        )

        d = state.to_dict()
        assert d["session_id"] == "test-session"
        assert d["phase"] == "story_intro"
        assert d["encounter_id"] == "enc1"
        assert d["encounter_name"] == "Test Encounter"
        assert d["story_text"] == "You enter a dark dungeon..."
        assert d["round"] == 1
        assert d["available_actions"] == ["start_combat"]

    def test_to_dict_with_choices(self):
        """to_dict should include choice data when present."""
        state = CampaignState(
            session_id="test",
            phase=SessionPhase.CHOICE,
            encounter_id="choice1",
            encounter_name="Fork in the Road",
            encounter_type="choice",
            story_text="You come to a fork.",
            combat_id=None,
            round=1,
            party_summary=[],
            world_time={"day": 1},
            available_actions=["make_choice"],
            choices=[{"id": "left", "text": "Go left"}],
            choice_result={"outcome": "success"},
        )

        d = state.to_dict()
        assert d["choices"] == [{"id": "left", "text": "Go left"}]
        assert d["choice_result"] == {"outcome": "success"}

    def test_to_dict_with_ai_content(self):
        """to_dict should include AI-generated content."""
        state = CampaignState(
            session_id="test",
            phase=SessionPhase.STORY_INTRO,
            encounter_id="enc1",
            encounter_name="Test",
            encounter_type="combat",
            story_text="Original text",
            combat_id=None,
            round=1,
            party_summary=[],
            world_time={"day": 1},
            available_actions=[],
            ai_scene_description="The AI sees a dragon...",
            ai_narration="The AI narrates the scene.",
        )

        d = state.to_dict()
        assert d["ai_scene_description"] == "The AI sees a dragon..."
        assert d["ai_narration"] == "The AI narrates the scene."


class TestCampaignEngineCreation:
    """Tests for CampaignEngine initialization."""

    def create_test_campaign(self):
        """Create a minimal test campaign."""
        return Campaign(
            id="test-campaign",
            name="Test Campaign",
            description="A test campaign",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="First Encounter",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Welcome!"),
                    transitions=EncounterTransitions(on_victory="enc2"),
                ),
                "enc2": Encounter(
                    id="enc2",
                    name="Second Encounter",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="The journey continues."),
                ),
            },
        )

    def create_test_party(self):
        """Create a minimal test party."""
        return [
            PartyMember(
                id="player1",
                name="Hero",
                character_class="Fighter",
                _level=1,
                max_hp=12,
                current_hp=12,
                strength=16,
                dexterity=14,
                constitution=14,
                intelligence=10,
                wisdom=12,
                charisma=8,
            )
        ]

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_create_new(self, mock_ai_dm):
        """create_new should initialize a new campaign."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)
        campaign = self.create_test_campaign()
        party = self.create_test_party()

        engine = CampaignEngine.create_new(campaign, party)

        assert engine.campaign == campaign
        assert engine.session is not None
        assert len(engine.session.party) == 1
        assert engine.session.phase == SessionPhase.MENU

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_from_save(self, mock_ai_dm):
        """from_save should restore from session data."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)
        campaign = self.create_test_campaign()

        session_data = {
            "id": "saved-session",
            "campaign_id": "test-campaign",
            "phase": "story_intro",
            "current_encounter_id": "enc1",
            "party": [
                {
                    "id": "player1",
                    "name": "Saved Hero",
                    "character_class": "Wizard",
                    "level": 3,
                    "max_hp": 18,
                    "current_hp": 15,
                }
            ],
            "world_state": {
                "flags": ["visited_town"],
                "variables": {},
                "time": {"day": 2, "hour": 14},
            },
        }

        engine = CampaignEngine.from_save(campaign, session_data)

        assert engine.session.id == "saved-session"
        assert engine.session.phase == SessionPhase.STORY_INTRO


class TestCampaignEngineState:
    """Tests for CampaignEngine state management."""

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_get_state_returns_campaign_state(self, mock_ai_dm):
        """get_state should return a CampaignState object."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="Test Encounter",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Hello"),
                ),
            },
        )

        party = [
            PartyMember(
                id="p1",
                name="Hero",
                character_class="Fighter",
            )
        ]

        engine = CampaignEngine.create_new(campaign, party)
        state = engine.get_state()

        assert isinstance(state, CampaignState)
        assert state.phase == SessionPhase.MENU
        assert state.session_id == engine.session.id

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_get_state_includes_party_summary(self, mock_ai_dm):
        """get_state should include party member info."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="Test",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Hello"),
                ),
            },
        )

        party = [
            PartyMember(
                id="hero1",
                name="Thorin",
                character_class="Fighter",
                _level=5,
                max_hp=45,
                current_hp=40,
                strength=18,
            )
        ]

        engine = CampaignEngine.create_new(campaign, party)
        state = engine.get_state()

        assert len(state.party_summary) == 1
        member = state.party_summary[0]
        assert member["name"] == "Thorin"
        assert member["class"] == "Fighter"
        assert member["level"] == 5
        assert member["hp"] == 40
        assert member["max_hp"] == 45


class TestCampaignEngineAvailableActions:
    """Tests for available actions in different phases."""

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_menu_phase_actions(self, mock_ai_dm):
        """Menu phase should allow starting campaign."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="Test",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Hello"),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        state = engine.get_state()
        assert CampaignAction.START_CAMPAIGN.value in state.available_actions

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_story_intro_combat_actions(self, mock_ai_dm):
        """Story intro for combat should allow starting combat."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="combat1",
            encounters={
                "combat1": Encounter(
                    id="combat1",
                    name="Battle",
                    type=EncounterType.COMBAT,
                    story=StoryContent(intro_text="Enemies approach!"),
                    combat=CombatSetup(
                        enemies=[],
                        environment=GridEnvironment(
                            width=10, height=10,
                            player_spawns=[], enemy_spawns=[],
                            obstacles=[], difficult_terrain=[],
                        ),
                    ),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        # Start campaign to move to STORY_INTRO
        engine.advance(CampaignAction.START_CAMPAIGN)
        state = engine.get_state()

        assert state.phase == SessionPhase.STORY_INTRO
        assert CampaignAction.START_COMBAT.value in state.available_actions

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_game_over_actions(self, mock_ai_dm):
        """Game over should allow retry or quit."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="Test",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Hello"),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        # Manually set to game over
        engine.session.phase = SessionPhase.GAME_OVER

        state = engine.get_state()
        assert CampaignAction.RETRY.value in state.available_actions
        assert CampaignAction.QUIT.value in state.available_actions


class TestCampaignEngineAdvance:
    """Tests for campaign state advancement."""

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_start_campaign_advances_to_story_intro(self, mock_ai_dm):
        """START_CAMPAIGN should move to STORY_INTRO."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="Opening",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Welcome adventurer!"),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        state, _ = engine.advance(CampaignAction.START_CAMPAIGN)

        assert state.phase == SessionPhase.STORY_INTRO
        assert state.encounter_id == "enc1"
        assert state.story_text == "Welcome adventurer!"

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_quit_returns_to_menu(self, mock_ai_dm):
        """QUIT should return to MENU phase."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="Test",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Hello"),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        # Start and then quit
        engine.advance(CampaignAction.START_CAMPAIGN)
        state, _ = engine.advance(CampaignAction.QUIT)

        assert state.phase == SessionPhase.MENU

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_continue_advances_through_cutscene(self, mock_ai_dm):
        """CONTINUE should advance through cutscene encounters."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="scene1",
            encounters={
                "scene1": Encounter(
                    id="scene1",
                    name="Scene 1",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="First scene"),
                    transitions=EncounterTransitions(on_victory="scene2"),
                ),
                "scene2": Encounter(
                    id="scene2",
                    name="Scene 2",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Second scene"),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        # Start campaign
        engine.advance(CampaignAction.START_CAMPAIGN)

        # Continue through first cutscene
        state, extra = engine.advance(CampaignAction.CONTINUE)

        # Should have advanced to scene2
        assert state.encounter_id == "scene2"
        assert state.story_text == "Second scene"


class TestCampaignEngineRest:
    """Tests for rest encounter handling."""

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_rest_encounter_allows_rest_or_skip(self, mock_ai_dm):
        """Rest encounter should allow REST or SKIP_REST."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="rest1",
            encounters={
                "rest1": Encounter(
                    id="rest1",
                    name="Camp",
                    type=EncounterType.REST,
                    story=StoryContent(intro_text="You find a safe place to rest."),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        # Start campaign - should be at rest encounter
        engine.advance(CampaignAction.START_CAMPAIGN)
        state = engine.get_state()

        assert CampaignAction.REST.value in state.available_actions
        assert CampaignAction.SKIP_REST.value in state.available_actions


class TestCampaignEngineRetry:
    """Tests for retry encounter handling."""

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_retry_restores_party_hp(self, mock_ai_dm):
        """RETRY should restore party HP to max."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="Test",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Hello"),
                ),
            },
        )

        party = [
            PartyMember(
                id="p1",
                name="Hero",
                character_class="Fighter",
                max_hp=20,
                current_hp=5,  # Damaged
                is_active=False,  # Knocked out
            )
        ]

        engine = CampaignEngine.create_new(campaign, party)
        engine.session.phase = SessionPhase.GAME_OVER

        # Retry
        engine.advance(CampaignAction.RETRY)

        # Check party is restored
        member = engine.session.party[0]
        assert member.current_hp == 20  # Full HP
        assert member.is_active is True


class TestCampaignLoaderFunctions:
    """Tests for campaign loading functions."""

    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    def test_load_campaign_returns_campaign(self, mock_open, mock_exists):
        """load_campaign should load and parse campaign JSON."""
        mock_exists.return_value = True

        campaign_json = {
            "id": "test-campaign",
            "name": "Test Campaign",
            "description": "A test",
            "author": "Tester",
            "starting_encounter": "enc1",
            "encounters": {
                "enc1": {
                    "id": "enc1",
                    "name": "Test Encounter",
                    "type": "cutscene",
                    "story": {"intro_text": "Hello"},
                },
            },
        }

        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(campaign_json)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        # We need to patch json.load as well
        with patch('json.load', return_value=campaign_json):
            result = load_campaign("test-campaign")

        # Result should be a Campaign object
        assert result is not None
        assert result.name == "Test Campaign"

    @patch('pathlib.Path.exists')
    def test_load_campaign_returns_none_for_missing(self, mock_exists):
        """load_campaign should return None for missing campaigns."""
        mock_exists.return_value = False

        result = load_campaign("nonexistent-campaign")

        assert result is None

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.glob')
    def test_list_campaigns_returns_campaign_info(self, mock_glob, mock_exists):
        """list_campaigns should return list of campaign metadata."""
        mock_exists.return_value = True

        # Create mock path objects
        mock_file1 = MagicMock()
        mock_file1.stem = "campaign1"

        mock_file2 = MagicMock()
        mock_file2.stem = "campaign2"

        mock_glob.return_value = [mock_file1, mock_file2]

        campaign1_data = {
            "name": "First Campaign",
            "description": "The first one",
            "author": "Author1",
        }

        campaign2_data = {
            "campaign": {
                "name": "Second Campaign",
                "description": "The second one",
                "author": "Author2",
            }
        }

        def mock_open_impl(path, *args, **kwargs):
            mock_ctx = MagicMock()
            if "campaign1" in str(path):
                mock_ctx.__enter__.return_value = MagicMock()
            elif "campaign2" in str(path):
                mock_ctx.__enter__.return_value = MagicMock()
            mock_ctx.__exit__ = MagicMock(return_value=False)
            return mock_ctx

        with patch('builtins.open', side_effect=mock_open_impl):
            with patch('json.load', side_effect=[campaign1_data, campaign2_data]):
                result = list_campaigns()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "campaign1"
        assert result[0]["name"] == "First Campaign"
        assert result[1]["id"] == "campaign2"
        assert result[1]["name"] == "Second Campaign"


class TestCampaignEngineChoices:
    """Tests for choice encounter handling."""

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_choice_encounter_shows_choices(self, mock_ai_dm):
        """Choice encounter should include choice options in state."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="choice1",
            encounters={
                "choice1": Encounter(
                    id="choice1",
                    name="Fork in Road",
                    type=EncounterType.CHOICE,
                    story=StoryContent(intro_text="You see two paths."),
                    choices=ChoiceSetup(
                        choices=[
                            Choice(id="left", text="Go left"),
                            Choice(id="right", text="Go right"),
                        ],
                    ),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        # Start campaign
        engine.advance(CampaignAction.START_CAMPAIGN)

        # Continue to choice phase
        engine.advance(CampaignAction.CONTINUE)

        state = engine.get_state()
        assert state.phase == SessionPhase.CHOICE
        assert state.choices is not None
        assert len(state.choices) == 2


class TestCampaignEngineCombat:
    """Tests for combat encounter handling."""

    @patch('app.core.campaign_engine.get_ai_dm')
    @patch('app.core.campaign_engine.CombatEngine')
    def test_end_combat_victory_moves_to_resolution(self, mock_combat_engine, mock_ai_dm):
        """END_COMBAT with victory should move to COMBAT_RESOLUTION."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="Test",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Hello"),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        # Set up as if in combat
        engine.session.phase = SessionPhase.COMBAT
        engine.session.combat_id = "combat-123"
        engine.combat_engine = MagicMock()
        engine.combat_engine.get_combat_state.return_value = {"combatants": []}

        # End combat with victory
        state, extra = engine.advance(CampaignAction.END_COMBAT, {"victory": True})

        assert state.phase == SessionPhase.COMBAT_RESOLUTION
        assert extra["victory"] is True

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_end_combat_defeat_moves_to_game_over(self, mock_ai_dm):
        """END_COMBAT with defeat should move to GAME_OVER."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="enc1",
            encounters={
                "enc1": Encounter(
                    id="enc1",
                    name="Test",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(intro_text="Hello"),
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        # Set up as if in combat
        engine.session.phase = SessionPhase.COMBAT
        engine.session.combat_id = "combat-123"
        engine.combat_engine = MagicMock()
        engine.combat_engine.get_combat_state.return_value = {"combatants": []}

        # End combat with defeat
        state, extra = engine.advance(CampaignAction.END_COMBAT, {"victory": False})

        assert state.phase == SessionPhase.GAME_OVER
        assert extra["victory"] is False


class TestCampaignVictory:
    """Tests for campaign victory conditions."""

    @patch('app.core.campaign_engine.get_ai_dm')
    def test_last_encounter_leads_to_victory(self, mock_ai_dm):
        """Completing last encounter should trigger VICTORY phase."""
        mock_ai_dm.return_value = MagicMock(is_ai_enabled=False)

        campaign = Campaign(
            id="test",
            name="Test",
            description="Test",
            author="Test",
            starting_encounter="final",
            encounters={
                "final": Encounter(
                    id="final",
                    name="The End",
                    type=EncounterType.CUTSCENE,
                    story=StoryContent(
                        intro_text="Victory is near!",
                        outcome_victory="You have won!",
                    ),
                    # No transitions means end of campaign
                ),
            },
        )

        engine = CampaignEngine.create_new(campaign, [
            PartyMember(id="p1", name="Hero", character_class="Fighter")
        ])

        # Start and complete the campaign
        engine.advance(CampaignAction.START_CAMPAIGN)

        # Continue through the final encounter
        state, extra = engine.advance(CampaignAction.CONTINUE)

        # Should reach victory
        assert extra is not None
        assert extra.get("campaign_complete") is True
        assert state.phase == SessionPhase.VICTORY
