"""
Campaign Engine.

State machine that orchestrates campaign flow:
- Menu -> Story -> Combat -> Outcome -> Next Encounter
- Manages transitions between encounters
- Integrates with CombatEngine for tactical combat
- Handles rests, rewards, and story flags
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import json
import uuid

from app.models.campaign import (
    Campaign,
    Encounter,
    EncounterType,
    RestType,
    CombatSetup,
    EnemySpawn,
    ChoiceSetup,
    Choice,
)
from app.models.game_session import (
    GameSession,
    SessionPhase,
    PartyMember,
)
from app.core.combat_engine import CombatEngine
from app.core.initiative import Combatant, CombatantType
from app.core.skill_checks import (
    perform_skill_check,
    perform_group_check,
    get_dc_difficulty_label,
    get_skill_modifier,
)
from app.models.campaign import CheckType
from app.core.movement import CombatGrid
from app.core.reactions import ReactionsManager
from app.core.combat_storage import active_combats, active_grids, reactions_managers
from app.services.ai_dm import get_ai_dm
from app.core.progression import calculate_encounter_xp, can_level_up, get_xp_for_cr
from app.core.loot_system import get_loot_generator


class CampaignAction(str, Enum):
    """Actions that can advance the campaign state."""
    START_CAMPAIGN = "start_campaign"
    CONTINUE = "continue"           # Advance from story to next phase
    START_COMBAT = "start_combat"   # Begin combat encounter
    END_COMBAT = "end_combat"       # Combat finished
    MAKE_CHOICE = "make_choice"     # Player selects a choice (may trigger skill check)
    REST = "rest"                   # Take a rest
    SKIP_REST = "skip_rest"         # Skip rest encounter
    RETRY = "retry"                 # Retry failed encounter
    QUIT = "quit"                   # Exit to menu


@dataclass
class CampaignState:
    """Snapshot of current campaign state for frontend."""
    session_id: str
    phase: SessionPhase
    encounter_id: Optional[str]
    encounter_name: Optional[str]
    encounter_type: Optional[str]
    story_text: Optional[str]
    combat_id: Optional[str]
    round: int
    party_summary: List[Dict[str, Any]]
    world_time: Dict[str, int]
    available_actions: List[str]
    # Choice encounter data
    choices: Optional[List[Dict[str, Any]]] = None
    choice_result: Optional[Dict[str, Any]] = None
    # AI DM generated content
    ai_scene_description: Optional[str] = None
    ai_narration: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "phase": self.phase.value,
            "encounter_id": self.encounter_id,
            "encounter_name": self.encounter_name,
            "encounter_type": self.encounter_type,
            "story_text": self.story_text,
            "combat_id": self.combat_id,
            "round": self.round,
            "party_summary": self.party_summary,
            "world_time": self.world_time,
            "available_actions": self.available_actions,
            "choices": self.choices,
            "choice_result": self.choice_result,
            "ai_scene_description": self.ai_scene_description,
            "ai_narration": self.ai_narration,
        }


class CampaignEngine:
    """
    Orchestrates campaign flow through encounters.

    State machine flow:
    MENU -> STORY_INTRO -> COMBAT/REST -> STORY_OUTCOME -> (next encounter)
    """

    def __init__(self, campaign: Campaign, session: GameSession):
        self.campaign = campaign
        self.session = session
        self.session.set_campaign(campaign)

        # Combat engine reference (created when entering combat)
        self.combat_engine: Optional[CombatEngine] = None

        # Enemy data cache
        self._enemy_cache: Dict[str, Dict[str, Any]] = {}

        # Last choice result (for showing skill check results)
        self._last_choice_result: Optional[Dict[str, Any]] = None

        # Pending next encounter after choice
        self._pending_next_encounter: Optional[str] = None

        # AI DM reference
        self._ai_dm = get_ai_dm()

        # AI-generated content cache (per encounter)
        self._ai_scene_description: Optional[str] = None
        self._ai_narration: Optional[str] = None

    @classmethod
    def create_new(
        cls,
        campaign: Campaign,
        party: List[PartyMember]
    ) -> "CampaignEngine":
        """Create a new campaign playthrough."""
        session = GameSession.create_new(campaign, party)
        return cls(campaign, session)

    @classmethod
    def from_save(
        cls,
        campaign: Campaign,
        session_data: Dict[str, Any]
    ) -> "CampaignEngine":
        """Load campaign from saved session data."""
        session = GameSession.from_dict(session_data)
        return cls(campaign, session)

    def get_state(self) -> CampaignState:
        """Get current campaign state for frontend."""
        encounter = self.session.get_current_encounter()
        story_text = None
        encounter_type = None
        encounter_name = None
        choices_data = None

        if encounter:
            encounter_type = encounter.type.value
            encounter_name = encounter.name

            # Get appropriate story text based on phase
            if self.session.phase == SessionPhase.STORY_INTRO:
                story_text = encounter.story.intro_text
            elif self.session.phase == SessionPhase.STORY_OUTCOME:
                story_text = encounter.story.outcome_victory
            elif self.session.phase == SessionPhase.GAME_OVER:
                story_text = encounter.story.outcome_defeat

            # Get choices for choice encounters
            if encounter.type == EncounterType.CHOICE and encounter.choices:
                choices_data = self._get_filtered_choices(encounter.choices)

        # Build party summary
        party_summary = []
        for member in self.session.party:
            party_summary.append({
                "id": member.id,
                "name": member.name,
                "class": member.character_class,
                "level": member.level,
                "hp": member.current_hp,
                "max_hp": member.max_hp,
                "is_active": member.is_active,
                "str": member.strength,
                "dex": member.dexterity,
                "con": member.constitution,
                "int": member.intelligence,
                "wis": member.wisdom,
                "cha": member.charisma,
            })

        # Determine available actions based on phase
        available_actions = self._get_available_actions()

        return CampaignState(
            session_id=self.session.id,
            phase=self.session.phase,
            encounter_id=self.session.current_encounter_id,
            encounter_name=encounter_name,
            encounter_type=encounter_type,
            story_text=story_text,
            combat_id=self.session.combat_id,
            round=self.session.world_state.time.get("day", 1),
            party_summary=party_summary,
            world_time=self.session.world_state.time,
            available_actions=available_actions,
            choices=choices_data,
            choice_result=self._last_choice_result,
            ai_scene_description=self._ai_scene_description,
            ai_narration=self._ai_narration,
        )

    def _get_filtered_choices(self, choice_setup: ChoiceSetup) -> List[Dict[str, Any]]:
        """Get choices filtered by requirements and enhanced with skill info."""
        filtered = []
        for choice in choice_setup.choices:
            # Check required flags
            if choice.requires_flags:
                has_all = all(
                    self.session.world_state.has_flag(f)
                    for f in choice.requires_flags
                )
                if not has_all:
                    continue

            # Check hidden flags
            if choice.hidden_if_flags:
                has_any = any(
                    self.session.world_state.has_flag(f)
                    for f in choice.hidden_if_flags
                )
                if has_any:
                    continue

            # Build choice data with skill check info
            choice_dict = {
                "id": choice.id,
                "text": choice.text,
                "description": choice.description,
            }

            if choice.skill_check:
                skill_check = choice.skill_check
                choice_dict["skill_check"] = {
                    "skill": skill_check.skill,
                    "dc": skill_check.dc,
                    "difficulty": get_dc_difficulty_label(skill_check.dc),
                    "check_type": skill_check.check_type.value,
                }

            filtered.append(choice_dict)

        return filtered

    def _get_available_actions(self) -> List[str]:
        """Get list of valid actions for current phase."""
        phase = self.session.phase

        if phase == SessionPhase.MENU:
            return [CampaignAction.START_CAMPAIGN.value]

        elif phase == SessionPhase.STORY_INTRO:
            encounter = self.session.get_current_encounter()
            if encounter and encounter.type == EncounterType.COMBAT:
                return [CampaignAction.START_COMBAT.value]
            elif encounter and encounter.type == EncounterType.REST:
                return [CampaignAction.REST.value, CampaignAction.SKIP_REST.value]
            elif encounter and encounter.type == EncounterType.CHOICE:
                return [CampaignAction.CONTINUE.value]  # Advance to CHOICE phase
            else:
                return [CampaignAction.CONTINUE.value]

        elif phase == SessionPhase.CHOICE:
            # Player can make a choice
            return [CampaignAction.MAKE_CHOICE.value]

        elif phase == SessionPhase.CHOICE_RESULT:
            # After seeing skill check result, continue
            return [CampaignAction.CONTINUE.value]

        elif phase == SessionPhase.COMBAT:
            # Combat actions handled by CombatEngine
            return []

        elif phase == SessionPhase.COMBAT_RESOLUTION:
            return [CampaignAction.CONTINUE.value]

        elif phase == SessionPhase.STORY_OUTCOME:
            return [CampaignAction.CONTINUE.value]

        elif phase == SessionPhase.REST:
            return [CampaignAction.REST.value, CampaignAction.SKIP_REST.value]

        elif phase == SessionPhase.GAME_OVER:
            return [CampaignAction.RETRY.value, CampaignAction.QUIT.value]

        elif phase == SessionPhase.VICTORY:
            return [CampaignAction.QUIT.value]

        return []

    def advance(
        self,
        action: CampaignAction,
        data: Optional[Dict[str, Any]] = None
    ) -> Tuple[CampaignState, Optional[Dict[str, Any]]]:
        """
        Advance campaign state based on action.

        Returns:
            Tuple of (new_state, extra_data)
            extra_data may contain combat_state for combat encounters
        """
        phase = self.session.phase
        extra_data = None

        # Clear previous choice result unless we're showing it
        if action != CampaignAction.MAKE_CHOICE:
            self._last_choice_result = None

        # Handle action based on current phase
        if action == CampaignAction.START_CAMPAIGN:
            self._start_campaign()

        elif action == CampaignAction.CONTINUE:
            extra_data = self._handle_continue()

        elif action == CampaignAction.START_COMBAT:
            extra_data = self._start_combat()

        elif action == CampaignAction.END_COMBAT:
            victory = data.get("victory", False) if data else False
            extra_data = self._end_combat(victory, data)

        elif action == CampaignAction.MAKE_CHOICE:
            choice_id = data.get("choice_id") if data else None
            player_id = data.get("player_id") if data else None  # For player_choice checks
            if choice_id:
                extra_data = self._handle_choice(choice_id, player_id)

        elif action == CampaignAction.REST:
            rest_type = RestType.SHORT
            if data and data.get("rest_type") == "long":
                rest_type = RestType.LONG
            extra_data = self._handle_rest(rest_type)

        elif action == CampaignAction.SKIP_REST:
            self._skip_rest()

        elif action == CampaignAction.RETRY:
            self._retry_encounter()

        elif action == CampaignAction.QUIT:
            self.session.phase = SessionPhase.MENU

        return self.get_state(), extra_data

    def _start_campaign(self):
        """Start the campaign from the beginning."""
        self.session.current_encounter_id = self.campaign.starting_encounter
        self.session.phase = SessionPhase.STORY_INTRO
        # Clear any cached AI content for new encounter
        self._ai_scene_description = None
        self._ai_narration = None

    async def _generate_ai_scene_description(self) -> Optional[str]:
        """Generate AI scene description for current encounter."""
        if not self._ai_dm.is_ai_enabled:
            return None

        encounter = self.session.get_current_encounter()
        if not encounter:
            return None

        # Build party data
        party_data = [
            {
                "name": m.name,
                "class": m.character_class,
                "level": m.level,
            }
            for m in self.session.party
            if m.is_active
        ]

        # Build encounter data
        encounter_data = {
            "name": encounter.name,
            "type": encounter.type.value if encounter.type else "exploration",
            "story": {
                "intro_text": encounter.story.intro_text if encounter.story else "",
            },
        }

        # Build world state data
        world_state_data = self.session.world_state.to_dict()

        try:
            description = await self._ai_dm.generate_scene_description(
                encounter_data,
                party_data,
                world_state_data,
            )
            return description
        except Exception as e:
            print(f"[CampaignEngine] Failed to generate AI scene description: {e}")
            return None

    async def _generate_ai_skill_check_narration(
        self,
        character_name: str,
        skill: str,
        dc: int,
        roll: int,
        success: bool,
        context: str,
    ) -> Optional[str]:
        """Generate AI narration for skill check result."""
        if not self._ai_dm.is_ai_enabled:
            return None

        try:
            narration = await self._ai_dm.generate_skill_check_result(
                character_name,
                skill,
                dc,
                roll,
                success,
                context,
            )
            return narration
        except Exception as e:
            print(f"[CampaignEngine] Failed to generate AI skill check narration: {e}")
            return None

    def _handle_continue(self) -> Optional[Dict[str, Any]]:
        """Handle continue action based on current phase."""
        phase = self.session.phase
        encounter = self.session.get_current_encounter()

        if phase == SessionPhase.STORY_INTRO:
            # Move to appropriate phase based on encounter type
            if encounter.type == EncounterType.CUTSCENE:
                # Cutscenes just advance to next encounter
                return self._advance_to_next_encounter("victory")
            elif encounter.type == EncounterType.COMBAT:
                self.session.phase = SessionPhase.COMBAT_SETUP
            elif encounter.type == EncounterType.REST:
                self.session.phase = SessionPhase.REST
            elif encounter.type == EncounterType.CHOICE:
                # Move to choice phase to show options
                self.session.phase = SessionPhase.CHOICE
            else:
                self.session.phase = SessionPhase.STORY_OUTCOME

        elif phase == SessionPhase.CHOICE_RESULT:
            # After seeing skill check result, use the stored next encounter
            if self._pending_next_encounter:
                next_id = self._pending_next_encounter
                self._pending_next_encounter = None
                self.session.advance_to_encounter(next_id)
                return {"next_encounter": next_id}
            else:
                # Fallback to victory transition
                return self._advance_to_next_encounter("victory")

        elif phase == SessionPhase.COMBAT_RESOLUTION:
            # Apply rewards and move to outcome
            if encounter and encounter.rewards:
                rewards = encounter.rewards
                self.session.apply_rewards(
                    rewards.xp,
                    rewards.gold,
                    rewards.items,
                    rewards.story_flags,
                )
            self.session.phase = SessionPhase.STORY_OUTCOME

        elif phase == SessionPhase.STORY_OUTCOME:
            # Advance to next encounter
            return self._advance_to_next_encounter("victory")

        return None

    def _handle_choice(self, choice_id: str, player_id: str = None) -> Dict[str, Any]:
        """
        Handle player making a choice, potentially with skill check.

        Args:
            choice_id: The choice being made
            player_id: For player_choice checks, which character is rolling
        """
        encounter = self.session.get_current_encounter()
        if not encounter or not encounter.choices:
            return {"error": "No choices available"}

        # Find the selected choice
        selected_choice = None
        for choice in encounter.choices.choices:
            if choice.id == choice_id:
                selected_choice = choice
                break

        if not selected_choice:
            return {"error": f"Choice {choice_id} not found"}

        result = {
            "choice_id": choice_id,
            "choice_text": selected_choice.text,
        }

        # Determine next encounter
        next_encounter_id = None

        if selected_choice.skill_check:
            skill_check = selected_choice.skill_check
            check_type = skill_check.check_type

            # Handle different check types
            if check_type == CheckType.PLAYER_CHOICE:
                # Player needs to select who will make the check
                if not player_id:
                    # Return party options for selection
                    party_options = []
                    for member in self.session.party:
                        if member.is_active:
                            stats = {
                                "str": member.strength,
                                "dex": member.dexterity,
                                "con": member.constitution,
                                "int": member.intelligence,
                                "wis": member.wisdom,
                                "cha": member.charisma,
                                "level": member.level,
                            }
                            modifier = get_skill_modifier(stats, skill_check.skill)
                            party_options.append({
                                "id": member.id,
                                "name": member.name,
                                "modifier": modifier,
                                "modifier_display": f"+{modifier}" if modifier >= 0 else str(modifier),
                            })

                    result["awaiting_player_selection"] = True
                    result["skill"] = skill_check.skill
                    result["dc"] = skill_check.dc
                    result["party_options"] = party_options
                    self._last_choice_result = result
                    return result

                # Player selected - find the chosen character
                roller = next((m for m in self.session.party if m.id == player_id and m.is_active), None)
                if not roller:
                    return {"error": f"Character {player_id} not found or not active"}
            elif check_type == CheckType.GROUP:
                # Group check - all party members roll
                party_data = []
                for member in self.session.party:
                    if member.is_active:
                        party_data.append({
                            "id": member.id,
                            "name": member.name,
                            "strength": member.strength,
                            "dexterity": member.dexterity,
                            "constitution": member.constitution,
                            "intelligence": member.intelligence,
                            "wisdom": member.wisdom,
                            "charisma": member.charisma,
                            "level": member.level,
                        })

                group_result = perform_group_check(
                    skill=skill_check.skill,
                    dc=skill_check.dc,
                    party_members=party_data,
                    advantage=skill_check.advantage,
                    disadvantage=skill_check.disadvantage,
                )

                # Build group check result
                result["skill_check"] = {
                    "check_type": "group",
                    "skill": group_result.skill,
                    "dc": group_result.dc,
                    "success": group_result.success,
                    "successes": group_result.successes,
                    "failures": group_result.failures,
                    "needed_successes": group_result.needed_successes,
                    "individual_results": [
                        {
                            "character_id": getattr(r, 'character_id', ''),
                            "character_name": getattr(r, 'character_name', 'Unknown'),
                            "roll": r.roll,
                            "modifier": r.modifier,
                            "total": r.total,
                            "success": r.success,
                            "critical_success": r.critical_success,
                            "critical_failure": r.critical_failure,
                            "rolls": r.rolls,
                        }
                        for r in group_result.individual_results
                    ],
                }

                # Determine outcome based on group success
                if group_result.success:
                    next_encounter_id = selected_choice.on_success
                    result["outcome_text"] = selected_choice.success_text or "The group succeeds!"
                else:
                    next_encounter_id = selected_choice.on_failure
                    result["outcome_text"] = selected_choice.failure_text or "The group fails..."

                self.session.phase = SessionPhase.CHOICE_RESULT
                self._pending_next_encounter = next_encounter_id
                self._last_choice_result = result
                return result
            else:
                # INDIVIDUAL check - use party leader
                roller = next((m for m in self.session.party if m.is_active), None)
                if not roller:
                    return {"error": "No active party members"}

            # Perform individual skill check (for INDIVIDUAL or PLAYER_CHOICE with player_id)
            character_stats = {
                "str": roller.strength,
                "dex": roller.dexterity,
                "con": roller.constitution,
                "int": roller.intelligence,
                "wis": roller.wisdom,
                "cha": roller.charisma,
                "level": roller.level,
            }

            check_result = perform_skill_check(
                skill=skill_check.skill,
                dc=skill_check.dc,
                character_stats=character_stats,
                advantage=skill_check.advantage,
                disadvantage=skill_check.disadvantage,
            )

            # Build result
            result["skill_check"] = {
                "check_type": check_type.value,
                "skill": check_result.skill,
                "roll": check_result.roll,
                "modifier": check_result.modifier,
                "total": check_result.total,
                "dc": check_result.dc,
                "success": check_result.success,
                "critical_success": check_result.critical_success,
                "critical_failure": check_result.critical_failure,
                "rolls": check_result.rolls,
                "character_name": roller.name,
                "character_id": roller.id,
            }

            # Determine next encounter based on success/failure
            if check_result.success:
                next_encounter_id = selected_choice.on_success
                result["outcome_text"] = selected_choice.success_text or "Success!"
            else:
                next_encounter_id = selected_choice.on_failure
                result["outcome_text"] = selected_choice.failure_text or "Failed..."

            # Move to CHOICE_RESULT phase to show the dice animation
            self.session.phase = SessionPhase.CHOICE_RESULT

        else:
            # No skill check - just use on_select for direct transition
            next_encounter_id = selected_choice.on_select or selected_choice.on_success
            result["outcome_text"] = selected_choice.success_text

            # If no skill check, can skip straight to next encounter
            if next_encounter_id:
                self.session.advance_to_encounter(next_encounter_id)
                result["next_encounter"] = next_encounter_id
            else:
                self.session.phase = SessionPhase.STORY_OUTCOME

        # Store for later continuation
        self._pending_next_encounter = next_encounter_id
        self._last_choice_result = result

        return result

    def _advance_to_next_encounter(self, outcome: str) -> Optional[Dict[str, Any]]:
        """Advance to the next encounter based on outcome."""
        current_id = self.session.current_encounter_id
        next_id = self.campaign.get_next_encounter(current_id, outcome)

        # Clear AI cache when advancing
        self._ai_scene_description = None
        self._ai_narration = None

        if next_id:
            self.session.advance_to_encounter(next_id)
            return {"next_encounter": next_id, "needs_ai_scene": True}
        else:
            # Campaign complete!
            self.session.phase = SessionPhase.VICTORY
            return {"campaign_complete": True}

    def _start_combat(self) -> Dict[str, Any]:
        """Initialize combat for current encounter."""
        encounter = self.session.get_current_encounter()
        if not encounter or not encounter.combat:
            return {"error": "No combat setup for this encounter"}

        # Build player dicts directly from party members
        players_dicts = []
        for member in self.session.party:
            # DEBUG: Log party member data
            import sys
            print(f"[_START_COMBAT] Member: {member.name}, character_class='{member.character_class}', level={member.level}, weapons={member.weapons}", flush=True)
            print(f"[_START_COMBAT] Member: {member.name}, character_class='{member.character_class}', level={member.level}", file=sys.stderr, flush=True)

            if not member.is_active:
                continue

            # Get weapons list - filter out Unarmed Strike for equipment slots
            weapons_list = member.weapons if hasattr(member, 'weapons') and member.weapons else []
            # Unarmed Strike is an innate ability, not a physical weapon to equip
            equippable_weapons = [w for w in weapons_list if w.get('name', '').lower() != 'unarmed strike']

            # Helper to ensure weapon has ID and item_type
            def ensure_weapon_fields(weapon):
                if not weapon:
                    return None
                return {
                    **weapon,
                    "id": weapon.get("id", weapon.get("name", "unknown").lower().replace(" ", "_").replace("'", "")),
                    "item_type": weapon.get("item_type", "weapon"),
                }

            # Build equipment structure for frontend
            equipment_struct = None
            if member.equipment_data:
                # Use existing equipment_data if available
                equipment_struct = member.equipment_data
            elif equippable_weapons:
                # Build from equippable weapons list (excluding Unarmed Strike)
                equipment_struct = {
                    "main_hand": ensure_weapon_fields(equippable_weapons[0]) if len(equippable_weapons) > 0 else None,
                    "off_hand": ensure_weapon_fields(equippable_weapons[1]) if len(equippable_weapons) > 1 else None,
                    "ranged": None,
                }

            # Build spellcasting structure for caster classes
            spellcasting_struct = None
            caster_classes = ['paladin', 'cleric', 'wizard', 'druid', 'bard', 'sorcerer', 'warlock', 'ranger', 'artificer']
            if member.character_class.lower() in caster_classes:
                # Calculate spellcasting ability modifier
                spell_ability_map = {
                    'wizard': 'intelligence', 'artificer': 'intelligence',
                    'cleric': 'wisdom', 'druid': 'wisdom', 'ranger': 'wisdom',
                    'bard': 'charisma', 'paladin': 'charisma', 'sorcerer': 'charisma', 'warlock': 'charisma'
                }
                spell_ability = spell_ability_map.get(member.character_class.lower(), 'charisma')
                ability_score = getattr(member, spell_ability, 10)
                ability_mod = (ability_score - 10) // 2
                prof_bonus = 2 + (member.level - 1) // 4

                # Calculate used slots
                slots_used = {}
                for level, max_slots in member.spell_slots_max.items():
                    remaining = member.spell_slots.get(level, max_slots)
                    slots_used[level] = max_slots - remaining

                # Get spellcasting data from member if available (passed from import)
                member_spellcasting = member.spellcasting or {}

                spellcasting_struct = {
                    "ability": spell_ability[:3],  # 'int', 'wis', 'cha'
                    "ability_modifier": ability_mod,
                    "spell_save_dc": 8 + prof_bonus + ability_mod,
                    "spell_attack_bonus": prof_bonus + ability_mod,
                    "spell_slots": member.spell_slots_max if member.spell_slots_max else member_spellcasting.get('spell_slots', {}),
                    "spell_slots_used": slots_used,
                    # USE member.spellcasting data instead of empty arrays!
                    "cantrips_known": member_spellcasting.get('cantrips', member_spellcasting.get('cantrips_known', [])),
                    "prepared_spells": member_spellcasting.get('prepared_spells', []),
                    "spells_known": member_spellcasting.get('spells_known', []),
                    "concentrating_on": member_spellcasting.get('concentrating_on'),
                }

            player_dict = {
                "id": member.id,
                "name": member.name,
                "type": "player",
                # CRITICAL: Include class/level at TOP LEVEL for initiative tracker
                "class": member.character_class,
                "character_class": member.character_class,
                "level": member.level,
                "current_hp": member.current_hp,
                "max_hp": member.max_hp,
                "ac": member.ac,
                "speed": member.speed,
                # CRITICAL: Include all ability modifiers for attack/damage calculations
                "str_mod": (member.strength - 10) // 2,
                "dex_mod": (member.dexterity - 10) // 2,
                "con_mod": (member.constitution - 10) // 2,
                "int_mod": (member.intelligence - 10) // 2,
                "wis_mod": (member.wisdom - 10) // 2,
                "cha_mod": (member.charisma - 10) // 2,
                "stats": {
                    "class": member.character_class,
                    "level": member.level,
                    "str": member.strength,
                    "dex": member.dexterity,
                    "con": member.constitution,
                    "int": member.intelligence,
                    "wis": member.wisdom,
                    "cha": member.charisma,
                    "strength": member.strength,  # Also include full names for frontend compatibility
                    "dexterity": member.dexterity,
                    "constitution": member.constitution,
                    "intelligence": member.intelligence,
                    "wisdom": member.wisdom,
                    "charisma": member.charisma,
                    "weapons": weapons_list,
                    "weapon": weapons_list[0] if weapons_list else None,  # Primary weapon for character panel
                },
                "weapons": weapons_list,
                "actions": [],
                # Add abilities dict with full ability score data for Combatant.to_dict()
                "abilities": {
                    "class": member.character_class.lower() if member.character_class else "",
                    "level": member.level,
                    "str": member.strength,
                    "dex": member.dexterity,
                    "con": member.constitution,
                    "int": member.intelligence,
                    "wis": member.wisdom,
                    "cha": member.charisma,
                    "str_score": member.strength,
                    "dex_score": member.dexterity,
                    "con_score": member.constitution,
                    "int_score": member.intelligence,
                    "wis_score": member.wisdom,
                    "cha_score": member.charisma,
                },
                # Add equipment structure for weapon display
                "equipment": equipment_struct,
                # Add spellcasting for caster classes
                "spellcasting": spellcasting_struct,
                # Start with healing potions for testing
                "inventory": [
                    {
                        "id": "potion_of_healing_1",
                        "name": "Potion of Healing",
                        "type": "consumable",
                        "item_type": "consumable",
                        "icon": "🧪",
                        "rarity": "common",
                        "description": "Regain 2d4+2 HP (Bonus Action)",
                        "quantity": 1,
                    },
                    {
                        "id": "potion_of_healing_2",
                        "name": "Potion of Healing",
                        "type": "consumable",
                        "item_type": "consumable",
                        "icon": "🧪",
                        "rarity": "common",
                        "description": "Regain 2d4+2 HP (Bonus Action)",
                        "quantity": 1,
                    },
                ],
            }
            # DEBUG: Print player_dict key values to verify class/level/weapons
            print(f"[_START_COMBAT] player_dict created: name='{player_dict.get('name')}', class='{player_dict.get('class')}', character_class='{player_dict.get('character_class')}', level={player_dict.get('level')}, weapons_count={len(player_dict.get('weapons', []))}", flush=True)
            players_dicts.append(player_dict)

        # Build enemy dicts from combat setup
        enemies_dicts = self._create_enemy_dicts(encounter.combat)

        # Build initial positions from environment spawn points
        positions = {}
        env = encounter.combat.environment

        # Assign player positions from spawn points
        for i, player_dict in enumerate(players_dicts):
            if i < len(env.player_spawns):
                spawn = env.player_spawns[i]
                positions[player_dict["id"]] = (spawn[0], spawn[1])
            else:
                # Fallback position if not enough spawn points
                positions[player_dict["id"]] = (1, 6 + i)

        # Assign enemy positions from spawn points
        for i, enemy_dict in enumerate(enemies_dicts):
            if i < len(env.enemy_spawns):
                spawn = env.enemy_spawns[i]
                positions[enemy_dict["id"]] = (spawn[0], spawn[1])
            else:
                # Fallback position if not enough spawn points
                positions[enemy_dict["id"]] = (6, 1 + i)

        print(f"[CampaignEngine] Combat positions: {positions}")

        # Create combat grid from environment dimensions
        grid = CombatGrid(env.width, env.height)

        # Mark obstacles on the grid (set terrain to IMPASSABLE)
        from app.core.movement import TerrainType
        for obs in env.obstacles:
            if len(obs) >= 2:
                grid.set_terrain(obs[0], obs[1], TerrainType.IMPASSABLE)

        # Mark difficult terrain
        for dt in env.difficult_terrain:
            if len(dt) >= 2:
                grid.set_terrain(dt[0], dt[1], TerrainType.DIFFICULT)

        # Set occupants on the grid
        for combatant_id, pos in positions.items():
            grid.set_occupant(pos[0], pos[1], combatant_id)

        # Initialize combat engine
        self.combat_engine = CombatEngine()

        # Start combat with positions
        self.combat_engine.start_combat(players_dicts, enemies_dicts, positions)

        # Get combat_id from the combat state
        combat_id = self.combat_engine.state.id

        # Create reactions manager and register all combatants
        reactions_mgr = ReactionsManager()
        for p in players_dicts:
            reactions_mgr.register_combatant(p["id"])
        for e in enemies_dicts:
            reactions_mgr.register_combatant(e["id"])

        # Register in shared combat storage so API routes can find it
        active_combats[combat_id] = self.combat_engine
        active_grids[combat_id] = grid
        reactions_managers[combat_id] = reactions_mgr
        print(f"[CampaignEngine] Registered combat {combat_id} in shared storage")

        # Update session
        self.session.start_combat(combat_id)

        # Get initial combat state
        combat_state = self.combat_engine.get_combat_state()

        return {
            "combat_id": combat_id,
            "combat_state": combat_state,
        }

    def _create_enemy_dicts(self, combat_setup: CombatSetup) -> List[Dict[str, Any]]:
        """Create enemy dicts directly from combat setup for the combat engine."""
        enemies = []

        for spawn in combat_setup.enemies:
            template = self._load_enemy_template(spawn.template)
            if not template:
                print(f"[CampaignEngine] Warning: Could not load template '{spawn.template}'")
                continue

            for i in range(spawn.count):
                name = spawn.name_override or template.get("name", spawn.template)
                if spawn.count > 1:
                    name = f"{name} {i + 1}"

                # Get abilities from nested object or flat keys
                abilities = template.get("abilities", {})
                dex_val = abilities.get("dexterity", template.get("dexterity", 10))
                # Use hit_points_average from JSON, fallback to hit_points, then default to 10
                hp = template.get("hit_points_average", template.get("hit_points", 10))
                enemy_dict = {
                    "id": f"enemy-{spawn.template}-{uuid.uuid4().hex[:6]}",
                    "name": name,
                    "type": "enemy",
                    "current_hp": hp,
                    "max_hp": hp,
                    "ac": template.get("armor_class", 10),
                    "speed": template.get("speed", 30),
                    "dex_mod": (dex_val - 10) // 2,
                    "stats": {
                        "str": abilities.get("strength", template.get("strength", 10)),
                        "dex": dex_val,
                        "con": abilities.get("constitution", template.get("constitution", 10)),
                        "int": abilities.get("intelligence", template.get("intelligence", 10)),
                        "wis": abilities.get("wisdom", template.get("wisdom", 10)),
                        "cha": abilities.get("charisma", template.get("charisma", 10)),
                        "challenge_rating": template.get("challenge_rating", 0.25),
                    },
                    "weapons": [],
                    "actions": template.get("actions", []),
                }
                enemies.append(enemy_dict)

        return enemies

    def _create_enemies(self, combat_setup: CombatSetup) -> List[Combatant]:
        """Create enemy combatants from combat setup."""
        enemies = []

        for spawn in combat_setup.enemies:
            template = self._load_enemy_template(spawn.template)
            if not template:
                continue

            for i in range(spawn.count):
                name = spawn.name_override or template.get("name", spawn.template)
                if spawn.count > 1:
                    name = f"{name} {i + 1}"

                # Use hit_points_average from JSON, fallback to hit_points, then default to 10
                hp = template.get("hit_points_average", template.get("hit_points", 10))
                # Get abilities from nested object or flat keys
                abilities = template.get("abilities", {})
                enemy = Combatant(
                    id=f"enemy-{spawn.template}-{uuid.uuid4().hex[:6]}",
                    name=name,
                    type=CombatantType.ENEMY,
                    max_hp=hp,
                    current_hp=hp,
                    ac=template.get("armor_class", 10),
                    speed=template.get("speed", 30),
                    stats={
                        "str": abilities.get("strength", template.get("strength", 10)),
                        "dex": abilities.get("dexterity", template.get("dexterity", 10)),
                        "con": abilities.get("constitution", template.get("constitution", 10)),
                        "int": abilities.get("intelligence", template.get("intelligence", 10)),
                        "wis": abilities.get("wisdom", template.get("wisdom", 10)),
                        "cha": abilities.get("charisma", template.get("charisma", 10)),
                        "actions": template.get("actions", []),
                        "challenge_rating": template.get("challenge_rating", 0.25),
                    },
                )
                enemies.append(enemy)

        return enemies

    def _load_enemy_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Load enemy template from data files."""
        if template_id in self._enemy_cache:
            return self._enemy_cache[template_id]

        enemies_path = Path(__file__).parent.parent / "data" / "enemies" / f"{template_id}.json"
        try:
            with open(enemies_path) as f:
                data = json.load(f)
            self._enemy_cache[template_id] = data
            return data
        except Exception as e:
            print(f"[CampaignEngine] Failed to load enemy template {template_id}: {e}")
            return None

    def _end_combat(
        self,
        victory: bool,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """End combat and update party state."""
        result = {
            "victory": victory,
            "combat_id": self.session.combat_id,
            "enemies_defeated": [],
            "xp_earned": 0,
            "xp_per_player": 0,
            "level_ups": [],
            "loot": None,
        }

        # Get combat_id for cleanup
        combat_id = self.session.combat_id

        # Sync party HP and extract combat data
        defeated_enemies = []
        if self.combat_engine:
            combat_state = self.combat_engine.get_combat_state()

            # Sync player HP
            for combatant_data in combat_state.get("combatants", []):
                if combatant_data.get("type") == "player":
                    member = next(
                        (m for m in self.session.party if m.id == combatant_data["id"]),
                        None
                    )
                    if member:
                        member.current_hp = combatant_data.get("current_hp", member.current_hp)
                        member.is_active = combatant_data.get("is_active", True)

            # Extract defeated enemies for XP and loot
            if victory:
                combatant_stats = combat_state.get("combatant_stats", {})
                for combatant_data in combat_state.get("combatants", []):
                    cid = combatant_data.get("id", "")
                    stats = combatant_stats.get(cid, {})

                    # Enemy is defeated if type is enemy and is_active is False
                    if stats.get("type") == "enemy" and not combatant_data.get("is_active", True):
                        cr = stats.get("cr", stats.get("challenge_rating", 0.25))
                        xp_value = get_xp_for_cr(str(cr))
                        defeated_enemies.append({
                            "id": cid,
                            "name": combatant_data.get("name", "Unknown"),
                            "cr": cr,
                            "xp": xp_value,
                        })

        result["enemies_defeated"] = defeated_enemies

        # Calculate and award XP if victory
        if victory and defeated_enemies:
            # Get CR list for XP calculation
            cr_list = [str(e["cr"]) for e in defeated_enemies]
            party_size = len([m for m in self.session.party if m.is_active])

            # Calculate total XP (not divided - we'll divide per player)
            total_xp = calculate_encounter_xp(cr_list, party_size=1, divide_among_party=False)
            xp_per_player = total_xp // max(party_size, 1)

            result["xp_earned"] = total_xp
            result["xp_per_player"] = xp_per_player

            # Award XP to each party member and check for level-ups
            for member in self.session.party:
                if member.is_active and not member.is_dead:
                    old_xp = member.xp
                    member.xp += xp_per_player

                    # Check for level up
                    if can_level_up(member.xp, member.level):
                        result["level_ups"].append({
                            "member_id": member.id,
                            "member_name": member.name,
                            "old_level": member.level,
                            "xp_before": old_xp,
                            "xp_after": member.xp,
                        })

            print(f"[CampaignEngine] Awarded {xp_per_player} XP to {party_size} party members (total: {total_xp})")

            # Generate loot
            try:
                generator = get_loot_generator()
                loot = generator.generate_encounter_loot(
                    defeated_enemies=defeated_enemies,
                    encounter_difficulty="medium",
                    is_boss_encounter=len(defeated_enemies) == 1 and defeated_enemies[0].get("cr", 0) >= 5
                )
                result["loot"] = loot.to_dict()
                print(f"[CampaignEngine] Generated loot: {result['loot'].get('coins', {})}")
            except Exception as e:
                print(f"[CampaignEngine] Failed to generate loot: {e}")

        # Clean up shared combat storage (but keep combat_id for loot retrieval)
        # Note: We don't delete from active_combats yet so loot endpoint can still access it
        if combat_id:
            if combat_id in active_grids:
                del active_grids[combat_id]
            if combat_id in reactions_managers:
                del reactions_managers[combat_id]
            print(f"[CampaignEngine] Cleaned up combat {combat_id} (kept engine for loot)")

        # Clear combat reference
        self.session.end_combat(victory)
        self.combat_engine = None

        if victory:
            self.session.phase = SessionPhase.COMBAT_RESOLUTION
        else:
            self.session.phase = SessionPhase.GAME_OVER

        return result

    def _handle_rest(self, rest_type: RestType) -> Dict[str, Any]:
        """Handle short or long rest."""
        result = self.session.rest(rest_type)

        # Move to outcome phase
        self.session.phase = SessionPhase.STORY_OUTCOME

        return result

    def _skip_rest(self):
        """Skip rest and continue."""
        self.session.phase = SessionPhase.STORY_OUTCOME

    def _retry_encounter(self):
        """Retry the current encounter from the beginning."""
        # Restore party to pre-encounter state
        # For now, just reset HP and restart the encounter
        for member in self.session.party:
            member.current_hp = member.max_hp
            member.is_active = True

        self.session.phase = SessionPhase.STORY_INTRO

    def get_combat_engine(self) -> Optional[CombatEngine]:
        """Get the active combat engine, if in combat."""
        return self.combat_engine


# Campaign loader functions

def load_campaign(campaign_id: str) -> Optional[Campaign]:
    """Load a campaign from the data directory."""
    campaigns_path = Path(__file__).parent.parent / "data" / "campaigns"
    campaign_file = campaigns_path / f"{campaign_id}.json"

    if not campaign_file.exists():
        return None

    try:
        with open(campaign_file, encoding="utf-8") as f:
            data = json.load(f)
        return Campaign.from_dict(data)
    except Exception as e:
        print(f"[CampaignEngine] Failed to load campaign {campaign_id}: {e}")
        return None


def list_campaigns() -> List[Dict[str, str]]:
    """List all available campaigns."""
    campaigns_path = Path(__file__).parent.parent / "data" / "campaigns"
    campaigns = []

    if not campaigns_path.exists():
        return campaigns

    for file in campaigns_path.glob("*.json"):
        try:
            with open(file, encoding="utf-8") as f:
                data = json.load(f)

            campaign_info = data.get("campaign", data)
            campaigns.append({
                "id": file.stem,
                "name": campaign_info.get("name", file.stem),
                "description": campaign_info.get("description", ""),
                "author": campaign_info.get("author", "Unknown"),
            })
        except Exception as e:
            print(f"[CampaignEngine] Failed to read campaign {file}: {e}")

    return campaigns
