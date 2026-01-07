"""
NPC Generator Service.

Generates memorable NPCs with BG3-quality personalities:
- Distinct personality traits and quirks
- Consistent voice and speech patterns
- Dynamic dialogue based on relationship
- Character arcs and secrets
- Situational bark lines
"""

from typing import Optional, Dict, Any, List
import asyncio
import logging
import json
import uuid

from app.config import get_settings
from app.models.npc import (
    NPC, NPCRole, NPCPersonality, HumorStyle, SpeechPattern,
    DialogueTree, DialogueNode, DialogueOption, NPCArc,
    RelationshipTier, create_companion_npc, create_villain_npc,
)
from app.services.prompts.campaign_prompts import (
    build_npc_prompt,
    DIALOGUE_TREE_PROMPT,
)

logger = logging.getLogger(__name__)


class NPCGeneratorService:
    """
    Generates memorable NPCs with BG3-quality personalities.

    Features:
    - Rich personality generation with distinct traits
    - Dialogue tree generation based on personality
    - Bark lines for situational immersion
    - Character arc design
    - Relationship-aware dialogue
    """

    _instance: Optional["NPCGeneratorService"] = None

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.ANTHROPIC_API_KEY
        self._client = None
        self._model = "claude-sonnet-4-20250514"

        if self._api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
                logger.info("NPC Generator initialized with Claude API")
            except ImportError:
                logger.warning("anthropic package not installed")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")

    @classmethod
    def get_instance(cls) -> "NPCGeneratorService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_available(self) -> bool:
        """Check if generator is available."""
        return self._client is not None

    # =========================================================================
    # NPC GENERATION
    # =========================================================================

    async def generate_npc(
        self,
        role: str,
        context: Dict[str, Any],
    ) -> Optional[NPC]:
        """
        Generate a new NPC with full personality.

        Args:
            role: NPC role (companion, villain, quest_giver, etc.)
            context: Generation context including campaign info

        Returns:
            Generated NPC or None
        """
        if not self._client:
            logger.warning("Using fallback NPC generation - no AI client")
            return self._generate_fallback_npc(role, context)

        prompt = build_npc_prompt(
            campaign_name=context.get("campaign_name", "Unknown Campaign"),
            tone=context.get("tone", "mixed"),
            story_context=context.get("story_context", ""),
            role=role,
            importance=context.get("importance", "major"),
            first_appearance=context.get("first_appearance", "Act 1"),
            npc_id=str(uuid.uuid4()),
        )

        response = await self._call_claude(prompt, max_tokens=2500)
        if not response:
            return self._generate_fallback_npc(role, context)

        try:
            npc_data = self._parse_json_response(response)
            if not npc_data:
                return self._generate_fallback_npc(role, context)

            return NPC.from_dict(npc_data)

        except Exception as e:
            logger.error(f"Failed to parse NPC: {e}")
            return self._generate_fallback_npc(role, context)

    async def generate_dialogue_tree(
        self,
        npc: NPC,
        topic: str,
        context: Dict[str, Any],
    ) -> Optional[DialogueTree]:
        """
        Generate a dialogue tree for an NPC on a specific topic.

        Args:
            npc: The NPC
            topic: Dialogue topic (greeting, quest_intro, romance, etc.)
            context: Context including player goals, available flags, etc.

        Returns:
            Generated DialogueTree or None
        """
        if not self._client:
            return self._generate_fallback_dialogue(npc, topic)

        # Build personality summary
        personality_summary = ", ".join(npc.personality.traits)

        prompt = DIALOGUE_TREE_PROMPT.format(
            npc_name=npc.name,
            personality_summary=personality_summary,
            speech_pattern=npc.personality.speech_pattern.value,
            disposition=npc.current_disposition,
            disposition_tier=npc.get_relationship_tier().value,
            encounter_name=context.get("encounter_name", ""),
            topic=topic,
            npc_knowledge=context.get("npc_knowledge", ""),
            npc_wants=context.get("npc_wants", ""),
            player_goal=context.get("player_goal", ""),
            available_flags="\n".join(context.get("available_flags", [])),
        )

        response = await self._call_claude(prompt, max_tokens=3000)
        if not response:
            return self._generate_fallback_dialogue(npc, topic)

        try:
            tree_data = self._parse_json_response(response)
            if not tree_data:
                return self._generate_fallback_dialogue(npc, topic)

            return DialogueTree.from_dict(tree_data)

        except Exception as e:
            logger.error(f"Failed to parse dialogue tree: {e}")
            return self._generate_fallback_dialogue(npc, topic)

    async def generate_bark_lines(
        self,
        npc: NPC,
        situations: List[str] = None,
    ) -> Dict[str, List[str]]:
        """
        Generate situational bark lines for an NPC.

        Args:
            npc: The NPC
            situations: List of situations to generate lines for

        Returns:
            Dictionary of situation -> list of lines
        """
        if situations is None:
            situations = [
                "combat_start",
                "low_health",
                "victory",
                "rest",
                "exploration",
                "approval_high",
                "approval_low",
                "discovery",
                "trap",
                "death_nearby",
            ]

        if not self._client:
            return self._generate_fallback_barks(npc, situations)

        personality_summary = ", ".join(npc.personality.traits)
        humor = npc.personality.humor_style.value

        prompt = f"""Generate situational bark lines (short one-liners) for this D&D NPC:

NPC: {npc.name}
Personality: {personality_summary}
Humor Style: {humor}
Speech Pattern: {npc.personality.speech_pattern.value}
Catchphrase: {npc.personality.catchphrase or 'None'}

Generate 2-3 bark lines for each situation. Lines should:
- Match the NPC's personality and voice
- Be brief (under 15 words each)
- Show character through word choice
- Include humor where appropriate for the character

Situations to generate lines for:
{chr(10).join(f'- {s}' for s in situations)}

Output JSON:
{{
  "combat_start": ["Line 1", "Line 2"],
  "low_health": ["Line 1", "Line 2"],
  ...
}}"""

        response = await self._call_claude(prompt, max_tokens=1500)
        if not response:
            return self._generate_fallback_barks(npc, situations)

        try:
            barks = self._parse_json_response(response)
            if barks:
                return barks
        except Exception as e:
            logger.error(f"Failed to parse bark lines: {e}")

        return self._generate_fallback_barks(npc, situations)

    async def evolve_npc(
        self,
        npc: NPC,
        events: List[Dict[str, Any]],
    ) -> NPC:
        """
        Evolve an NPC based on story events (character growth).

        Args:
            npc: The NPC to evolve
            events: List of events that affected them

        Returns:
            Updated NPC with evolved personality/arc
        """
        if not npc.arc:
            return npc

        # Check if any events match growth triggers
        growth_triggered = False
        for event in events:
            event_type = event.get("type", "")
            for trigger in npc.arc.growth_triggers:
                if trigger.lower() in event_type.lower():
                    growth_triggered = True
                    break

        if growth_triggered:
            npc.arc.current_stage += 1
            logger.info(f"NPC {npc.name} grew to stage {npc.arc.current_stage}")

            # Could use AI to generate new personality aspects
            # For now, just track the stage change

        return npc

    # =========================================================================
    # RELATIONSHIP-AWARE METHODS
    # =========================================================================

    def get_greeting(
        self,
        npc: NPC,
        world_state_flags: List[str] = None,
    ) -> str:
        """
        Get an appropriate greeting based on relationship.

        Args:
            npc: The NPC
            world_state_flags: Current world state flags

        Returns:
            Greeting text
        """
        tier = npc.get_relationship_tier()

        if tier == RelationshipTier.HOSTILE:
            return f"*{npc.name} glares at you with barely contained hostility.*"
        elif tier == RelationshipTier.UNFRIENDLY:
            return f"*{npc.name} regards you coldly.* \"What do you want?\""
        elif tier == RelationshipTier.NEUTRAL:
            return f"*{npc.name} nods in acknowledgment.* \"Can I help you?\""
        elif tier == RelationshipTier.FRIENDLY:
            return f"*{npc.name}'s face brightens.* \"Good to see you again!\""
        elif tier == RelationshipTier.DEVOTED:
            return f"*{npc.name} greets you warmly.* \"My friend! I'm glad you're here.\""
        else:  # ROMANCE
            return f"*{npc.name} smiles softly.* \"I was hoping you'd come.\""

    def get_bark_for_situation(
        self,
        npc: NPC,
        situation: str,
    ) -> Optional[str]:
        """
        Get a bark line for a specific situation.

        Args:
            npc: The NPC
            situation: The situation type

        Returns:
            A bark line or None
        """
        return npc.get_bark_line(situation)

    # =========================================================================
    # FALLBACK GENERATION (when AI unavailable)
    # =========================================================================

    def _generate_fallback_npc(
        self,
        role: str,
        context: Dict[str, Any],
    ) -> NPC:
        """Generate a basic NPC without AI."""
        npc_id = str(uuid.uuid4())
        name = context.get("name", f"NPC_{npc_id[:8]}")

        if role == "companion":
            return create_companion_npc(
                name=name,
                traits=["loyal", "brave", "curious"],
                motivation="Seeks adventure and purpose",
                fear="Being alone",
                likes=["helping others", "honesty"],
                dislikes=["cruelty", "deception"],
            )
        elif role == "villain":
            return create_villain_npc(
                name=name,
                traits=["cunning", "ambitious", "ruthless"],
                motivation="Power and control",
                tragic_flaw="Cannot trust anyone",
            )
        else:
            personality = NPCPersonality(
                traits=["friendly", "helpful"],
                surface_motivation="Help adventurers",
                humor_style=HumorStyle.EARNEST,
                speech_pattern=SpeechPattern.CASUAL,
            )
            return NPC(
                id=npc_id,
                name=name,
                role=NPCRole.NEUTRAL,
                personality=personality,
            )

    def _generate_fallback_dialogue(
        self,
        npc: NPC,
        topic: str,
    ) -> DialogueTree:
        """Generate basic dialogue without AI."""
        tree_id = f"dialogue-{topic}"

        # Create simple greeting node
        greeting_node = DialogueNode(
            id="node-1",
            npc_text=self.get_greeting(npc),
            options=[
                DialogueOption(
                    id="opt-1",
                    text="I'd like to ask you something.",
                    npc_response="Of course, what is it?",
                    leads_to="node-2",
                ),
                DialogueOption(
                    id="opt-2",
                    text="Never mind.",
                    npc_response="Very well. Come back if you need anything.",
                    leads_to=None,
                ),
            ],
        )

        # Create follow-up node
        question_node = DialogueNode(
            id="node-2",
            npc_text="I'm listening.",
            options=[
                DialogueOption(
                    id="opt-3",
                    text="Tell me about yourself.",
                    npc_response="There's not much to tell, really.",
                    disposition_change=5,
                ),
                DialogueOption(
                    id="opt-4",
                    text="What do you know about this place?",
                    npc_response="I know a few things...",
                ),
            ],
            is_exit=True,
        )

        return DialogueTree(
            id=tree_id,
            topic=topic,
            nodes={"node-1": greeting_node, "node-2": question_node},
            entry_node="node-1",
        )

    def _generate_fallback_barks(
        self,
        npc: NPC,
        situations: List[str],
    ) -> Dict[str, List[str]]:
        """Generate basic bark lines without AI."""
        name = npc.name

        default_barks = {
            "combat_start": [
                f"Here we go!",
                f"Stay alert!",
            ],
            "low_health": [
                f"I need healing!",
                f"This isn't good...",
            ],
            "victory": [
                f"Well fought!",
                f"That's done.",
            ],
            "rest": [
                f"Finally, a moment to breathe.",
                f"I could use the rest.",
            ],
            "exploration": [
                f"Interesting...",
                f"What's this?",
            ],
            "approval_high": [
                f"I knew I could count on you.",
                f"Well done.",
            ],
            "approval_low": [
                f"I expected better.",
                f"Hmm.",
            ],
            "discovery": [
                f"Look at this!",
                f"I found something.",
            ],
            "trap": [
                f"Watch out!",
                f"Careful!",
            ],
            "death_nearby": [
                f"We'll avenge them.",
                f"Such a waste...",
            ],
        }

        return {s: default_barks.get(s, ["..."]) for s in situations}

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def _call_claude(
        self,
        prompt: str,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        """Call Claude API."""
        if not self._client:
            return None

        try:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    system="""You are an expert at creating memorable D&D NPCs with distinct personalities.
Your NPCs have:
- Unique voices and speech patterns
- Layered motivations and secrets
- Consistent behavior across interactions
- Appropriate humor for their personality
Always output valid JSON matching the requested schema.""",
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            return message.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from response."""
        try:
            response = response.strip()

            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()

            return json.loads(response)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_npc_generator() -> NPCGeneratorService:
    """Get the NPC generator service instance."""
    return NPCGeneratorService.get_instance()


async def quick_generate_npc(
    role: str,
    campaign_name: str = "Adventure",
    tone: str = "mixed",
) -> Optional[NPC]:
    """Quick helper to generate an NPC."""
    generator = get_npc_generator()
    return await generator.generate_npc(
        role=role,
        context={
            "campaign_name": campaign_name,
            "tone": tone,
            "importance": "major" if role in ["companion", "villain"] else "supporting",
        },
    )
