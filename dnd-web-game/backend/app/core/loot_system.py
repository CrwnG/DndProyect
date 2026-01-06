"""
D&D 5e Loot & Treasure Generation System.

Generates treasure based on:
- Encounter CR (Challenge Rating)
- Encounter type (individual vs hoard)
- DMG treasure tables
- Magic item rarity tables
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
import random
import re
import json
from pathlib import Path


class TreasureType(Enum):
    """Types of treasure generation."""
    INDIVIDUAL = "individual"  # Per-creature loot (quick fights)
    HOARD = "hoard"           # Boss/lair treasure (major encounters)


class LootRarity(Enum):
    """Magic item rarity levels."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"
    ARTIFACT = "artifact"


@dataclass
class GemOrArt:
    """A gem or art object."""
    name: str
    description: str
    value: int  # Value in gold pieces
    type: str  # "gem" or "art"


@dataclass
class MagicItem:
    """A magic item from the treasure."""
    id: str
    name: str
    rarity: LootRarity
    type: str  # "weapon", "armor", "potion", "scroll", "wondrous", etc.
    description: str = ""
    requires_attunement: bool = False


@dataclass
class TreasureResult:
    """Generated treasure from an encounter."""
    copper: int = 0
    silver: int = 0
    electrum: int = 0
    gold: int = 0
    platinum: int = 0
    gems: List[GemOrArt] = field(default_factory=list)
    art_objects: List[GemOrArt] = field(default_factory=list)
    magic_items: List[MagicItem] = field(default_factory=list)
    mundane_items: List[Dict[str, Any]] = field(default_factory=list)
    source_cr: float = 0
    treasure_type: TreasureType = TreasureType.INDIVIDUAL

    @property
    def total_gold_value(self) -> float:
        """Calculate total value converted to gold pieces."""
        coins_gp = (
            (self.copper / 100) +
            (self.silver / 10) +
            (self.electrum / 2) +
            self.gold +
            (self.platinum * 10)
        )
        gems_gp = sum(g.value for g in self.gems)
        art_gp = sum(a.value for a in self.art_objects)
        return coins_gp + gems_gp + art_gp

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "coins": {
                "cp": self.copper,
                "sp": self.silver,
                "ep": self.electrum,
                "gp": self.gold,
                "pp": self.platinum,
            },
            "total_gold_value": round(self.total_gold_value, 2),
            "gems": [
                {"name": g.name, "description": g.description, "value": g.value}
                for g in self.gems
            ],
            "art_objects": [
                {"name": a.name, "description": a.description, "value": a.value}
                for a in self.art_objects
            ],
            "magic_items": [
                {
                    "id": m.id,
                    "name": m.name,
                    "rarity": m.rarity.value,
                    "type": m.type,
                    "description": m.description,
                    "requires_attunement": m.requires_attunement,
                }
                for m in self.magic_items
            ],
            "mundane_items": self.mundane_items,
            "source_cr": self.source_cr,
            "treasure_type": self.treasure_type.value,
        }


