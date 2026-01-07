"""
Campaign Generator Service.

Generates BG3-quality campaigns from user prompts using AI.
Supports:
- Full campaign generation from concept
- Act and chapter structure
- Encounter generation with pacing
- NPC creation with depth
- Consequence chain design
"""

from typing import Optional, Dict, Any, List, Tuple
import asyncio
import logging
import json
import uuid

from app.config import get_settings
from app.models.campaign import (
    Campaign, Act, ActTheme, Chapter, Encounter, EncounterType,
    CombatSetup, ChoiceSetup, Choice, StoryContent, EnemySpawn,
    Rewards, EncounterTransitions, CampaignSettings, Difficulty,
)
from app.models.npc import NPC, NPCRole
from app.core.pacing_manager import PacingManager, EncounterPacing
from app.services.prompts.campaign_prompts import (
    build_campaign_prompt,
    build_chapter_prompt,
    build_encounter_prompt,
    build_npc_prompt,
    DIALOGUE_TREE_PROMPT,
    CONSEQUENCE_CHAIN_PROMPT,
)

logger = logging.getLogger(__name__)


class CampaignGeneratorService:
    """
    Generates BG3-quality campaigns from prompts.

    Uses multi-stage AI generation:
    1. High-level structure (acts, themes, antagonist)
    2. Chapter breakdown with pacing analysis
    3. Encounter design with variety balance
    4. NPC population with personalities
    5. Dialogue and choice generation
    6. Consequence mapping
    """

    _instance: Optional["CampaignGeneratorService"] = None

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.ANTHROPIC_API_KEY
        self._client = None
        self._model = "claude-sonnet-4-20250514"  # Good balance of quality/speed
        self._pacing_manager = PacingManager()

        # Initialize client if API key is available
        if self._api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
                logger.info("Campaign Generator initialized with Claude API")
            except ImportError:
                logger.warning("anthropic package not installed - generator disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")

    @classmethod
    def get_instance(cls) -> "CampaignGeneratorService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_available(self) -> bool:
        """Check if generator is available."""
        return self._client is not None

    # =========================================================================
    # MAIN GENERATION METHODS
    # =========================================================================

    async def generate_campaign(
        self,
        concept: str,
        party_level_range: Tuple[int, int] = (1, 10),
        length: str = "medium",
        tone: str = "mixed",
    ) -> Optional[Campaign]:
        """
        Generate a complete campaign from a concept.

        Args:
            concept: User's campaign idea/premise
            party_level_range: (start_level, end_level) for the campaign
            length: "short", "medium", "long", or "epic"
            tone: "dark", "heroic", "comedic", or "mixed"

        Returns:
            Generated Campaign object or None if generation fails
        """
        if not self._client:
            logger.error("Cannot generate campaign: AI client not available")
            return None

        logger.info(f"Generating campaign: {concept[:50]}...")

        # Step 1: Generate high-level structure
        structure = await self._generate_campaign_structure(
            concept, party_level_range, length, tone
        )
        if not structure:
            logger.error("Failed to generate campaign structure")
            return None

        # Step 2: Parse structure into Campaign object
        campaign = self._parse_campaign_structure(structure)
        if not campaign:
            logger.error("Failed to parse campaign structure")
            return None

        # Step 3: Generate detailed encounters for each chapter
        await self._populate_encounters(campaign, party_level_range[0])

        # Step 4: Generate NPCs
        await self._populate_npcs(campaign)

        logger.info(f"Campaign generated: {campaign.name}")
        return campaign

    async def generate_act_structure(
        self,
        concept: str,
        num_acts: int = 3,
    ) -> List[Act]:
        """
        Generate act structure for a campaign concept.

        Args:
            concept: Campaign concept
            num_acts: Number of acts (typically 3)

        Returns:
            List of Act objects
        """
        structure = await self._generate_campaign_structure(
            concept, (1, 10), "medium", "mixed"
        )

        if not structure or "acts" not in structure:
            return []

        acts = []
        for act_data in structure.get("acts", []):
            acts.append(Act.from_dict(act_data))

        return acts

    async def generate_chapter(
        self,
        campaign: Campaign,
        act: Act,
        chapter_index: int,
        party_level: int,
        previous_summary: str = "",
    ) -> Optional[Chapter]:
        """
        Generate a single chapter with encounters.

        Args:
            campaign: Parent campaign
            act: Parent act
            chapter_index: Index of chapter in act
            party_level: Current party level
            previous_summary: Summary of previous events

        Returns:
            Generated Chapter object
        """
        if not self._client:
            return None

        # Determine position and pacing
        total_chapters = len(act.chapters)
        position = "beginning" if chapter_index == 0 else (
            "end" if chapter_index == total_chapters - 1 else "middle"
        )

        # Get pacing targets
        encounter_budget = self._pacing_manager.get_encounter_budget(5)

        chapter_id = f"chapter-{act.id}-{chapter_index + 1}"

        prompt = build_chapter_prompt(
            campaign_name=campaign.name,
            central_conflict=campaign.central_conflict,
            act_name=act.name,
            act_theme=act.theme.value,
            emotional_arc=act.emotional_arc,
            chapter_id=chapter_id,
            chapter_title=f"Chapter {chapter_index + 1}",
            chapter_description=f"Chapter {chapter_index + 1} of {act.name}",
            position_in_act=position,
            party_level=party_level,
            party_size=4,
            previous_summary=previous_summary,
            encounter_count=5,
            encounter_targets=encounter_budget,
            pacing_curve="rising" if position != "end" else "climactic",
            required_types=["combat", "social"],
        )

        response = await self._call_claude(prompt, max_tokens=4000)
        if not response:
            return None

        try:
            encounters_data = self._parse_json_response(response)
            if not encounters_data:
                return None

            # Create chapter
            chapter = Chapter(
                id=chapter_id,
                title=f"Chapter {chapter_index + 1}",
                description="",
                encounters=[],
            )

            # Parse encounters
            for enc_data in encounters_data:
                encounter = Encounter.from_dict(enc_data)
                campaign.encounters[encounter.id] = encounter
                chapter.encounters.append(encounter.id)

            return chapter

        except Exception as e:
            logger.error(f"Failed to parse chapter: {e}")
            return None

    async def generate_encounter(
        self,
        campaign: Campaign,
        encounter_type: str,
        context: Dict[str, Any],
    ) -> Optional[Encounter]:
        """
        Generate a single encounter.

        Args:
            campaign: Parent campaign
            encounter_type: Type of encounter to generate
            context: Context including party info, story state, etc.

        Returns:
            Generated Encounter object
        """
        if not self._client:
            return None

        prompt = build_encounter_prompt(
            campaign_name=campaign.name,
            act_name=context.get("act_name", ""),
            act_theme=context.get("act_theme", "mystery"),
            chapter_name=context.get("chapter_name", ""),
            story_summary=context.get("story_summary", ""),
            party_level=context.get("party_level", 1),
            party_composition=context.get("party_composition", ""),
            recent_events=context.get("recent_events", ""),
            active_flags=context.get("active_flags", []),
            encounter_type=encounter_type,
            pacing=context.get("pacing", "tension_rise"),
            difficulty=context.get("difficulty", "medium"),
            callbacks=context.get("callbacks", []),
        )

        response = await self._call_claude(prompt, max_tokens=2000)
        if not response:
            return None

        try:
            enc_data = self._parse_json_response(response)
            if not enc_data:
                return None

            return Encounter.from_dict(enc_data)

        except Exception as e:
            logger.error(f"Failed to parse encounter: {e}")
            return None

    async def generate_npc(
        self,
        campaign: Campaign,
        role: str,
        context: Dict[str, Any],
    ) -> Optional[NPC]:
        """
        Generate a single NPC with BG3-quality depth.

        Args:
            campaign: Parent campaign
            role: NPC role (companion, villain, etc.)
            context: Generation context

        Returns:
            Generated NPC object
        """
        if not self._client:
            return None

        prompt = build_npc_prompt(
            campaign_name=campaign.name,
            tone=campaign.tone,
            story_context=context.get("story_context", ""),
            role=role,
            importance=context.get("importance", "major"),
            first_appearance=context.get("first_appearance", ""),
        )

        response = await self._call_claude(prompt, max_tokens=2000)
        if not response:
            return None

        try:
            npc_data = self._parse_json_response(response)
            if not npc_data:
                return None

            return NPC.from_dict(npc_data)

        except Exception as e:
            logger.error(f"Failed to parse NPC: {e}")
            return None

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    async def _generate_campaign_structure(
        self,
        concept: str,
        level_range: Tuple[int, int],
        length: str,
        tone: str,
    ) -> Optional[Dict[str, Any]]:
        """Generate the high-level campaign structure."""
        prompt = build_campaign_prompt(
            concept=concept,
            level_start=level_range[0],
            level_end=level_range[1],
            length=length,
            tone=tone,
        )

        response = await self._call_claude(prompt, max_tokens=4000)
        if not response:
            return None

        return self._parse_json_response(response)

    def _parse_campaign_structure(
        self,
        structure: Dict[str, Any],
    ) -> Optional[Campaign]:
        """Parse AI response into Campaign object."""
        try:
            campaign_id = str(uuid.uuid4())

            # Parse acts
            acts = []
            for act_data in structure.get("acts", []):
                theme_str = act_data.get("theme", "mystery")
                try:
                    theme = ActTheme(theme_str)
                except ValueError:
                    theme = ActTheme.MYSTERY

                act = Act(
                    id=act_data.get("id", f"act-{len(acts) + 1}"),
                    name=act_data.get("name", f"Act {len(acts) + 1}"),
                    theme=theme,
                    description=act_data.get("description", ""),
                    emotional_arc=act_data.get("emotional_arc", ""),
                    chapters=act_data.get("chapters", []),
                    key_revelations=act_data.get("key_revelations", []),
                )
                acts.append(act)

            # Parse chapters (placeholder - will be populated later)
            chapters = []
            for chapter_data in structure.get("chapters", []):
                chapter = Chapter(
                    id=chapter_data.get("id", f"chapter-{len(chapters) + 1}"),
                    title=chapter_data.get("title", f"Chapter {len(chapters) + 1}"),
                    description=chapter_data.get("description", ""),
                    encounters=[],
                )
                chapters.append(chapter)

            # Store NPC data for later population
            npcs_data = {}
            for npc_data in structure.get("major_npcs", []):
                npc_id = str(uuid.uuid4())
                npcs_data[npc_id] = npc_data

            # Create campaign
            campaign = Campaign(
                id=campaign_id,
                name=structure.get("title", "Untitled Campaign"),
                description=structure.get("hook", ""),
                author="AI Generated",
                settings=CampaignSettings(),
                acts=acts,
                chapters=chapters,
                encounters={},
                npcs=npcs_data,
                central_conflict=structure.get("central_conflict", ""),
                tone=structure.get("tone", "mixed"),
                estimated_playtime=self._get_playtime_from_encounters(
                    structure.get("estimated_encounters", {})
                ),
            )

            return campaign

        except Exception as e:
            logger.error(f"Failed to parse campaign structure: {e}")
            return None

    async def _populate_encounters(
        self,
        campaign: Campaign,
        starting_level: int,
    ):
        """Generate detailed encounters for all chapters."""
        party_level = starting_level
        previous_summary = "The adventure begins."

        for act_index, act in enumerate(campaign.acts):
            for chapter_index, chapter_id in enumerate(act.chapters):
                # Find the chapter
                chapter = None
                for c in campaign.chapters:
                    if c.id == chapter_id:
                        chapter = c
                        break

                if not chapter:
                    continue

                # Generate encounters for this chapter
                generated_chapter = await self.generate_chapter(
                    campaign=campaign,
                    act=act,
                    chapter_index=chapter_index,
                    party_level=party_level,
                    previous_summary=previous_summary,
                )

                if generated_chapter:
                    # Update chapter with generated encounters
                    chapter.encounters = generated_chapter.encounters

                    # Update summary for next chapter
                    if chapter.encounters:
                        previous_summary = f"Completed {chapter.title}"

            # Level up between acts
            party_level = min(party_level + 3, 20)

    async def _populate_npcs(self, campaign: Campaign):
        """Generate detailed NPC objects from the campaign's NPC data."""
        detailed_npcs = {}

        for npc_id, npc_data in campaign.npcs.items():
            npc = await self.generate_npc(
                campaign=campaign,
                role=npc_data.get("role", "ally"),
                context={
                    "story_context": campaign.central_conflict,
                    "importance": "major" if npc_data.get("role") in ["companion", "villain"] else "supporting",
                    "first_appearance": "Act 1",
                },
            )

            if npc:
                detailed_npcs[npc.id] = npc.to_dict()
            else:
                # Keep original data if generation fails
                detailed_npcs[npc_id] = npc_data

        campaign.npcs = detailed_npcs

    def _get_playtime_from_encounters(
        self,
        encounter_counts: Dict[str, int],
    ) -> str:
        """Estimate playtime from encounter counts."""
        total = sum(encounter_counts.values())

        if total <= 8:
            return "short"
        elif total <= 20:
            return "medium"
        elif total <= 40:
            return "long"
        else:
            return "epic"

    async def _call_claude(
        self,
        prompt: str,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        """Call Claude API with the given prompt."""
        if not self._client:
            return None

        try:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    system=self._get_system_prompt(),
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            return message.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    def _get_system_prompt(self) -> str:
        """Get system prompt for campaign generation."""
        return """You are an expert D&D campaign designer with deep knowledge of Baldur's Gate 3's narrative design.

Your campaigns feature:
- Complex, multi-layered plots with meaningful player agency
- Memorable NPCs with distinct personalities, motivations, and secrets
- Varied encounter types that maintain engagement
- Consequences that ripple through the story
- Balance of drama, humor, and action
- Multiple valid approaches to challenges

Always output valid JSON that matches the requested schema exactly.
Be creative but ensure content is appropriate for a fantasy adventure game."""

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from Claude's response."""
        try:
            # Try to find JSON in the response
            response = response.strip()

            # Handle markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()

            # Try parsing
            return json.loads(response)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"Response was: {response[:500]}...")
            return None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_campaign_generator() -> CampaignGeneratorService:
    """Get the campaign generator service instance."""
    return CampaignGeneratorService.get_instance()


async def quick_generate_campaign(
    concept: str,
    length: str = "medium",
    tone: str = "mixed",
) -> Optional[Campaign]:
    """
    Quick helper to generate a campaign.

    Args:
        concept: Campaign concept/premise
        length: Campaign length
        tone: Campaign tone

    Returns:
        Generated Campaign or None
    """
    generator = get_campaign_generator()
    return await generator.generate_campaign(
        concept=concept,
        party_level_range=(1, 10),
        length=length,
        tone=tone,
    )


# Default instance for imports
campaign_generator = CampaignGeneratorService.get_instance()
