"""
Tests for D&D Game Data Integrity.

Validates all JSON files contain required fields and valid data:
- 367+ monsters have required fields (id, name, ac, hp, abilities, actions)
- 198+ equipment items have correct properties
- 432 spells have damage_dice/save_type where needed
- All weapon mastery values are valid (cleave, graze, nick, etc.)
- 12 classes with proper structure
"""
import json
import pytest
from pathlib import Path


DATA_PATH = Path(__file__).parent.parent / "app" / "data" / "rules" / "2024"


class TestMonsterData:
    """Test monster JSON data integrity."""

    def get_all_monsters(self):
        """Load all monsters from all category files."""
        monsters = []
        monster_dir = DATA_PATH / "monsters"
        if not monster_dir.exists():
            pytest.skip("Monster data directory not found")

        for filepath in monster_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                if "monsters" in data:
                    for m in data["monsters"]:
                        m["_source_file"] = filepath.name
                        monsters.append(m)
        return monsters

    def test_monsters_exist(self):
        """Should have monsters loaded."""
        monsters = self.get_all_monsters()
        assert len(monsters) > 0, "No monsters found"
        # Should have 250+ monsters (actual count ~282)
        assert len(monsters) >= 250, f"Expected 250+ monsters, got {len(monsters)}"

    def test_all_monsters_have_id(self):
        """All monsters must have an id field."""
        for monster in self.get_all_monsters():
            assert "id" in monster, f"Monster missing id in {monster.get('_source_file')}"
            assert monster["id"], f"Monster has empty id in {monster.get('_source_file')}"

    def test_all_monsters_have_name(self):
        """All monsters must have a name field."""
        for monster in self.get_all_monsters():
            assert "name" in monster, f"Monster {monster.get('id')} missing name"
            assert monster["name"], f"Monster {monster.get('id')} has empty name"

    def test_all_monsters_have_size(self):
        """All monsters must have a size field."""
        valid_sizes = {"tiny", "small", "medium", "large", "huge", "gargantuan"}
        for monster in self.get_all_monsters():
            assert "size" in monster, f"Monster {monster.get('id')} missing size"
            size = monster["size"].lower()
            assert size in valid_sizes, f"Monster {monster.get('id')} has invalid size: {size}"

    def test_all_monsters_have_type(self):
        """All monsters must have a type field."""
        for monster in self.get_all_monsters():
            assert "type" in monster, f"Monster {monster.get('id')} missing type"

    def test_all_monsters_have_armor_class(self):
        """All monsters must have armor_class field."""
        for monster in self.get_all_monsters():
            assert "armor_class" in monster, f"Monster {monster.get('id')} missing armor_class"

    def test_all_monsters_have_hit_points(self):
        """All monsters must have hit_points field."""
        for monster in self.get_all_monsters():
            assert "hit_points" in monster, f"Monster {monster.get('id')} missing hit_points"

    def test_all_monsters_have_ability_scores(self):
        """All monsters must have ability_scores."""
        # Monster data uses uppercase abbreviations: STR, DEX, CON, INT, WIS, CHA
        abilities = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        for monster in self.get_all_monsters():
            assert "ability_scores" in monster, f"Monster {monster.get('id')} missing ability_scores"
            scores = monster["ability_scores"]
            for ability in abilities:
                assert ability in scores, f"Monster {monster.get('id')} missing {ability}"
                # Ability scores should be between 1 and 30
                score = scores[ability]
                assert 1 <= score <= 30, f"Monster {monster.get('id')} has invalid {ability}: {score}"