class LootGenerator:
    """
    D&D 5e treasure generation following DMG rules.

    Generates coins, gems, art objects, and magic items based on
    Challenge Rating using the official treasure tables.
    """

    def __init__(self):
        self._treasure_tables: Dict[str, Any] = {}
        self._gems_data: Dict[str, List[Dict]] = {}
        self._art_data: Dict[str, List[Dict]] = {}
        self._magic_items_cache: Dict[str, Any] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load all treasure table data from JSON files."""
        data_path = Path(__file__).parent.parent / "data" / "loot_tables"

        # Load treasure tables
        treasure_file = data_path / "treasure_by_cr.json"
        if treasure_file.exists():
            with open(treasure_file, 'r') as f:
                self._treasure_tables = json.load(f)

        # Load gems data
        gems_file = data_path / "gems.json"
        if gems_file.exists():
            with open(gems_file, 'r') as f:
                self._gems_data = json.load(f)

        # Load art objects data
        art_file = data_path / "art_objects.json"
        if art_file.exists():
            with open(art_file, 'r') as f:
                self._art_data = json.load(f)

        # Load magic items from existing data
        magic_path = Path(__file__).parent.parent / "data" / "rules" / "2024" / "magic_items"
        if magic_path.exists():
            for item_file in magic_path.glob("*.json"):
                try:
                    with open(item_file, 'r') as f:
                        items = json.load(f)
                        if isinstance(items, list):
                            for item in items:
                                if "id" in item:
                                    self._magic_items_cache[item["id"]] = item
                        elif isinstance(items, dict) and "items" in items:
                            for item in items["items"]:
                                if "id" in item:
                                    self._magic_items_cache[item["id"]] = item
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to load magic items from {item_file}: {e}")

    def _roll_dice(self, dice_str: str) -> int:
        """
        Roll dice from a string like '2d6', '3d6x10', '4d6x100'.

        Args:
            dice_str: Dice notation (e.g., "2d6", "3d6x100")

        Returns:
            Total rolled value
        """
        if not dice_str:
            return 0

        dice_str = dice_str.lower().strip()
        multiplier = 1

        # Handle multipliers (e.g., "3d6x100")
        if 'x' in dice_str:
            parts = dice_str.split('x')
            dice_str = parts[0]
            multiplier = int(parts[1])

        # Parse dice notation
        match = re.match(r'(\d+)d(\d+)', dice_str)
        if match:
            num_dice = int(match.group(1))
            die_size = int(match.group(2))
            total = sum(random.randint(1, die_size) for _ in range(num_dice))
            return total * multiplier

        # Handle flat numbers
        try:
            return int(dice_str) * multiplier
        except ValueError:
            return 0

    def _get_cr_tier(self, cr: float) -> str:
        """
        Map Challenge Rating to treasure table tier.

        Args:
            cr: Challenge Rating (0-30+)

        Returns:
            Tier string for table lookup
        """
        if cr <= 4:
            return "cr_0_4"
        elif cr <= 10:
            return "cr_5_10"
        elif cr <= 16:
            return "cr_11_16"
        else:
            return "cr_17_plus"

    def generate_individual_loot(self, cr: float) -> TreasureResult:
        """
        Generate individual treasure for a single creature.

        Uses DMG Individual Treasure tables based on CR.

        Args:
            cr: Challenge Rating of the creature

        Returns:
            TreasureResult with coins
        """
        result = TreasureResult(
            source_cr=cr,
            treasure_type=TreasureType.INDIVIDUAL
        )

        tier = self._get_cr_tier(cr)
        table = self._treasure_tables.get("individual_treasure", {}).get(tier, {})

        if not table:
            return result

        # Roll d100 to determine coin type
        roll = random.randint(1, 100)

        coins_table = table.get("coins", [])
        for entry in coins_table:
            if roll <= entry.get("weight", 0):
                coin_type = entry.get("coin", "gp")
                dice = entry.get("dice", "0")
                amount = self._roll_dice(dice)

                if coin_type == "cp":
                    result.copper = amount
                elif coin_type == "sp":
                    result.silver = amount
                elif coin_type == "ep":
                    result.electrum = amount
                elif coin_type == "gp":
                    result.gold = amount
                elif coin_type == "pp":
                    result.platinum = amount

                break

        return result

    def generate_hoard_loot(self, cr: float) -> TreasureResult:
        """
        Generate hoard treasure for a boss/lair encounter.

        Uses DMG Treasure Hoard tables based on CR.
        Includes coins, gems, art objects, and magic items.

        Args:
            cr: Challenge Rating of the encounter

        Returns:
            TreasureResult with full treasure
        """
        result = TreasureResult(
            source_cr=cr,
            treasure_type=TreasureType.HOARD
        )

        tier = self._get_cr_tier(cr)
        table = self._treasure_tables.get("hoard_treasure", {}).get(tier, {})

        if not table:
            return result

        # Generate coins
        coins = table.get("coins", {})
        if coins.get("cp"):
            result.copper = self._roll_dice(coins["cp"])
        if coins.get("sp"):
            result.silver = self._roll_dice(coins["sp"])
        if coins.get("ep"):
            result.electrum = self._roll_dice(coins["ep"])
        if coins.get("gp"):
            result.gold = self._roll_dice(coins["gp"])
        if coins.get("pp"):
            result.platinum = self._roll_dice(coins["pp"])

        # Roll for gems/art and magic items
        gems_art_table = table.get("gems_art", [])
        if gems_art_table:
            roll = random.randint(1, 100)

            for entry in gems_art_table:
                if roll <= entry.get("weight", 0):
                    # Generate gems or art
                    gem_table = entry.get("table")
                    if gem_table:
                        count = self._roll_dice(entry.get("dice", "1"))
                        self._add_gems_or_art(result, gem_table, count)

                    # Generate magic items
                    magic_table = entry.get("magic_table")
                    if magic_table:
                        magic_count = 1
                        if entry.get("magic_count"):
                            magic_count = self._roll_dice(entry["magic_count"])
                        self._add_magic_items(result, magic_table, magic_count)

                    break

        return result

    def _add_gems_or_art(self, result: TreasureResult, table_name: str, count: int) -> None:
        """Add gems or art objects to the result."""
        # Determine if this is gems or art
        if table_name.startswith("gems_"):
            value_str = table_name.replace("gems_", "").replace("gp", "")
            value = int(value_str)
            items = self._gems_data.get(table_name, [])
            for _ in range(count):
                if items:
                    item = random.choice(items)
                    result.gems.append(GemOrArt(
                        name=item.get("name", "Unknown Gem"),
                        description=item.get("description", ""),
                        value=value,
                        type="gem"
                    ))
        elif table_name.startswith("art_"):
            value_str = table_name.replace("art_", "").replace("gp", "")
            value = int(value_str)
            items = self._art_data.get(table_name, [])
            for _ in range(count):
                if items:
                    item = random.choice(items)
                    result.art_objects.append(GemOrArt(
                        name=item.get("name", "Unknown Art"),
                        description=item.get("description", ""),
                        value=value,
                        type="art"
                    ))

    def _add_magic_items(self, result: TreasureResult, table_name: str, count: int) -> None:
        """Add magic items to the result from a specific table."""
        magic_tables = self._treasure_tables.get("magic_item_tables", {})
        table = magic_tables.get(table_name, {})

        if not table:
            return

        items = table.get("items", [])
        rarity_str = table.get("rarity", "uncommon")

        # Map rarity string to enum
        rarity_map = {
            "common": LootRarity.COMMON,
            "uncommon": LootRarity.UNCOMMON,
            "uncommon_magic_weapon": LootRarity.UNCOMMON,
            "rare": LootRarity.RARE,
            "rare_magic_weapon": LootRarity.RARE,
            "very_rare": LootRarity.VERY_RARE,
            "very_rare_magic_weapon": LootRarity.VERY_RARE,
            "legendary": LootRarity.LEGENDARY,
        }
        rarity = rarity_map.get(rarity_str, LootRarity.UNCOMMON)

        for _ in range(count):
            roll = random.randint(1, 100)

            for entry in items:
                if roll <= entry.get("weight", 0):
                    item_id = entry.get("item", "potion_of_healing")

                    # Look up item details if we have them
                    item_data = self._magic_items_cache.get(item_id, {})

                    # Determine item type from ID
                    item_type = "wondrous"
                    if "weapon" in item_id or "sword" in item_id or "axe" in item_id:
                        item_type = "weapon"
                    elif "armor" in item_id or "shield" in item_id:
                        item_type = "armor"
                    elif "potion" in item_id:
                        item_type = "potion"
                    elif "scroll" in item_id or "spell_scroll" in item_id:
                        item_type = "scroll"
                    elif "ring" in item_id:
                        item_type = "ring"
                    elif "wand" in item_id or "rod" in item_id or "staff" in item_id:
                        item_type = "rod/staff/wand"

                    result.magic_items.append(MagicItem(
                        id=item_id,
                        name=item_data.get("name", self._format_item_name(item_id)),
                        rarity=rarity,
                        type=item_type,
                        description=item_data.get("description", ""),
                        requires_attunement=item_data.get("requires_attunement", False),
                    ))

                    break

    def _format_item_name(self, item_id: str) -> str:
        """Convert item ID to readable name."""
        name = item_id.replace("_", " ").title()
        # Handle common patterns
        name = name.replace("Plus 1", "+1")
        name = name.replace("Plus 2", "+2")
        name = name.replace("Plus 3", "+3")
        return name

    def generate_encounter_loot(
        self,
        defeated_enemies: List[Dict[str, Any]],
        encounter_difficulty: str = "medium",
        is_boss_encounter: bool = False
    ) -> TreasureResult:
        """
        Generate loot for a completed combat encounter.

        Args:
            defeated_enemies: List of defeated enemy data (must have 'cr' or 'challenge_rating')
            encounter_difficulty: "easy", "medium", "hard", "deadly"
            is_boss_encounter: If True, generates hoard treasure

        Returns:
            Combined TreasureResult for the encounter
        """
        if not defeated_enemies:
            return TreasureResult()

        # Calculate total CR
        total_cr = 0
        for enemy in defeated_enemies:
            cr = enemy.get("cr", enemy.get("challenge_rating", 0))
            if isinstance(cr, str):
                # Handle fractional CR like "1/4"
                if "/" in cr:
                    parts = cr.split("/")
                    cr = float(parts[0]) / float(parts[1])
                else:
                    cr = float(cr)
            total_cr += cr

        # Apply difficulty modifier
        difficulty_multipliers = {
            "easy": 0.5,
            "medium": 1.0,
            "hard": 1.5,
            "deadly": 2.0,
        }
        multiplier = difficulty_multipliers.get(encounter_difficulty, 1.0)

        if is_boss_encounter:
            # Generate hoard treasure for boss encounters
            result = self.generate_hoard_loot(total_cr)
        else:
            # Generate individual treasure per enemy and combine
            result = TreasureResult(
                source_cr=total_cr,
                treasure_type=TreasureType.INDIVIDUAL
            )

            for enemy in defeated_enemies:
                cr = enemy.get("cr", enemy.get("challenge_rating", 0))
                if isinstance(cr, str):
                    if "/" in cr:
                        parts = cr.split("/")
                        cr = float(parts[0]) / float(parts[1])
                    else:
                        cr = float(cr)

                individual = self.generate_individual_loot(cr)
                result.copper += individual.copper
                result.silver += individual.silver
                result.electrum += individual.electrum
                result.gold += individual.gold
                result.platinum += individual.platinum

        # Apply difficulty multiplier to coins
        result.copper = int(result.copper * multiplier)
        result.silver = int(result.silver * multiplier)
        result.electrum = int(result.electrum * multiplier)
        result.gold = int(result.gold * multiplier)
        result.platinum = int(result.platinum * multiplier)

        # Add chance for consumable drops on ALL encounters (not just bosses)
        # Higher CR = better chance of drops
        self._add_consumable_drops(result, total_cr, len(defeated_enemies))

        return result

    def _add_consumable_drops(
        self,
        result: TreasureResult,
        total_cr: float,
        enemy_count: int
    ) -> None:
        """
        Add chance for consumable item drops to any encounter.

        Args:
            result: TreasureResult to add items to
            total_cr: Total Challenge Rating of the encounter
            enemy_count: Number of enemies defeated
        """
        import random

        # Base drop chance: 15% per enemy, modified by CR
        # CR 0-1: 10%, CR 2-4: 20%, CR 5+: 35%
        base_chance = 0.15
        if total_cr >= 5:
            base_chance = 0.35
        elif total_cr >= 2:
            base_chance = 0.20
        elif total_cr < 1:
            base_chance = 0.10

        # Common consumables that can drop
        common_consumables = [
            {
                "id": "potion_of_healing",
                "name": "Potion of Healing",
                "type": "consumable",
                "rarity": "common",
                "value_gp": 50,
                "description": "Heals 2d4+2 HP when consumed. Bonus action to use.",
                "effect": {"type": "healing", "dice": "2d4+2"},
                "weight": 60  # Most common drop
            },
            {
                "id": "antitoxin",
                "name": "Antitoxin",
                "type": "consumable",
                "rarity": "common",
                "value_gp": 50,
                "description": "Grants advantage on saving throws vs poison for 1 hour.",
                "weight": 15
            },
            {
                "id": "alchemists_fire",
                "name": "Alchemist's Fire",
                "type": "consumable",
                "rarity": "common",
                "value_gp": 50,
                "description": "Thrown weapon dealing 1d4 fire damage per turn.",
                "weight": 10
            },
            {
                "id": "holy_water",
                "name": "Holy Water",
                "type": "consumable",
                "rarity": "common",
                "value_gp": 25,
                "description": "Deals 2d6 radiant damage to fiends and undead.",
                "weight": 10
            },
            {
                "id": "torch",
                "name": "Torch",
                "type": "gear",
                "rarity": "common",
                "value_gp": 1,
                "description": "Provides bright light for 20 feet.",
                "weight": 5
            },
        ]

        # Uncommon consumables (drop at higher CR)
        uncommon_consumables = [
            {
                "id": "potion_of_greater_healing",
                "name": "Potion of Greater Healing",
                "type": "consumable",
                "rarity": "uncommon",
                "value_gp": 150,
                "description": "Heals 4d4+4 HP when consumed. Bonus action to use.",
                "effect": {"type": "healing", "dice": "4d4+4"},
                "weight": 40
            },
            {
                "id": "oil_of_slipperiness",
                "name": "Oil of Slipperiness",
                "type": "consumable",
                "rarity": "uncommon",
                "value_gp": 100,
                "description": "Coats a creature for 8 hours, allowing it to move through tight spaces.",
                "weight": 20
            },
            {
                "id": "potion_of_climbing",
                "name": "Potion of Climbing",
                "type": "consumable",
                "rarity": "common",
                "value_gp": 75,
                "description": "Gain climbing speed equal to walking speed for 1 hour.",
                "weight": 20
            },
            {
                "id": "scroll_of_cure_wounds",
                "name": "Scroll of Cure Wounds",
                "type": "scroll",
                "rarity": "common",
                "value_gp": 50,
                "description": "Cast Cure Wounds (1st level) once.",
                "weight": 20
            },
        ]

        # Check for drops per enemy
        for i in range(enemy_count):
            roll = random.random()
            if roll < base_chance:
                # Determine rarity of drop
                rarity_roll = random.random()

                if total_cr >= 3 and rarity_roll < 0.25:
                    # 25% chance of uncommon at CR 3+
                    pool = uncommon_consumables
                else:
                    pool = common_consumables

                # Weighted random selection
                total_weight = sum(item["weight"] for item in pool)
                pick = random.uniform(0, total_weight)
                current = 0
                selected = pool[0]
                for item in pool:
                    current += item["weight"]
                    if pick <= current:
                        selected = item
                        break

                # Create the drop (copy to avoid modifying template)
                drop = {
                    "id": selected["id"],
                    "name": selected["name"],
                    "type": selected.get("type", "consumable"),
                    "rarity": selected.get("rarity", "common"),
                    "value_gp": selected.get("value_gp", 0),
                    "description": selected.get("description", ""),
                }
                if "effect" in selected:
                    drop["effect"] = selected["effect"]

                result.mundane_items.append(drop)
                print(f"[LootSystem] Added consumable drop: {drop['name']}")

    def generate_monster_drops(
        self,
        monster_id: str,
        monster_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate specific item drops from a monster.

        Uses monster-specific loot tables if defined.

        Args:
            monster_id: ID of the monster
            monster_data: Monster data dict (may contain 'treasure' field)

        Returns:
            List of dropped items
        """
        drops = []

        treasure = monster_data.get("treasure", {})
        if not treasure:
            return drops

        # Check for common drops
        common_drops = treasure.get("common_drops", [])
        drop_chance = treasure.get("drop_chance", 0.3)

        for item_id in common_drops:
            if random.random() < drop_chance:
                drops.append({
                    "id": item_id,
                    "name": self._format_item_name(item_id),
                    "type": "equipment",
                    "source": monster_id,
                })

        # Check for rare drops
        rare_drops = treasure.get("rare_drops", [])
        rare_chance = treasure.get("rare_drop_chance", 0.05)

        for item_id in rare_drops:
            if random.random() < rare_chance:
                drops.append({
                    "id": item_id,
                    "name": self._format_item_name(item_id),
                    "type": "equipment",
                    "rarity": "rare",
                    "source": monster_id,
                })

        return drops


# Singleton instance
_loot_generator: Optional[LootGenerator] = None


def get_loot_generator() -> LootGenerator:
    """Get or create the singleton LootGenerator instance."""
    global _loot_generator
    if _loot_generator is None:
        _loot_generator = LootGenerator()
    return _loot_generator
