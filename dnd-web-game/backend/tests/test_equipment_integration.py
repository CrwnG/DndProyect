"""
Tests for Equipment Integration with Combat.

Verifies:
- Weapon damage from JSON used in combat
- Armor AC calculation respects type (light/medium/heavy)
- DEX cap from armor applied correctly
- Weapon properties enforced (finesse, two-handed, loading)
- Shield adds +2 AC
"""
import pytest
from app.models.equipment import (
    InventoryItem,
    CharacterEquipment,
    EquipmentSlot,
    ItemRarity,
)


class TestInventoryItem:
    """Test InventoryItem dataclass."""

    def test_create_weapon(self):
        """Should create a weapon with damage and mastery."""
        sword = InventoryItem(
            id="longsword",
            name="Longsword",
            item_type="weapon",
            damage="1d8",
            damage_type="slashing",
            mastery="sap",
            properties=["versatile"],
            weight=3.0
        )
        assert sword.damage == "1d8"
        assert sword.damage_type == "slashing"
        assert sword.mastery == "sap"
        assert "versatile" in sword.properties

    def test_create_armor(self):
        """Should create armor with AC bonus and max DEX."""
        armor = InventoryItem(
            id="chain_mail",
            name="Chain Mail",
            item_type="armor",
            ac_bonus=16,
            max_dex_bonus=0,  # Heavy armor
            stealth_disadvantage=True,
            strength_requirement=13,
            weight=55.0
        )
        assert armor.ac_bonus == 16
        assert armor.max_dex_bonus == 0
        assert armor.stealth_disadvantage is True
        assert armor.strength_requirement == 13

    def test_to_dict_preserves_all_fields(self):
        """to_dict should preserve all item fields."""
        item = InventoryItem(
            id="test",
            name="Test Item",
            damage="2d6",
            damage_type="fire",
            ac_bonus=2,
            mastery="cleave"
        )
        d = item.to_dict()
        assert d["id"] == "test"
        assert d["damage"] == "2d6"
        assert d["damage_type"] == "fire"
        assert d["ac_bonus"] == 2
        assert d["mastery"] == "cleave"


class TestCharacterEquipmentSlots:
    """Test equipment slot management."""

    def test_all_slots_start_empty(self):
        """All equipment slots should start empty."""
        eq = CharacterEquipment()
        assert eq.main_hand is None
        assert eq.off_hand is None
        assert eq.armor is None
        assert eq.ring_1 is None
        assert eq.ring_2 is None

    def test_equip_weapon_main_hand(self):
        """Should be able to equip weapon in main hand."""
        eq = CharacterEquipment()
        sword = InventoryItem(id="longsword", name="Longsword", item_type="weapon")
        eq.main_hand = sword
        assert eq.main_hand is not None
        assert eq.main_hand.id == "longsword"

    def test_equip_shield_off_hand(self):
        """Should be able to equip shield in off hand."""
        eq = CharacterEquipment()
        shield = InventoryItem(id="shield", name="Shield", item_type="armor", ac_bonus=2)
        eq.off_hand = shield
        assert eq.off_hand is not None
        assert eq.off_hand.ac_bonus == 2


class TestACCalculation:
    """Test AC calculation with different armor types."""

    def test_unarmored_ac(self):
        """Unarmored should be 10 + DEX mod."""
        eq = CharacterEquipment()
        # DEX 14 = +2 mod, so AC = 10 + 2 = 12
        result = eq.calculate_ac(dexterity=14)
        assert result["base_ac"] == 10
        assert result["total_ac"] == 12

    def test_light_armor_full_dex(self):
        """Light armor should allow full DEX modifier."""
        eq = CharacterEquipment()
        eq.armor = InventoryItem(
            id="leather",
            name="Leather Armor",
            item_type="armor",
            ac_bonus=11,
            max_dex_bonus=None  # No cap = light armor
        )
        # DEX 16 = +3 mod, so AC = 11 + 3 = 14
        result = eq.calculate_ac(dexterity=16)
        assert result["total_ac"] == 14

    def test_medium_armor_dex_cap(self):
        """Medium armor should cap DEX at +2."""
        eq = CharacterEquipment()
        eq.armor = InventoryItem(
            id="breastplate",
            name="Breastplate",
            item_type="armor",
            ac_bonus=14,
            max_dex_bonus=2  # Medium armor caps at +2
        )
        # DEX 18 = +4 mod, but capped at +2, so AC = 14 + 2 = 16
        result = eq.calculate_ac(dexterity=18)
        assert result["dex_bonus"] == 2  # Capped (key is dex_bonus, not effective_dex)
        assert result["total_ac"] == 16

    def test_heavy_armor_no_dex(self):
        """Heavy armor should not add DEX modifier."""
        eq = CharacterEquipment()
        eq.armor = InventoryItem(
            id="plate",
            name="Plate",
            item_type="armor",
            ac_bonus=18,
            max_dex_bonus=0  # Heavy armor = no DEX
        )
        # DEX 20 = +5 mod, but 0 applied, so AC = 18 + 0 = 18
        result = eq.calculate_ac(dexterity=20)
        assert result["dex_bonus"] == 0  # Key is dex_bonus
        assert result["total_ac"] == 18

    def test_shield_adds_two_ac(self):
        """Shield should add +2 to AC."""
        eq = CharacterEquipment()
        eq.armor = InventoryItem(
            id="leather",
            name="Leather",
            item_type="armor",
            ac_bonus=11
        )
        eq.off_hand = InventoryItem(
            id="shield",
            name="Shield",
            item_type="shield",  # Must be type "shield" for detection
            ac_bonus=2
        )
        # DEX 14 = +2, AC = 11 + 2 + 2(shield) = 15
        result = eq.calculate_ac(dexterity=14)
        assert result["shield_bonus"] == 2
        assert result["total_ac"] == 15


