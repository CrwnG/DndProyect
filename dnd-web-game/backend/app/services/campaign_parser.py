"""
Campaign Document Parser Service.

Parses D&D campaign PDFs/text documents into playable Campaign structures.
Uses EntityExtractor for entity detection and AI for enhancement.

Features:
- PDF and plain text parsing
- Section classification (chapters, encounters, NPCs)
- Entity extraction (stat blocks, skill checks, items)
- AI enhancement for missing content
- BG3-style campaign structure generation
"""

import re
import uuid
import logging
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from app.config import get_settings
from app.services.entity_extractor import (
    EntityExtractor,
    ExtractedEntity,
    EntityType,
    StatBlock,
    SkillCheckInfo,
    ItemInfo,
)
from app.models.campaign import (
    Campaign,
    Act,
    ActTheme,
    Chapter,
    Encounter,
    EncounterType,
    CombatSetup,
    EnemySpawn,
    GridEnvironment,
    StoryContent,
    ChoiceSetup,
    Choice,
    SkillCheck,
    CheckType,
    Rewards,
    EncounterTransitions,
    CampaignSettings,
)

logger = logging.getLogger(__name__)


class SectionType(str, Enum):
    """Types of document sections."""
    INTRODUCTION = "introduction"
    CHAPTER_INTRO = "chapter_intro"
    ENCOUNTER_COMBAT = "encounter_combat"
    ENCOUNTER_SOCIAL = "encounter_social"
    ENCOUNTER_EXPLORATION = "encounter_exploration"
    STAT_BLOCK = "stat_block"
    ITEM_DESCRIPTION = "item_description"
    MAP_KEY = "map_key"
    NPC_DESCRIPTION = "npc_description"
    APPENDIX = "appendix"
    UNKNOWN = "unknown"


class EnhancementLevel(str, Enum):
    """How much AI enhancement to apply."""
    MINIMAL = "minimal"      # Just parse, minimal AI
    MODERATE = "moderate"    # Fill gaps with AI
    FULL = "full"           # Rich AI enhancement for BG3-quality


@dataclass
class ParsedSection:
    """A parsed section of the document."""
    title: str
    content: str
    section_type: SectionType
    entities: List[ExtractedEntity] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_line: int = 0
    end_line: int = 0


@dataclass
class ParsedDocument:
    """Complete parsed document."""
    title: str
    raw_text: str
    sections: List[ParsedSection] = field(default_factory=list)
    entities: List[ExtractedEntity] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CampaignStructure:
    """Intermediate campaign structure before full conversion."""
    name: str
    description: str = ""
    acts: List[Dict[str, Any]] = field(default_factory=list)
    chapters: List[Dict[str, Any]] = field(default_factory=list)
    encounters: List[Dict[str, Any]] = field(default_factory=list)
    npcs: List[Dict[str, Any]] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)


