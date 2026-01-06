"""
AI Dungeon Master Service.

Uses Claude API to generate:
- Story narration and descriptions
- NPC dialogue and reactions
- Dynamic encounter modifications
- Contextual responses to player actions

Supports AI/Human hybrid mode where human DM can override at any time.
Includes caching, rate limiting, fallbacks, and personality customization.
"""
from typing import Optional, Dict, Any, List
from enum import Enum
import asyncio
import logging

from app.config import get_settings
from app.services.ai_dm_cache import AIDMCache
from app.services.ai_dm_fallbacks import (
    get_scene_fallback,
    get_combat_fallback,
    get_skill_check_fallback,
    get_npc_dialogue_fallback,
    get_encounter_suggestion_fallback,
)
from app.services.ai_dm_rate_limiter import AIDMRateLimiter
from app.services.ai_dm_personalities import (
    DMPersonality,
    PERSONALITY_PRESETS,
    get_preset,
    list_presets,
)

logger = logging.getLogger(__name__)


class DMMode(str, Enum):
    """Who is controlling the DM."""
    AI = "ai"
    HUMAN = "human"
    HYBRID = "hybrid"  # AI generates, human approves


class AIDMService:
    """
    AI Dungeon Master powered by Claude.

    Generates narrative content while respecting:
    - D&D 5e 2024 rules
    - Current campaign context
    - Party composition and history
    - World state and flags
    """

    _instance: Optional["AIDMService"] = None

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.ANTHROPIC_API_KEY
        self._client = None
        self._model = "claude-sonnet-4-20250514"  # Fast model for real-time
        self._mode = DMMode.AI
        self._human_override_active = False

        # Initialize new components
        self._cache = AIDMCache(max_size=100, ttl_minutes=30)
        self._rate_limiter = AIDMRateLimiter(
            requests_per_minute=20,
            requests_per_hour=200,
            daily_cost_cap_usd=5.0,
        )
        self._personality = PERSONALITY_PRESETS.get("classic", DMPersonality())

        # Initialize client if API key is available
        if self._api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
                logger.info("AI DM service initialized with Claude API")
            except ImportError:
                logger.warning("anthropic package not installed - AI DM disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")

    @classmethod
    def get_instance(cls) -> "AIDMService":
        """Get singleton instance of AI DM service."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def mode(self) -> DMMode:
        """Get current DM mode."""
        return self._mode

    @property
    def is_ai_enabled(self) -> bool:
        """Check if AI is enabled and configured."""
        return self._client is not None and not self._human_override_active

    def set_mode(self, mode: DMMode) -> None:
        """Set DM mode."""
        self._mode = mode
        if mode == DMMode.HUMAN:
            self._human_override_active = True
        elif mode == DMMode.AI:
            self._human_override_active = False

    def set_human_override(self, active: bool) -> None:
        """Human DM takes or releases control."""
        self._human_override_active = active
        self._mode = DMMode.HUMAN if active else DMMode.AI

    async def generate_scene_description(
        self,
        encounter: Dict[str, Any],
        party: List[Dict[str, Any]],
        world_state: Dict[str, Any],
    ) -> Optional[str]:
        """
        Generate immersive scene description.

        Args:
            encounter: Current encounter data
            party: List of party member data
            world_state: Current world state and flags

        Returns:
            Generated scene description or fallback if AI unavailable
        """
        if self._human_override_active:
            return None

        encounter_type = encounter.get("type", "exploration")

        # Try AI generation if client available
        if self._client:
            cache_context = {
                "type": encounter_type,
                "story": encounter.get("story", {}),
            }
            prompt = self._build_scene_prompt(encounter, party, world_state)
            result = await self._call_claude(
                prompt,
                max_tokens=500,
                scenario_type="scene",
                cache_context=cache_context,
            )
            if result:
                return result

        # Fall back to pre-written templates
        logger.debug(f"Using fallback for scene description: {encounter_type}")
        return get_scene_fallback(encounter_type)

    async def generate_npc_dialogue(
        self,
        npc_name: str,
        npc_personality: str,
        context: str,
        player_input: str,
        disposition: str = "neutral",
        npc_type: str = "",
    ) -> Optional[str]:
        """
        Generate NPC response to player interaction.

        Args:
            npc_name: Name of the NPC
            npc_personality: Description of NPC's personality
            context: Current situation context
            player_input: What the player said/did
            disposition: NPC's attitude (friendly, neutral, hostile)
            npc_type: Type of NPC (merchant, quest_giver, etc.)

        Returns:
            Generated NPC dialogue or fallback if AI unavailable
        """
        if self._human_override_active:
            return None

        # Try AI generation if client available
        if self._client:
            cache_context = {
                "npc_type": npc_type,
                "personality": npc_personality[:50],
                "situation": context[:50],
            }
            prompt = self._build_npc_prompt(npc_name, npc_personality, context, player_input)
            result = await self._call_claude(
                prompt,
                max_tokens=300,
                scenario_type="npc",
                cache_context=cache_context,
            )
            if result:
                return result

        # Fall back to pre-written templates
        logger.debug(f"Using fallback for NPC dialogue: {npc_name}")
        return get_npc_dialogue_fallback(disposition=disposition, npc_type=npc_type)

    async def generate_combat_narration(
        self,
        action_result: Dict[str, Any],
        combatant: Dict[str, Any],
        target: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Generate dramatic combat narration.

        Args:
            action_result: Result of the combat action
            combatant: Actor data
            target: Target data (if any)

        Returns:
            Generated narration or fallback if AI unavailable
        """
        if self._human_override_active:
            return None

        actor_name = combatant.get("name", "The combatant")
        target_name = target.get("name", "the enemy") if target else "the enemy"
        hit = action_result.get("hit", False)
        is_kill = (target.get("current_hp", 1) <= 0) if target else False
        is_critical = action_result.get("critical", False)
        is_healing = action_result.get("action_type", "") == "heal"
        is_spell = action_result.get("is_spell", False)

        # Try AI generation if client available
        if self._client:
            cache_context = {
                "action_type": action_result.get("action_type", "attack"),
                "hit": hit,
                "current_hp": target.get("current_hp", 1) if target else 1,
                "damage_type": action_result.get("damage_type", ""),
            }
            prompt = self._build_combat_narration_prompt(action_result, combatant, target)
            result = await self._call_claude(
                prompt,
                max_tokens=150,
                scenario_type="combat",
                cache_context=cache_context,
            )
            if result:
                return result

        # Fall back to pre-written templates
        logger.debug(f"Using fallback for combat narration: {actor_name} vs {target_name}")
        return get_combat_fallback(
            actor_name=actor_name,
            target_name=target_name,
            hit=hit,
            is_kill=is_kill,
            is_critical=is_critical,
            is_healing=is_healing,
            is_spell=is_spell,
        )

    async def suggest_dynamic_encounter(
        self,
        party_status: Dict[str, Any],
        story_context: str,
        difficulty: str = "medium",
        terrain: str = "dungeon",
    ) -> Optional[Dict[str, Any]]:
        """
        Suggest dynamic encounter based on party status.

        Args:
            party_status: Current party state (HP, resources, etc.)
            story_context: Current story situation
            difficulty: Requested difficulty level
            terrain: Environment type

        Returns:
            Suggested encounter data or fallback if AI unavailable
        """
        if self._human_override_active:
            return None

        # Try AI generation if client available
        if self._client:
            prompt = self._build_encounter_suggestion_prompt(party_status, story_context)
            response = await self._call_claude(prompt, max_tokens=800)
            if response:
                result = self._parse_encounter_suggestion(response)
                if result:
                    return result

        # Fall back to pre-built encounter suggestion
        logger.debug(f"Using fallback for encounter suggestion: {difficulty} / {terrain}")
        return get_encounter_suggestion_fallback(difficulty=difficulty, terrain=terrain)

    async def generate_skill_check_result(
        self,
        character_name: str,
        skill: str,
        dc: int,
        roll: int,
        success: bool,
        context: str,
    ) -> Optional[str]:
        """
        Generate narrative description of skill check result.

        Args:
            character_name: Name of the character making the check
            skill: Skill being checked
            dc: Difficulty class
            roll: The roll result
            success: Whether the check succeeded
            context: What the character was trying to do

        Returns:
            Generated description or fallback if AI unavailable
        """
        if self._human_override_active:
            return None

        margin = roll - dc
        is_critical = roll == 20 or roll == 1

        # Try AI generation if client available
        if self._client:
            cache_context = {
                "skill": skill.lower(),
                "success": success,
                "roll": roll,
                "dc": dc,
            }
            prompt = f"""Describe the result of this skill check in 1-2 vivid sentences:

Character: {character_name}
Skill: {skill}
Attempting: {context}
Result: {"SUCCESS" if success else "FAILURE"} ({"exceeded" if success else "missed"} DC by {abs(margin)})

Write an engaging, in-world description. Don't mention dice or numbers."""

            result = await self._call_claude(
                prompt,
                max_tokens=100,
                scenario_type="skill_check",
                cache_context=cache_context,
            )
            if result:
                return result

        # Fall back to pre-written templates
        logger.debug(f"Using fallback for skill check: {skill} by {character_name}")
        return get_skill_check_fallback(
            character_name=character_name,
            skill=skill,
            success=success,
            is_critical=is_critical,
        )

    async def _call_claude(
        self,
        prompt: str,
        max_tokens: int = 500,
        scenario_type: str = "general",
        cache_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Make API call to Claude with caching and rate limiting.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens for response
            scenario_type: Type of scenario (for caching)
            cache_context: Context dict for cache key generation

        Returns:
            Generated text or None if unavailable
        """
        if not self._client:
            return None

        # Check cache first if context provided
        if cache_context:
            cached = self._cache.get(scenario_type, cache_context)
            if cached:
                logger.debug(f"Cache hit for {scenario_type}")
                return cached

        # Check rate limits
        allowed, reason, is_soft = self._rate_limiter.can_make_request()
        if not allowed:
            logger.warning(f"Rate limited: {reason}")
            return None
        if is_soft:
            logger.debug(f"Rate limit warning: {reason}")

        # Adjust max_tokens based on personality verbosity
        adjusted_tokens = self._personality.get_max_tokens(max_tokens)

        try:
            # Use sync client in async context via thread pool
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self._model,
                    max_tokens=adjusted_tokens,
                    system=self._get_system_prompt(),
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            response_text = message.content[0].text

            # Record usage
            input_tokens = len(prompt) // 4  # Rough estimate
            output_tokens = len(response_text) // 4
            self._rate_limiter.record_request(input_tokens, output_tokens)

            # Cache the response if context provided
            if cache_context:
                self._cache.set(scenario_type, cache_context, response_text)

            return response_text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            self._rate_limiter.record_request(success=False)
            return None

    def _get_system_prompt(self) -> str:
        """Get system prompt for AI DM with personality customization."""
        base_prompt = """You are an expert Dungeon Master for D&D 5e (2024 rules).
Your role is to create immersive, engaging narratives while:
- Respecting the game rules and current campaign state
- Adapting to player choices and party composition
- Maintaining consistent tone with the campaign setting
- Keeping descriptions concise but evocative (2-4 sentences typically)
- Never mention dice rolls, numbers, or game mechanics directly in narration
- Focus on sensory details, emotions, and dramatic tension"""

        # Add personality customization
        personality_addendum = self._personality.to_system_prompt_addendum()
        if personality_addendum:
            return f"{base_prompt}\n\n{personality_addendum}"
        return base_prompt

    # =========================================================================
    # PERSONALITY MANAGEMENT
    # =========================================================================

    def set_personality(self, personality: DMPersonality) -> None:
        """
        Set the DM personality.

        Args:
            personality: DMPersonality instance
        """
        self._personality = personality
        logger.info(f"DM personality set to: {personality.name}")

    def set_personality_preset(self, preset_name: str) -> bool:
        """
        Set personality from a preset name.

        Args:
            preset_name: Name of the preset (classic, epic, horror, etc.)

        Returns:
            True if preset was found and set, False otherwise
        """
        preset = get_preset(preset_name)
        if preset:
            self._personality = preset
            logger.info(f"DM personality set to preset: {preset_name}")
            return True
        logger.warning(f"Unknown personality preset: {preset_name}")
        return False

    def get_personality(self) -> Dict[str, Any]:
        """
        Get current personality settings.

        Returns:
            Dictionary with personality configuration
        """
        return self._personality.to_dict()

    def get_available_presets(self) -> List[Dict[str, str]]:
        """
        Get list of available personality presets.

        Returns:
            List of preset info dictionaries
        """
        return list_presets()

    # =========================================================================
    # USAGE STATISTICS
    # =========================================================================

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter usage statistics.

        Returns:
            Dictionary with usage stats and limits
        """
        return self._rate_limiter.get_stats()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return self._cache.get_stats()

    def set_rate_limits(
        self,
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
        daily_cost_cap_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Update rate limits.

        Args:
            requests_per_minute: New RPM limit (optional)
            requests_per_hour: New RPH limit (optional)
            daily_cost_cap_usd: New daily cost cap (optional)

        Returns:
            Dictionary with updated limits
        """
        return self._rate_limiter.set_limits(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            daily_cost_cap_usd=daily_cost_cap_usd,
        )

    def clear_cache(self) -> int:
        """
        Clear the response cache.

        Returns:
            Number of entries cleared
        """
        return self._cache.clear()

    def _build_scene_prompt(
        self,
        encounter: Dict[str, Any],
        party: List[Dict[str, Any]],
        world_state: Dict[str, Any],
    ) -> str:
        """Build prompt for scene description."""
        encounter_name = encounter.get("name", "Unknown Location")
        encounter_type = encounter.get("type", "exploration")
        base_description = encounter.get("story", {}).get("intro_text", "")

        party_classes = [p.get("class", "adventurer") for p in party]
        party_size = len(party)

        time_of_day = world_state.get("time", {}).get("hour", 12)
        time_str = "morning" if 6 <= time_of_day < 12 else "afternoon" if 12 <= time_of_day < 18 else "evening" if 18 <= time_of_day < 22 else "night"

        flags = list(world_state.get("flags", {}).keys())[:5]  # Limit flags

        return f"""Describe this scene for the players:

Encounter: {encounter_name} ({encounter_type})
Base description: {base_description}

Party: {party_size} adventurers ({', '.join(party_classes)})
Time: {time_str}
Relevant story flags: {', '.join(flags) if flags else 'none'}

Write an immersive 2-4 sentence description that sets the scene.
Focus on sensory details and atmosphere. What do they see, hear, smell?"""

    def _build_npc_prompt(
        self,
        npc_name: str,
        npc_personality: str,
        context: str,
        player_input: str,
    ) -> str:
        """Build prompt for NPC dialogue."""
        return f"""Generate dialogue for this NPC:

NPC: {npc_name}
Personality: {npc_personality}
Current situation: {context}
Player said: "{player_input}"

Respond in character as {npc_name}. Keep response to 1-3 sentences.
Include appropriate mannerisms and speech patterns.
Show personality through word choice and tone."""

    def _build_combat_narration_prompt(
        self,
        action_result: Dict[str, Any],
        combatant: Dict[str, Any],
        target: Optional[Dict[str, Any]],
    ) -> str:
        """Build prompt for combat narration."""
        actor_name = combatant.get("name", "The combatant")
        actor_class = combatant.get("class", "warrior")
        action_type = action_result.get("action_type", "attack")
        damage = action_result.get("damage", 0)
        result = "hit" if action_result.get("hit", False) else "missed"

        target_name = target.get("name", "the enemy") if target else "the enemy"
        target_hp = target.get("current_hp", 0) if target else 0
        is_kill = target_hp <= 0 if target else False

        return f"""Narrate this combat action dramatically:

Actor: {actor_name} ({actor_class})
Action: {action_type}
Target: {target_name}
Result: {result}{f' for {damage} damage' if result == 'hit' and damage > 0 else ''}
{f'KILLING BLOW!' if is_kill else ''}

Write 1-2 sentences of dramatic narration. Be vivid and exciting.
Don't mention dice, numbers, or game mechanics."""

    def _build_encounter_suggestion_prompt(
        self,
        party_status: Dict[str, Any],
        story_context: str,
    ) -> str:
        """Build prompt for encounter suggestion."""
        avg_level = party_status.get("avg_level", 1)
        party_size = party_status.get("party_size", 4)
        hp_percent = party_status.get("hp_percent", 100)
        resources = party_status.get("resources", "full")

        return f"""Suggest a balanced D&D 5e encounter:

Party status:
- Average level: {avg_level}
- Party size: {party_size}
- Current HP%: {hp_percent}
- Resources remaining: {resources}

Story context: {story_context}

Suggest an encounter in this JSON format:
{{"name": "encounter name", "difficulty": "easy/medium/hard/deadly",
  "enemies": [{{"template": "goblin/orc/etc", "count": N}}],
  "narrative_hook": "one sentence hook"}}

Consider party resources when choosing difficulty."""

    def _parse_encounter_suggestion(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse encounter suggestion from Claude response."""
        import json
        import re

        # Try to find JSON in response
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError as e:
                import logging
                logging.debug(f"AI DM response was not valid JSON: {e}")

        # Fallback: return raw text as narrative hook
        return {
            "name": "Dynamic Encounter",
            "difficulty": "medium",
            "enemies": [],
            "narrative_hook": response[:200] if response else "An unexpected challenge awaits.",
        }


# Singleton accessor
def get_ai_dm() -> AIDMService:
    """Get the AI DM service singleton."""
    return AIDMService.get_instance()
