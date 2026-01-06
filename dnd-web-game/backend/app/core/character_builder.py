"""
D&D 2024 Character Builder.

Handles step-by-step character creation with validation following D&D 2024 rules.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import uuid

from app.services.rules_loader import get_rules_loader, RulesLoader


class CreationStep(str, Enum):
    """Character creation steps in order."""
    SPECIES = "species"
    CLASS = "class"
    BACKGROUND = "background"
    ABILITIES = "abilities"
    FEAT = "feat"
    EQUIPMENT = "equipment"
    DETAILS = "details"
    REVIEW = "review"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CharacterBuild:
    """In-progress character build state."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Core choices
    species_id: Optional[str] = None
    class_id: Optional[str] = None
    subclass_id: Optional[str] = None
    background_id: Optional[str] = None
    level: int = 1

    # Ability scores (base scores before bonuses)
    ability_scores: Dict[str, int] = field(default_factory=lambda: {
        "strength": 8, "dexterity": 8, "constitution": 8,
        "intelligence": 8, "wisdom": 8, "charisma": 8
    })
    ability_method: str = "point_buy"  # "point_buy" or "standard_array"

    # Background ability bonuses (+2/+1 or +1/+1/+1)
    ability_bonuses: Dict[str, int] = field(default_factory=dict)

    # Feats
    origin_feat_id: Optional[str] = None

    # Proficiency choices
    skill_choices: List[str] = field(default_factory=list)
    tool_choices: List[str] = field(default_factory=list)
    language_choices: List[str] = field(default_factory=list)

    # Equipment choices
    equipment_choices: List[Dict[str, Any]] = field(default_factory=list)

    # Class feature choices
    fighting_style: Optional[str] = None
    weapon_masteries: List[str] = field(default_factory=list)

    # Character details
    name: str = ""
    appearance: Optional[str] = None
    personality: Optional[str] = None
    backstory: Optional[str] = None

    # Size choice (for species that allow it)
    size: Optional[str] = None

    def get_current_step(self) -> CreationStep:
        """Determine which step the character is currently on."""
        if not self.species_id:
            return CreationStep.SPECIES
        if not self.class_id:
            return CreationStep.CLASS
        if not self.background_id:
            return CreationStep.BACKGROUND
        if not self.ability_bonuses:
            return CreationStep.ABILITIES
        if not self.origin_feat_id:
            return CreationStep.FEAT
        if not self.equipment_choices:
            return CreationStep.EQUIPMENT
        if not self.name:
            return CreationStep.DETAILS
        return CreationStep.REVIEW

    def get_final_ability_scores(self) -> Dict[str, int]:
        """Get ability scores with background bonuses applied."""
        final = dict(self.ability_scores)
        for ability, bonus in self.ability_bonuses.items():
            if ability in final:
                final[ability] = min(20, final[ability] + bonus)
        return final

    def get_ability_modifiers(self) -> Dict[str, int]:
        """Get ability modifiers from final scores."""
        scores = self.get_final_ability_scores()
        return {
            ability: (score - 10) // 2
            for ability, score in scores.items()
        }


