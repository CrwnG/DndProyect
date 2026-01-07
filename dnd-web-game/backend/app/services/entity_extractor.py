"""
Entity Extractor for D&D Campaign Documents.

Extracts game entities from text using regex patterns and AI:
- Stat blocks (monsters, NPCs)
- Skill checks and DCs
- Items and treasure
- Locations and areas
- NPC names and dialogue

Used by CampaignParserService to convert documents into playable campaigns.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """Types of extractable entities."""
    STAT_BLOCK = "stat_block"
    SKILL_CHECK = "skill_check"
    ITEM = "item"
    LOCATION = "location"
    NPC = "npc"
    ENCOUNTER = "encounter"
    TRAP = "trap"
    TREASURE = "treasure"


@dataclass
class ExtractedEntity:
    """A single extracted entity from text."""
    entity_type: EntityType
    name: str
    raw_text: str
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0  # 0.0 to 1.0
    source_line: int = 0


@dataclass
class StatBlock:
    """Extracted monster/NPC stat block."""
    name: str
    size: str = "Medium"
    creature_type: str = "humanoid"
    alignment: str = "neutral"
    armor_class: int = 10
    hit_points: int = 10
    hit_dice: str = "2d8"
    speed: str = "30 ft."

    # Ability scores
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    # Combat
    challenge_rating: str = "0"
    actions: List[Dict[str, str]] = field(default_factory=list)
    traits: List[Dict[str, str]] = field(default_factory=list)

    # Optional
    skills: Dict[str, int] = field(default_factory=dict)
    senses: str = ""
    languages: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size,
            "creature_type": self.creature_type,
            "alignment": self.alignment,
            "armor_class": self.armor_class,
            "hit_points": self.hit_points,
            "hit_dice": self.hit_dice,
            "speed": self.speed,
            "abilities": {
                "strength": self.strength,
                "dexterity": self.dexterity,
                "constitution": self.constitution,
                "intelligence": self.intelligence,
                "wisdom": self.wisdom,
                "charisma": self.charisma,
            },
            "challenge_rating": self.challenge_rating,
            "actions": self.actions,
            "traits": self.traits,
            "skills": self.skills,
            "senses": self.senses,
            "languages": self.languages,
        }


@dataclass
class SkillCheckInfo:
    """Extracted skill check information."""
    skill: str
    dc: int
    context: str = ""
    success_outcome: str = ""
    failure_outcome: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill,
            "dc": self.dc,
            "context": self.context,
            "success_outcome": self.success_outcome,
            "failure_outcome": self.failure_outcome,
        }


@dataclass
class ItemInfo:
    """Extracted item information."""
    name: str
    item_type: str = "misc"  # weapon, armor, potion, misc, magic
    description: str = ""
    value: str = ""
    properties: List[str] = field(default_factory=list)
    magic: bool = False
    rarity: str = "common"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "item_type": self.item_type,
            "description": self.description,
            "value": self.value,
            "properties": self.properties,
            "magic": self.magic,
            "rarity": self.rarity,
        }


class EntityExtractor:
    """
    Extracts D&D game entities from text using regex patterns.

    Usage:
        extractor = EntityExtractor()
        entities = extractor.extract_all(document_text)
        stat_blocks = extractor.extract_stat_blocks(document_text)
        skill_checks = extractor.extract_skill_checks(document_text)
    """

    # ==========================================================================
    # REGEX PATTERNS
    # ==========================================================================

    # Stat block patterns
    STAT_BLOCK_HEADER = re.compile(
        r'^([A-Z][A-Za-z\s\-\']+)\s*\n'  # Name
        r'(Tiny|Small|Medium|Large|Huge|Gargantuan)\s+'  # Size
        r'(aberration|beast|celestial|construct|dragon|elemental|fey|fiend|'
        r'giant|humanoid|monstrosity|ooze|plant|undead)[,\s]+'  # Type
        r'(lawful good|lawful neutral|lawful evil|neutral good|neutral|'
        r'neutral evil|chaotic good|chaotic neutral|chaotic evil|unaligned)',  # Alignment
        re.MULTILINE | re.IGNORECASE
    )

    AC_PATTERN = re.compile(
        r'Armor Class[:\s]+(\d+)(?:\s*\(([^)]+)\))?',
        re.IGNORECASE
    )

    HP_PATTERN = re.compile(
        r'Hit Points[:\s]+(\d+)(?:\s*\(([^)]+)\))?',
        re.IGNORECASE
    )

    SPEED_PATTERN = re.compile(
        r'Speed[:\s]+(.+?)(?:\n|$)',
        re.IGNORECASE
    )

    ABILITY_SCORES_PATTERN = re.compile(
        r'STR\s+DEX\s+CON\s+INT\s+WIS\s+CHA\s*\n'
        r'\s*(\d+)\s*(?:\([+-]?\d+\))?\s*'
        r'(\d+)\s*(?:\([+-]?\d+\))?\s*'
        r'(\d+)\s*(?:\([+-]?\d+\))?\s*'
        r'(\d+)\s*(?:\([+-]?\d+\))?\s*'
        r'(\d+)\s*(?:\([+-]?\d+\))?\s*'
        r'(\d+)\s*(?:\([+-]?\d+\))?',
        re.IGNORECASE | re.MULTILINE
    )

    CR_PATTERN = re.compile(
        r'Challenge[:\s]+(\d+(?:/\d+)?)\s*\([\d,]+\s*XP\)',
        re.IGNORECASE
    )

    # Skill check patterns
    DC_PATTERN = re.compile(
        r'DC\s*(\d+)\s+'
        r'(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma|'
        r'Acrobatics|Animal Handling|Arcana|Athletics|Deception|History|'
        r'Insight|Intimidation|Investigation|Medicine|Nature|Perception|'
        r'Performance|Persuasion|Religion|Sleight of Hand|Stealth|Survival)',
        re.IGNORECASE
    )

    # Alternative DC pattern: "succeed on a DC 15 Dexterity saving throw"
    DC_SAVING_THROW_PATTERN = re.compile(
        r'(?:succeed on a |make a |attempt a )?'
        r'DC\s*(\d+)\s+'
        r'(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+'
        r'(?:saving throw|save|check)',
        re.IGNORECASE
    )

    # Item patterns
    MAGIC_ITEM_PATTERN = re.compile(
        r'^([A-Z][A-Za-z\s\-\']+)\s*\n'
        r'(?:Wondrous item|Weapon|Armor|Ring|Rod|Staff|Wand|Potion|Scroll),?\s*'
        r'(common|uncommon|rare|very rare|legendary|artifact)?',
        re.MULTILINE | re.IGNORECASE
    )

    TREASURE_PATTERN = re.compile(
        r'(\d+)\s*(cp|sp|ep|gp|pp)',
        re.IGNORECASE
    )

    # Location patterns
    AREA_PATTERN = re.compile(
        r'^(?:Area\s+)?([A-Z]\d*|[0-9]+)[.:\s]+([A-Z][^.\n]+)',
        re.MULTILINE
    )

    ROOM_PATTERN = re.compile(
        r'^(?:Room|Chamber|Hall|Corridor)\s+(\d+|[A-Z]\d*)[.:\s]*([^\n]+)',
        re.MULTILINE | re.IGNORECASE
    )

    # NPC patterns
    NPC_DIALOGUE_PATTERN = re.compile(
        r'"([^"]+)"\s*(?:says?|replies?|asks?|exclaims?|whispers?)\s+(\w+)',
        re.IGNORECASE
    )

    NPC_NAME_PATTERN = re.compile(
        r'(?:a |an |the )?'
        r'(?:male |female )?'
        r'(?:human|elf|dwarf|halfling|gnome|half-elf|half-orc|tiefling|dragonborn)?\s*'
        r'((?:[A-Z][a-z]+\s+)?[A-Z][a-z]+)'
        r'(?:,?\s+(?:the|a|an)\s+\w+)?',
        re.IGNORECASE
    )

    # Encounter patterns
    ENCOUNTER_PATTERN = re.compile(
        r'(?:encounter|combat|battle|fight)[:\s]+'
        r'(\d+)\s+([A-Za-z\s]+)',
        re.IGNORECASE
    )

    # ==========================================================================
    # MAIN EXTRACTION METHODS
    # ==========================================================================

    def extract_all(self, text: str) -> List[ExtractedEntity]:
        """
        Extract all entity types from text.

        Args:
            text: Document text to extract from

        Returns:
            List of all extracted entities
        """
        entities = []

        # Extract each type
        entities.extend(self._wrap_stat_blocks(self.extract_stat_blocks(text)))
        entities.extend(self._wrap_skill_checks(self.extract_skill_checks(text)))
        entities.extend(self._wrap_items(self.extract_items(text)))
        entities.extend(self._wrap_locations(self.extract_locations(text)))
        entities.extend(self._wrap_npcs(self.extract_npc_references(text)))

        logger.info(f"Extracted {len(entities)} total entities from text")
        return entities

    def extract_stat_blocks(self, text: str) -> List[StatBlock]:
        """
        Extract monster/NPC stat blocks from text.

        Args:
            text: Document text

        Returns:
            List of StatBlock objects
        """
        stat_blocks = []

        # Split by potential stat block headers
        sections = self._split_into_sections(text)

        for section in sections:
            stat_block = self._parse_stat_block_section(section)
            if stat_block:
                stat_blocks.append(stat_block)

        logger.debug(f"Extracted {len(stat_blocks)} stat blocks")
        return stat_blocks

    def extract_skill_checks(self, text: str) -> List[SkillCheckInfo]:
        """
        Extract skill check requirements from text.

        Args:
            text: Document text

        Returns:
            List of SkillCheckInfo objects
        """
        skill_checks = []

        # Find all DC patterns
        for match in self.DC_PATTERN.finditer(text):
            dc = int(match.group(1))
            skill = match.group(2)

            # Get surrounding context
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end].strip()

            skill_checks.append(SkillCheckInfo(
                skill=skill.title(),
                dc=dc,
                context=context,
            ))

        # Find saving throw patterns
        for match in self.DC_SAVING_THROW_PATTERN.finditer(text):
            dc = int(match.group(1))
            ability = match.group(2)

            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end].strip()

            skill_checks.append(SkillCheckInfo(
                skill=f"{ability.title()} Save",
                dc=dc,
                context=context,
            ))

        logger.debug(f"Extracted {len(skill_checks)} skill checks")
        return skill_checks

    def extract_items(self, text: str) -> List[ItemInfo]:
        """
        Extract item descriptions from text.

        Args:
            text: Document text

        Returns:
            List of ItemInfo objects
        """
        items = []

        # Find magic items
        for match in self.MAGIC_ITEM_PATTERN.finditer(text):
            name = match.group(1).strip()
            rarity = match.group(2) or "common"

            # Get description (next paragraph)
            end_pos = match.end()
            desc_end = text.find('\n\n', end_pos)
            if desc_end == -1:
                desc_end = min(end_pos + 500, len(text))
            description = text[end_pos:desc_end].strip()

            items.append(ItemInfo(
                name=name,
                item_type="magic",
                description=description,
                magic=True,
                rarity=rarity.lower(),
            ))

        # Find treasure
        for match in self.TREASURE_PATTERN.finditer(text):
            amount = int(match.group(1))
            currency = match.group(2).lower()

            items.append(ItemInfo(
                name=f"{amount} {currency}",
                item_type="treasure",
                value=f"{amount} {currency}",
            ))

        logger.debug(f"Extracted {len(items)} items")
        return items

    def extract_locations(self, text: str) -> List[Dict[str, str]]:
        """
        Extract location/area descriptions from text.

        Args:
            text: Document text

        Returns:
            List of location dictionaries
        """
        locations = []

        # Find area references
        for match in self.AREA_PATTERN.finditer(text):
            area_id = match.group(1)
            name = match.group(2).strip()

            # Get description
            start = match.end()
            end = text.find('\n\n', start)
            if end == -1:
                end = min(start + 500, len(text))
            description = text[start:end].strip()

            locations.append({
                "id": area_id,
                "name": name,
                "description": description,
            })

        # Find room references
        for match in self.ROOM_PATTERN.finditer(text):
            room_id = match.group(1)
            name = match.group(2).strip()

            locations.append({
                "id": f"Room {room_id}",
                "name": name,
                "description": "",
            })

        logger.debug(f"Extracted {len(locations)} locations")
        return locations

    def extract_npc_references(self, text: str) -> List[Dict[str, str]]:
        """
        Extract NPC names and dialogue from text.

        Args:
            text: Document text

        Returns:
            List of NPC info dictionaries
        """
        npcs = {}  # Use dict to deduplicate by name

        # Find dialogue
        for match in self.NPC_DIALOGUE_PATTERN.finditer(text):
            dialogue = match.group(1)
            name = match.group(2)

            if name not in npcs:
                npcs[name] = {
                    "name": name,
                    "dialogue": [],
                    "mentions": 0,
                }

            npcs[name]["dialogue"].append(dialogue)
            npcs[name]["mentions"] += 1

        logger.debug(f"Extracted {len(npcs)} NPCs")
        return list(npcs.values())

    def extract_encounters(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract encounter definitions from text.

        Args:
            text: Document text

        Returns:
            List of encounter dictionaries
        """
        encounters = []

        # Find explicit encounter mentions
        for match in self.ENCOUNTER_PATTERN.finditer(text):
            count = int(match.group(1))
            enemy_type = match.group(2).strip()

            encounters.append({
                "enemies": [{
                    "type": enemy_type,
                    "count": count,
                }],
            })

        logger.debug(f"Extracted {len(encounters)} encounters")
        return encounters

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _split_into_sections(self, text: str) -> List[str]:
        """Split text into potential stat block sections."""
        # Split on double newlines or headers
        sections = re.split(r'\n{3,}', text)
        return [s.strip() for s in sections if s.strip()]

    def _parse_stat_block_section(self, section: str) -> Optional[StatBlock]:
        """Parse a section of text into a stat block if possible."""
        # Check for stat block header
        header_match = self.STAT_BLOCK_HEADER.search(section)
        if not header_match:
            # Try simpler detection
            if not self.AC_PATTERN.search(section):
                return None

        # Initialize with defaults
        stat_block = StatBlock(
            name=header_match.group(1).strip() if header_match else "Unknown"
        )

        if header_match:
            stat_block.size = header_match.group(2).title()
            stat_block.creature_type = header_match.group(3).lower()
            stat_block.alignment = header_match.group(4).lower()

        # Extract AC
        ac_match = self.AC_PATTERN.search(section)
        if ac_match:
            stat_block.armor_class = int(ac_match.group(1))

        # Extract HP
        hp_match = self.HP_PATTERN.search(section)
        if hp_match:
            stat_block.hit_points = int(hp_match.group(1))
            if hp_match.group(2):
                stat_block.hit_dice = hp_match.group(2)

        # Extract Speed
        speed_match = self.SPEED_PATTERN.search(section)
        if speed_match:
            stat_block.speed = speed_match.group(1).strip()

        # Extract Ability Scores
        abilities_match = self.ABILITY_SCORES_PATTERN.search(section)
        if abilities_match:
            stat_block.strength = int(abilities_match.group(1))
            stat_block.dexterity = int(abilities_match.group(2))
            stat_block.constitution = int(abilities_match.group(3))
            stat_block.intelligence = int(abilities_match.group(4))
            stat_block.wisdom = int(abilities_match.group(5))
            stat_block.charisma = int(abilities_match.group(6))

        # Extract CR
        cr_match = self.CR_PATTERN.search(section)
        if cr_match:
            stat_block.challenge_rating = cr_match.group(1)

        # Extract Actions (simplified)
        stat_block.actions = self._extract_actions(section)

        return stat_block

    def _extract_actions(self, section: str) -> List[Dict[str, str]]:
        """Extract action descriptions from a stat block section."""
        actions = []

        # Look for action headers
        action_pattern = re.compile(
            r'^([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)\.\s*(.+?)(?=\n[A-Z]|\n\n|$)',
            re.MULTILINE | re.DOTALL
        )

        # Find the Actions section
        actions_start = section.lower().find('actions')
        if actions_start != -1:
            action_section = section[actions_start:]

            for match in action_pattern.finditer(action_section):
                name = match.group(1)
                description = match.group(2).strip()

                # Skip section headers
                if name.lower() in ['actions', 'reactions', 'legendary actions', 'lair actions']:
                    continue

                actions.append({
                    "name": name,
                    "description": description,
                })

        return actions

    def _wrap_stat_blocks(self, stat_blocks: List[StatBlock]) -> List[ExtractedEntity]:
        """Wrap StatBlock objects as ExtractedEntity."""
        return [
            ExtractedEntity(
                entity_type=EntityType.STAT_BLOCK,
                name=sb.name,
                raw_text="",
                data=sb.to_dict(),
            )
            for sb in stat_blocks
        ]

    def _wrap_skill_checks(self, skill_checks: List[SkillCheckInfo]) -> List[ExtractedEntity]:
        """Wrap SkillCheckInfo objects as ExtractedEntity."""
        return [
            ExtractedEntity(
                entity_type=EntityType.SKILL_CHECK,
                name=f"DC {sc.dc} {sc.skill}",
                raw_text=sc.context,
                data=sc.to_dict(),
            )
            for sc in skill_checks
        ]

    def _wrap_items(self, items: List[ItemInfo]) -> List[ExtractedEntity]:
        """Wrap ItemInfo objects as ExtractedEntity."""
        return [
            ExtractedEntity(
                entity_type=EntityType.ITEM,
                name=item.name,
                raw_text=item.description,
                data=item.to_dict(),
            )
            for item in items
        ]

    def _wrap_locations(self, locations: List[Dict]) -> List[ExtractedEntity]:
        """Wrap location dicts as ExtractedEntity."""
        return [
            ExtractedEntity(
                entity_type=EntityType.LOCATION,
                name=loc.get("name", "Unknown"),
                raw_text=loc.get("description", ""),
                data=loc,
            )
            for loc in locations
        ]

    def _wrap_npcs(self, npcs: List[Dict]) -> List[ExtractedEntity]:
        """Wrap NPC dicts as ExtractedEntity."""
        return [
            ExtractedEntity(
                entity_type=EntityType.NPC,
                name=npc.get("name", "Unknown"),
                raw_text="",
                data=npc,
            )
            for npc in npcs
        ]