class CampaignParserService:
    """
    Parses campaign documents into playable Campaign structures.

    Usage:
        parser = CampaignParserService()
        doc = await parser.parse_pdf(file_path)
        structure = await parser.extract_structure(doc)
        campaign = await parser.convert_to_campaign(structure)
    """

    _instance: Optional["CampaignParserService"] = None

    # Section header patterns
    CHAPTER_PATTERN = re.compile(
        r'^(?:Chapter|Part|Section|Act)\s+(\d+|[IVX]+)[:\.]?\s*(.+)?$',
        re.MULTILINE | re.IGNORECASE
    )

    AREA_HEADER_PATTERN = re.compile(
        r'^(?:Area|Room|Location)\s+([A-Z]?\d+)[:\.]?\s*(.+)?$',
        re.MULTILINE | re.IGNORECASE
    )

    ENCOUNTER_PATTERN = re.compile(
        r'^(?:Encounter|Combat|Event)\s*[:\.]?\s*(.+)?$',
        re.MULTILINE | re.IGNORECASE
    )

    APPENDIX_PATTERN = re.compile(
        r'^(?:Appendix|Appendices)\s*([A-Z])?[:\.]?\s*(.+)?$',
        re.MULTILINE | re.IGNORECASE
    )

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.ANTHROPIC_API_KEY
        self._client = None
        self._model = "claude-sonnet-4-20250514"
        self._entity_extractor = EntityExtractor()

        if self._api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
                logger.info("Campaign Parser initialized with Claude API")
            except ImportError:
                logger.warning("anthropic package not installed")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")

    @classmethod
    def get_instance(cls) -> "CampaignParserService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_available(self) -> bool:
        """Check if AI enhancement is available."""
        return self._client is not None

    # =========================================================================
    # MAIN PARSING METHODS
    # =========================================================================

    async def parse_pdf(self, file_path: str) -> ParsedDocument:
        """
        Parse a PDF campaign document.

        Args:
            file_path: Path to the PDF file

        Returns:
            ParsedDocument with extracted content
        """
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber required for PDF parsing")

        raw_text = ""
        page_texts = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                page_texts.append(text)
                raw_text += text + "\n\n"

        # Extract document title
        title = self._extract_document_title(raw_text, file_path)

        # Parse into sections
        sections = self._split_into_sections(raw_text)

        # Extract entities from full text
        entities = self._entity_extractor.extract_all(raw_text)

        logger.info(f"Parsed PDF '{title}': {len(sections)} sections, {len(entities)} entities")

        return ParsedDocument(
            title=title,
            raw_text=raw_text,
            sections=sections,
            entities=entities,
            metadata={
                "source": file_path,
                "page_count": len(page_texts),
            },
        )

    async def parse_text(self, content: str, title: str = "Untitled Campaign") -> ParsedDocument:
        """
        Parse plain text campaign content.

        Args:
            content: Campaign text content
            title: Optional title for the document

        Returns:
            ParsedDocument with extracted content
        """
        # Detect title from content if not provided
        if title == "Untitled Campaign":
            detected_title = self._extract_document_title(content, "")
            if detected_title:
                title = detected_title

        # Parse into sections
        sections = self._split_into_sections(content)

        # Extract entities
        entities = self._entity_extractor.extract_all(content)

        logger.info(f"Parsed text '{title}': {len(sections)} sections, {len(entities)} entities")

        return ParsedDocument(
            title=title,
            raw_text=content,
            sections=sections,
            entities=entities,
            metadata={"source": "text_input"},
        )

    async def extract_structure(self, doc: ParsedDocument) -> CampaignStructure:
        """
        Extract campaign structure from parsed document.

        Args:
            doc: Parsed document

        Returns:
            CampaignStructure with organized content
        """
        structure = CampaignStructure(
            name=doc.title,
            description=self._extract_campaign_description(doc),
        )

        # Group sections into chapters
        current_chapter = None
        chapter_encounters = []

        for section in doc.sections:
            if section.section_type == SectionType.CHAPTER_INTRO:
                # Save previous chapter
                if current_chapter:
                    current_chapter["encounters"] = chapter_encounters
                    structure.chapters.append(current_chapter)
                    chapter_encounters = []

                # Start new chapter
                current_chapter = {
                    "id": f"chapter-{len(structure.chapters) + 1}",
                    "title": section.title,
                    "description": section.content[:500],
                    "encounters": [],
                }

            elif section.section_type in [
                SectionType.ENCOUNTER_COMBAT,
                SectionType.ENCOUNTER_SOCIAL,
                SectionType.ENCOUNTER_EXPLORATION,
                SectionType.MAP_KEY,
            ]:
                encounter = self._section_to_encounter(section, doc.entities)
                chapter_encounters.append(encounter)
                structure.encounters.append(encounter)

            elif section.section_type == SectionType.NPC_DESCRIPTION:
                npc = self._section_to_npc(section)
                structure.npcs.append(npc)

        # Save last chapter
        if current_chapter:
            current_chapter["encounters"] = chapter_encounters
            structure.chapters.append(current_chapter)

        # If no chapters found, create one default chapter
        if not structure.chapters and structure.encounters:
            structure.chapters.append({
                "id": "chapter-1",
                "title": "Main Adventure",
                "description": doc.title,
                "encounters": [e["id"] for e in structure.encounters],
            })

        # Extract NPCs from entities
        for entity in doc.entities:
            if entity.entity_type == EntityType.NPC:
                npc_data = {
                    "id": f"npc-{len(structure.npcs) + 1}",
                    "name": entity.name,
                    "dialogue": entity.data.get("dialogue", []),
                }
                # Avoid duplicates
                if not any(n["name"] == npc_data["name"] for n in structure.npcs):
                    structure.npcs.append(npc_data)

        # Extract items from entities
        for entity in doc.entities:
            if entity.entity_type == EntityType.ITEM:
                structure.items.append(entity.data)

        # Generate act structure
        structure.acts = self._generate_acts(structure.chapters)

        logger.info(
            f"Extracted structure: {len(structure.acts)} acts, "
            f"{len(structure.chapters)} chapters, {len(structure.encounters)} encounters"
        )

        return structure

    async def convert_to_campaign(
        self,
        structure: CampaignStructure,
        enhancement_level: EnhancementLevel = EnhancementLevel.MODERATE,
    ) -> Campaign:
        """
        Convert structure to full Campaign model.

        Args:
            structure: Campaign structure to convert
            enhancement_level: How much AI enhancement to apply

        Returns:
            Complete Campaign model
        """
        campaign_id = str(uuid.uuid4())

        # Convert acts
        acts = []
        for act_data in structure.acts:
            act = Act(
                id=act_data.get("id", str(uuid.uuid4())),
                name=act_data.get("name", "Unknown Act"),
                theme=ActTheme(act_data.get("theme", "mystery")),
                description=act_data.get("description", ""),
                emotional_arc=act_data.get("emotional_arc", ""),
                chapters=act_data.get("chapters", []),
            )
            acts.append(act)

        # Convert chapters
        chapters = []
        for ch_data in structure.chapters:
            chapter = Chapter(
                id=ch_data.get("id", str(uuid.uuid4())),
                title=ch_data.get("title", "Unknown Chapter"),
                description=ch_data.get("description", ""),
                encounters=[e["id"] if isinstance(e, dict) else e for e in ch_data.get("encounters", [])],
            )
            chapters.append(chapter)

        # Convert encounters
        encounters = {}
        for i, enc_data in enumerate(structure.encounters):
            encounter = self._create_encounter(enc_data, i, len(structure.encounters))
            encounters[encounter.id] = encounter

        # Link encounters
        self._link_encounters(encounters, chapters)

        # Create NPCs dict
        npcs = {}
        for npc_data in structure.npcs:
            npc_id = npc_data.get("id", str(uuid.uuid4()))
            npcs[npc_id] = npc_data

        # Determine starting encounter
        starting_encounter = None
        if chapters and chapters[0].encounters:
            starting_encounter = chapters[0].encounters[0]

        # Enhance with AI if available and requested
        if self._client and enhancement_level != EnhancementLevel.MINIMAL:
            campaign = Campaign(
                id=campaign_id,
                name=structure.name,
                description=structure.description,
                acts=acts,
                chapters=chapters,
                encounters=encounters,
                npcs=npcs,
                starting_encounter=starting_encounter,
            )

            if enhancement_level == EnhancementLevel.FULL:
                campaign = await self._enhance_campaign_full(campaign)
            else:
                campaign = await self._enhance_campaign_moderate(campaign)

            return campaign

        return Campaign(
            id=campaign_id,
            name=structure.name,
            description=structure.description,
            acts=acts,
            chapters=chapters,
            encounters=encounters,
            npcs=npcs,
            starting_encounter=starting_encounter,
        )

    async def parse_and_convert(
        self,
        content: str,
        is_pdf: bool = False,
        file_path: str = "",
        enhancement_level: EnhancementLevel = EnhancementLevel.MODERATE,
    ) -> Campaign:
        """
        Parse content and convert to campaign in one call.

        Args:
            content: Text content or file path for PDF
            is_pdf: Whether content is a PDF file path
            file_path: File path for PDF
            enhancement_level: AI enhancement level

        Returns:
            Complete Campaign
        """
        if is_pdf:
            doc = await self.parse_pdf(file_path or content)
        else:
            doc = await self.parse_text(content)

        structure = await self.extract_structure(doc)
        return await self.convert_to_campaign(structure, enhancement_level)

    # =========================================================================
    # SECTION PARSING
    # =========================================================================

    def _split_into_sections(self, text: str) -> List[ParsedSection]:
        """Split text into logical sections."""
        sections = []
        lines = text.split('\n')

        current_section = None
        current_content = []
        current_start = 0

        for i, line in enumerate(lines):
            # Check for section headers
            section_type, title = self._classify_line_as_header(line)

            if section_type:
                # Save previous section
                if current_section:
                    content = '\n'.join(current_content).strip()
                    if content:
                        current_section.content = content
                        current_section.end_line = i - 1
                        sections.append(current_section)

                # Start new section
                current_section = ParsedSection(
                    title=title or line.strip(),
                    content="",
                    section_type=section_type,
                    start_line=i,
                )
                current_content = []
                current_start = i
            else:
                current_content.append(line)

        # Save last section
        if current_section:
            content = '\n'.join(current_content).strip()
            if content:
                current_section.content = content
                current_section.end_line = len(lines) - 1
                sections.append(current_section)

        # Classify sections more specifically
        for section in sections:
            section.section_type = self._classify_section(section)
            section.entities = self._entity_extractor.extract_all(section.content)

        return sections

    def _classify_line_as_header(self, line: str) -> Tuple[Optional[SectionType], Optional[str]]:
        """Check if line is a section header."""
        line = line.strip()
        if not line:
            return None, None

        # Check for chapter headers
        match = self.CHAPTER_PATTERN.match(line)
        if match:
            title = match.group(2) if match.group(2) else f"Chapter {match.group(1)}"
            return SectionType.CHAPTER_INTRO, title.strip()

        # Check for area headers
        match = self.AREA_HEADER_PATTERN.match(line)
        if match:
            title = match.group(2) if match.group(2) else f"Area {match.group(1)}"
            return SectionType.MAP_KEY, title.strip()

        # Check for encounter headers
        match = self.ENCOUNTER_PATTERN.match(line)
        if match:
            title = match.group(1) if match.group(1) else "Encounter"
            return SectionType.ENCOUNTER_COMBAT, title.strip()

        # Check for appendix headers
        match = self.APPENDIX_PATTERN.match(line)
        if match:
            title = match.group(2) if match.group(2) else "Appendix"
            return SectionType.APPENDIX, title.strip()

        # Check for all-caps headers (common in D&D modules)
        if line.isupper() and len(line) > 3 and len(line) < 50:
            return SectionType.UNKNOWN, line.title()

        return None, None

    def _classify_section(self, section: ParsedSection) -> SectionType:
        """Classify section type based on content."""
        content_lower = section.content.lower()

        # Check for stat blocks
        if any(entity.entity_type == EntityType.STAT_BLOCK for entity in section.entities):
            return SectionType.STAT_BLOCK

        # Check for combat indicators
        combat_indicators = [
            'initiative', 'combat begins', 'attack', 'hit points', 'armor class',
            'enemies:', 'hostile', 'fight', 'battle',
        ]
        if any(ind in content_lower for ind in combat_indicators):
            return SectionType.ENCOUNTER_COMBAT

        # Check for social/dialogue indicators
        social_indicators = [
            'dialogue', 'conversation', 'persuasion', 'deception', 'roleplay',
            'speaks', 'says', 'tells you', 'asks',
        ]
        if any(ind in content_lower for ind in social_indicators):
            return SectionType.ENCOUNTER_SOCIAL

        # Check for exploration indicators
        exploration_indicators = [
            'investigation', 'search', 'examine', 'discover', 'find',
            'puzzle', 'trap', 'secret',
        ]
        if any(ind in content_lower for ind in exploration_indicators):
            return SectionType.ENCOUNTER_EXPLORATION

        # Check for NPC descriptions
        npc_indicators = [
            'npc', 'character:', 'personality', 'motivation', 'appearance',
        ]
        if any(ind in content_lower for ind in npc_indicators):
            return SectionType.NPC_DESCRIPTION

        # Check for item descriptions
        item_indicators = [
            'magic item', 'treasure', 'reward', 'loot', 'artifact',
        ]
        if any(ind in content_lower for ind in item_indicators):
            return SectionType.ITEM_DESCRIPTION

        # Default based on original classification
        return section.section_type

    # =========================================================================
    # CONVERSION HELPERS
    # =========================================================================

    def _extract_document_title(self, text: str, file_path: str) -> str:
        """Extract document title from content or filename."""
        lines = text.split('\n')

        # Check first few non-empty lines for title
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) > 3 and len(line) < 100:
                # Skip common headers
                if not any(skip in line.lower() for skip in ['chapter', 'contents', 'introduction']):
                    return line

        # Fall back to filename
        if file_path:
            path = Path(file_path)
            return path.stem.replace('_', ' ').replace('-', ' ').title()

        return "Untitled Campaign"

    def _extract_campaign_description(self, doc: ParsedDocument) -> str:
        """Extract campaign description from document."""
        # Look for introduction section
        for section in doc.sections:
            if section.section_type == SectionType.INTRODUCTION:
                return section.content[:1000]

        # Fall back to first section content
        if doc.sections:
            return doc.sections[0].content[:500]

        return ""

    def _section_to_encounter(
        self,
        section: ParsedSection,
        all_entities: List[ExtractedEntity],
    ) -> Dict[str, Any]:
        """Convert a section to encounter data."""
        encounter_type = {
            SectionType.ENCOUNTER_COMBAT: "combat",
            SectionType.ENCOUNTER_SOCIAL: "social",
            SectionType.ENCOUNTER_EXPLORATION: "exploration",
            SectionType.MAP_KEY: "exploration",
        }.get(section.section_type, "exploration")

        encounter = {
            "id": f"encounter-{uuid.uuid4().hex[:8]}",
            "name": section.title,
            "type": encounter_type,
            "description": section.content[:500],
            "entities": section.entities,
        }

        # Extract skill checks
        skill_checks = [e for e in section.entities if e.entity_type == EntityType.SKILL_CHECK]
        if skill_checks:
            encounter["skill_checks"] = [e.data for e in skill_checks]

        # Extract enemies for combat
        if encounter_type == "combat":
            stat_blocks = [e for e in section.entities if e.entity_type == EntityType.STAT_BLOCK]
            encounter["enemies"] = [e.data for e in stat_blocks]

        return encounter

    def _section_to_npc(self, section: ParsedSection) -> Dict[str, Any]:
        """Convert a section to NPC data."""
        return {
            "id": f"npc-{uuid.uuid4().hex[:8]}",
            "name": section.title,
            "description": section.content[:500],
        }

    def _generate_acts(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate act structure from chapters."""
        if not chapters:
            return []

        # Simple 3-act structure based on chapter count
        num_chapters = len(chapters)

        if num_chapters <= 3:
            # All chapters in one act
            return [{
                "id": "act-1",
                "name": "Act 1: The Adventure",
                "theme": "exploration",
                "description": "The main adventure",
                "emotional_arc": "introduction -> rising action -> conclusion",
                "chapters": [c["id"] for c in chapters],
            }]

        # Split into 3 acts
        act1_end = num_chapters // 3
        act2_end = 2 * num_chapters // 3

        return [
            {
                "id": "act-1",
                "name": "Act 1: The Setup",
                "theme": "mystery",
                "description": "Introduction and initial conflict",
                "emotional_arc": "curiosity -> engagement",
                "chapters": [c["id"] for c in chapters[:act1_end]],
            },
            {
                "id": "act-2",
                "name": "Act 2: The Rising Action",
                "theme": "revelation",
                "description": "Complications and escalation",
                "emotional_arc": "tension -> determination",
                "chapters": [c["id"] for c in chapters[act1_end:act2_end]],
            },
            {
                "id": "act-3",
                "name": "Act 3: The Climax",
                "theme": "confrontation",
                "description": "Final confrontation and resolution",
                "emotional_arc": "desperation -> triumph",
                "chapters": [c["id"] for c in chapters[act2_end:]],
            },
        ]

    def _create_encounter(
        self,
        enc_data: Dict[str, Any],
        index: int,
        total: int,
    ) -> Encounter:
        """Create Encounter model from data."""
        enc_type = EncounterType(enc_data.get("type", "exploration"))
        enc_id = enc_data.get("id", f"encounter-{index + 1}")

        # Create story content
        story = StoryContent(
            intro_text=enc_data.get("description", ""),
        )

        # Create type-specific content
        combat = None
        choices = None

        if enc_type == EncounterType.COMBAT:
            enemies = []
            for enemy_data in enc_data.get("enemies", []):
                enemies.append(EnemySpawn(
                    template=enemy_data.get("name", "goblin").lower().replace(" ", "_"),
                    count=1,
                ))

            if enemies:
                combat = CombatSetup(
                    enemies=enemies,
                    environment=GridEnvironment(),
                )

        elif enc_type in [EncounterType.SOCIAL, EncounterType.EXPLORATION, EncounterType.CHOICE]:
            # Create choices from skill checks
            skill_checks = enc_data.get("skill_checks", [])
            choice_list = []

            for i, sc_data in enumerate(skill_checks[:4]):  # Max 4 choices
                choice = Choice(
                    id=f"choice-{i + 1}",
                    text=f"Attempt {sc_data.get('skill', 'check')} check",
                    skill_check=SkillCheck(
                        skill=sc_data.get("skill", "perception"),
                        dc=sc_data.get("dc", 15),
                        check_type=CheckType.INDIVIDUAL,
                    ),
                    success_text="You succeed!",
                    failure_text="You fail.",
                )
                choice_list.append(choice)

            if choice_list:
                choices = ChoiceSetup(choices=choice_list)
                enc_type = EncounterType.CHOICE

        return Encounter(
            id=enc_id,
            type=enc_type,
            name=enc_data.get("name", f"Encounter {index + 1}"),
            story=story,
            combat=combat,
            choices=choices,
            rewards=Rewards(),
            transitions=EncounterTransitions(),
        )

    def _link_encounters(self, encounters: Dict[str, Encounter], chapters: List[Chapter]):
        """Link encounters with transitions."""
        # Build ordered list of encounter IDs
        encounter_order = []
        for chapter in chapters:
            encounter_order.extend(chapter.encounters)

        # Link each encounter to the next
        for i, enc_id in enumerate(encounter_order):
            if enc_id in encounters:
                if i + 1 < len(encounter_order):
                    next_id = encounter_order[i + 1]
                    encounters[enc_id].transitions.on_victory = next_id
                else:
                    # Last encounter - campaign end
                    encounters[enc_id].transitions.on_victory = None

    # =========================================================================
    # AI ENHANCEMENT
    # =========================================================================

    async def _enhance_campaign_moderate(self, campaign: Campaign) -> Campaign:
        """Apply moderate AI enhancement - fill gaps."""
        if not self._client:
            return campaign

        # Enhance encounter descriptions that are too short
        for enc_id, encounter in campaign.encounters.items():
            if len(encounter.story.intro_text or "") < 100:
                enhanced_text = await self._generate_encounter_description(encounter)
                if enhanced_text:
                    encounter.story.intro_text = enhanced_text

        return campaign

    async def _enhance_campaign_full(self, campaign: Campaign) -> Campaign:
        """Apply full AI enhancement for BG3 quality."""
        if not self._client:
            return campaign

        # Generate rich descriptions for all encounters
        for enc_id, encounter in campaign.encounters.items():
            enhanced_text = await self._generate_encounter_description(encounter, detailed=True)
            if enhanced_text:
                encounter.story.intro_text = enhanced_text

            # Add outcomes
            if encounter.type == EncounterType.COMBAT:
                encounter.story.outcome_victory = await self._generate_victory_text(encounter)
                encounter.story.outcome_defeat = await self._generate_defeat_text(encounter)

        # Generate campaign description if missing
        if len(campaign.description) < 100:
            campaign.description = await self._generate_campaign_description(campaign)

        return campaign

    async def _generate_encounter_description(
        self,
        encounter: Encounter,
        detailed: bool = False,
    ) -> Optional[str]:
        """Generate encounter description with AI."""
        if not self._client:
            return None

        prompt = f"""Generate a {"detailed, immersive" if detailed else "brief"} D&D encounter description.

Encounter: {encounter.name}
Type: {encounter.type.value}
Current description: {encounter.story.intro_text[:200] if encounter.story.intro_text else "None"}

Requirements:
- Write in second person ("You see...", "As you enter...")
- Be atmospheric and engaging
- {"Include sensory details (sights, sounds, smells)" if detailed else "Keep it concise (2-3 sentences)"}
- Set the scene for the players

Output ONLY the description text, no formatting or labels."""

        try:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self._model,
                    max_tokens=500 if detailed else 200,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            return message.content[0].text.strip()

        except Exception as e:
            logger.error(f"AI enhancement failed: {e}")
            return None

    async def _generate_victory_text(self, encounter: Encounter) -> Optional[str]:
        """Generate victory outcome text."""
        if not self._client:
            return None

        prompt = f"""Generate a brief victory description for this D&D combat encounter:

Encounter: {encounter.name}

Write 1-2 sentences describing the aftermath of victory. Be triumphant but brief.
Output ONLY the description text."""

        try:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self._model,
                    max_tokens=100,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            return message.content[0].text.strip()

        except Exception as e:
            logger.error(f"AI enhancement failed: {e}")
            return None

    async def _generate_defeat_text(self, encounter: Encounter) -> Optional[str]:
        """Generate defeat outcome text."""
        if not self._client:
            return "The party has fallen..."

        return "The party has fallen. The adventure ends here... unless you wish to try again."

    async def _generate_campaign_description(self, campaign: Campaign) -> str:
        """Generate campaign description with AI."""
        if not self._client:
            return campaign.description or "An exciting D&D adventure awaits."

        chapter_names = [c.title for c in campaign.chapters[:5]]

        prompt = f"""Generate a compelling campaign description for this D&D adventure:

Campaign: {campaign.name}
Chapters: {', '.join(chapter_names)}

Write 2-3 sentences that hook players and hint at the adventure ahead.
Output ONLY the description text."""

        try:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self._model,
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            return message.content[0].text.strip()

        except Exception as e:
            logger.error(f"AI enhancement failed: {e}")
            return campaign.description or "An exciting D&D adventure awaits."


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_campaign_parser() -> CampaignParserService:
    """Get the campaign parser service instance."""
    return CampaignParserService.get_instance()


async def quick_parse_text(
    content: str,
    enhancement: str = "moderate",
) -> Campaign:
    """Quick helper to parse text content into a campaign."""
    parser = get_campaign_parser()
    level = EnhancementLevel(enhancement)
    return await parser.parse_and_convert(content, is_pdf=False, enhancement_level=level)


async def quick_parse_pdf(
    file_path: str,
    enhancement: str = "moderate",
) -> Campaign:
    """Quick helper to parse PDF into a campaign."""
    parser = get_campaign_parser()
    level = EnhancementLevel(enhancement)
    return await parser.parse_and_convert(file_path, is_pdf=True, file_path=file_path, enhancement_level=level)
