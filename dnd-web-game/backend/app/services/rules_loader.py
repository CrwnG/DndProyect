"""
D&D 2024 Rules Data Loader.

Singleton service that loads and caches all D&D 2024 rules data from JSON files.
Provides access to species, classes, backgrounds, feats, and equipment data.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache


class RulesLoader:
    """Loads and caches D&D 2024 rules data from JSON files."""

    _instance: Optional['RulesLoader'] = None
    _initialized: bool = False

    # Data caches
    _species: Dict[str, Dict] = {}
    _classes: Dict[str, Dict] = {}
    _backgrounds: Dict[str, Dict] = {}
    _origin_feats: List[Dict] = []
    _general_feats: List[Dict] = []
    _epic_boons: List[Dict] = []
    _equipment: Dict[str, Dict] = {}

    def __new__(cls) -> 'RulesLoader':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._load_all_data()
            RulesLoader._initialized = True

    @classmethod
    def get_instance(cls) -> 'RulesLoader':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (useful for testing)."""
        cls._instance = None
        cls._initialized = False
        cls._species = {}
        cls._classes = {}
        cls._backgrounds = {}
        cls._origin_feats = []
        cls._general_feats = []
        cls._epic_boons = []
        cls._equipment = {}

    def _get_data_path(self) -> Path:
        """Get the path to the rules data directory."""
        # Navigate from services to data/rules/2024
        current_dir = Path(__file__).parent
        return current_dir.parent / "data" / "rules" / "2024"

    def _load_json_file(self, filepath: Path) -> Optional[Dict]:
        """Load a single JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error loading {filepath}: {e}")
            return None

    def _load_directory(self, subdir: str) -> Dict[str, Dict]:
        """Load all JSON files from a subdirectory."""
        data = {}
        dir_path = self._get_data_path() / subdir

        if not dir_path.exists():
            print(f"Directory not found: {dir_path}")
            return data

        for filepath in dir_path.glob("*.json"):
            file_data = self._load_json_file(filepath)
            if file_data and "id" in file_data:
                data[file_data["id"]] = file_data

        return data

    def _load_all_data(self):
        """Load all rules data from JSON files."""
        data_path = self._get_data_path()

        # Load species
        self._species = self._load_directory("species")
        print(f"Loaded {len(self._species)} species")

        # Load classes
        self._classes = self._load_directory("classes")
        print(f"Loaded {len(self._classes)} classes")

        # Load backgrounds
        self._backgrounds = self._load_directory("backgrounds")
        print(f"Loaded {len(self._backgrounds)} backgrounds")

        # Load feats
        feats_path = data_path / "feats"

        origin_feats_file = feats_path / "origin_feats.json"
        if origin_feats_file.exists():
            feats_data = self._load_json_file(origin_feats_file)
            if feats_data and "feats" in feats_data:
                self._origin_feats = feats_data["feats"]
                print(f"Loaded {len(self._origin_feats)} origin feats")

        general_feats_file = feats_path / "general_feats.json"
        if general_feats_file.exists():
            feats_data = self._load_json_file(general_feats_file)
            if feats_data and "feats" in feats_data:
                self._general_feats = feats_data["feats"]
                print(f"Loaded {len(self._general_feats)} general feats")

        epic_boons_file = feats_path / "epic_boons.json"
        if epic_boons_file.exists():
            boons_data = self._load_json_file(epic_boons_file)
            if boons_data and "boons" in boons_data:
                self._epic_boons = boons_data["boons"]
                print(f"Loaded {len(self._epic_boons)} epic boons")

        # Load equipment
        equipment_path = data_path / "equipment"
        if equipment_path.exists():
            for filepath in equipment_path.glob("*.json"):
                equip_data = self._load_json_file(filepath)
                if equip_data:
                    # Equipment files have different structures
                    # Check for weapon categories (simple_melee_weapons, martial_melee_weapons, etc.)
                    weapon_keys = [k for k in equip_data.keys() if 'weapon' in k.lower()]
                    for key in weapon_keys:
                        items = equip_data.get(key, [])
                        if isinstance(items, list):
                            for weapon in items:
                                if isinstance(weapon, dict) and "id" in weapon:
                                    weapon["item_type"] = "weapon"
                                    self._equipment[weapon["id"]] = weapon

                    # Check for armor categories
                    armor_keys = [k for k in equip_data.keys() if 'armor' in k.lower()]
                    for key in armor_keys:
                        items = equip_data.get(key, [])
                        if isinstance(items, list):
                            for armor in items:
                                if isinstance(armor, dict) and "id" in armor:
                                    armor["item_type"] = "armor"
                                    self._equipment[armor["id"]] = armor

                    # Check for generic items/gear
                    if "items" in equip_data:
                        for item in equip_data["items"]:
                            if isinstance(item, dict) and "id" in item:
                                self._equipment[item["id"]] = item
                    if "gear" in equip_data:
                        for item in equip_data["gear"]:
                            if isinstance(item, dict) and "id" in item:
                                item["item_type"] = "gear"
                                self._equipment[item["id"]] = item

            print(f"Loaded {len(self._equipment)} equipment items")

    # ==================== Species ====================

    def get_all_species(self) -> List[Dict]:
        """Get all species as a list."""
        return list(self._species.values())

    def get_species(self, species_id: str) -> Optional[Dict]:
        """Get a specific species by ID."""
        return self._species.get(species_id)

    def get_species_summary(self) -> List[Dict]:
        """Get species summary (id, name, description, speed, size)."""
        return [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s.get("description", ""),
                "speed": s.get("speed", 30),
                "size": s.get("size", "Medium"),
                "traits": [t["name"] for t in s.get("traits", [])]
            }
            for s in self._species.values()
        ]

    # ==================== Classes ====================

    def get_all_classes(self) -> List[Dict]:
        """Get all classes as a list."""
        return list(self._classes.values())

    def get_class(self, class_id: str) -> Optional[Dict]:
        """Get a specific class by ID."""
        return self._classes.get(class_id)

    def get_class_summary(self) -> List[Dict]:
        """Get class summary (id, name, description, hit_die, primary_ability)."""
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "description": c.get("description", ""),
                "hit_die": c.get("hit_die", "d8"),
                "primary_ability": c.get("primary_ability", ""),
                "saving_throws": c.get("saving_throw_proficiencies", []),
                "armor_proficiencies": c.get("armor_proficiencies", []),
                "weapon_proficiencies": c.get("weapon_proficiencies", [])
            }
            for c in self._classes.values()
        ]

    def get_class_features_at_level(self, class_id: str, level: int) -> List[Dict]:
        """Get class features available at a specific level."""
        class_data = self.get_class(class_id)
        if not class_data:
            return []

        features = []
        for feature in class_data.get("class_features", []):
            if feature.get("level", 1) <= level:
                features.append(feature)

        return features

    def get_class_equipment_choices(self, class_id: str) -> Dict:
        """Get starting equipment choices for a class."""
        class_data = self.get_class(class_id)
        if not class_data:
            return {"choices": [], "default": []}

        return class_data.get("starting_equipment", {"choices": [], "default": []})

    # ==================== Backgrounds ====================

    def get_all_backgrounds(self) -> List[Dict]:
        """Get all backgrounds as a list."""
        return list(self._backgrounds.values())

    def get_background(self, background_id: str) -> Optional[Dict]:
        """Get a specific background by ID."""
        return self._backgrounds.get(background_id)

    def get_background_summary(self) -> List[Dict]:
        """Get background summary."""
        return [
            {
                "id": b["id"],
                "name": b["name"],
                "description": b.get("description", ""),
                "skill_proficiencies": b.get("skill_proficiencies", []),
                "origin_feat": b.get("origin_feat", ""),
                "ability_options": b.get("ability_score_increases", {}).get("options", [])
            }
            for b in self._backgrounds.values()
        ]

    # ==================== Feats ====================

    def get_origin_feats(self) -> List[Dict]:
        """Get all origin feats."""
        return self._origin_feats

    def get_general_feats(self) -> List[Dict]:
        """Get all general feats."""
        return self._general_feats

    def get_epic_boons(self) -> List[Dict]:
        """Get all epic boons."""
        return self._epic_boons

    def get_feat(self, feat_id: str) -> Optional[Dict]:
        """Get a specific feat by ID (searches all feat types)."""
        # Search origin feats
        for feat in self._origin_feats:
            if feat.get("id") == feat_id:
                return feat

        # Search general feats
        for feat in self._general_feats:
            if feat.get("id") == feat_id:
                return feat

        # Search epic boons
        for boon in self._epic_boons:
            if boon.get("id") == feat_id:
                return boon

        return None

    def get_feats_by_category(self, category: str) -> List[Dict]:
        """Get feats by category (Origin, General, Epic Boon)."""
        category_lower = category.lower()

        if category_lower == "origin":
            return self._origin_feats
        elif category_lower == "general":
            return self._general_feats
        elif category_lower in ("epic", "epic_boon", "boon"):
            return self._epic_boons

        return []

    # ==================== Equipment ====================

    def get_equipment(self, item_id: str) -> Optional[Dict]:
        """Get a specific equipment item by ID."""
        return self._equipment.get(item_id)

    def get_all_equipment(self) -> List[Dict]:
        """Get all equipment items."""
        return list(self._equipment.values())

    def get_equipment_by_type(self, item_type: str) -> List[Dict]:
        """Get equipment items by type (weapon, armor, gear)."""
        return [
            item for item in self._equipment.values()
            if item.get("type", "").lower() == item_type.lower()
        ]

    # ==================== Utility ====================

    def get_ability_modifier(self, score: int) -> int:
        """Calculate ability modifier from score."""
        return (score - 10) // 2

    def get_proficiency_bonus(self, level: int) -> int:
        """Get proficiency bonus for a level."""
        return 2 + ((level - 1) // 4)

    def get_point_buy_cost(self, score: int) -> int:
        """Get point buy cost for an ability score."""
        costs = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
        return costs.get(score, 0)

    def validate_point_buy(self, scores: Dict[str, int]) -> Dict[str, Any]:
        """Validate point buy ability scores."""
        TOTAL_POINTS = 27
        ABILITIES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

        errors = []
        total_cost = 0

        for ability in ABILITIES:
            score = scores.get(ability, 8)

            if score < 8 or score > 15:
                errors.append(f"{ability.capitalize()} must be between 8 and 15")
            else:
                total_cost += self.get_point_buy_cost(score)

        if total_cost > TOTAL_POINTS:
            errors.append(f"Total point cost ({total_cost}) exceeds {TOTAL_POINTS} points")

        return {
            "valid": len(errors) == 0,
            "total_cost": total_cost,
            "points_remaining": TOTAL_POINTS - total_cost,
            "errors": errors
        }

    def get_standard_array(self) -> List[int]:
        """Get the standard array for ability scores."""
        return [15, 14, 13, 12, 10, 8]


# Convenience function to get the singleton
def get_rules_loader() -> RulesLoader:
    """Get the RulesLoader singleton instance."""
    return RulesLoader.get_instance()