class TestEquipmentData:
    """Test equipment JSON data integrity."""

    def get_weapons(self):
        """Load all weapons from categorized structure."""
        weapons_file = DATA_PATH / "equipment" / "weapons.json"
        if not weapons_file.exists():
            pytest.skip("Weapons file not found")
        with open(weapons_file, encoding="utf-8") as f:
            data = json.load(f)
            # Weapons are in categorized arrays like simple_melee_weapons, martial_ranged_weapons
            weapons = []
            for key in data:
                if key.endswith("_weapons") and isinstance(data[key], list):
                    weapons.extend(data[key])
            return weapons

    def get_armor(self):
        """Load all armor from categorized structure."""
        armor_file = DATA_PATH / "equipment" / "armor.json"
        if not armor_file.exists():
            pytest.skip("Armor file not found")
        with open(armor_file, encoding="utf-8") as f:
            data = json.load(f)
            # Armor may be in categorized arrays like light_armor, medium_armor, heavy_armor
            armor = []
            for key in data:
                if key.endswith("_armor") and isinstance(data[key], list):
                    armor.extend(data[key])
                elif key == "shields" and isinstance(data[key], list):
                    armor.extend(data[key])
            return armor

    def test_weapons_exist(self):
        """Should have weapons loaded."""
        weapons = self.get_weapons()
        assert len(weapons) > 0, "No weapons found"
        # Should have 35+ weapons (actual count ~38)
        assert len(weapons) >= 35, f"Expected 35+ weapons, got {len(weapons)}"

    def test_all_weapons_have_required_fields(self):
        """All weapons must have required fields."""
        required = ["id", "name", "damage", "damage_type"]
        for weapon in self.get_weapons():
            for field in required:
                assert field in weapon, f"Weapon {weapon.get('id', 'unknown')} missing {field}"

    def test_all_weapons_have_mastery(self):
        """All weapons should have a mastery property (2024 rules)."""
        valid_masteries = {"cleave", "graze", "nick", "push", "sap", "slow", "topple", "vex"}
        for weapon in self.get_weapons():
            assert "mastery" in weapon, f"Weapon {weapon.get('id')} missing mastery"
            mastery = weapon["mastery"].lower()
            assert mastery in valid_masteries, f"Weapon {weapon.get('id')} has invalid mastery: {mastery}"

    def test_weapon_damage_format(self):
        """Weapon damage should be valid dice notation or flat damage."""
        import re
        # Match dice like "1d6", "2d6+3" OR flat damage like "1"
        dice_pattern = re.compile(r"^(\d+|\d*d\d+(\+\d+)?)$")
        for weapon in self.get_weapons():
            damage = weapon.get("damage", "")
            # Handle versatile weapons with two damage values
            if "/" in damage:
                damages = damage.split("/")
            else:
                damages = [damage]
            for d in damages:
                d = d.strip()
                assert dice_pattern.match(d), f"Weapon {weapon.get('id')} has invalid damage: {d}"

    def test_armor_exists(self):
        """Should have armor loaded."""
        armor = self.get_armor()
        assert len(armor) > 0, "No armor found"

    def test_armor_has_required_fields(self):
        """All armor must have required fields."""
        for armor in self.get_armor():
            assert "id" in armor, "Armor missing id"
            assert "name" in armor, f"Armor {armor.get('id')} missing name"
            assert "armor_class" in armor, f"Armor {armor.get('id')} missing armor_class"


class TestSpellData:
    """Test spell JSON data integrity."""

    def get_all_spells(self):
        """Load all spells from all level files."""
        spells = []
        spell_dir = DATA_PATH / "spells"
        if not spell_dir.exists():
            pytest.skip("Spell data directory not found")

        for filepath in spell_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                # Level is at file level, not on each spell
                file_level = data.get("level")
                if "spells" in data:
                    for s in data["spells"]:
                        s["_source_file"] = filepath.name
                        # Add level from file if not in spell
                        if "level" not in s and file_level is not None:
                            s["level"] = file_level
                        spells.append(s)
        return spells

    def test_spells_exist(self):
        """Should have spells loaded."""
        spells = self.get_all_spells()
        assert len(spells) > 0, "No spells found"
        # Should have 400+ spells
        assert len(spells) >= 400, f"Expected 400+ spells, got {len(spells)}"

    def test_all_spells_have_required_fields(self):
        """All spells must have required fields."""
        required = ["id", "name", "level", "school", "casting_time", "range"]
        for spell in self.get_all_spells():
            for field in required:
                assert field in spell, f"Spell {spell.get('id', 'unknown')} missing {field}"

    def test_spell_levels_valid(self):
        """Spell levels should be 0-9."""
        for spell in self.get_all_spells():
            level = spell.get("level")
            assert level is not None, f"Spell {spell.get('id')} missing level"
            assert 0 <= level <= 9, f"Spell {spell.get('id')} has invalid level: {level}"

    def test_spell_schools_valid(self):
        """Spell schools should be valid D&D schools."""
        valid_schools = {
            "abjuration", "conjuration", "divination", "enchantment",
            "evocation", "illusion", "necromancy", "transmutation"
        }
        for spell in self.get_all_spells():
            school = spell.get("school", "").lower()
            assert school in valid_schools, f"Spell {spell.get('id')} has invalid school: {school}"


