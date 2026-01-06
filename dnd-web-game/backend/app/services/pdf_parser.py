"""
D&D Beyond PDF Character Sheet Parser

Parses D&D Beyond character sheet PDFs to extract character data.
Uses pdfplumber for text extraction and regex patterns for data parsing.
"""

import pdfplumber
import re
from typing import Dict, Any, List, Optional
from pathlib import Path


class DnDBeyondPDFParser:
    """Parse D&D Beyond character sheet PDFs."""

    def parse(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parse a D&D Beyond PDF character sheet.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary containing parsed character data
        """
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from all pages
            all_text = ""
            page_texts = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                page_texts.append(text)
                all_text += text + "\n"

        # Parse character data
        character = {
            "name": self._extract_name(all_text),
            "class": self._extract_class(all_text),
            "level": self._extract_level(all_text),
            "species": self._extract_species(all_text),
            "background": self._extract_background(all_text),
            "hp": self._extract_hp(all_text),
            "max_hp": self._extract_max_hp(all_text),
            "ac": self._extract_ac(all_text),
            "speed": self._extract_speed(all_text),
            "proficiency_bonus": self._extract_proficiency_bonus(all_text),
            "initiative": self._extract_initiative(all_text),
            "abilities": self._extract_abilities(all_text),
            "saving_throws": self._extract_saving_throws(all_text),
            "skills": self._extract_skills(all_text),
            "weapons": self._extract_weapons(all_text),
            "spellcasting": self._extract_spellcasting(all_text),
            "features": self._extract_features(all_text),
            "equipment": self._extract_equipment(all_text),
            "senses": self._extract_senses(all_text),
        }

        return character

    def _extract_name(self, text: str) -> str:
        """Extract character name."""
        # D&D Beyond format usually has name at the top
        # Look for pattern like "Character Name" before class info
        lines = text.split('\n')
        for i, line in enumerate(lines[:10]):  # Check first 10 lines
            # Skip common header words
            if line.strip() and not any(kw in line.upper() for kw in
                ['LEVEL', 'CLASS', 'BACKGROUND', 'SPECIES', 'RACE', 'HIT POINTS', 'ARMOR']):
                # Check if next line has class info (indicates this is the name)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].upper()
                    if any(c in next_line for c in ['FIGHTER', 'PALADIN', 'WIZARD', 'CLERIC',
                        'ROGUE', 'RANGER', 'BARBARIAN', 'BARD', 'DRUID', 'MONK', 'SORCERER', 'WARLOCK']):
                        return line.strip()
                # Could be standalone name line
                if len(line.strip()) > 2 and len(line.strip()) < 50:
                    return line.strip()
        return "Unknown Character"

    def _extract_class(self, text: str) -> str:
        """Extract character class."""
        classes = ['Fighter', 'Paladin', 'Wizard', 'Cleric', 'Rogue', 'Ranger',
                   'Barbarian', 'Bard', 'Druid', 'Monk', 'Sorcerer', 'Warlock']

        for cls in classes:
            # Look for class name followed by level
            pattern = rf'\b({cls})\s*(\d+)?'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return cls
        return "Unknown"

    def _extract_level(self, text: str) -> int:
        """Extract character level."""
        # Pattern: "Level X" or "Lv X" or class name followed by number
        patterns = [
            r'Level\s+(\d+)',
            r'Lv\.?\s*(\d+)',
            r'(?:Fighter|Paladin|Wizard|Cleric|Rogue|Ranger|Barbarian|Bard|Druid|Monk|Sorcerer|Warlock)\s+(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 1

    def _extract_species(self, text: str) -> str:
        """Extract character species/race."""
        species_list = ['Human', 'Elf', 'Dwarf', 'Halfling', 'Gnome', 'Half-Elf',
                       'Half-Orc', 'Tiefling', 'Dragonborn', 'Goliath', 'Aasimar',
                       'Genasi', 'Tabaxi', 'Kenku', 'Firbolg', 'Triton']

        for species in species_list:
            if re.search(rf'\b{species}\b', text, re.IGNORECASE):
                return species
        return "Unknown"

    def _extract_background(self, text: str) -> str:
        """Extract character background."""
        backgrounds = ['Soldier', 'Noble', 'Acolyte', 'Criminal', 'Folk Hero',
                      'Sage', 'Hermit', 'Outlander', 'Guild Artisan', 'Entertainer',
                      'Charlatan', 'Sailor', 'Urchin']

        # Look for "Background: X" or just the background name
        pattern = r'Background[:\s]+(\w+(?:\s+\w+)?)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        for bg in backgrounds:
            if re.search(rf'\b{bg}\b', text, re.IGNORECASE):
                return bg
        return "Unknown"

    def _extract_hp(self, text: str) -> int:
        """Extract current hit points."""
        # Look for "Current HP: X" or "HP: X/Y" patterns
        patterns = [
            r'(?:Current\s+)?(?:Hit\s+Points?|HP)[:\s]+(\d+)',
            r'(\d+)\s*/\s*\d+\s*(?:HP|Hit\s*Points)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Fallback: use max HP
        return self._extract_max_hp(text)

    def _extract_max_hp(self, text: str) -> int:
        """Extract maximum hit points."""
        patterns = [
            r'(?:Max(?:imum)?\s+)?(?:Hit\s+Points?|HP)[:\s]+\d+\s*/\s*(\d+)',
            r'(?:Hit\s+Points?|HP)\s+Maximum[:\s]+(\d+)',
            r'(?:Hit\s+Points?|HP)[:\s]+(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 10

    def _extract_ac(self, text: str) -> int:
        """Extract armor class."""
        patterns = [
            r'(?:Armor\s+Class|AC)[:\s]+(\d+)',
            r'AC\s*[:=]?\s*(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 10

    def _extract_speed(self, text: str) -> int:
        """Extract movement speed in feet."""
        patterns = [
            r'Speed[:\s]+(\d+)\s*(?:ft|feet)',
            r'Walking[:\s]+(\d+)\s*(?:ft|feet)',
            r'(\d+)\s*(?:ft|feet)\s*(?:speed|walking)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 30

    def _extract_proficiency_bonus(self, text: str) -> int:
        """Extract proficiency bonus."""
        patterns = [
            r'Proficiency\s+Bonus[:\s]+\+?(\d+)',
            r'\+(\d+)\s+Proficiency',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Calculate from level if not found
        level = self._extract_level(text)
        return (level - 1) // 4 + 2

    def _extract_initiative(self, text: str) -> int:
        """Extract initiative modifier."""
        patterns = [
            r'Initiative[:\s]+([+-]?\d+)',
            r'([+-]\d+)\s+Initiative',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Default to DEX modifier
        abilities = self._extract_abilities(text)
        return abilities.get('dex', {}).get('mod', 0)

    def _extract_abilities(self, text: str) -> Dict[str, Dict[str, int]]:
        """Extract ability scores and modifiers."""
        abilities = {}
        ability_names = {
            'STRENGTH': 'str',
            'DEXTERITY': 'dex',
            'CONSTITUTION': 'con',
            'INTELLIGENCE': 'int',
            'WISDOM': 'wis',
            'CHARISMA': 'cha',
            'STR': 'str',
            'DEX': 'dex',
            'CON': 'con',
            'INT': 'int',
            'WIS': 'wis',
            'CHA': 'cha',
        }

        # Pattern: STRENGTH 13 +1 or STR: 13 (+1)
        for full_name, short_name in ability_names.items():
            if short_name in abilities:
                continue

            patterns = [
                rf'{full_name}\s+(\d+)\s+([+-]\d+)',
                rf'{full_name}[:\s]+(\d+)\s*\(([+-]\d+)\)',
                rf'{full_name}\s+(\d+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    score = int(match.group(1))
                    if len(match.groups()) > 1:
                        mod = int(match.group(2))
                    else:
                        mod = (score - 10) // 2
                    abilities[short_name] = {'score': score, 'mod': mod}
                    break

        # Fill in defaults for missing abilities
        for short_name in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
            if short_name not in abilities:
                abilities[short_name] = {'score': 10, 'mod': 0}

        return abilities

    def _extract_saving_throws(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Extract saving throw modifiers and proficiencies."""
        saves = {}
        abilities = self._extract_abilities(text)

        save_names = ['str', 'dex', 'con', 'int', 'wis', 'cha']
        full_names = {
            'str': 'Strength', 'dex': 'Dexterity', 'con': 'Constitution',
            'int': 'Intelligence', 'wis': 'Wisdom', 'cha': 'Charisma'
        }

        for short_name in save_names:
            full_name = full_names[short_name]

            # Look for saving throw entry
            pattern = rf'{full_name}\s+Save[:\s]+([+-]?\d+)'
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                mod = int(match.group(1))
                base_mod = abilities[short_name]['mod']
                proficient = mod > base_mod  # If modifier is higher, likely proficient
                saves[short_name] = {'mod': mod, 'proficient': proficient}
            else:
                saves[short_name] = {
                    'mod': abilities[short_name]['mod'],
                    'proficient': False
                }

        return saves

    def _extract_skills(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Extract skill modifiers and proficiencies."""
        skills = {}

        skill_list = [
            'Acrobatics', 'Animal Handling', 'Arcana', 'Athletics', 'Deception',
            'History', 'Insight', 'Intimidation', 'Investigation', 'Medicine',
            'Nature', 'Perception', 'Performance', 'Persuasion', 'Religion',
            'Sleight of Hand', 'Stealth', 'Survival'
        ]

        for skill in skill_list:
            pattern = rf'{skill}[:\s]+([+-]?\d+)'
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                mod = int(match.group(1))
                skills[skill.lower().replace(' ', '_')] = {
                    'mod': mod,
                    'proficient': True  # If listed, likely proficient
                }

        return skills

    def _extract_weapons(self, text: str) -> List[Dict[str, Any]]:
        """Extract weapon attacks."""
        weapons = []

        # Look for weapon attack patterns
        # Format: "Weapon Name +X 1dY+Z damage_type properties"
        weapon_section = self._get_section(text, 'WEAPON ATTACKS', 'NOTES')
        if not weapon_section:
            weapon_section = self._get_section(text, 'ATTACKS', 'EQUIPMENT')
        if not weapon_section:
            weapon_section = text

        # Pattern for weapon entries
        patterns = [
            # "Greataxe +3 1d12+1 Slashing"
            r'(\w+(?:\s+\w+)?)\s+([+-]\d+)\s+([\dd]+(?:[+-]\d+)?)\s+(\w+)',
            # "Longsword: +5 to hit, 1d8+3 slashing"
            r'(\w+(?:\s+\w+)?)[:\s]+([+-]\d+)\s+(?:to\s+hit)?,?\s*([\dd]+(?:[+-]\d+)?)\s+(\w+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, weapon_section, re.IGNORECASE)
            for match in matches:
                name, attack_bonus, damage, damage_type = match

                # Skip if not a real weapon
                if name.lower() in ['strength', 'dexterity', 'attack', 'hit', 'damage']:
                    continue

                weapon_name = name.strip()
                weapons.append({
                    'id': weapon_name.lower().replace(' ', '_').replace("'", ""),  # Generate unique ID
                    'name': weapon_name,
                    'attack_bonus': int(attack_bonus),
                    'damage': damage,
                    'damage_type': damage_type.lower(),
                    'properties': self._get_weapon_properties(name, text),
                    'range': self._get_weapon_range(name, text),
                    'item_type': 'weapon',  # Mark as weapon for proper handling
                })

        # NOTE: Unarmed Strike is NOT added to weapons list - it's an innate ability
        # handled by CharacterEquipment.get_available_weapons() in combat

        return weapons

    def _get_weapon_properties(self, weapon_name: str, text: str) -> List[str]:
        """Get properties for a weapon."""
        properties = []
        weapon_lower = weapon_name.lower()

        # Check for common weapon properties
        property_map = {
            'greataxe': ['heavy', 'two-handed'],
            'greatsword': ['heavy', 'two-handed'],
            'longsword': ['versatile'],
            'shortsword': ['light', 'finesse'],
            'dagger': ['light', 'finesse', 'thrown'],
            'longbow': ['ammunition', 'two-handed', 'heavy'],
            'shortbow': ['ammunition', 'two-handed'],
            'handaxe': ['light', 'thrown'],
            'javelin': ['thrown'],
            'rapier': ['finesse'],
            'scimitar': ['light', 'finesse'],
            'warhammer': ['versatile'],
            'battleaxe': ['versatile'],
            'glaive': ['heavy', 'reach', 'two-handed'],
            'halberd': ['heavy', 'reach', 'two-handed'],
        }

        for weapon, props in property_map.items():
            if weapon in weapon_lower:
                return props

        return properties

    def _get_weapon_range(self, weapon_name: str, text: str) -> Optional[int]:
        """Get range for a weapon."""
        weapon_lower = weapon_name.lower()

        range_map = {
            'longbow': 150,
            'shortbow': 80,
            'light crossbow': 80,
            'heavy crossbow': 100,
            'hand crossbow': 30,
            'javelin': 30,
            'dagger': 5,  # Can be thrown 20ft
            'handaxe': 5,  # Can be thrown 20ft
        }

        for weapon, range_val in range_map.items():
            if weapon in weapon_lower:
                return range_val

        return 5  # Default melee range

    def _extract_spellcasting(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract spellcasting information if present."""
        # Check if character has spellcasting
        if not re.search(r'spell|cantrip|spellcasting', text, re.IGNORECASE):
            return None

        spellcasting = {
            'ability': self._extract_spellcasting_ability(text),
            'spell_save_dc': self._extract_spell_save_dc(text),
            'spell_attack_bonus': self._extract_spell_attack_bonus(text),
            'spell_slots': self._extract_spell_slots(text),
            'cantrips': self._extract_cantrips(text),
            'prepared_spells': self._extract_prepared_spells(text),
        }

        return spellcasting

    def _extract_spellcasting_ability(self, text: str) -> str:
        """Extract spellcasting ability."""
        # Look for "Spellcasting Ability: X" or infer from class
        pattern = r'Spellcasting\s+Ability[:\s]+(\w+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            ability = match.group(1).upper()[:3]
            return ability

        # Infer from class
        char_class = self._extract_class(text).lower()
        class_ability_map = {
            'wizard': 'INT',
            'cleric': 'WIS',
            'paladin': 'CHA',
            'sorcerer': 'CHA',
            'warlock': 'CHA',
            'bard': 'CHA',
            'druid': 'WIS',
            'ranger': 'WIS',
        }

        return class_ability_map.get(char_class, 'CHA')

    def _extract_spell_save_dc(self, text: str) -> int:
        """Extract spell save DC."""
        patterns = [
            r'Spell\s+Save\s+DC[:\s]+(\d+)',
            r'Save\s+DC[:\s]+(\d+)',
            r'DC\s+(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Calculate: 8 + proficiency + ability mod
        prof = self._extract_proficiency_bonus(text)
        abilities = self._extract_abilities(text)
        ability = self._extract_spellcasting_ability(text).lower()
        ability_mod = abilities.get(ability, {}).get('mod', 0)

        return 8 + prof + ability_mod

    def _extract_spell_attack_bonus(self, text: str) -> int:
        """Extract spell attack bonus."""
        patterns = [
            r'Spell\s+Attack[:\s]+([+-]?\d+)',
            r'Spell\s+Attack\s+Bonus[:\s]+([+-]?\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Calculate: proficiency + ability mod
        prof = self._extract_proficiency_bonus(text)
        abilities = self._extract_abilities(text)
        ability = self._extract_spellcasting_ability(text).lower()
        ability_mod = abilities.get(ability, {}).get('mod', 0)

        return prof + ability_mod

    def _extract_spell_slots(self, text: str) -> Dict[int, int]:
        """Extract spell slots by level."""
        slots = {}

        # Pattern: "1st level: X slots" or "Level 1: X"
        for level in range(1, 10):
            ordinal = {1: '1st', 2: '2nd', 3: '3rd'}.get(level, f'{level}th')
            patterns = [
                rf'{ordinal}\s+(?:level)?[:\s]+(\d+)\s*(?:slot|spell)',
                rf'Level\s+{level}[:\s]+(\d+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    slots[level] = int(match.group(1))
                    break

        return slots

    def _extract_cantrips(self, text: str) -> List[Dict[str, Any]]:
        """Extract cantrips."""
        cantrips = []

        # Common cantrips to look for
        cantrip_list = [
            'Sacred Flame', 'Fire Bolt', 'Eldritch Blast', 'Chill Touch',
            'Ray of Frost', 'Shocking Grasp', 'Light', 'Mage Hand',
            'Prestidigitation', 'Minor Illusion', 'Guidance', 'Thaumaturgy',
            'Spare the Dying', 'Toll the Dead', 'Word of Radiance', 'Blade Ward',
        ]

        for cantrip in cantrip_list:
            if re.search(rf'\b{cantrip}\b', text, re.IGNORECASE):
                cantrips.append({
                    'name': cantrip,
                    'level': 0,
                    'source': self._extract_class(text),
                })

        return cantrips

    def _extract_prepared_spells(self, text: str) -> List[Dict[str, Any]]:
        """Extract prepared spells."""
        spells = []

        # Common low-level spells to look for
        spell_list = [
            ('Cure Wounds', 1), ('Healing Word', 1), ('Shield of Faith', 1),
            ('Bless', 1), ('Command', 1), ('Divine Favor', 1), ('Shield', 1),
            ('Magic Missile', 1), ('Burning Hands', 1), ('Thunderwave', 1),
            ('Hex', 1), ('Hunter\'s Mark', 1), ('Smite', 1), ('Divine Smite', 0),
            ('Lay on Hands', 0),
        ]

        for spell, level in spell_list:
            if re.search(rf'\b{spell}\b', text, re.IGNORECASE):
                spells.append({
                    'name': spell,
                    'level': level,
                    'source': self._extract_class(text),
                })

        return spells

    def _extract_features(self, text: str) -> List[Dict[str, Any]]:
        """Extract class and racial features."""
        features = []

        # Common features to look for
        feature_list = [
            ('Second Wind', 'Fighter', 'Bonus action to regain 1d10+level HP'),
            ('Action Surge', 'Fighter', 'Take an additional action'),
            ('Extra Attack', 'Fighter', 'Attack twice with Attack action'),
            ('Lay on Hands', 'Paladin', 'Heal up to 5×level HP'),
            ('Divine Smite', 'Paladin', 'Spend spell slot for extra radiant damage'),
            ('Divine Sense', 'Paladin', 'Detect celestials, fiends, undead'),
            ('Sneak Attack', 'Rogue', 'Extra damage on finesse/ranged attacks'),
            ('Cunning Action', 'Rogue', 'Dash, Disengage, or Hide as bonus action'),
            ('Rage', 'Barbarian', 'Bonus damage, resistance to physical damage'),
            ('Reckless Attack', 'Barbarian', 'Advantage on attacks, enemies have advantage'),
            ('Wild Shape', 'Druid', 'Transform into beasts'),
            ('Bardic Inspiration', 'Bard', 'Give d6 bonus to ally'),
            ('Ki', 'Monk', 'Special martial arts abilities'),
            ('Flurry of Blows', 'Monk', 'Two unarmed strikes as bonus action'),
            ('Favored Enemy', 'Ranger', 'Advantage tracking certain creatures'),
            ('Fighting Style', 'Fighter', 'Combat specialization'),
            ('Weapon Mastery', 'Fighter', 'Special weapon properties'),
        ]

        for name, source, description in feature_list:
            if re.search(rf'\b{name}\b', text, re.IGNORECASE):
                features.append({
                    'name': name,
                    'source': source,
                    'description': description,
                })

        return features

    def _extract_equipment(self, text: str) -> List[Dict[str, Any]]:
        """Extract equipment items."""
        equipment = []

        equipment_section = self._get_section(text, 'EQUIPMENT', 'FEATURES')
        if not equipment_section:
            equipment_section = text

        # Look for common equipment items
        items = [
            'Chain Mail', 'Plate Armor', 'Leather Armor', 'Shield',
            'Backpack', 'Bedroll', 'Rope', 'Torch', 'Rations',
            'Potion of Healing', 'Greater Healing', 'Holy Symbol',
            'Thieves\' Tools', 'Component Pouch', 'Spellbook',
        ]

        for item in items:
            if re.search(rf'\b{item}\b', equipment_section, re.IGNORECASE):
                equipment.append({
                    'name': item,
                    'quantity': 1,
                })

        # Look for currency
        gold_match = re.search(r'(\d+)\s*(?:GP|Gold)', text, re.IGNORECASE)
        if gold_match:
            equipment.append({
                'name': 'Gold Pieces',
                'quantity': int(gold_match.group(1)),
            })

        return equipment

    def _extract_senses(self, text: str) -> List[str]:
        """Extract special senses."""
        senses = []

        sense_patterns = [
            (r'Darkvision\s+(\d+)\s*(?:ft|feet)', 'Darkvision'),
            (r'Blindsight\s+(\d+)\s*(?:ft|feet)', 'Blindsight'),
            (r'Truesight\s+(\d+)\s*(?:ft|feet)', 'Truesight'),
            (r'Tremorsense\s+(\d+)\s*(?:ft|feet)', 'Tremorsense'),
        ]

        for pattern, sense_name in sense_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                senses.append(f'{sense_name} {match.group(1)} ft.')

        return senses

    def _get_section(self, text: str, start_header: str, end_header: str) -> str:
        """Extract a section of text between headers."""
        start_pattern = rf'{start_header}'
        end_pattern = rf'{end_header}'

        start_match = re.search(start_pattern, text, re.IGNORECASE)
        end_match = re.search(end_pattern, text, re.IGNORECASE)

        if start_match and end_match:
            return text[start_match.end():end_match.start()]
        elif start_match:
            return text[start_match.end():]

        return ""