class CharacterBuilder:
    """Builds and validates characters step by step."""

    def __init__(self):
        self.rules: RulesLoader = get_rules_loader()
        self._builds: Dict[str, CharacterBuild] = {}

    def create_new_build(self) -> CharacterBuild:
        """Create a new character build."""
        build = CharacterBuild()
        self._builds[build.id] = build
        return build

    def get_build(self, build_id: str) -> Optional[CharacterBuild]:
        """Get an existing build by ID."""
        return self._builds.get(build_id)

    def delete_build(self, build_id: str) -> bool:
        """Delete a build."""
        if build_id in self._builds:
            del self._builds[build_id]
            return True
        return False

    # ==================== Species ====================

    def set_species(self, build: CharacterBuild, species_id: str) -> ValidationResult:
        """Set the species for a character build."""
        species = self.rules.get_species(species_id)

        if not species:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown species: {species_id}"]
            )

        build.species_id = species_id

        # Set default size if species has fixed size
        size = species.get("size", "Medium")
        if "or" not in size.lower():
            build.size = size

        return ValidationResult(
            valid=True,
            data={
                "species": species,
                "size_choice_required": "or" in size.lower(),
                "traits": species.get("traits", []),
                "languages": species.get("languages", []),
                "speed": species.get("speed", 30)
            }
        )

    def set_size_choice(self, build: CharacterBuild, size: str) -> ValidationResult:
        """Set size for species that allow choice (Human, etc.)."""
        if size not in ["Small", "Medium"]:
            return ValidationResult(
                valid=False,
                errors=["Size must be 'Small' or 'Medium'"]
            )

        build.size = size
        return ValidationResult(valid=True)

    # ==================== Class ====================

    def set_class(self, build: CharacterBuild, class_id: str) -> ValidationResult:
        """Set the class for a character build."""
        class_data = self.rules.get_class(class_id)

        if not class_data:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown class: {class_id}"]
            )

        build.class_id = class_id

        # Get skill choices info
        skill_choices = class_data.get("skill_choices", {})

        return ValidationResult(
            valid=True,
            data={
                "class": class_data,
                "hit_die": class_data.get("hit_die", "d8"),
                "skill_options": skill_choices.get("options", []),
                "skill_count": skill_choices.get("count", 2),
                "armor_proficiencies": class_data.get("armor_proficiencies", []),
                "weapon_proficiencies": class_data.get("weapon_proficiencies", []),
                "features_at_level_1": self.rules.get_class_features_at_level(class_id, 1),
                "equipment_choices": self.rules.get_class_equipment_choices(class_id)
            }
        )

    def set_skill_choices(self, build: CharacterBuild, skills: List[str]) -> ValidationResult:
        """Set skill proficiency choices for the class."""
        if not build.class_id:
            return ValidationResult(
                valid=False,
                errors=["Must select a class first"]
            )

        class_data = self.rules.get_class(build.class_id)
        skill_choices = class_data.get("skill_choices", {})
        allowed_skills = skill_choices.get("options", [])
        required_count = skill_choices.get("count", 2)

        errors = []

        # Validate count
        if len(skills) != required_count:
            errors.append(f"Must select exactly {required_count} skills")

        # Validate each skill is allowed
        for skill in skills:
            if skill not in allowed_skills:
                errors.append(f"'{skill}' is not a valid skill option for this class")

        # Check for duplicates
        if len(skills) != len(set(skills)):
            errors.append("Cannot select the same skill twice")

        if errors:
            return ValidationResult(valid=False, errors=errors)

        build.skill_choices = skills
        return ValidationResult(valid=True)

    # ==================== Background ====================

    def set_background(self, build: CharacterBuild, background_id: str) -> ValidationResult:
        """Set the background for a character build."""
        background = self.rules.get_background(background_id)

        if not background:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown background: {background_id}"]
            )

        build.background_id = background_id

        ability_options = background.get("ability_score_increases", {}).get("options", [])

        return ValidationResult(
            valid=True,
            data={
                "background": background,
                "skill_proficiencies": background.get("skill_proficiencies", []),
                "origin_feat": background.get("origin_feat", ""),
                "ability_options": ability_options,
                "starting_equipment": background.get("starting_equipment", {})
            }
        )

    # ==================== Ability Scores ====================

    def set_ability_scores(
        self,
        build: CharacterBuild,
        scores: Dict[str, int],
        method: str = "point_buy"
    ) -> ValidationResult:
        """Set base ability scores."""
        ABILITIES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

        errors = []

        # Validate all abilities present
        for ability in ABILITIES:
            if ability not in scores:
                errors.append(f"Missing ability score: {ability}")

        if errors:
            return ValidationResult(valid=False, errors=errors)

        if method == "point_buy":
            validation = self.rules.validate_point_buy(scores)
            if not validation["valid"]:
                return ValidationResult(
                    valid=False,
                    errors=validation["errors"]
                )
            build.ability_scores = scores
            build.ability_method = "point_buy"

            return ValidationResult(
                valid=True,
                data={
                    "points_used": validation["total_cost"],
                    "points_remaining": validation["points_remaining"]
                }
            )

        elif method == "standard_array":
            standard = self.rules.get_standard_array()
            provided = sorted(scores.values(), reverse=True)

            if provided != standard:
                return ValidationResult(
                    valid=False,
                    errors=[f"Standard array must use exactly these values: {standard}"]
                )

            build.ability_scores = scores
            build.ability_method = "standard_array"
            return ValidationResult(valid=True)

        else:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown ability score method: {method}"]
            )

    def set_ability_bonuses(
        self,
        build: CharacterBuild,
        bonuses: Dict[str, int]
    ) -> ValidationResult:
        """Set ability bonuses from background."""
        if not build.background_id:
            return ValidationResult(
                valid=False,
                errors=["Must select a background first"]
            )

        background = self.rules.get_background(build.background_id)
        ability_options = background.get("ability_score_increases", {}).get("options", [])

        # Validate the bonus pattern
        total_bonus = sum(bonuses.values())
        valid_patterns = [
            (3, {2, 1}),      # +2 to one, +1 to another
            (3, {1, 1, 1}),   # +1 to three different
        ]

        bonus_values = list(bonuses.values())

        # Check if valid pattern
        is_valid = False
        for expected_total, expected_set in valid_patterns:
            if total_bonus == expected_total and set(bonus_values) <= expected_set:
                is_valid = True
                break

        if not is_valid:
            return ValidationResult(
                valid=False,
                errors=["Invalid ability bonus pattern. Must be +2/+1 to two abilities or +1/+1/+1 to three abilities"]
            )

        # Validate abilities are real
        ABILITIES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
        for ability in bonuses.keys():
            if ability not in ABILITIES:
                return ValidationResult(
                    valid=False,
                    errors=[f"Invalid ability: {ability}"]
                )

        build.ability_bonuses = bonuses

        return ValidationResult(
            valid=True,
            data={
                "final_scores": build.get_final_ability_scores(),
                "modifiers": build.get_ability_modifiers()
            }
        )

    # ==================== Feats ====================

    def set_origin_feat(self, build: CharacterBuild, feat_id: str) -> ValidationResult:
        """Set the origin feat."""
        feat = self.rules.get_feat(feat_id)

        if not feat:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown feat: {feat_id}"]
            )

        # Verify it's an origin feat
        if feat.get("category", "").lower() != "origin":
            return ValidationResult(
                valid=False,
                errors=[f"'{feat.get('name')}' is not an Origin feat"]
            )

        build.origin_feat_id = feat_id

        return ValidationResult(
            valid=True,
            data={"feat": feat}
        )

    # ==================== Equipment ====================

    def set_equipment_choices(
        self,
        build: CharacterBuild,
        choices: List[Dict[str, Any]]
    ) -> ValidationResult:
        """Set equipment choices."""
        if not build.class_id:
            return ValidationResult(
                valid=False,
                errors=["Must select a class first"]
            )

        # Store equipment choices
        build.equipment_choices = choices

        return ValidationResult(valid=True)

    # ==================== Class Features ====================

    def set_fighting_style(self, build: CharacterBuild, style_id: str) -> ValidationResult:
        """Set fighting style for classes that have it."""
        if not build.class_id:
            return ValidationResult(
                valid=False,
                errors=["Must select a class first"]
            )

        class_data = self.rules.get_class(build.class_id)

        # Find fighting style feature
        fighting_style_feature = None
        for feature in class_data.get("class_features", []):
            if feature.get("id") == "fighting_style":
                fighting_style_feature = feature
                break

        if not fighting_style_feature:
            return ValidationResult(
                valid=False,
                errors=["This class does not have Fighting Style"]
            )

        # Validate the style
        valid_styles = [opt["id"] for opt in fighting_style_feature.get("options", [])]
        if style_id not in valid_styles:
            return ValidationResult(
                valid=False,
                errors=[f"Invalid fighting style: {style_id}"]
            )

        build.fighting_style = style_id
        return ValidationResult(valid=True)

    def set_weapon_masteries(self, build: CharacterBuild, weapons: List[str]) -> ValidationResult:
        """Set weapon mastery choices for classes that have it."""
        if not build.class_id:
            return ValidationResult(
                valid=False,
                errors=["Must select a class first"]
            )

        class_data = self.rules.get_class(build.class_id)
        level_info = None

        for lvl in class_data.get("level_progression", []):
            if lvl.get("level") == build.level:
                level_info = lvl
                break

        if not level_info or "weapon_masteries" not in level_info:
            return ValidationResult(
                valid=False,
                errors=["This class does not have Weapon Mastery"]
            )

        max_masteries = level_info.get("weapon_masteries", 0)
        if len(weapons) > max_masteries:
            return ValidationResult(
                valid=False,
                errors=[f"Can only select {max_masteries} weapon masteries at level {build.level}"]
            )

        build.weapon_masteries = weapons
        return ValidationResult(valid=True)

    # ==================== Details ====================

    def set_details(
        self,
        build: CharacterBuild,
        name: str,
        appearance: Optional[str] = None,
        personality: Optional[str] = None,
        backstory: Optional[str] = None
    ) -> ValidationResult:
        """Set character details."""
        if not name or len(name.strip()) < 1:
            return ValidationResult(
                valid=False,
                errors=["Character name is required"]
            )

        build.name = name.strip()
        build.appearance = appearance
        build.personality = personality
        build.backstory = backstory

        return ValidationResult(valid=True)

    # ==================== Level ====================

    def set_level(self, build: CharacterBuild, level: int) -> ValidationResult:
        """Set character level (1-20)."""
        if level < 1 or level > 20:
            return ValidationResult(
                valid=False,
                errors=["Level must be between 1 and 20"]
            )

        build.level = level
        return ValidationResult(valid=True, data={"level": level})

    # ==================== Validation & Finalization ====================

    def validate_build(self, build: CharacterBuild) -> ValidationResult:
        """Validate that a build is complete and valid."""
        errors = []
        warnings = []

        # Required fields
        if not build.species_id:
            errors.append("Species is required")
        if not build.class_id:
            errors.append("Class is required")
        if not build.background_id:
            errors.append("Background is required")
        if not build.ability_bonuses:
            errors.append("Ability score bonuses must be assigned")
        if not build.origin_feat_id:
            errors.append("Origin feat is required")
        if not build.name:
            errors.append("Character name is required")

        # Validate size is set for species that need it
        if build.species_id:
            species = self.rules.get_species(build.species_id)
            if species:
                size = species.get("size", "Medium")
                if "or" in size.lower() and not build.size:
                    errors.append("Size choice is required for this species")

        # Validate skill choices if class is set
        if build.class_id and not build.skill_choices:
            class_data = self.rules.get_class(build.class_id)
            skill_choices = class_data.get("skill_choices", {})
            if skill_choices.get("count", 0) > 0:
                errors.append("Skill proficiencies must be selected")

        # Warnings for optional fields
        if not build.equipment_choices:
            warnings.append("No equipment choices made - will use defaults")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def finalize_character(self, build: CharacterBuild) -> Tuple[bool, Dict[str, Any]]:
        """
        Finalize the character build into a full character sheet.

        Returns (success, character_data or errors)
        """
        validation = self.validate_build(build)
        if not validation.valid:
            return False, {"errors": validation.errors}

        species = self.rules.get_species(build.species_id)
        class_data = self.rules.get_class(build.class_id)
        background = self.rules.get_background(build.background_id)
        origin_feat = self.rules.get_feat(build.origin_feat_id)

        final_scores = build.get_final_ability_scores()
        modifiers = build.get_ability_modifiers()

        # Calculate HP
        hit_die = class_data.get("hit_die", "d8")
        hit_die_max = int(hit_die[1:])  # Extract number from "d10" -> 10
        hp = hit_die_max + modifiers.get("constitution", 0)

        # Calculate AC (base 10 + DEX mod, no armor)
        ac = 10 + modifiers.get("dexterity", 0)

        # Build proficiencies
        skill_proficiencies = list(build.skill_choices) + background.get("skill_proficiencies", [])
        saving_throws = class_data.get("saving_throw_proficiencies", [])

        # Build features list
        features = []

        # Species traits
        for trait in species.get("traits", []):
            features.append({
                "source": "species",
                "name": trait.get("name"),
                "description": trait.get("description")
            })

        # Class features at level 1
        for feature in self.rules.get_class_features_at_level(build.class_id, build.level):
            features.append({
                "source": "class",
                "name": feature.get("name"),
                "description": feature.get("description")
            })

        # Origin feat
        features.append({
            "source": "feat",
            "name": origin_feat.get("name"),
            "description": origin_feat.get("description")
        })

        character = {
            "id": str(uuid.uuid4()),
            "build_id": build.id,
            "name": build.name,
            "species": species.get("name"),
            "species_id": build.species_id,
            "class": class_data.get("name"),
            "class_id": build.class_id,
            "subclass_id": build.subclass_id,
            "background": background.get("name"),
            "background_id": build.background_id,
            "level": build.level,
            "experience": 0,

            # Ability scores
            "ability_scores": final_scores,
            "ability_modifiers": modifiers,

            # Combat stats
            "hit_points": hp,
            "max_hit_points": hp,
            "armor_class": ac,
            "speed": species.get("speed", 30),
            "size": build.size or species.get("size", "Medium"),
            "hit_die": hit_die,
            "hit_dice_remaining": 1,

            # Proficiencies
            "proficiency_bonus": self.rules.get_proficiency_bonus(build.level),
            "skill_proficiencies": list(set(skill_proficiencies)),
            "saving_throw_proficiencies": saving_throws,
            "armor_proficiencies": class_data.get("armor_proficiencies", []),
            "weapon_proficiencies": class_data.get("weapon_proficiencies", []),
            "tool_proficiencies": build.tool_choices,
            "languages": species.get("languages", ["Common"]) + build.language_choices,

            # Features & feats
            "features": features,
            "origin_feat": origin_feat.get("name"),
            "origin_feat_id": build.origin_feat_id,

            # Class feature choices
            "fighting_style": build.fighting_style,
            "weapon_masteries": build.weapon_masteries,

            # Equipment (simplified for now)
            "equipment": build.equipment_choices,
            "gold": background.get("starting_equipment", {}).get("gold", 0),

            # Details
            "appearance": build.appearance,
            "personality": build.personality,
            "backstory": build.backstory,

            # Spellcasting (if applicable, will be populated by class)
            "spellcasting": None,

            # Creation metadata
            "ability_method": build.ability_method,
            "created_via": "character_builder"
        }

        # Add spellcasting if class has it
        if build.class_id in ["wizard", "sorcerer", "cleric", "druid", "bard", "warlock", "paladin", "ranger"]:
            character["spellcasting"] = self._build_spellcasting(build, class_data, modifiers)

        return True, character

    def _build_spellcasting(
        self,
        build: CharacterBuild,
        class_data: Dict,
        modifiers: Dict[str, int]
    ) -> Dict[str, Any]:
        """Build spellcasting data for spellcasting classes."""
        # Determine spellcasting ability
        spellcasting_abilities = {
            "wizard": "intelligence",
            "sorcerer": "charisma",
            "cleric": "wisdom",
            "druid": "wisdom",
            "bard": "charisma",
            "warlock": "charisma",
            "paladin": "charisma",
            "ranger": "wisdom"
        }

        ability = spellcasting_abilities.get(build.class_id, "intelligence")
        ability_mod = modifiers.get(ability, 0)
        prof_bonus = self.rules.get_proficiency_bonus(build.level)

        # Spell slots at level 1 (varies by class)
        # Most full casters get 2 1st-level slots at level 1
        # Half casters (paladin, ranger) get spells at level 2
        spell_slots = {}
        cantrips_known = []
        spells_known = []

        if build.level >= 1 and build.class_id in ["wizard", "sorcerer", "cleric", "druid", "bard"]:
            spell_slots = {1: 2}
        elif build.level >= 2 and build.class_id in ["paladin", "ranger"]:
            spell_slots = {1: 2}
        elif build.class_id == "warlock":
            spell_slots = {1: 1}  # Pact slots work differently

        return {
            "ability": ability,
            "spell_save_dc": 8 + prof_bonus + ability_mod,
            "spell_attack_bonus": prof_bonus + ability_mod,
            "spell_slots_max": spell_slots,
            "spell_slots_used": {},
            "cantrips_known": cantrips_known,
            "spells_known": spells_known,
            "prepared_spells": [],
            "spellcasting_type": "prepared" if build.class_id in ["wizard", "cleric", "druid", "paladin"] else "known"
        }


# Convenience function
def get_character_builder() -> CharacterBuilder:
    """Get a CharacterBuilder instance."""
    return CharacterBuilder()