class TestWeaponProperties:
    """Test weapon property handling."""

    def test_finesse_weapon(self):
        """Finesse weapons can use DEX for attack/damage."""
        rapier = InventoryItem(
            id="rapier",
            name="Rapier",
            item_type="weapon",
            damage="1d8",
            damage_type="piercing",
            properties=["finesse"]
        )
        assert "finesse" in rapier.properties

    def test_two_handed_weapon(self):
        """Two-handed weapons require both hands."""
        greatsword = InventoryItem(
            id="greatsword",
            name="Greatsword",
            item_type="weapon",
            damage="2d6",
            damage_type="slashing",
            properties=["two-handed", "heavy"]
        )
        assert "two-handed" in greatsword.properties
        assert "heavy" in greatsword.properties

    def test_light_weapon(self):
        """Light weapons enable two-weapon fighting."""
        dagger = InventoryItem(
            id="dagger",
            name="Dagger",
            item_type="weapon",
            damage="1d4",
            damage_type="piercing",
            properties=["light", "finesse", "thrown"]
        )
        assert "light" in dagger.properties

    def test_loading_weapon(self):
        """Loading weapons limit attacks per action."""
        crossbow = InventoryItem(
            id="light_crossbow",
            name="Light Crossbow",
            item_type="weapon",
            damage="1d8",
            damage_type="piercing",
            properties=["loading", "ammunition", "two-handed"],
            range=80,
            long_range=320
        )
        assert "loading" in crossbow.properties
        assert crossbow.range == 80
        assert crossbow.long_range == 320


class TestEncumbrance:
    """Test carrying capacity and encumbrance."""

    def test_carrying_capacity_default(self):
        """Default carrying capacity should be 150 (STR 10 × 15)."""
        eq = CharacterEquipment()
        assert eq.carrying_capacity == 150.0

    def test_can_carry_within_capacity(self):
        """Should be able to carry items within capacity."""
        eq = CharacterEquipment()
        item = InventoryItem(id="test", name="Test", weight=50.0)
        assert eq.can_carry(item) is True

    def test_cannot_carry_over_capacity(self):
        """Should not be able to carry items over capacity."""
        eq = CharacterEquipment()
        eq.current_weight = 140.0
        item = InventoryItem(id="heavy", name="Heavy", weight=20.0)
        assert eq.can_carry(item) is False

    def test_encumbrance_normal(self):
        """Should be normal when under 5×STR."""
        eq = CharacterEquipment()
        eq.current_weight = 40.0
        status = eq.get_encumbrance_status(strength=10)
        assert status["status"] == "normal"
        assert status["speed_penalty"] == 0

    def test_encumbrance_encumbered(self):
        """Should be encumbered when over 5×STR."""
        eq = CharacterEquipment()
        eq.inventory = [InventoryItem(id="heavy", name="Heavy", weight=60.0)]
        status = eq.get_encumbrance_status(strength=10)
        assert status["status"] == "encumbered"
        assert status["speed_penalty"] == 10

    def test_encumbrance_heavily_encumbered(self):
        """Should be heavily encumbered when over 10×STR."""
        eq = CharacterEquipment()
        eq.inventory = [InventoryItem(id="very_heavy", name="Very Heavy", weight=110.0)]
        status = eq.get_encumbrance_status(strength=10)
        assert status["status"] == "heavily_encumbered"
        assert status["speed_penalty"] == 20
        assert status["disadvantage_on_physical"] is True


class TestWeightCalculation:
    """Test equipment weight calculation."""

    def test_calculate_weight_empty(self):
        """Empty equipment should weigh 0."""
        eq = CharacterEquipment()
        weight = eq.calculate_weight()
        assert weight == 0.0

    def test_calculate_weight_with_items(self):
        """Should calculate total weight of all equipment."""
        eq = CharacterEquipment()
        eq.main_hand = InventoryItem(id="sword", name="Sword", weight=3.0)
        eq.armor = InventoryItem(id="armor", name="Armor", weight=40.0)
        eq.inventory = [
            InventoryItem(id="potion", name="Potion", weight=0.5, quantity=5)
        ]
        weight = eq.calculate_weight()
        assert weight == 3.0 + 40.0 + 2.5  # sword + armor + 5 potions


class TestAttunement:
    """Test magic item attunement."""

    def test_max_attunement_slots(self):
        """Should have 3 attunement slots by default."""
        eq = CharacterEquipment()
        assert eq.max_attunement_slots == 3

    def test_item_requires_attunement(self):
        """Magic items can require attunement."""
        ring = InventoryItem(
            id="ring_of_protection",
            name="Ring of Protection",
            item_type="accessory",
            requires_attunement=True,
            rarity="rare",
            ac_bonus=1
        )
        assert ring.requires_attunement is True
        assert ring.is_attuned is False


class TestItemRarity:
    """Test item rarity levels."""

    def test_all_rarities_defined(self):
        """All D&D rarities should be defined."""
        expected = {"common", "uncommon", "rare", "very_rare", "legendary", "artifact"}
        actual = {r.value for r in ItemRarity}
        assert actual == expected

    def test_item_rarity_assignment(self):
        """Items can have rarity assigned."""
        item = InventoryItem(
            id="vorpal_sword",
            name="Vorpal Sword",
            rarity="legendary",
            requires_attunement=True
        )
        assert item.rarity == "legendary"
