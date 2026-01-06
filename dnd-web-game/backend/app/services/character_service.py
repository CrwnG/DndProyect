"""
Character Service

Converts parsed character data (from PDF or JSON) to CombatantData format
for use in the combat system.
"""

from typing import Dict, Any, List, Optional
import uuid


def to_combatant_data(character: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert parsed character data to CombatantData format.

    This maps all character sheet data to the format expected by the
    combat engine, enabling full D&D 5e combat with imported characters.

    Args:
        character: Parsed character data from PDF or JSON

    Returns:
        CombatantData-compatible dictionary
    """
    abilities = character.get('abilities', {})
    weapons = character.get('weapons', [])
    primary_weapon = weapons[0] if weapons else None

    # Get ability modifiers
    str_mod = abilities.get('str', {}).get('mod', 0)
    dex_mod = abilities.get('dex', {}).get('mod', 0)
    con_mod = abilities.get('con', {}).get('mod', 0)
    int_mod = abilities.get('int', {}).get('mod', 0)
    wis_mod = abilities.get('wis', {}).get('mod', 0)
    cha_mod = abilities.get('cha', {}).get('mod', 0)

    # Determine attack bonus and damage
    if primary_weapon:
        attack_bonus = primary_weapon.get('attack_bonus', str_mod)
        damage_dice = primary_weapon.get('damage', '1d8')
        damage_type = primary_weapon.get('damage_type', 'slashing')
    else:
        attack_bonus = str_mod + character.get('proficiency_bonus', 2)
        damage_dice = '1d4'
        damage_type = 'bludgeoning'

    # Build equipment structure
    equipment = build_equipment_structure(character)

    # Build abilities structure with class features
    abilities_data = {
        'class': character.get('class', 'fighter').lower(),
        'level': character.get('level', 1),
        'proficiency_bonus': character.get('proficiency_bonus', 2),
        'str_score': abilities.get('str', {}).get('score', 10),
        'dex_score': abilities.get('dex', {}).get('score', 10),
        'con_score': abilities.get('con', {}).get('score', 10),
        'int_score': abilities.get('int', {}).get('score', 10),
        'wis_score': abilities.get('wis', {}).get('score', 10),
        'cha_score': abilities.get('cha', {}).get('score', 10),
        'saving_throws': character.get('saving_throws', {}),
        'skills': character.get('skills', {}),
        'features': [f['name'] for f in character.get('features', [])],
        'senses': character.get('senses', []),
        'weapons': weapons,  # Include weapons for frontend display
    }

    # Add spellcasting if present
    spellcasting = character.get('spellcasting')
    if spellcasting:
        abilities_data['spellcasting'] = {
            'ability': spellcasting.get('ability', 'CHA'),
            'spell_save_dc': spellcasting.get('spell_save_dc', 10),
            'spell_attack_bonus': spellcasting.get('spell_attack_bonus', 0),
            'spell_slots': spellcasting.get('spell_slots', {}),
            'cantrips': spellcasting.get('cantrips', []),
            'prepared_spells': spellcasting.get('prepared_spells', []),
        }

    # Get class and level for top-level access
    char_class = character.get('class', 'fighter')
    char_level = character.get('level', 1)

    # Build stats object for frontend display (character panel)
    stats = {
        'class': char_class,
        'level': char_level,
        'strength': abilities.get('str', {}).get('score', 10),
        'dexterity': abilities.get('dex', {}).get('score', 10),
        'constitution': abilities.get('con', {}).get('score', 10),
        'intelligence': abilities.get('int', {}).get('score', 10),
        'wisdom': abilities.get('wis', {}).get('score', 10),
        'charisma': abilities.get('cha', {}).get('score', 10),
        'gold': character.get('gold', 0),
    }

    combatant = {
        'id': f'player-{str(uuid.uuid4())[:8]}',
        'name': character.get('name', 'Unknown Character'),
        'type': 'player',
        # Include class and level at TOP LEVEL for easy frontend access
        'class': char_class,
        'character_class': char_class,
        'level': char_level,
        'hp': character.get('hp', 10),
        'max_hp': character.get('max_hp', 10),
        'ac': character.get('ac', 10),
        'speed': character.get('speed', 30),
        'str_mod': str_mod,
        'dex_mod': dex_mod,
        'con_mod': con_mod,
        'int_mod': int_mod,
        'wis_mod': wis_mod,
        'cha_mod': cha_mod,
        'attack_bonus': attack_bonus,
        'damage_dice': damage_dice,
        'damage_type': damage_type,
        'abilities': abilities_data,
        'equipment': equipment,
        'weapons': weapons,  # Include raw weapons list for frontend
        'initiative_mod': character.get('initiative', dex_mod),
        'conditions': [],
        # Stats object for character panel display
        'stats': stats,
        # Include spellcasting at top level for frontend access
        'spellcasting': character.get('spellcasting'),
        # Gold for inventory display
        'gold': character.get('gold', 0),
        # Inventory items
        'inventory': character.get('inventory', []),
    }

    return combatant


def build_equipment_structure(character: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the equipment structure expected by the combat system.

    This creates equipped slots (main_hand, off_hand, ranged) and
    inventory for the character.
    """
    weapons = character.get('weapons', [])
    equipment_items = character.get('equipment', [])

    # Find primary melee weapon
    melee_weapons = [w for w in weapons if not is_ranged_weapon(w)]
    ranged_weapons = [w for w in weapons if is_ranged_weapon(w)]

    # Build main hand
    main_hand = None
    if melee_weapons:
        main_weapon = melee_weapons[0]
        main_hand = {
            'id': main_weapon['name'].lower().replace(' ', '_'),
            'name': main_weapon['name'],
            'damage': main_weapon.get('damage', '1d8'),
            'damage_type': main_weapon.get('damage_type', 'slashing'),
            'properties': main_weapon.get('properties', []),
            'attack_bonus': main_weapon.get('attack_bonus', 0),
            'weight': 3,
            'icon': get_weapon_icon(main_weapon['name']),
            'mastery': get_weapon_mastery(main_weapon['name']),
        }

    # Build ranged slot
    ranged = None
    if ranged_weapons:
        ranged_weapon = ranged_weapons[0]
        ranged = {
            'id': ranged_weapon['name'].lower().replace(' ', '_'),
            'name': ranged_weapon['name'],
            'damage': ranged_weapon.get('damage', '1d8'),
            'damage_type': ranged_weapon.get('damage_type', 'piercing'),
            'properties': ranged_weapon.get('properties', []),
            'attack_bonus': ranged_weapon.get('attack_bonus', 0),
            'range': ranged_weapon.get('range', 80),
            'long_range': ranged_weapon.get('long_range', 320),
            'weight': 2,
            'icon': get_weapon_icon(ranged_weapon['name']),
        }

    # Build inventory from remaining weapons and items
    inventory = []

    # Add remaining melee weapons to inventory
    for weapon in melee_weapons[1:]:
        inventory.append({
            'id': weapon['name'].lower().replace(' ', '_'),
            'name': weapon['name'],
            'damage': weapon.get('damage', '1d6'),
            'damage_type': weapon.get('damage_type', 'slashing'),
            'properties': weapon.get('properties', []),
            'weight': 2,
            'icon': get_weapon_icon(weapon['name']),
        })

    # Add consumables and other equipment
    for item in equipment_items:
        if 'potion' in item.get('name', '').lower():
            inventory.append({
                'id': item['name'].lower().replace(' ', '_').replace("'", ''),
                'name': item['name'],
                'quantity': item.get('quantity', 1),
                'type': 'consumable',
                'effect': 'healing',
            })

    # Determine armor
    armor = None
    for item in equipment_items:
        item_name = item.get('name', '').lower()
        if 'mail' in item_name or 'armor' in item_name or 'plate' in item_name:
            armor = {
                'id': item['name'].lower().replace(' ', '_'),
                'name': item['name'],
                'ac_bonus': get_armor_ac(item['name']),
                'weight': get_armor_weight(item['name']),
            }
            break

    return {
        'main_hand': main_hand,
        'off_hand': None,
        'ranged': ranged,
        'armor': armor,
        'inventory': inventory,
        'carrying_capacity': 150,
        'current_weight': calculate_weight(main_hand, ranged, armor, inventory),
    }


def is_ranged_weapon(weapon: Dict) -> bool:
    """Check if a weapon is ranged."""
    properties = weapon.get('properties', [])
    name = weapon.get('name', '').lower()

    if 'ammunition' in properties or 'thrown' in properties:
        return True

    ranged_names = ['bow', 'crossbow', 'sling', 'dart', 'javelin']
    return any(r in name for r in ranged_names)


def get_weapon_icon(name: str) -> str:
    """Get an appropriate emoji icon for a weapon."""
    name_lower = name.lower()

    icon_map = {
        'sword': '⚔️',
        'longsword': '⚔️',
        'shortsword': '🗡️',
        'greatsword': '⚔️',
        'axe': '🪓',
        'greataxe': '🪓',
        'battleaxe': '🪓',
        'handaxe': '🪓',
        'bow': '🏹',
        'longbow': '🏹',
        'shortbow': '🏹',
        'crossbow': '🏹',
        'dagger': '🔪',
        'mace': '🔨',
        'warhammer': '🔨',
        'hammer': '🔨',
        'staff': '🪄',
        'quarterstaff': '🪄',
        'spear': '🔱',
        'javelin': '🔱',
        'flail': '⚔️',
        'rapier': '🗡️',
        'scimitar': '🗡️',
        'glaive': '⚔️',
        'halberd': '⚔️',
        'pike': '🔱',
        'trident': '🔱',
    }

    for weapon_type, icon in icon_map.items():
        if weapon_type in name_lower:
            return icon

    return '⚔️'


def get_weapon_mastery(name: str) -> Optional[str]:
    """Get the 2024 PHB weapon mastery for a weapon."""
    name_lower = name.lower()

    mastery_map = {
        'longsword': 'Sap',
        'shortsword': 'Vex',
        'greatsword': 'Graze',
        'greataxe': 'Cleave',
        'battleaxe': 'Topple',
        'handaxe': 'Vex',
        'dagger': 'Nick',
        'rapier': 'Vex',
        'scimitar': 'Nick',
        'longbow': 'Slow',
        'shortbow': 'Vex',
        'light crossbow': 'Slow',
        'heavy crossbow': 'Push',
        'warhammer': 'Push',
        'mace': 'Sap',
        'quarterstaff': 'Topple',
        'spear': 'Sap',
        'javelin': 'Slow',
        'glaive': 'Graze',
        'halberd': 'Cleave',
        'pike': 'Push',
        'flail': 'Sap',
        'morningstar': 'Sap',
        'trident': 'Topple',
    }

    for weapon_type, mastery in mastery_map.items():
        if weapon_type in name_lower:
            return mastery

    return None


def get_armor_ac(name: str) -> int:
    """Get the AC bonus for armor."""
    name_lower = name.lower()

    ac_map = {
        'leather': 11,
        'studded leather': 12,
        'hide': 12,
        'chain shirt': 13,
        'scale mail': 14,
        'breastplate': 14,
        'half plate': 15,
        'ring mail': 14,
        'chain mail': 16,
        'splint': 17,
        'plate': 18,
    }

    for armor_type, ac in ac_map.items():
        if armor_type in name_lower:
            return ac

    return 10


def get_armor_weight(name: str) -> int:
    """Get the weight of armor in pounds."""
    name_lower = name.lower()

    weight_map = {
        'leather': 10,
        'studded leather': 13,
        'hide': 12,
        'chain shirt': 20,
        'scale mail': 45,
        'breastplate': 20,
        'half plate': 40,
        'ring mail': 40,
        'chain mail': 55,
        'splint': 60,
        'plate': 65,
    }

    for armor_type, weight in weight_map.items():
        if armor_type in name_lower:
            return weight

    return 10


def calculate_weight(main_hand, ranged, armor, inventory) -> float:
    """Calculate total carried weight."""
    weight = 0.0

    if main_hand:
        weight += main_hand.get('weight', 0)
    if ranged:
        weight += ranged.get('weight', 0)
    if armor:
        weight += armor.get('weight', 0)

    for item in inventory:
        item_weight = item.get('weight', 0) * item.get('quantity', 1)
        weight += item_weight

    return weight


def validate_character(character: Dict[str, Any]) -> List[str]:
    """
    Validate character data and return list of warnings/issues.

    Args:
        character: Parsed character data

    Returns:
        List of warning messages (empty if all good)
    """
    warnings = []

    # Check required fields
    if not character.get('name'):
        warnings.append("Character name is missing")

    if character.get('hp', 0) <= 0:
        warnings.append("Hit points should be greater than 0")

    if character.get('ac', 0) < 1:
        warnings.append("Armor class seems too low")

    # Check ability scores
    abilities = character.get('abilities', {})
    for stat in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
        if stat not in abilities:
            warnings.append(f"Missing ability score: {stat.upper()}")
        elif abilities[stat].get('score', 0) < 1 or abilities[stat].get('score', 0) > 30:
            warnings.append(f"Unusual {stat.upper()} score: {abilities[stat].get('score')}")

    # Check level
    level = character.get('level', 0)
    if level < 1 or level > 20:
        warnings.append(f"Unusual character level: {level}")

    # Check weapons
    if not character.get('weapons'):
        warnings.append("No weapons found - unarmed strike will be used")

    return warnings


def create_demo_combatant(name: str = "Demo Fighter") -> Dict[str, Any]:
    """
    Create a demo combatant for testing.

    Returns a level 5 Fighter with standard equipment.
    """
    demo_character = {
        'name': name,
        'class': 'Fighter',
        'level': 5,
        'species': 'Human',
        'background': 'Soldier',
        'hp': 44,
        'max_hp': 44,
        'ac': 18,
        'speed': 30,
        'proficiency_bonus': 3,
        'initiative': 1,
        'abilities': {
            'str': {'score': 16, 'mod': 3},
            'dex': {'score': 12, 'mod': 1},
            'con': {'score': 14, 'mod': 2},
            'int': {'score': 10, 'mod': 0},
            'wis': {'score': 12, 'mod': 1},
            'cha': {'score': 10, 'mod': 0},
        },
        'saving_throws': {
            'str': {'mod': 6, 'proficient': True},
            'dex': {'mod': 1, 'proficient': False},
            'con': {'mod': 5, 'proficient': True},
            'int': {'mod': 0, 'proficient': False},
            'wis': {'mod': 1, 'proficient': False},
            'cha': {'mod': 0, 'proficient': False},
        },
        'weapons': [
            {
                'name': 'Longsword',
                'attack_bonus': 6,
                'damage': '1d8+3',
                'damage_type': 'slashing',
                'properties': ['versatile'],
            },
            {
                'name': 'Longbow',
                'attack_bonus': 4,
                'damage': '1d8+1',
                'damage_type': 'piercing',
                'properties': ['ammunition', 'two-handed', 'heavy'],
                'range': 150,
                'long_range': 600,
            },
            {
                'name': 'Shortsword',
                'attack_bonus': 6,
                'damage': '1d6+3',
                'damage_type': 'piercing',
                'properties': ['light', 'finesse'],
            },
        ],
        'features': [
            {'name': 'Second Wind', 'source': 'Fighter'},
            {'name': 'Action Surge', 'source': 'Fighter'},
            {'name': 'Extra Attack', 'source': 'Fighter'},
            {'name': 'Fighting Style: Defense', 'source': 'Fighter'},
        ],
        'equipment': [
            {'name': 'Chain Mail', 'type': 'Armor'},
            {'name': 'Shield', 'type': 'Shield'},
            {'name': 'Potion of Healing', 'quantity': 2},
        ],
        'senses': [],
    }

    return to_combatant_data(demo_character)
