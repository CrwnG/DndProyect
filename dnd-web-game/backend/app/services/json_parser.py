"""
D&D Beyond JSON Character Parser

Parses D&D Beyond JSON character exports (from browser extensions or API).
This provides the most complete and accurate character data.
"""

from typing import Dict, Any, List, Optional
import json


class DnDBeyondJSONParser:
    """Parse D&D Beyond JSON character exports."""

    def parse(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse D&D Beyond JSON character data.

        The JSON can come from:
        - D&D Beyond browser extensions
        - D&D Beyond API (via proxy)
        - Manual character JSON export
        - Custom format with characterInfo structure

        Args:
            json_data: Raw JSON character data

        Returns:
            Normalized character dictionary
        """
        # Detect custom format (characterInfo structure)
        if 'characterInfo' in json_data:
            return self._parse_custom_format(json_data)

        # Handle different D&D Beyond JSON formats
        if 'data' in json_data:
            # API response format
            data = json_data['data']
        elif 'character' in json_data:
            # Extension export format
            data = json_data['character']
        else:
            # Direct character data
            data = json_data

        return self._parse_character(data)

    def _parse_custom_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse custom JSON format with characterInfo structure.

        This format has:
        - characterInfo: name, class, level, species, background
        - abilityScores: strength.score/modifier, etc.
        - combat: armorClass, hitPoints.maximum/current, speed
        - weapons: array with name, attackBonus, damage, damageType
        - spellcasting: class, ability, spellSaveDC, spellAttackBonus
        - features: classFeatures, speciesTraits, feats
        """
        char_info = data.get('characterInfo', {})
        ability_scores = data.get('abilityScores', {})
        combat = data.get('combat', {})

        # Parse ability scores
        abilities = {}
        ability_map = {
            'strength': 'str',
            'dexterity': 'dex',
            'constitution': 'con',
            'intelligence': 'int',
            'wisdom': 'wis',
            'charisma': 'cha'
        }
        for full_name, short_name in ability_map.items():
            ability_data = ability_scores.get(full_name, {})
            abilities[short_name] = {
                'score': ability_data.get('score', 10),
                'mod': ability_data.get('modifier', 0)
            }

        # Parse HP
        hp_data = combat.get('hitPoints', {})
        max_hp = hp_data.get('maximum', 10)
        current_hp = hp_data.get('current', max_hp)

        # Parse speed (convert "30 ft. (Walking)" to 30)
        speed_str = combat.get('speed', '30 ft.')
        speed = 30
        if isinstance(speed_str, str):
            import re
            speed_match = re.search(r'(\d+)', speed_str)
            if speed_match:
                speed = int(speed_match.group(1))
        elif isinstance(speed_str, (int, float)):
            speed = int(speed_str)

        # Parse weapons
        weapons = []
        for weapon in data.get('weapons', []):
            weapon_name = weapon.get('name', 'Unknown Weapon')
            # Skip Unarmed Strike - it's an innate ability, not equipment
            if weapon_name.lower() == 'unarmed strike':
                continue
            weapons.append({
                'id': weapon_name.lower().replace(' ', '_').replace("'", ""),  # Generate unique ID
                'name': weapon_name,
                'attack_bonus': weapon.get('attackBonus', 0),
                'damage': weapon.get('damage', '1d4'),
                'damage_type': weapon.get('damageType', 'bludgeoning').lower(),
                'properties': [p.lower() for p in weapon.get('properties', [])],
                'range': 5,  # Default melee
                'item_type': 'weapon',  # Mark as weapon for proper handling
            })

        # NOTE: Unarmed Strike is NOT added to weapons list - it's an innate ability
        # handled by CharacterEquipment.get_available_weapons() in combat

        # Parse spellcasting
        spellcasting = None
        spell_data = data.get('spellcasting')
        if spell_data:
            spellcasting = {
                'ability': spell_data.get('ability', 'CHA'),
                'spell_save_dc': spell_data.get('spellSaveDC', 8),
                'spell_attack_bonus': spell_data.get('spellAttackBonus', 0),
                'spell_slots': {},
                'cantrips': [],
                'prepared_spells': [],
            }

            # Parse spell slots
            slots = spell_data.get('spellSlots', {})
            for level, slot_info in slots.items():
                level_num = int(level[0]) if level[0].isdigit() else 1
                spellcasting['spell_slots'][level_num] = slot_info.get('total', 0)

            # Parse spells
            spells = data.get('spells', {})
            for cantrip in spells.get('cantrips', []):
                spellcasting['cantrips'].append({
                    'name': cantrip.get('name', 'Unknown'),
                    'level': 0,
                    'source': cantrip.get('source', 'Class'),
                })
            for spell in spells.get('1stLevel', []):
                if spell.get('prepared', False):
                    spellcasting['prepared_spells'].append({
                        'name': spell.get('name', 'Unknown'),
                        'level': 1,
                        'source': spell.get('source', 'Class'),
                    })

        # Parse features
        features = []
        features_data = data.get('features', {})
        for feature in features_data.get('classFeatures', []):
            features.append({
                'name': feature.get('name', 'Unknown'),
                'source': feature.get('source', 'Class'),
                'description': feature.get('description', ''),
            })
        for trait in features_data.get('speciesTraits', []):
            features.append({
                'name': trait.get('name', 'Unknown'),
                'source': trait.get('source', 'Species'),
                'description': trait.get('description', ''),
            })
        for feat in features_data.get('feats', []):
            features.append({
                'name': feat.get('name', 'Unknown'),
                'source': feat.get('source', 'Feat'),
                'description': feat.get('description', ''),
            })

        # Parse saving throws
        saving_throws = {}
        saves_data = data.get('savingThrows', {})
        for stat, save_info in saves_data.items():
            short_name = ability_map.get(stat, stat[:3])
            saving_throws[short_name] = {
                'mod': save_info.get('modifier', 0),
                'proficient': save_info.get('proficient', False)
            }

        # Parse skills
        skills = {}
        skills_data = data.get('skills', {})
        for skill_name, skill_info in skills_data.items():
            # Convert camelCase to snake_case
            snake_name = ''.join(['_'+c.lower() if c.isupper() else c for c in skill_name]).lstrip('_')
            skills[snake_name] = {
                'mod': skill_info.get('modifier', 0),
                'proficient': skill_info.get('proficient', False),
                'expertise': False
            }

        # Parse equipment
        equipment = []
        for item in data.get('equipment', []):
            equipment.append({
                'name': item.get('name', 'Unknown'),
                'quantity': item.get('quantity', 1),
                'equipped': True,  # Assume equipped if in equipment list
                'type': 'Equipment',
                'weight': item.get('weight') or 0,
            })

        # Parse senses
        senses = data.get('senses', [])

        # Build the character object
        level = char_info.get('level', 1)
        proficiency_bonus = combat.get('proficiencyBonus', (level - 1) // 4 + 2)

        return {
            'name': char_info.get('name', 'Unknown Character'),
            'class': char_info.get('class', 'Unknown'),
            'level': level,
            'species': char_info.get('species', 'Unknown'),
            'background': char_info.get('background', 'Unknown'),
            'hp': current_hp,
            'max_hp': max_hp,
            'ac': combat.get('armorClass', 10),
            'speed': speed,
            'proficiency_bonus': proficiency_bonus,
            'initiative': abilities.get('dex', {}).get('mod', 0),
            'abilities': abilities,
            'saving_throws': saving_throws,
            'skills': skills,
            'weapons': weapons,
            'spellcasting': spellcasting,
            'features': features,
            'equipment': equipment,
            'senses': senses,
            'classes': [{'name': char_info.get('class', 'Unknown'), 'level': level}],
        }

    def _parse_character(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse normalized character data."""
        # Extract ability scores
        abilities = self._parse_abilities(data)

        # Extract class info
        classes = self._parse_classes(data)
        primary_class = classes[0] if classes else {'name': 'Unknown', 'level': 1}

        # Calculate level
        total_level = sum(c['level'] for c in classes)

        # Proficiency bonus based on level
        proficiency_bonus = (total_level - 1) // 4 + 2

        character = {
            'name': self._get_name(data),
            'class': primary_class['name'],
            'level': total_level,
            'species': self._get_species(data),
            'background': self._get_background(data),
            'hp': self._get_current_hp(data),
            'max_hp': self._get_max_hp(data),
            'ac': self._calculate_ac(data, abilities),
            'speed': self._get_speed(data),
            'proficiency_bonus': proficiency_bonus,
            'initiative': abilities.get('dex', {}).get('mod', 0),
            'abilities': abilities,
            'saving_throws': self._parse_saving_throws(data, abilities, proficiency_bonus),
            'skills': self._parse_skills(data, abilities, proficiency_bonus),
            'weapons': self._parse_weapons(data, abilities, proficiency_bonus),
            'spellcasting': self._parse_spellcasting(data, abilities, proficiency_bonus),
            'features': self._parse_features(data),
            'equipment': self._parse_equipment(data),
            'senses': self._parse_senses(data),
            'classes': classes,
        }

        return character

    def _get_name(self, data: Dict) -> str:
        """Get character name."""
        return data.get('name', 'Unknown Character')

    def _get_species(self, data: Dict) -> str:
        """Get character species/race."""
        if 'race' in data:
            race_data = data['race']
            if isinstance(race_data, dict):
                return race_data.get('fullName', race_data.get('baseName', 'Unknown'))
            return str(race_data)
        return data.get('species', 'Unknown')

    def _get_background(self, data: Dict) -> str:
        """Get character background."""
        if 'background' in data:
            bg_data = data['background']
            if isinstance(bg_data, dict):
                return bg_data.get('definition', {}).get('name', 'Unknown')
            return str(bg_data)
        return 'Unknown'

    def _get_current_hp(self, data: Dict) -> int:
        """Get current hit points."""
        if 'overrideHitPoints' in data and data['overrideHitPoints']:
            return data['overrideHitPoints']

        max_hp = self._get_max_hp(data)
        removed = data.get('removedHitPoints', 0)
        return max_hp - removed

    def _get_max_hp(self, data: Dict) -> int:
        """Get maximum hit points."""
        if 'overrideHitPoints' in data and data['overrideHitPoints']:
            return data['overrideHitPoints']

        base_hp = data.get('baseHitPoints', 0)
        bonus_hp = data.get('bonusHitPoints', 0)

        # Constitution modifier × level
        abilities = self._parse_abilities(data)
        con_mod = abilities.get('con', {}).get('mod', 0)
        classes = self._parse_classes(data)
        total_level = sum(c['level'] for c in classes)

        return base_hp + bonus_hp + (con_mod * total_level) if base_hp else 10

    def _get_speed(self, data: Dict) -> int:
        """Get movement speed in feet."""
        if 'race' in data and isinstance(data['race'], dict):
            racial_traits = data['race'].get('racialTraits', [])
            for trait in racial_traits:
                if 'speed' in str(trait).lower():
                    return 30  # Default

        if 'walkingSpeed' in data:
            return data['walkingSpeed']

        return 30  # Default walking speed

    def _parse_abilities(self, data: Dict) -> Dict[str, Dict[str, int]]:
        """Parse ability scores and calculate modifiers."""
        abilities = {}

        # D&D Beyond uses stat IDs: 1=STR, 2=DEX, 3=CON, 4=INT, 5=WIS, 6=CHA
        stat_map = {1: 'str', 2: 'dex', 3: 'con', 4: 'int', 5: 'wis', 6: 'cha'}

        if 'stats' in data:
            for stat in data['stats']:
                stat_id = stat.get('id')
                if stat_id in stat_map:
                    value = stat.get('value', 10)
                    abilities[stat_map[stat_id]] = {
                        'score': value,
                        'mod': (value - 10) // 2
                    }

        # Handle modifiers from race/class/items
        if 'modifiers' in data:
            for modifier_source in data['modifiers'].values():
                if isinstance(modifier_source, list):
                    for mod in modifier_source:
                        if mod.get('type') == 'bonus' and 'stat' in str(mod.get('subType', '')).lower():
                            stat_name = mod.get('subType', '').replace('-score', '')[:3].lower()
                            if stat_name in abilities:
                                abilities[stat_name]['score'] += mod.get('value', 0)
                                abilities[stat_name]['mod'] = (abilities[stat_name]['score'] - 10) // 2

        # Fill defaults
        for stat in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
            if stat not in abilities:
                abilities[stat] = {'score': 10, 'mod': 0}

        return abilities

    def _parse_classes(self, data: Dict) -> List[Dict[str, Any]]:
        """Parse class information."""
        classes = []

        if 'classes' in data:
            for cls in data['classes']:
                class_def = cls.get('definition', {})
                classes.append({
                    'name': class_def.get('name', 'Unknown'),
                    'level': cls.get('level', 1),
                    'hit_dice': class_def.get('hitDice', 8),
                    'subclass': cls.get('subclassDefinition', {}).get('name') if cls.get('subclassDefinition') else None,
                })

        if not classes:
            classes.append({'name': 'Unknown', 'level': 1, 'hit_dice': 8})

        return classes

    def _calculate_ac(self, data: Dict, abilities: Dict) -> int:
        """Calculate armor class."""
        base_ac = 10 + abilities.get('dex', {}).get('mod', 0)

        if 'armorClass' in data:
            return data['armorClass']

        # Check equipped armor
        if 'inventory' in data:
            for item in data['inventory']:
                definition = item.get('definition', {})
                if definition.get('armorClass'):
                    armor_ac = definition['armorClass']
                    armor_type = definition.get('armorTypeId', 0)

                    # Heavy armor: no DEX
                    if armor_type == 3:
                        base_ac = armor_ac
                    # Medium armor: max +2 DEX
                    elif armor_type == 2:
                        dex_bonus = min(2, abilities.get('dex', {}).get('mod', 0))
                        base_ac = armor_ac + dex_bonus
                    # Light armor: full DEX
                    elif armor_type == 1:
                        base_ac = armor_ac + abilities.get('dex', {}).get('mod', 0)

                # Check for shield
                if definition.get('name', '').lower() == 'shield':
                    base_ac += 2

        return base_ac

    def _parse_saving_throws(self, data: Dict, abilities: Dict, prof_bonus: int) -> Dict[str, Dict]:
        """Parse saving throw proficiencies and modifiers."""
        saves = {}

        # Default: just ability modifier
        for stat in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
            saves[stat] = {
                'mod': abilities[stat]['mod'],
                'proficient': False
            }

        # Check for save proficiencies from class
        if 'classes' in data:
            for cls in data['classes']:
                class_def = cls.get('definition', {})
                save_stats = class_def.get('savingThrows', [])
                for save_id in save_stats:
                    stat_map = {1: 'str', 2: 'dex', 3: 'con', 4: 'int', 5: 'wis', 6: 'cha'}
                    if save_id in stat_map:
                        stat = stat_map[save_id]
                        saves[stat]['proficient'] = True
                        saves[stat]['mod'] = abilities[stat]['mod'] + prof_bonus

        return saves

    def _parse_skills(self, data: Dict, abilities: Dict, prof_bonus: int) -> Dict[str, Dict]:
        """Parse skill proficiencies and modifiers."""
        skills = {}

        # Skill to ability mapping
        skill_abilities = {
            'acrobatics': 'dex', 'animal_handling': 'wis', 'arcana': 'int',
            'athletics': 'str', 'deception': 'cha', 'history': 'int',
            'insight': 'wis', 'intimidation': 'cha', 'investigation': 'int',
            'medicine': 'wis', 'nature': 'int', 'perception': 'wis',
            'performance': 'cha', 'persuasion': 'cha', 'religion': 'int',
            'sleight_of_hand': 'dex', 'stealth': 'dex', 'survival': 'wis'
        }

        # Initialize with base ability mods
        for skill, ability in skill_abilities.items():
            skills[skill] = {
                'mod': abilities[ability]['mod'],
                'proficient': False,
                'expertise': False
            }

        # Check modifiers for proficiencies
        if 'modifiers' in data:
            for source_mods in data['modifiers'].values():
                if isinstance(source_mods, list):
                    for mod in source_mods:
                        if mod.get('type') == 'proficiency':
                            skill_name = mod.get('subType', '').replace('-', '_').lower()
                            if skill_name in skills:
                                skills[skill_name]['proficient'] = True
                                ability = skill_abilities[skill_name]
                                skills[skill_name]['mod'] = abilities[ability]['mod'] + prof_bonus
                        elif mod.get('type') == 'expertise':
                            skill_name = mod.get('subType', '').replace('-', '_').lower()
                            if skill_name in skills:
                                skills[skill_name]['expertise'] = True
                                ability = skill_abilities[skill_name]
                                skills[skill_name]['mod'] = abilities[ability]['mod'] + (prof_bonus * 2)

        return skills

    def _parse_weapons(self, data: Dict, abilities: Dict, prof_bonus: int) -> List[Dict]:
        """Parse equipped weapons and attacks."""
        weapons = []

        if 'inventory' in data:
            for item in data['inventory']:
                definition = item.get('definition', {})
                if definition.get('filterType') == 'Weapon' and item.get('equipped'):
                    weapon = self._parse_weapon_item(definition, abilities, prof_bonus)
                    if weapon:
                        weapons.append(weapon)

        # NOTE: Unarmed Strike is NOT added to weapons list - it's an innate ability
        # handled by CharacterEquipment.get_available_weapons() in combat

        return weapons

    def _parse_weapon_item(self, definition: Dict, abilities: Dict, prof_bonus: int) -> Optional[Dict]:
        """Parse a single weapon item."""
        name = definition.get('name', 'Unknown Weapon')
        properties = [p.get('name', '').lower() for p in definition.get('properties', [])]

        # Determine which ability to use
        is_finesse = 'finesse' in properties
        is_ranged = definition.get('attackType') == 2

        if is_ranged:
            ability_mod = abilities.get('dex', {}).get('mod', 0)
        elif is_finesse:
            # Use higher of STR or DEX
            str_mod = abilities.get('str', {}).get('mod', 0)
            dex_mod = abilities.get('dex', {}).get('mod', 0)
            ability_mod = max(str_mod, dex_mod)
        else:
            ability_mod = abilities.get('str', {}).get('mod', 0)

        attack_bonus = ability_mod + prof_bonus

        # Parse damage
        damage_dice = definition.get('damage', {}).get('diceString', '1d4')
        if ability_mod != 0:
            damage = f"{damage_dice}+{ability_mod}" if ability_mod > 0 else f"{damage_dice}{ability_mod}"
        else:
            damage = damage_dice

        damage_type = definition.get('damageType', 'slashing').lower()

        # Get range
        range_val = definition.get('range', 5)
        long_range = definition.get('longRange')

        return {
            'id': name.lower().replace(' ', '_').replace("'", ""),  # Generate unique ID
            'name': name,
            'attack_bonus': attack_bonus,
            'damage': damage,
            'damage_type': damage_type,
            'properties': properties,
            'range': range_val,
            'long_range': long_range,
            'item_type': 'weapon',  # Mark as weapon for proper handling
        }

    def _parse_spellcasting(self, data: Dict, abilities: Dict, prof_bonus: int) -> Optional[Dict]:
        """Parse spellcasting information."""
        # Check if character has spellcasting
        has_spells = False
        if 'spells' in data:
            for spell_source in data['spells'].values():
                if spell_source:
                    has_spells = True
                    break

        if not has_spells:
            return None

        # Determine spellcasting ability from class
        classes = self._parse_classes(data)
        class_name = classes[0]['name'].lower() if classes else ''

        ability_map = {
            'wizard': 'int', 'cleric': 'wis', 'paladin': 'cha',
            'sorcerer': 'cha', 'warlock': 'cha', 'bard': 'cha',
            'druid': 'wis', 'ranger': 'wis'
        }
        spell_ability = ability_map.get(class_name, 'cha')
        ability_mod = abilities.get(spell_ability, {}).get('mod', 0)

        return {
            'ability': spell_ability.upper(),
            'spell_save_dc': 8 + prof_bonus + ability_mod,
            'spell_attack_bonus': prof_bonus + ability_mod,
            'spell_slots': self._parse_spell_slots(data, classes),
            'cantrips': self._parse_spells(data, 0),
            'prepared_spells': self._parse_spells(data),
        }

    def _parse_spell_slots(self, data: Dict, classes: List[Dict]) -> Dict[int, int]:
        """Calculate spell slots based on class levels."""
        slots = {}

        # Simplified spell slot table (full casters)
        slot_table = {
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
            4: {1: 4, 2: 3},
            5: {1: 4, 2: 3, 3: 2},
        }

        total_level = sum(c['level'] for c in classes)
        if total_level in slot_table:
            slots = slot_table[total_level]

        return slots

    def _parse_spells(self, data: Dict, level: Optional[int] = None) -> List[Dict]:
        """Parse known/prepared spells."""
        spells = []

        if 'spells' not in data:
            return spells

        for source_name, spell_list in data['spells'].items():
            if not spell_list:
                continue

            for spell in spell_list:
                spell_def = spell.get('definition', {})
                spell_level = spell_def.get('level', 0)

                # Filter by level if specified
                if level is not None and spell_level != level:
                    continue

                spells.append({
                    'name': spell_def.get('name', 'Unknown Spell'),
                    'level': spell_level,
                    'source': source_name,
                    'school': spell_def.get('school', 'Unknown'),
                    'range': spell_def.get('range', {}).get('origin', 'Self'),
                    'casting_time': spell_def.get('activation', {}).get('activationType', 1),
                    'components': self._format_components(spell_def),
                    'concentration': spell_def.get('concentration', False),
                    'prepared': spell.get('prepared', True),
                })

        return spells

    def _format_components(self, spell_def: Dict) -> str:
        """Format spell components string."""
        components = []
        if spell_def.get('components', {}).get('verbal'):
            components.append('V')
        if spell_def.get('components', {}).get('somatic'):
            components.append('S')
        if spell_def.get('components', {}).get('material'):
            components.append('M')
        return ','.join(components)

    def _parse_features(self, data: Dict) -> List[Dict]:
        """Parse class and racial features."""
        features = []

        # Class features
        if 'classes' in data:
            for cls in data['classes']:
                class_features = cls.get('classFeatures', [])
                for feature in class_features:
                    definition = feature.get('definition', {})
                    features.append({
                        'name': definition.get('name', 'Unknown Feature'),
                        'source': cls.get('definition', {}).get('name', 'Class'),
                        'description': definition.get('description', ''),
                        'level': definition.get('requiredLevel', 1),
                    })

        # Racial features
        if 'race' in data and isinstance(data['race'], dict):
            racial_traits = data['race'].get('racialTraits', [])
            for trait in racial_traits:
                definition = trait.get('definition', {})
                features.append({
                    'name': definition.get('name', 'Unknown Trait'),
                    'source': data['race'].get('baseName', 'Race'),
                    'description': definition.get('description', ''),
                })

        return features

    def _parse_equipment(self, data: Dict) -> List[Dict]:
        """Parse equipment and inventory."""
        equipment = []

        if 'inventory' in data:
            for item in data['inventory']:
                definition = item.get('definition', {})
                equipment.append({
                    'name': definition.get('name', 'Unknown Item'),
                    'quantity': item.get('quantity', 1),
                    'equipped': item.get('equipped', False),
                    'type': definition.get('filterType', 'Other'),
                    'weight': definition.get('weight', 0),
                })

        # Currency
        if 'currencies' in data:
            currencies = data['currencies']
            for currency_type in ['cp', 'sp', 'ep', 'gp', 'pp']:
                amount = currencies.get(currency_type, 0)
                if amount > 0:
                    equipment.append({
                        'name': currency_type.upper(),
                        'quantity': amount,
                        'type': 'Currency',
                    })

        return equipment

    def _parse_senses(self, data: Dict) -> List[str]:
        """Parse special senses."""
        senses = []

        # Check racial traits for senses
        if 'race' in data and isinstance(data['race'], dict):
            racial_traits = data['race'].get('racialTraits', [])
            for trait in racial_traits:
                definition = trait.get('definition', {})
                name = definition.get('name', '').lower()
                if 'darkvision' in name:
                    senses.append('Darkvision 60 ft.')
                elif 'superior darkvision' in name:
                    senses.append('Darkvision 120 ft.')

        # Check for additional sense modifiers
        if 'modifiers' in data:
            for source_mods in data['modifiers'].values():
                if isinstance(source_mods, list):
                    for mod in source_mods:
                        subtype = mod.get('subType', '').lower()
                        if 'darkvision' in subtype:
                            if 'Darkvision' not in str(senses):
                                senses.append(f"Darkvision {mod.get('value', 60)} ft.")

        return senses


def parse_json_file(json_path: str) -> Dict[str, Any]:
    """Parse a JSON file containing character data."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    parser = DnDBeyondJSONParser()
    return parser.parse(data)


def parse_json_string(json_string: str) -> Dict[str, Any]:
    """Parse a JSON string containing character data."""
    data = json.loads(json_string)
    parser = DnDBeyondJSONParser()
    return parser.parse(data)
