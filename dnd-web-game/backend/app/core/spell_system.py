"""
D&D 5e 2024 Spell System - Core Logic.

Handles spell loading, casting, slot management, and effect resolution.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from app.models.spells import (
    Spell, SpellComponents, SpellSchool, SpellTargetType, SpellEffectType,
    CharacterSpellcasting, SpellcastingType, SpellCastResult, DamageType
)
from app.core.dice import roll_d20, D20Result
from app.core.rules_engine import roll_damage


class SpellRegistry:
    """
    Singleton that loads and indexes all spells from JSON files.

    Provides fast lookup by ID, level, class, and school.
    """
    _instance: Optional['SpellRegistry'] = None

    def __init__(self):
        self._spells: Dict[str, Spell] = {}
        self._spells_by_level: Dict[int, List[Spell]] = {i: [] for i in range(10)}
        self._spells_by_class: Dict[str, List[Spell]] = {}
        self._spells_by_school: Dict[str, List[Spell]] = {}
        self._loaded = False

    @classmethod
    def get_instance(cls) -> 'SpellRegistry':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_all_spells()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (useful for testing)."""
        cls._instance = None

    def _load_all_spells(self):
        """Load spells from all JSON files."""
        if self._loaded:
            return

        # Get the spells directory
        base_path = Path(__file__).parent.parent / "data" / "rules" / "2024" / "spells"

        # Load each spell level file
        spell_files = [
            "cantrips.json",
            "level_1.json",
            "level_2.json",
            "level_3.json",
            "level_4.json",
            "level_5.json",
            "level_6.json",
            "level_7.json",
            "level_8.json",
            "level_9.json",
        ]

        for filename in spell_files:
            filepath = base_path / filename
            if filepath.exists():
                self._load_spell_file(filepath)

        self._loaded = True

    def _load_spell_file(self, filepath: Path):
        """Load spells from a single JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            level = data.get("level", 0)
            spells_data = data.get("spells", [])

            for spell_data in spells_data:
                spell = self._parse_spell(spell_data, level)
                self._index_spell(spell)

        except Exception as e:
            print(f"[SpellRegistry] Error loading {filepath}: {e}")

    def _parse_spell(self, data: Dict, level: int) -> Spell:
        """Parse a spell from JSON data into a Spell model."""
        # Parse components
        comp_data = data.get("components", {})
        if isinstance(comp_data, dict):
            components = SpellComponents(
                verbal=comp_data.get("verbal", False),
                somatic=comp_data.get("somatic", False),
                material=comp_data.get("material")
            )
        else:
            # Handle list format ["V", "S", "M"]
            components = SpellComponents(
                verbal="V" in comp_data or "verbal" in str(comp_data).lower(),
                somatic="S" in comp_data or "somatic" in str(comp_data).lower(),
                material=None
            )

        # Create base spell
        spell = Spell(
            id=data.get("id", data.get("name", "").lower().replace(" ", "_")),
            name=data.get("name", "Unknown Spell"),
            level=level,
            school=data.get("school", "evocation").lower(),
            casting_time=data.get("casting_time", "Action"),
            range=data.get("range", "Self"),
            components=components,
            duration=data.get("duration", "Instantaneous"),
            concentration=data.get("concentration", False) or "concentration" in data.get("duration", "").lower(),
            ritual=data.get("ritual", False),
            description=data.get("description", ""),
            higher_levels=data.get("higher_levels"),
            classes=data.get("classes", []),
        )

        # Parse combat-relevant data
        self._parse_combat_data(spell, data)

        return spell

    def _parse_combat_data(self, spell: Spell, data: Dict):
        """Parse combat-relevant data from spell description and explicit JSON fields."""
        description = spell.description.lower()

        # First, check for explicit values in JSON data
        if data.get("target_type"):
            target_type_map = {
                "self": SpellTargetType.SELF,
                "touch": SpellTargetType.TOUCH,
                "single": SpellTargetType.SINGLE,
                "cone": SpellTargetType.AREA_CONE,
                "sphere": SpellTargetType.AREA_SPHERE,
                "line": SpellTargetType.AREA_LINE,
                "cube": SpellTargetType.AREA_CUBE,
                "cylinder": SpellTargetType.AREA_CYLINDER,
            }
            spell.target_type = target_type_map.get(data["target_type"], SpellTargetType.SINGLE)
        else:
            # Fall back to detection from range/description
            range_str = spell.range.lower()
            if "self" in range_str:
                spell.target_type = SpellTargetType.SELF
            elif "touch" in range_str:
                spell.target_type = SpellTargetType.TOUCH
            elif "cone" in range_str or "cone" in description:
                spell.target_type = SpellTargetType.AREA_CONE
            elif "sphere" in description or "radius" in description:
                spell.target_type = SpellTargetType.AREA_SPHERE
            elif "line" in description:
                spell.target_type = SpellTargetType.AREA_LINE
            elif "cube" in description:
                spell.target_type = SpellTargetType.AREA_CUBE
            elif "cylinder" in description:
                spell.target_type = SpellTargetType.AREA_CYLINDER
            else:
                spell.target_type = SpellTargetType.SINGLE

        # Check for explicit damage/save data from JSON
        # Support both "damage_dice" (2024 format) and "damage" (older format)
        if data.get("damage_dice"):
            spell.damage_dice = data["damage_dice"]
        elif data.get("damage") and isinstance(data["damage"], str) and "d" in data["damage"]:
            # Fallback: some JSON files use "damage" instead of "damage_dice"
            spell.damage_dice = data["damage"]
        if data.get("damage_type"):
            spell.damage_type = data["damage_type"]
        if data.get("save_type"):
            spell.save_type = data["save_type"]
            # Normalize abbreviated save types to full names
            SAVE_TYPE_MAP = {
                "str": "strength",
                "dex": "dexterity",
                "con": "constitution",
                "int": "intelligence",
                "wis": "wisdom",
                "cha": "charisma",
            }
            if spell.save_type and spell.save_type.lower() in SAVE_TYPE_MAP:
                spell.save_type = SAVE_TYPE_MAP[spell.save_type.lower()]
        if data.get("combat_usable") is not None:
            spell.combat_usable = data["combat_usable"]
        if data.get("trigger"):
            spell.trigger = data["trigger"]

        # Detect effect type
        if "damage" in description or "hit" in description:
            spell.effect_type = SpellEffectType.DAMAGE
        elif "heal" in description or "regain" in description or "restore" in description:
            spell.effect_type = SpellEffectType.HEALING
        elif any(word in description for word in ["charmed", "frightened", "restrained", "paralyzed", "stunned"]):
            spell.effect_type = SpellEffectType.CONTROL
        elif "advantage" in description or "bonus" in description:
            spell.effect_type = SpellEffectType.BUFF
        elif "disadvantage" in description or "penalty" in description:
            spell.effect_type = SpellEffectType.DEBUFF
        else:
            spell.effect_type = SpellEffectType.UTILITY

        # Extract damage dice
        damage_match = re.search(r'(\d+d\d+)\s+(acid|fire|cold|lightning|thunder|force|necrotic|radiant|poison|psychic|bludgeoning|piercing|slashing)', description)
        if damage_match:
            spell.damage_dice = damage_match.group(1)
            spell.damage_type = damage_match.group(2)

        # Extract healing dice
        healing_match = re.search(r'regain[s]?\s+(?:hit points equal to\s+)?(\d+d\d+)', description)
        if healing_match:
            spell.healing_dice = healing_match.group(1)

        # Detect save type
        for save_type in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            if f"{save_type} saving throw" in description:
                spell.save_type = save_type
                break

        # Detect attack type
        if "spell attack" in description:
            if "melee" in description:
                spell.attack_type = "melee_spell"
            else:
                spell.attack_type = "ranged_spell"

        # Extract area size
        area_match = re.search(r'(\d+)[- ]foot[- ](radius|cone|line|cube|sphere)', description)
        if area_match:
            spell.area_size = int(area_match.group(1))

        # Detect conditions
        conditions = ["blinded", "charmed", "deafened", "frightened", "grappled",
                     "incapacitated", "invisible", "paralyzed", "petrified",
                     "poisoned", "prone", "restrained", "stunned", "unconscious"]
        spell.conditions_applied = [c for c in conditions if c in description]

    def _index_spell(self, spell: Spell):
        """Add spell to all indexes."""
        self._spells[spell.id] = spell
        self._spells_by_level[spell.level].append(spell)

        # Index by school
        school = spell.school.lower()
        if school not in self._spells_by_school:
            self._spells_by_school[school] = []
        self._spells_by_school[school].append(spell)

        # Index by class
        for class_name in spell.classes:
            class_lower = class_name.lower()
            if class_lower not in self._spells_by_class:
                self._spells_by_class[class_lower] = []
            self._spells_by_class[class_lower].append(spell)

    def get_spell(self, spell_id: str) -> Optional[Spell]:
        """Get a spell by ID."""
        return self._spells.get(spell_id.lower().replace(" ", "_"))

    def get_all_spells(self) -> List[Spell]:
        """Get all loaded spells."""
        return list(self._spells.values())

    def get_spells_by_level(self, level: int) -> List[Spell]:
        """Get all spells of a specific level."""
        return self._spells_by_level.get(level, [])

    def get_spells_for_class(self, class_name: str, max_level: int = 9) -> List[Spell]:
        """Get all spells available to a class up to a max level."""
        class_spells = self._spells_by_class.get(class_name.lower(), [])
        return [s for s in class_spells if s.level <= max_level]

    def get_spells_by_school(self, school: str) -> List[Spell]:
        """Get all spells of a specific school."""
        return self._spells_by_school.get(school.lower(), [])

    def search_spells(
        self,
        query: Optional[str] = None,
        level: Optional[int] = None,
        school: Optional[str] = None,
        class_name: Optional[str] = None,
        ritual: Optional[bool] = None,
        concentration: Optional[bool] = None,
    ) -> List[Spell]:
        """Search spells with multiple filters."""
        results = list(self._spells.values())

        if level is not None:
            results = [s for s in results if s.level == level]

        if school:
            results = [s for s in results if s.school.lower() == school.lower()]

        if class_name:
            results = [s for s in results if class_name.lower() in [c.lower() for c in s.classes]]

        if ritual is not None:
            results = [s for s in results if s.ritual == ritual]

        if concentration is not None:
            results = [s for s in results if s.concentration == concentration]

        if query:
            query_lower = query.lower()
            results = [s for s in results if
                      query_lower in s.name.lower() or
                      query_lower in s.description.lower()]

        return results


class SpellCaster:
    """
    Manages spellcasting for a character.

    Handles spell preparation, slot management, and casting validation.
    """

    def __init__(self, character_data: Dict, spellcasting_data: Optional[Dict] = None):
        """
        Initialize spellcaster from character data.

        Args:
            character_data: Character's full data dict
            spellcasting_data: Optional override for spellcasting info
        """
        self.character = character_data
        self.spellcasting = self._init_spellcasting(spellcasting_data)
        self._registry = SpellRegistry.get_instance()

    def _init_spellcasting(self, override_data: Optional[Dict] = None) -> CharacterSpellcasting:
        """Initialize spellcasting from character data."""
        # Get spellcasting data from character or override
        spell_data = override_data or self.character.get("spellcasting", {})

        # Debug logging
        print(f"[SpellCaster] _init_spellcasting - spell_data keys: {spell_data.keys() if spell_data else 'None'}")
        raw_cantrips = spell_data.get("cantrips_known", spell_data.get("cantrips", []))
        print(f"[SpellCaster] Raw cantrips data: {raw_cantrips}")

        # Get class info for defaults
        class_name = self.character.get("class", "").lower()
        level = self.character.get("level", 1)

        # Import here to avoid circular imports
        from app.core.class_spellcasting import (
            get_spellcasting_ability,
            get_spellcasting_type,
            get_spell_slots_for_level,
            get_max_prepared_spells
        )

        # Helper to convert spell list items (dicts or strings) to spell IDs
        def to_spell_ids(items):
            if not items:
                return []
            result = []
            for item in items:
                if isinstance(item, dict):
                    # Extract ID from dict: try 'id' first, then convert 'name' to ID format
                    spell_id = item.get('id') or item.get('name', '').lower().replace(' ', '_')
                    if spell_id:
                        result.append(spell_id)
                elif isinstance(item, str):
                    result.append(item)
            return result

        # Calculate ability modifier
        ability = spell_data.get("ability") or get_spellcasting_ability(class_name)
        stats = self.character.get("stats", {})

        # Try to get ability score - handle both abbreviated ("cha") and full ("charisma") names
        ABILITY_NAME_MAP = {
            "str": "strength", "strength": "strength",
            "dex": "dexterity", "dexterity": "dexterity",
            "con": "constitution", "constitution": "constitution",
            "int": "intelligence", "intelligence": "intelligence",
            "wis": "wisdom", "wisdom": "wisdom",
            "cha": "charisma", "charisma": "charisma",
        }
        ability_key = ability.lower() if ability else ""
        full_ability_name = ABILITY_NAME_MAP.get(ability_key, ability_key)

        # Try full name first, then abbreviated, then default to 10
        ability_score = stats.get(full_ability_name) or stats.get(ability_key) or 10
        ability_mod = (ability_score - 10) // 2

        # Calculate proficiency bonus
        prof_bonus = 2 + ((level - 1) // 4)

        # DEBUG: Log the DC calculation
        calculated_dc = 8 + prof_bonus + ability_mod
        existing_dc = spell_data.get("spell_save_dc")
        print(f"[SpellCaster] DC Calculation: ability={ability}, score={ability_score}, mod={ability_mod}, prof={prof_bonus}, calc_dc={calculated_dc}, existing_dc={existing_dc}")
        print(f"[SpellCaster] Stats available: {list(stats.keys()) if stats else 'None'}")

        # Get spell slots for level
        spell_slots = spell_data.get("spell_slots") or get_spell_slots_for_level(class_name, level)

        # Use pre-calculated DC/bonus if available, otherwise calculate
        final_dc = spell_data.get("spell_save_dc") or (8 + prof_bonus + ability_mod)
        final_attack_bonus = spell_data.get("spell_attack_bonus") or (prof_bonus + ability_mod)

        return CharacterSpellcasting(
            ability=ability,
            spell_save_dc=final_dc,
            spell_attack_bonus=final_attack_bonus,
            spellcasting_type=get_spellcasting_type(class_name),
            spell_slots_max=spell_slots,
            spell_slots_used=spell_data.get("spell_slots_used", {}),
            cantrips_known=to_spell_ids(spell_data.get("cantrips_known", spell_data.get("cantrips", []))),
            spells_known=to_spell_ids(spell_data.get("spells_known", [])),
            spellbook=to_spell_ids(spell_data.get("spellbook", [])),
            prepared_spells=to_spell_ids(spell_data.get("prepared_spells", [])),
            max_prepared=spell_data.get("max_prepared") or get_max_prepared_spells(
                class_name, level, ability_mod
            ),
            concentrating_on=spell_data.get("concentrating_on"),
            concentration_start_round=spell_data.get("concentration_start_round"),
        )

    def can_cast_spell(
        self,
        spell_id: str,
        slot_level: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Check if character can cast a spell.

        Args:
            spell_id: ID of the spell to cast
            slot_level: Level of slot to use (None for cantrips)

        Returns:
            Tuple of (can_cast, reason_if_not)
        """
        spell = self._registry.get_spell(spell_id)
        if not spell:
            return False, f"Unknown spell: {spell_id}"

        # Check if it's a cantrip
        if spell.level == 0:
            # Must know the cantrip - cantrips_known may contain dicts or strings
            cantrip_known = False
            for cantrip in self.spellcasting.cantrips_known:
                if isinstance(cantrip, dict):
                    # Handle dict format: {"name": "Sacred Flame", "level": 0, ...}
                    cantrip_id = cantrip.get('id') or cantrip.get('name', '').lower().replace(' ', '_')
                    if cantrip_id == spell.id:
                        cantrip_known = True
                        break
                elif cantrip == spell.id:
                    # Handle string format: "sacred_flame"
                    cantrip_known = True
                    break

            if not cantrip_known:
                return False, f"You don't know the cantrip {spell.name}"
            return True, ""

        # For leveled spells, check preparation/known
        # Helper to check if spell_id is in a list of dicts or strings
        def spell_in_list(spell_id: str, spell_list: list) -> bool:
            for item in spell_list:
                if isinstance(item, dict):
                    item_id = item.get('id') or item.get('name', '').lower().replace(' ', '_')
                    if item_id == spell_id:
                        return True
                elif item == spell_id:
                    return True
            return False

        is_prepared = spell_in_list(spell.id, self.spellcasting.prepared_spells)
        is_known = spell_in_list(spell.id, self.spellcasting.spells_known)

        if self.spellcasting.spellcasting_type == SpellcastingType.PREPARED:
            if not is_prepared:
                return False, f"{spell.name} is not prepared"
        elif self.spellcasting.spellcasting_type in [SpellcastingType.KNOWN, SpellcastingType.PACT_MAGIC]:
            if not is_known and not is_prepared:
                return False, f"You don't know the spell {spell.name}"

        # Check slot level
        cast_level = slot_level or spell.level
        if cast_level < spell.level:
            return False, f"{spell.name} requires at least a {spell.level}-level slot"

        # Check if we have a slot
        if not self.spellcasting.has_slot(cast_level):
            return False, f"No {cast_level}-level spell slots remaining"

        return True, ""

    def get_available_spells(self) -> List[Spell]:
        """Get all spells the character can currently cast."""
        available = []

        # Helper to extract spell ID from string or dict
        def get_spell_id(item):
            if isinstance(item, dict):
                # Try 'id' first, then 'name' (lowercased, hyphenated for registry lookup)
                return item.get('id') or item.get('name', '').lower().replace(' ', '_')
            return item

        # Debug logging
        print(f"[SpellCaster] get_available_spells - cantrips_known: {self.spellcasting.cantrips_known}")
        print(f"[SpellCaster] Registry has {len(self._registry._spells)} spells loaded")

        # Add cantrips (filter out non-combat usable ones like Mending with 1-minute cast time)
        for cantrip in self.spellcasting.cantrips_known:
            cantrip_id = get_spell_id(cantrip)
            spell = self._registry.get_spell(cantrip_id)
            print(f"[SpellCaster] Looking up cantrip '{cantrip_id}': {'FOUND' if spell else 'NOT FOUND'}")
            if spell and spell.combat_usable:
                available.append(spell)
            elif spell:
                print(f"[SpellCaster] Skipping cantrip '{cantrip_id}' - not combat usable")

        # Add prepared/known spells that have available slots
        spell_list = (
            self.spellcasting.prepared_spells
            if self.spellcasting.spellcasting_type == SpellcastingType.PREPARED
            else self.spellcasting.spells_known
        )

        for spell_item in spell_list:
            spell_id = get_spell_id(spell_item)
            spell = self._registry.get_spell(spell_id)
            if spell and spell.level > 0:
                # Check if we have any slot that can cast it
                for level in range(spell.level, 10):
                    if self.spellcasting.has_slot(level):
                        available.append(spell)
                        break

        return available

    def start_concentration(self, spell_id: str, round_num: int):
        """Start concentrating on a spell."""
        self.spellcasting.concentrating_on = spell_id
        self.spellcasting.concentration_start_round = round_num

    def end_concentration(self) -> Optional[str]:
        """End concentration, returning the spell ID that was dropped."""
        old_spell = self.spellcasting.concentrating_on
        self.spellcasting.concentrating_on = None
        self.spellcasting.concentration_start_round = None
        return old_spell

    def check_concentration(self, damage_taken: int, con_mod: int = 0, prof_bonus: int = 0, is_proficient: bool = False) -> Tuple[bool, int, int]:
        """
        Make a concentration check.

        Args:
            damage_taken: Damage that triggered the check
            con_mod: Constitution modifier
            prof_bonus: Proficiency bonus
            is_proficient: Whether proficient in CON saves

        Returns:
            Tuple of (maintained, roll, dc)
        """
        if not self.spellcasting.concentrating_on:
            return True, 0, 0

        dc = max(10, damage_taken // 2)
        roll_result = roll_d20()
        total = roll_result.total + con_mod
        if is_proficient:
            total += prof_bonus

        maintained = total >= dc
        return maintained, roll_result.total, dc

    def prepare_spells(self, spell_ids: List[str]) -> Tuple[bool, str]:
        """
        Prepare spells for the day.

        Args:
            spell_ids: List of spell IDs to prepare

        Returns:
            Tuple of (success, message)
        """
        if self.spellcasting.spellcasting_type != SpellcastingType.PREPARED:
            return False, "Your class doesn't prepare spells"

        if len(spell_ids) > self.spellcasting.max_prepared:
            return False, f"Can only prepare {self.spellcasting.max_prepared} spells"

        # Validate all spells
        class_name = self.character.get("class", "").lower()
        max_spell_level = max(self.spellcasting.spell_slots_max.keys()) if self.spellcasting.spell_slots_max else 0

        for spell_id in spell_ids:
            spell = self._registry.get_spell(spell_id)
            if not spell:
                return False, f"Unknown spell: {spell_id}"

            if spell.level == 0:
                return False, f"Cantrips don't need to be prepared: {spell.name}"

            if spell.level > max_spell_level:
                return False, f"Cannot prepare {spell.name} - spell level too high"

            # Check class access
            if class_name not in [c.lower() for c in spell.classes]:
                return False, f"{spell.name} is not on your class spell list"

        self.spellcasting.prepared_spells = spell_ids
        return True, f"Prepared {len(spell_ids)} spells"

    def to_dict(self) -> Dict:
        """Export spellcasting state to dict for saving."""
        return {
            "ability": self.spellcasting.ability,
            "spell_save_dc": self.spellcasting.spell_save_dc,
            "spell_attack_bonus": self.spellcasting.spell_attack_bonus,
            "spell_slots": self.spellcasting.spell_slots_max,
            "spell_slots_used": self.spellcasting.spell_slots_used,
            "cantrips_known": self.spellcasting.cantrips_known,  # Use consistent key name
            "cantrips": self.spellcasting.cantrips_known,  # Keep for backward compatibility
            "spells_known": self.spellcasting.spells_known,
            "spellbook": self.spellcasting.spellbook,
            "prepared_spells": self.spellcasting.prepared_spells,
            "max_prepared": self.spellcasting.max_prepared,
            "concentrating_on": self.spellcasting.concentrating_on,
            "concentration_start_round": self.spellcasting.concentration_start_round,
        }


class SpellEffectResolver:
    """
    Resolves spell effects in combat.

    Handles attack rolls, saving throws, damage, and healing calculations.
    """

    @staticmethod
    def resolve_attack_spell(
        spell: Spell,
        spell_attack_bonus: int,
        target_ac: int,
        caster_level: int = 1,
        slot_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a spell attack.

        Returns dict with: hit, critical, attack_roll, attack_total, damage
        """
        attack_roll = roll_d20()
        attack_total = attack_roll.total + spell_attack_bonus

        critical = attack_roll.natural_20
        hit = critical or (attack_total >= target_ac and not attack_roll.natural_1)

        result = {
            "hit": hit,
            "critical": critical,
            "attack_roll": attack_roll.total,
            "attack_total": attack_total,
            "damage": 0,
            "damage_type": spell.damage_type,
        }

        if hit and spell.damage_dice:
            # Calculate damage dice with scaling
            damage_dice = SpellEffectResolver._calculate_spell_damage(
                spell, caster_level, slot_level
            )

            damage_result = roll_damage(damage_dice, critical=critical)
            result["damage"] = damage_result.total
            result["damage_dice"] = damage_dice

        return result

    @staticmethod
    def resolve_save_spell(
        spell: Spell,
        spell_save_dc: int,
        target_save_bonus: int,
        caster_level: int = 1,
        slot_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a saving throw spell for one target.

        Returns dict with: saved, save_roll, save_total, damage (if applicable)
        """
        save_roll = roll_d20()
        save_total = save_roll.total + target_save_bonus

        saved = save_total >= spell_save_dc

        # DEBUG: Log the save roll details
        print(f"[SPELL SAVE] {spell.name}: Target rolled {save_roll.total} + {target_save_bonus} = {save_total} vs DC {spell_save_dc} -> {'SAVED' if saved else 'FAILED'}")

        result = {
            "saved": saved,
            "save_roll": save_roll.total,
            "save_total": save_total,
            "save_dc": spell_save_dc,
            "save_type": spell.save_type,
            "damage": 0,
            "damage_type": spell.damage_type,
        }

        # DEBUG: Log damage_dice to verify it's set
        print(f"[SPELL SAVE] {spell.name} damage_dice={spell.damage_dice}, damage_type={spell.damage_type}")

        if spell.damage_dice:
            damage_dice = SpellEffectResolver._calculate_spell_damage(
                spell, caster_level, slot_level
            )
            damage_result = roll_damage(damage_dice)
            print(f"[SPELL SAVE] Rolled damage: {damage_dice} -> {damage_result.total}")

            if saved:
                # Cantrips (level 0) deal NO damage on successful save
                # Higher-level spells typically deal half damage on save
                # Check for explicit half_damage_on_save property, else use level-based default
                half_damage = getattr(spell, 'half_damage_on_save', spell.level > 0)
                if half_damage:
                    result["damage"] = damage_result.total // 2
                else:
                    result["damage"] = 0  # No damage for cantrips on successful save
            else:
                result["damage"] = damage_result.total

            result["damage_dice"] = damage_dice
            result["damage_rolls"] = damage_result.rolls  # Individual die values for animation

        return result

    @staticmethod
    def resolve_healing_spell(
        spell: Spell,
        ability_mod: int,
        caster_level: int = 1,
        slot_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a healing spell.

        Returns dict with: healing amount
        """
        healing_dice = spell.healing_dice or "1d8"

        # Handle upcasting for healing
        if slot_level and slot_level > spell.level:
            extra_dice = slot_level - spell.level
            base_match = re.match(r'(\d+)d(\d+)', healing_dice)
            if base_match:
                num_dice = int(base_match.group(1)) + extra_dice
                die_size = base_match.group(2)
                healing_dice = f"{num_dice}d{die_size}"

        healing_result = roll_damage(healing_dice)
        total_healing = healing_result.total + ability_mod

        return {
            "healing": max(0, total_healing),
            "healing_dice": healing_dice,
            "ability_mod_added": ability_mod,
        }

    @staticmethod
    def _calculate_spell_damage(
        spell: Spell,
        caster_level: int,
        slot_level: Optional[int] = None
    ) -> str:
        """Calculate damage dice accounting for level and upcasting."""
        if not spell.damage_dice:
            return "0"

        damage_dice = spell.damage_dice

        # Cantrip scaling
        if spell.level == 0:
            base_match = re.match(r'(\d+)d(\d+)', damage_dice)
            if base_match:
                base_dice = int(base_match.group(1))
                die_size = base_match.group(2)

                # Cantrips scale at 5, 11, 17
                if caster_level >= 17:
                    num_dice = base_dice * 4
                elif caster_level >= 11:
                    num_dice = base_dice * 3
                elif caster_level >= 5:
                    num_dice = base_dice * 2
                else:
                    num_dice = base_dice

                damage_dice = f"{num_dice}d{die_size}"

        # Upcasting (leveled spells)
        elif slot_level and slot_level > spell.level and spell.higher_levels:
            # Parse higher level scaling from description
            extra_levels = slot_level - spell.level
            base_match = re.match(r'(\d+)d(\d+)', damage_dice)

            if base_match:
                num_dice = int(base_match.group(1))
                die_size = base_match.group(2)

                # Most spells add 1 die per slot level
                # Check for different scaling patterns
                if "1d" in spell.higher_levels.lower():
                    num_dice += extra_levels
                elif "2d" in spell.higher_levels.lower():
                    num_dice += extra_levels * 2

                damage_dice = f"{num_dice}d{die_size}"

        return damage_dice

    @staticmethod
    def resolve_area_spell(
        spell: Spell,
        spell_save_dc: int,
        targets: List[Dict],
        caster_level: int = 1,
        slot_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Resolve an area effect spell (Fireball, Lightning Bolt, etc.).

        Each target in the area makes a saving throw. Damage is rolled once
        and applied to all targets (half on successful save for most spells).

        Args:
            spell: The spell being cast
            spell_save_dc: Caster's spell save DC
            targets: List of targets in the area
            caster_level: Caster's level
            slot_level: Slot level used (for upcasting)

        Returns:
            Dict with area effect results
        """
        # Calculate damage dice once for the whole area
        damage_dice = SpellEffectResolver._calculate_spell_damage(
            spell, caster_level, slot_level
        )

        # Roll damage once (same damage for all targets)
        base_damage_result = roll_damage(damage_dice)
        base_damage = base_damage_result.total

        result = {
            "damage_dice": damage_dice,
            "base_damage": base_damage,
            "save_dc": spell_save_dc,
            "save_type": spell.save_type,
            "damage_type": spell.damage_type,
            "targets": {},
            "total_damage": 0,
            "saves_made": 0,
            "saves_failed": 0,
        }

        for target in targets:
            target_id = target.get("id", "unknown")
            # Use helper to get save mod from various possible field names
            save_mod = _get_target_save_modifier(target, spell.save_type) if spell.save_type else 0

            # Roll save for each target
            save_roll = roll_d20()
            save_total = save_roll.total + save_mod
            saved = save_total >= spell_save_dc

            # Calculate damage based on save
            if saved:
                target_damage = base_damage // 2  # Half damage on save
                result["saves_made"] += 1
            else:
                target_damage = base_damage
                result["saves_failed"] += 1

            result["targets"][target_id] = {
                "name": target.get("name", "Unknown"),
                "save_roll": save_roll.total,
                "save_total": save_total,
                "saved": saved,
                "damage": target_damage,
            }
            result["total_damage"] += target_damage

        return result

    @staticmethod
    def resolve_buff_spell(
        spell: Spell,
        targets: List[Dict],
        caster_level: int = 1,
        current_round: int = 1,
    ) -> Dict[str, Any]:
        """
        Resolve a buff spell (Bless, Shield of Faith, etc.).

        Returns effect data that should be tracked for duration.

        Args:
            spell: The buff spell
            targets: Targets receiving the buff
            caster_level: Caster's level
            current_round: Current combat round

        Returns:
            Dict with buff effect data
        """
        # Parse duration in rounds (concentration spells last until concentration ends)
        duration_rounds = SpellEffectResolver._parse_duration(spell.duration)

        # Determine buff effects based on spell
        buff_effects = SpellEffectResolver._determine_buff_effects(spell)

        result = {
            "spell_id": spell.id,
            "spell_name": spell.name,
            "concentration": spell.concentration,
            "duration_rounds": duration_rounds,
            "start_round": current_round,
            "end_round": current_round + duration_rounds if duration_rounds else None,
            "effects": buff_effects,
            "targets": {},
        }

        for target in targets:
            target_id = target.get("id", "unknown")
            result["targets"][target_id] = {
                "name": target.get("name", "Unknown"),
                "active": True,
                "applied_effects": buff_effects,
            }

        return result

    @staticmethod
    def resolve_condition_spell(
        spell: Spell,
        spell_save_dc: int,
        targets: List[Dict],
        caster_level: int = 1,
        current_round: int = 1,
    ) -> Dict[str, Any]:
        """
        Resolve a spell that applies conditions (Hold Person, etc.).

        Args:
            spell: The condition spell
            spell_save_dc: Caster's spell save DC
            targets: Targets of the spell
            caster_level: Caster's level
            current_round: Current combat round

        Returns:
            Dict with condition application results
        """
        duration_rounds = SpellEffectResolver._parse_duration(spell.duration)

        result = {
            "spell_id": spell.id,
            "spell_name": spell.name,
            "save_dc": spell_save_dc,
            "save_type": spell.save_type,
            "concentration": spell.concentration,
            "conditions": spell.conditions_applied or [],
            "duration_rounds": duration_rounds,
            "start_round": current_round,
            "targets": {},
            "conditions_applied_count": 0,
            "saves_made": 0,
        }

        for target in targets:
            target_id = target.get("id", "unknown")
            # Use helper to get save mod from various possible field names
            save_mod = _get_target_save_modifier(target, spell.save_type) if spell.save_type else 0

            # Roll initial save
            save_roll = roll_d20()
            save_total = save_roll.total + save_mod
            saved = save_total >= spell_save_dc

            target_result = {
                "name": target.get("name", "Unknown"),
                "save_roll": save_roll.total,
                "save_total": save_total,
                "saved": saved,
                "conditions_applied": [],
            }

            if not saved and spell.conditions_applied:
                target_result["conditions_applied"] = spell.conditions_applied
                result["conditions_applied_count"] += 1
            else:
                result["saves_made"] += 1

            result["targets"][target_id] = target_result

        return result

    @staticmethod
    def _parse_duration(duration_str: str) -> Optional[int]:
        """Parse spell duration into rounds."""
        if not duration_str:
            return None

        duration_lower = duration_str.lower()

        if "instantaneous" in duration_lower:
            return 0

        # Parse minutes to rounds (1 minute = 10 rounds)
        minute_match = re.search(r'(\d+)\s*minute', duration_lower)
        if minute_match:
            return int(minute_match.group(1)) * 10

        # Parse rounds
        round_match = re.search(r'(\d+)\s*round', duration_lower)
        if round_match:
            return int(round_match.group(1))

        # Parse hours to rounds (1 hour = 600 rounds)
        hour_match = re.search(r'(\d+)\s*hour', duration_lower)
        if hour_match:
            return int(hour_match.group(1)) * 600

        # Concentration spells without explicit duration
        if "concentration" in duration_lower:
            return 100  # Default to 10 minutes (100 rounds)

        return None

    @staticmethod
    def _determine_buff_effects(spell: Spell) -> Dict[str, Any]:
        """Determine mechanical effects of a buff spell."""
        effects = {}
        description = spell.description.lower()

        # Bless: +1d4 to attack rolls and saving throws
        if "bless" in spell.id or "1d4" in description and "attack" in description:
            effects["attack_bonus_dice"] = "1d4"
            effects["save_bonus_dice"] = "1d4"

        # Shield of Faith: +2 AC
        if "shield of faith" in spell.id or "+2 bonus to ac" in description:
            effects["ac_bonus"] = 2

        # Haste: Various bonuses
        if "haste" in spell.id:
            effects["ac_bonus"] = 2
            effects["advantage_dex_saves"] = True
            effects["extra_action"] = True
            effects["speed_multiplier"] = 2

        # Heroism: Temp HP and immunity to frightened
        if "heroism" in spell.id:
            effects["temp_hp_per_round"] = True
            effects["immunity"] = ["frightened"]

        # Mage Armor: AC = 13 + DEX
        if "mage armor" in spell.id:
            effects["base_ac"] = 13

        # Guidance: +1d4 to ability checks
        if "guidance" in spell.id:
            effects["ability_check_bonus_dice"] = "1d4"

        # Resistance: +1d4 to saving throws (single use)
        if "resistance" in spell.id and spell.level == 0:
            effects["save_bonus_dice"] = "1d4"
            effects["single_use"] = True

        # Protection from Evil and Good
        if "protection from evil" in spell.id:
            effects["attack_disadvantage_from"] = ["aberration", "celestial", "elemental", "fey", "fiend", "undead"]
            effects["charm_immunity_from"] = ["aberration", "celestial", "elemental", "fey", "fiend", "undead"]

        return effects


def _get_target_save_modifier(target: Dict, save_type: Optional[str]) -> int:
    """
    Get the save modifier for a target against a specific saving throw type.

    Handles multiple naming conventions:
    - dexterity_save, dex_save (explicit save bonus)
    - dex_mod, dexterity_mod (ability modifier)
    - dex, dexterity (ability score)

    Args:
        target: Target's data dict
        save_type: Save type (e.g., "dexterity", "dex", "wisdom", etc.)

    Returns:
        Save modifier (int)
    """
    if not save_type:
        return 0

    save_type_lower = save_type.lower()

    # Map abbreviated to full names
    ABILITY_MAP = {
        "str": "strength", "strength": "strength",
        "dex": "dexterity", "dexterity": "dexterity",
        "con": "constitution", "constitution": "constitution",
        "int": "intelligence", "intelligence": "intelligence",
        "wis": "wisdom", "wisdom": "wisdom",
        "cha": "charisma", "charisma": "charisma",
    }

    # Get both short and full ability names
    full_name = ABILITY_MAP.get(save_type_lower, save_type_lower)
    short_name = save_type_lower[:3]

    # Try to find save modifier in order of preference:
    # 1. Explicit save bonus (e.g., "dexterity_save", "dex_save")
    save_mod = target.get(f"{full_name}_save")
    if save_mod is not None:
        return save_mod

    save_mod = target.get(f"{short_name}_save")
    if save_mod is not None:
        return save_mod

    # 2. Ability modifier (e.g., "dex_mod", "dexterity_mod")
    ability_mod = target.get(f"{short_name}_mod")
    if ability_mod is not None:
        return ability_mod

    ability_mod = target.get(f"{full_name}_mod")
    if ability_mod is not None:
        return ability_mod

    # 3. Calculate from ability score
    ability_score = target.get(full_name) or target.get(short_name)
    if ability_score is not None:
        return (ability_score - 10) // 2

    # 4. Check in abilities dict
    abilities = target.get("abilities", {})
    ability_score = abilities.get(full_name) or abilities.get(short_name)
    if ability_score is not None:
        return (ability_score - 10) // 2

    # Default to 0 if nothing found
    return 0


def cast_spell(
    caster_data: Dict,
    spell_id: str,
    slot_level: Optional[int],
    targets: List[Dict],
    combat_state: Optional[Dict] = None,
) -> SpellCastResult:
    """
    High-level function to cast a spell.

    Args:
        caster_data: Caster's character data
        spell_id: ID of spell to cast
        slot_level: Slot level to use (None for cantrips)
        targets: List of target dictionaries
        combat_state: Optional combat state for round tracking

    Returns:
        SpellCastResult with all casting information
    """
    registry = SpellRegistry.get_instance()
    spell = registry.get_spell(spell_id)

    if not spell:
        return SpellCastResult(
            success=False,
            spell_id=spell_id,
            spell_name="Unknown",
            caster_id=caster_data.get("id", ""),
            caster_name=caster_data.get("name", "Unknown"),
            description=f"Unknown spell: {spell_id}"
        )

    # Create SpellCaster for validation
    spell_caster = SpellCaster(caster_data)

    # Validate casting
    can_cast, reason = spell_caster.can_cast_spell(spell_id, slot_level)
    if not can_cast:
        return SpellCastResult(
            success=False,
            spell_id=spell.id,
            spell_name=spell.name,
            caster_id=caster_data.get("id", ""),
            caster_name=caster_data.get("name", "Unknown"),
            description=reason
        )

    # Determine actual slot level
    cast_level = slot_level or spell.level
    caster_level = caster_data.get("level", 1)

    # Handle concentration
    concentration_ended = None
    if spell.concentration and spell_caster.spellcasting.concentrating_on:
        concentration_ended = spell_caster.end_concentration()

    # Resolve spell effect based on type
    result = SpellCastResult(
        success=True,
        spell_id=spell.id,
        spell_name=spell.name,
        slot_used=cast_level if spell.level > 0 else None,
        caster_id=caster_data.get("id", ""),
        caster_name=caster_data.get("name", "Unknown"),
        damage_type=spell.damage_type,
        # Initialize these to empty dicts to ensure they're never null in the response
        damage_dealt={},
        save_results={},
    )

    if spell.attack_type and targets:
        # Attack spell
        target = targets[0]
        attack_result = SpellEffectResolver.resolve_attack_spell(
            spell,
            spell_caster.spellcasting.spell_attack_bonus,
            target.get("ac", 10),
            caster_level,
            cast_level
        )

        result.attack_roll = attack_result["attack_roll"]
        result.attack_total = attack_result["attack_total"]
        result.hit = attack_result["hit"]
        result.critical = attack_result["critical"]

        if attack_result["hit"]:
            result.damage_dealt = {target.get("id", "target"): attack_result["damage"]}
            result.description = f"{result.caster_name} casts {spell.name}! Hits for {attack_result['damage']} {spell.damage_type} damage!"
        else:
            result.description = f"{result.caster_name} casts {spell.name}... but misses!"

    elif spell.save_type and targets:
        # Saving throw spell
        result.save_dc = spell_caster.spellcasting.spell_save_dc
        result.save_type = spell.save_type
        result.save_results = {}
        result.damage_dealt = {}

        # Check if this is an area spell (Fireball, etc.)
        is_area_spell = spell.target_type in [
            SpellTargetType.AREA_SPHERE, SpellTargetType.AREA_CONE,
            SpellTargetType.AREA_LINE, SpellTargetType.AREA_CUBE,
            SpellTargetType.AREA_CYLINDER
        ]

        if is_area_spell and spell.damage_dice:
            # Use area spell resolution (roll damage once, apply to all)
            area_result = SpellEffectResolver.resolve_area_spell(
                spell,
                result.save_dc,
                targets,
                caster_level,
                cast_level
            )

            for target_id, target_result in area_result["targets"].items():
                result.save_results[target_id] = {
                    "roll": target_result["save_roll"],
                    "total": target_result["save_total"],
                    "saved": target_result["saved"]
                }
                if target_result["damage"] > 0:
                    result.damage_dealt[target_id] = target_result["damage"]

            result.description = (
                f"{result.caster_name} casts {spell.name}! "
                f"({area_result['base_damage']} base damage) "
                f"{area_result['saves_failed']}/{len(targets)} fail their saves for "
                f"{area_result['total_damage']} total damage!"
            )

        elif spell.conditions_applied:
            # Condition-applying spell (Hold Person, etc.)
            current_round = combat_state.get("round_number", 1) if combat_state else 1
            condition_result = SpellEffectResolver.resolve_condition_spell(
                spell,
                result.save_dc,
                targets,
                caster_level,
                current_round
            )

            result.conditions_applied = {}
            for target_id, target_result in condition_result["targets"].items():
                result.save_results[target_id] = {
                    "roll": target_result["save_roll"],
                    "total": target_result["save_total"],
                    "saved": target_result["saved"]
                }
                if target_result["conditions_applied"]:
                    result.conditions_applied[target_id] = target_result["conditions_applied"]

            result.description = (
                f"{result.caster_name} casts {spell.name}! "
                f"{condition_result['conditions_applied_count']}/{len(targets)} fail and are "
                f"{', '.join(condition_result['conditions'])}!"
            )

        else:
            # Standard single-target save spells
            for target in targets:
                # Get save modifier - try explicit save key first, then calculate from ability mod
                save_mod = _get_target_save_modifier(target, spell.save_type)
                save_result = SpellEffectResolver.resolve_save_spell(
                    spell,
                    result.save_dc,
                    save_mod,
                    caster_level,
                    cast_level
                )

                target_id = target.get("id", "target")
                result.save_results[target_id] = {
                    "roll": save_result["save_roll"],
                    "total": save_result["save_total"],
                    "saved": save_result["saved"]
                }

                if save_result["damage"] > 0:
                    result.damage_dealt[target_id] = save_result["damage"]

                # Store damage dice info for frontend animation
                if save_result.get("damage_dice"):
                    result.damage_dice = save_result["damage_dice"]
                if save_result.get("damage_rolls"):
                    result.damage_rolls = save_result["damage_rolls"]

            total_damage = sum(result.damage_dealt.values())
            saves = sum(1 for r in result.save_results.values() if r["saved"])
            result.description = f"{result.caster_name} casts {spell.name}! {len(targets) - saves}/{len(targets)} fail their saves for {total_damage} total damage!"

    elif spell.healing_dice and targets:
        # Healing spell
        ability_mod = (caster_data.get("stats", {}).get(spell_caster.spellcasting.ability, 10) - 10) // 2
        healing_result = SpellEffectResolver.resolve_healing_spell(
            spell, ability_mod, caster_level, cast_level
        )

        result.healing_done = {}
        for target in targets:
            result.healing_done[target.get("id", "target")] = healing_result["healing"]

        result.description = f"{result.caster_name} casts {spell.name}! Heals for {healing_result['healing']} HP!"

    else:
        # Utility/buff/debuff spell
        current_round = combat_state.get("round_number", 1) if combat_state else 1

        if spell.effect_type == SpellEffectType.BUFF and targets:
            # Buff spell - resolve and track effects
            buff_result = SpellEffectResolver.resolve_buff_spell(
                spell, targets, caster_level, current_round
            )

            result.buff_effects = buff_result["effects"]
            result.description = f"{result.caster_name} casts {spell.name} on {len(targets)} target(s)!"

            # Store buff data for duration tracking
            if hasattr(result, 'extra_data'):
                result.extra_data["buff"] = buff_result
            else:
                result.extra_data = {"buff": buff_result}

        elif spell.conditions_applied and targets:
            # Condition-applying utility spell (no save required)
            result.conditions_applied = {}
            for target in targets:
                result.conditions_applied[target.get("id", "target")] = spell.conditions_applied
            result.description = f"{result.caster_name} casts {spell.name}!"

        else:
            result.description = f"{result.caster_name} casts {spell.name}!"

    # Handle concentration
    if spell.concentration:
        round_num = combat_state.get("round_number", 1) if combat_state else 1
        spell_caster.start_concentration(spell.id, round_num)
        result.concentration_started = True

    if concentration_ended:
        result.concentration_ended = concentration_ended

    # Use spell slot
    if spell.level > 0:
        spell_caster.spellcasting.use_slot(cast_level)

    return result


# =============================================================================
# METAMAGIC INTEGRATION
# =============================================================================

def cast_spell_with_metamagic(
    caster_data: Dict,
    spell_id: str,
    slot_level: Optional[int],
    targets: List[Dict],
    combat_state: Optional[Dict] = None,
    metamagic_options: Optional[List[str]] = None,
    sorcery_state: Optional[Dict] = None,
) -> Tuple[SpellCastResult, Dict[str, Any]]:
    """
    Cast a spell with optional Metamagic applied.

    Args:
        caster_data: Caster's character data
        spell_id: ID of spell to cast
        slot_level: Slot level to use (None for cantrips)
        targets: List of target dictionaries
        combat_state: Optional combat state for round tracking
        metamagic_options: List of metamagic IDs to apply (e.g., ["twinned_spell"])
        sorcery_state: Sorcery point state dict (from sorcerer_features)

    Returns:
        Tuple of (SpellCastResult, metamagic_info_dict)
    """
    from app.core.sorcerer_features import (
        MetamagicType, SorceryPointState, use_metamagic,
        can_use_metamagic, METAMAGIC_OPTIONS
    )

    metamagic_info = {
        "applied": [],
        "points_spent": 0,
        "effects": [],
        "errors": [],
    }

    # If no metamagic, just cast normally
    if not metamagic_options or not sorcery_state:
        result = cast_spell(caster_data, spell_id, slot_level, targets, combat_state)
        return result, metamagic_info

    # Get spell info for validation
    registry = SpellRegistry.get_instance()
    spell = registry.get_spell(spell_id)
    if not spell:
        result = cast_spell(caster_data, spell_id, slot_level, targets, combat_state)
        return result, metamagic_info

    spell_level = slot_level or spell.level

    # Convert dict to SorceryPointState
    state = SorceryPointState.from_dict(sorcery_state)

    # Track modifications to apply
    use_bonus_action = False  # Quickened
    add_second_target = False  # Twinned
    no_components = False  # Subtle
    double_range = False  # Distant
    heighten_saves = False  # Heightened
    reroll_damage = False  # Empowered
    double_duration = False  # Extended
    careful_creatures = []  # Careful
    transmuted_damage_type = None  # Transmuted
    can_reroll_attack = False  # Seeking

    # Process each metamagic option
    for mm_id in metamagic_options:
        try:
            mm_type = MetamagicType(mm_id)
        except ValueError:
            metamagic_info["errors"].append(f"Unknown metamagic: {mm_id}")
            continue

        # Check if can use
        can_use, reason = can_use_metamagic(state, mm_type, spell_level)
        if not can_use:
            metamagic_info["errors"].append(f"{mm_type.value}: {reason}")
            continue

        # Validate metamagic applicability
        valid, validation_error = _validate_metamagic_for_spell(mm_type, spell, targets)
        if not valid:
            metamagic_info["errors"].append(validation_error)
            continue

        # Apply metamagic
        success, msg, effect_data = use_metamagic(state, mm_type, spell_level)
        if success:
            metamagic_info["applied"].append(mm_type.value)
            metamagic_info["points_spent"] += effect_data.get("cost", 0)
            metamagic_info["effects"].append(effect_data)

            # Set flags based on metamagic type
            if mm_type == MetamagicType.QUICKENED:
                use_bonus_action = True
            elif mm_type == MetamagicType.TWINNED:
                add_second_target = True
            elif mm_type == MetamagicType.SUBTLE:
                no_components = True
            elif mm_type == MetamagicType.DISTANT:
                double_range = True
            elif mm_type == MetamagicType.HEIGHTENED:
                heighten_saves = True
            elif mm_type == MetamagicType.EMPOWERED:
                reroll_damage = True
            elif mm_type == MetamagicType.EXTENDED:
                double_duration = True
            elif mm_type == MetamagicType.CAREFUL:
                careful_creatures = True  # Set in targets
            elif mm_type == MetamagicType.SEEKING:
                can_reroll_attack = True

    # Update sorcery state in the dict
    sorcery_state.update(state.to_dict())

    # Cast the spell with modifications
    # For Twinned Spell, we cast on two targets
    if add_second_target and len(targets) >= 2:
        # Cast on first target
        result1 = cast_spell(caster_data, spell_id, slot_level, [targets[0]], combat_state)
        # Cast on second target (without using another slot)
        result2 = cast_spell(caster_data, spell_id, slot_level, [targets[1]], combat_state)

        # Combine results
        result = result1
        result.description += f" (Twinned: Also affects {targets[1].get('name', 'second target')})"
        if result2.damage_dealt:
            result.damage_dealt.update(result2.damage_dealt)
        if result2.healing_done:
            result.healing_done.update(result2.healing_done)
    else:
        result = cast_spell(caster_data, spell_id, slot_level, targets, combat_state)

    # Apply metamagic effects to result
    if metamagic_info["applied"]:
        applied_names = [METAMAGIC_OPTIONS[MetamagicType(m)].name for m in metamagic_info["applied"]]
        metamagic_str = ", ".join(applied_names)
        result.description = f"[{metamagic_str}] {result.description}"

        # Add metamagic flags to result
        if result.extra_data is None:
            result.extra_data = {}

        result.extra_data["metamagic"] = {
            "applied": metamagic_info["applied"],
            "points_spent": metamagic_info["points_spent"],
            "quickened": use_bonus_action,
            "subtle": no_components,
            "distant": double_range,
            "heightened": heighten_saves,
            "empowered": reroll_damage,
            "extended": double_duration,
            "seeking": can_reroll_attack,
        }

    return result, metamagic_info


def _validate_metamagic_for_spell(
    metamagic: "MetamagicType",
    spell: Spell,
    targets: List[Dict]
) -> Tuple[bool, str]:
    """
    Validate that a metamagic option can be applied to a specific spell.

    Args:
        metamagic: The metamagic type
        spell: The spell being cast
        targets: List of targets

    Returns:
        Tuple of (is_valid, error_message)
    """
    from app.core.sorcerer_features import MetamagicType

    if metamagic == MetamagicType.TWINNED:
        # Twinned: Only works on single-target spells that don't have range of self
        if spell.target_type in [SpellTargetType.SELF, SpellTargetType.AREA_SPHERE,
                                  SpellTargetType.AREA_CONE, SpellTargetType.AREA_LINE,
                                  SpellTargetType.AREA_CUBE, SpellTargetType.AREA_CYLINDER]:
            return False, "Twinned Spell only works on single-target spells"
        if len(targets) < 2:
            return False, "Twinned Spell requires two targets"

    elif metamagic == MetamagicType.QUICKENED:
        # Quickened: Only works on spells with 1 action casting time
        # Handle various formats: "1 action", "Action", "1 Action", etc.
        casting_time_lower = spell.casting_time.lower() if spell.casting_time else ""
        is_action = "action" in casting_time_lower and "bonus" not in casting_time_lower and "reaction" not in casting_time_lower
        if not is_action:
            return False, "Quickened Spell only works on spells with 1 action casting time"

    elif metamagic == MetamagicType.EXTENDED:
        # Extended: Only works on spells with 1 minute or longer duration
        duration = spell.duration.lower() if spell.duration else ""
        if "instant" in duration or "1 round" in duration:
            return False, "Extended Spell only works on spells with duration 1 minute or longer"

    elif metamagic == MetamagicType.HEIGHTENED:
        # Heightened: Only works on spells that force saving throws
        if not spell.save_type:
            return False, "Heightened Spell only works on spells that force saving throws"

    elif metamagic == MetamagicType.EMPOWERED:
        # Empowered: Only works on spells that deal damage
        if not spell.damage_dice:
            return False, "Empowered Spell only works on spells that deal damage"

    elif metamagic == MetamagicType.SEEKING:
        # Seeking: Only works on spells that make attack rolls
        if not spell.attack_type:
            return False, "Seeking Spell only works on spells that make attack rolls"

    elif metamagic == MetamagicType.CAREFUL:
        # Careful: Only works on area spells that force saving throws
        if not spell.save_type:
            return False, "Careful Spell only works on spells that force saving throws"

    elif metamagic == MetamagicType.TRANSMUTED:
        # Transmuted: Only works on spells that deal acid, cold, fire, lightning, poison, or thunder
        valid_types = {"acid", "cold", "fire", "lightning", "poison", "thunder"}
        if spell.damage_type and spell.damage_type.lower() not in valid_types:
            return False, "Transmuted Spell only works on acid, cold, fire, lightning, poison, or thunder spells"

    return True, ""


def get_available_metamagic_for_spell(
    spell_id: str,
    sorcery_state: Dict,
    spell_level: int = 1
) -> List[Dict[str, Any]]:
    """
    Get list of metamagic options available for a specific spell.

    Args:
        spell_id: The spell to check
        sorcery_state: Current sorcery point state
        spell_level: Level the spell will be cast at

    Returns:
        List of available metamagic option dicts
    """
    from app.core.sorcerer_features import (
        MetamagicType, SorceryPointState, can_use_metamagic, METAMAGIC_OPTIONS
    )

    registry = SpellRegistry.get_instance()
    spell = registry.get_spell(spell_id)
    if not spell:
        return []

    state = SorceryPointState.from_dict(sorcery_state)
    available = []

    for mm_type in state.metamagic_known:
        can_use, reason = can_use_metamagic(state, mm_type, spell_level)
        valid_for_spell, spell_reason = _validate_metamagic_for_spell(mm_type, spell, [])

        option = METAMAGIC_OPTIONS.get(mm_type)
        if option:
            available.append({
                "id": mm_type.value,
                "name": option.name,
                "cost": option.get_cost(spell_level),
                "can_use": can_use and valid_for_spell,
                "reason": reason if not can_use else (spell_reason if not valid_for_spell else ""),
                "description": option.description,
                "effect": option.effect,
            })

    return available