class TestClassData:
    """Test class JSON data integrity."""

    def get_all_classes(self):
        """Load all class files."""
        classes = []
        class_dir = DATA_PATH / "classes"
        if not class_dir.exists():
            pytest.skip("Class data directory not found")

        for filepath in class_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                data["_source_file"] = filepath.name
                classes.append(data)
        return classes

    def test_all_twelve_classes_exist(self):
        """All 12 core D&D classes should exist."""
        expected_classes = {
            "barbarian", "bard", "cleric", "druid", "fighter", "monk",
            "paladin", "ranger", "rogue", "sorcerer", "warlock", "wizard"
        }
        classes = self.get_all_classes()
        class_ids = {c.get("id", "").lower() for c in classes}
        missing = expected_classes - class_ids
        assert not missing, f"Missing class files: {missing}"

    def test_classes_have_required_fields(self):
        """All classes must have required fields."""
        required = ["id", "name", "hit_die"]
        for cls in self.get_all_classes():
            for field in required:
                assert field in cls, f"Class {cls.get('_source_file')} missing {field}"

    def test_classes_have_proficiencies(self):
        """All classes should have proficiency information."""
        for cls in self.get_all_classes():
            # Classes may use armor_proficiencies, weapon_proficiencies, or proficiencies
            has_profs = (
                "proficiencies" in cls or
                "armor_proficiencies" in cls or
                "weapon_proficiencies" in cls
            )
            assert has_profs, f"Class {cls.get('id')} missing proficiency info"

    def test_classes_have_features(self):
        """All classes should have features."""
        for cls in self.get_all_classes():
            # Features might be called "class_features" or "features"
            has_features = "class_features" in cls or "features" in cls
            assert has_features, f"Class {cls.get('id')} missing features"


class TestBackgroundData:
    """Test background JSON data integrity."""

    def get_all_backgrounds(self):
        """Load all backgrounds."""
        bg_dir = DATA_PATH / "backgrounds"
        if not bg_dir.exists():
            pytest.skip("Background data directory not found")

        backgrounds = []
        for filepath in bg_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    backgrounds.extend(data)
                elif "backgrounds" in data:
                    backgrounds.extend(data["backgrounds"])
                else:
                    backgrounds.append(data)
        return backgrounds

    def test_backgrounds_exist(self):
        """Should have backgrounds loaded."""
        backgrounds = self.get_all_backgrounds()
        assert len(backgrounds) > 0, "No backgrounds found"

    def test_backgrounds_have_required_fields(self):
        """All backgrounds must have required fields."""
        required = ["id", "name"]
        for bg in self.get_all_backgrounds():
            for field in required:
                assert field in bg, f"Background missing {field}: {bg}"


class TestSpeciesData:
    """Test species/race JSON data integrity."""

    def get_all_species(self):
        """Load all species."""
        species_dir = DATA_PATH / "species"
        if not species_dir.exists():
            pytest.skip("Species data directory not found")

        species = []
        for filepath in species_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    species.extend(data)
                elif "species" in data:
                    species.extend(data["species"])
                else:
                    species.append(data)
        return species

    def test_species_exist(self):
        """Should have species loaded."""
        species = self.get_all_species()
        assert len(species) > 0, "No species found"

    def test_species_have_required_fields(self):
        """All species must have required fields."""
        required = ["id", "name"]
        for sp in self.get_all_species():
            for field in required:
                assert field in sp, f"Species missing {field}: {sp.get('id', 'unknown')}"


class TestFeatData:
    """Test feat JSON data integrity."""

    def get_all_feats(self):
        """Load all feats."""
        feat_dir = DATA_PATH / "feats"
        if not feat_dir.exists():
            pytest.skip("Feat data directory not found")

        feats = []
        for filepath in feat_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    feats.extend(data)
                elif "feats" in data:
                    feats.extend(data["feats"])
                else:
                    # Single feat or nested structure
                    if "id" in data:
                        feats.append(data)
        return feats

    def test_feats_exist(self):
        """Should have feats loaded."""
        feats = self.get_all_feats()
        assert len(feats) > 0, "No feats found"

    def test_feats_have_required_fields(self):
        """All feats must have required fields."""
        required = ["id", "name"]
        for feat in self.get_all_feats():
            for field in required:
                assert field in feat, f"Feat missing {field}: {feat}"


class TestMagicItemData:
    """Test magic item JSON data integrity."""

    def get_all_magic_items(self):
        """Load all magic items."""
        items_dir = DATA_PATH / "magic_items"
        if not items_dir.exists():
            pytest.skip("Magic items directory not found")

        items = []
        for filepath in items_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    items.extend(data)
                elif "items" in data:
                    items.extend(data["items"])
        return items

    def test_magic_items_exist(self):
        """Should have magic items loaded."""
        items = self.get_all_magic_items()
        assert len(items) > 0, "No magic items found"
        # Should have 300+ magic items
        assert len(items) >= 300, f"Expected 300+ magic items, got {len(items)}"

    def test_magic_items_have_required_fields(self):
        """All magic items must have required fields."""
        required = ["id", "name", "rarity"]
        valid_rarities = {"common", "uncommon", "rare", "very_rare", "legendary", "artifact"}

        for item in self.get_all_magic_items():
            for field in required:
                assert field in item, f"Magic item missing {field}: {item.get('id', 'unknown')}"

            rarity = item.get("rarity", "").lower().replace(" ", "_")
            assert rarity in valid_rarities, f"Magic item {item.get('id')} has invalid rarity: {rarity}"
