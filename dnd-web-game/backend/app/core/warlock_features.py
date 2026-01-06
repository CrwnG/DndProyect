"""
Warlock Features System for D&D 5e 2024

Comprehensive Warlock feature implementation:
- Pact Magic (short rest spell slots)
- Pact Boons (Blade, Chain, Tome)
- Eldritch Invocations with prerequisites
- Patron features integration
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum


class PactBoon(str, Enum):
    """Warlock Pact Boon options."""
    BLADE = "pact_of_the_blade"
    CHAIN = "pact_of_the_chain"
    TOME = "pact_of_the_tome"
    TALISMAN = "pact_of_the_talisman"


class WarlockPatron(str, Enum):
    """Warlock Patron (subclass) options."""
    ARCHFEY = "archfey"
    FIEND = "fiend"
    GREAT_OLD_ONE = "great_old_one"
    CELESTIAL = "celestial"
    HEXBLADE = "hexblade"
    FATHOMLESS = "fathomless"
    GENIE = "genie"
    UNDEAD = "undead"


@dataclass
class InvocationPrerequisite:
    """Prerequisites for an Eldritch Invocation."""
    min_level: int = 0
    pact_boon: Optional[PactBoon] = None
    patron: Optional[WarlockPatron] = None
    required_spell: Optional[str] = None  # Must know this spell
    required_cantrip: Optional[str] = None  # Must know this cantrip

    def check(
        self,
        level: int,
        pact: Optional[PactBoon],
        patron: Optional[WarlockPatron],
        spells_known: List[str],
        cantrips_known: List[str]
    ) -> bool:
        """Check if prerequisites are met."""
        if level < self.min_level:
            return False

        if self.pact_boon and pact != self.pact_boon:
            return False

        if self.patron and patron != self.patron:
            return False

        if self.required_spell and self.required_spell not in spells_known:
            return False

        if self.required_cantrip and self.required_cantrip not in cantrips_known:
            return False

        return True

    def description(self) -> str:
        """Get human-readable prerequisite description."""
        parts = []
        if self.min_level > 0:
            parts.append(f"Level {self.min_level}+")
        if self.pact_boon:
            parts.append(self.pact_boon.value.replace("_", " ").title())
        if self.patron:
            parts.append(f"{self.patron.value.replace('_', ' ').title()} Patron")
        if self.required_spell:
            parts.append(f"Knows {self.required_spell}")
        if self.required_cantrip:
            parts.append(f"Knows {self.required_cantrip}")

        return ", ".join(parts) if parts else "None"


@dataclass
class EldritchInvocation:
    """An Eldritch Invocation option."""
    id: str
    name: str
    description: str
    prerequisites: InvocationPrerequisite = field(default_factory=InvocationPrerequisite)

    # Mechanical effects
    grants_spell: Optional[str] = None  # At-will spell
    grants_spell_once_per_rest: Optional[str] = None  # Once per long rest
    modifies_cantrip: Optional[str] = None  # e.g., "eldritch_blast"
    grants_proficiency: List[str] = field(default_factory=list)
    passive_effect: Optional[str] = None  # Description of passive effect

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "prerequisites": self.prerequisites.description(),
            "grants_spell": self.grants_spell,
            "grants_spell_once_per_rest": self.grants_spell_once_per_rest,
            "modifies_cantrip": self.modifies_cantrip,
        }


# =============================================================================
# ELDRITCH INVOCATIONS
# =============================================================================

ELDRITCH_INVOCATIONS: Dict[str, EldritchInvocation] = {
    # No prerequisites
    "armor_of_shadows": EldritchInvocation(
        id="armor_of_shadows",
        name="Armor of Shadows",
        description="You can cast Mage Armor on yourself at will, without expending a spell slot or material components.",
        grants_spell="mage_armor",
    ),
    "beast_speech": EldritchInvocation(
        id="beast_speech",
        name="Beast Speech",
        description="You can cast Speak with Animals at will, without expending a spell slot.",
        grants_spell="speak_with_animals",
    ),
    "beguiling_influence": EldritchInvocation(
        id="beguiling_influence",
        name="Beguiling Influence",
        description="You gain proficiency in the Deception and Persuasion skills.",
        grants_proficiency=["deception", "persuasion"],
    ),
    "devils_sight": EldritchInvocation(
        id="devils_sight",
        name="Devil's Sight",
        description="You can see normally in darkness, both magical and nonmagical, to a distance of 120 feet.",
        passive_effect="See in all darkness 120 ft.",
    ),
    "eldritch_mind": EldritchInvocation(
        id="eldritch_mind",
        name="Eldritch Mind",
        description="You have advantage on Constitution saving throws to maintain concentration on a spell.",
        passive_effect="Advantage on concentration checks",
    ),
    "eldritch_sight": EldritchInvocation(
        id="eldritch_sight",
        name="Eldritch Sight",
        description="You can cast Detect Magic at will, without expending a spell slot.",
        grants_spell="detect_magic",
    ),
    "eyes_of_the_rune_keeper": EldritchInvocation(
        id="eyes_of_the_rune_keeper",
        name="Eyes of the Rune Keeper",
        description="You can read all writing.",
        passive_effect="Read all writing",
    ),
    "fiendish_vigor": EldritchInvocation(
        id="fiendish_vigor",
        name="Fiendish Vigor",
        description="You can cast False Life on yourself at will, without expending a spell slot or material components.",
        grants_spell="false_life",
    ),
    "gaze_of_two_minds": EldritchInvocation(
        id="gaze_of_two_minds",
        name="Gaze of Two Minds",
        description="You can use your action to touch a willing humanoid and perceive through its senses.",
        passive_effect="Perceive through touched creature's senses",
    ),
    "mask_of_many_faces": EldritchInvocation(
        id="mask_of_many_faces",
        name="Mask of Many Faces",
        description="You can cast Disguise Self at will, without expending a spell slot.",
        grants_spell="disguise_self",
    ),
    "misty_visions": EldritchInvocation(
        id="misty_visions",
        name="Misty Visions",
        description="You can cast Silent Image at will, without expending a spell slot or material components.",
        grants_spell="silent_image",
    ),

    # Eldritch Blast modifiers (require eldritch_blast cantrip)
    "agonizing_blast": EldritchInvocation(
        id="agonizing_blast",
        name="Agonizing Blast",
        description="When you cast Eldritch Blast, add your Charisma modifier to the damage it deals on a hit.",
        prerequisites=InvocationPrerequisite(required_cantrip="eldritch_blast"),
        modifies_cantrip="eldritch_blast",
    ),
    "eldritch_spear": EldritchInvocation(
        id="eldritch_spear",
        name="Eldritch Spear",
        description="When you cast Eldritch Blast, its range is 300 feet.",
        prerequisites=InvocationPrerequisite(required_cantrip="eldritch_blast"),
        modifies_cantrip="eldritch_blast",
    ),
    "grasp_of_hadar": EldritchInvocation(
        id="grasp_of_hadar",
        name="Grasp of Hadar",
        description="When you hit with Eldritch Blast, you can move the target 10 feet closer to you in a straight line.",
        prerequisites=InvocationPrerequisite(required_cantrip="eldritch_blast"),
        modifies_cantrip="eldritch_blast",
    ),
    "lance_of_lethargy": EldritchInvocation(
        id="lance_of_lethargy",
        name="Lance of Lethargy",
        description="When you hit with Eldritch Blast, you can reduce the target's speed by 10 feet until the end of your next turn.",
        prerequisites=InvocationPrerequisite(required_cantrip="eldritch_blast"),
        modifies_cantrip="eldritch_blast",
    ),
    "repelling_blast": EldritchInvocation(
        id="repelling_blast",
        name="Repelling Blast",
        description="When you hit with Eldritch Blast, you can push the target 10 feet away from you in a straight line.",
        prerequisites=InvocationPrerequisite(required_cantrip="eldritch_blast"),
        modifies_cantrip="eldritch_blast",
    ),

    # Level 5+ invocations
    "mire_the_mind": EldritchInvocation(
        id="mire_the_mind",
        name="Mire the Mind",
        description="You can cast Slow once using a warlock spell slot. You can't do so again until you finish a long rest.",
        prerequisites=InvocationPrerequisite(min_level=5),
        grants_spell_once_per_rest="slow",
    ),
    "one_with_shadows": EldritchInvocation(
        id="one_with_shadows",
        name="One with Shadows",
        description="When you are in dim light or darkness, you can use your action to become invisible until you move or take an action or reaction.",
        prerequisites=InvocationPrerequisite(min_level=5),
        passive_effect="Become invisible in darkness (until move/act)",
    ),
    "sign_of_ill_omen": EldritchInvocation(
        id="sign_of_ill_omen",
        name="Sign of Ill Omen",
        description="You can cast Bestow Curse once using a warlock spell slot. You can't do so again until you finish a long rest.",
        prerequisites=InvocationPrerequisite(min_level=5),
        grants_spell_once_per_rest="bestow_curse",
    ),
    "thirsting_blade": EldritchInvocation(
        id="thirsting_blade",
        name="Thirsting Blade",
        description="You can attack with your pact weapon twice instead of once when you take the Attack action on your turn.",
        prerequisites=InvocationPrerequisite(min_level=5, pact_boon=PactBoon.BLADE),
        passive_effect="Extra Attack with pact weapon",
    ),

    # Level 7+ invocations
    "bewitching_whispers": EldritchInvocation(
        id="bewitching_whispers",
        name="Bewitching Whispers",
        description="You can cast Compulsion once using a warlock spell slot. You can't do so again until you finish a long rest.",
        prerequisites=InvocationPrerequisite(min_level=7),
        grants_spell_once_per_rest="compulsion",
    ),
    "ghostly_gaze": EldritchInvocation(
        id="ghostly_gaze",
        name="Ghostly Gaze",
        description="You can see through solid objects to 30 feet. Lasts 1 minute, once per short/long rest.",
        prerequisites=InvocationPrerequisite(min_level=7),
        passive_effect="See through objects 30 ft. (1 min, 1/rest)",
    ),
    "sculptor_of_flesh": EldritchInvocation(
        id="sculptor_of_flesh",
        name="Sculptor of Flesh",
        description="You can cast Polymorph once using a warlock spell slot. You can't do so again until you finish a long rest.",
        prerequisites=InvocationPrerequisite(min_level=7),
        grants_spell_once_per_rest="polymorph",
    ),

    # Level 9+ invocations
    "ascendant_step": EldritchInvocation(
        id="ascendant_step",
        name="Ascendant Step",
        description="You can cast Levitate on yourself at will, without expending a spell slot or material components.",
        prerequisites=InvocationPrerequisite(min_level=9),
        grants_spell="levitate",
    ),
    "minions_of_chaos": EldritchInvocation(
        id="minions_of_chaos",
        name="Minions of Chaos",
        description="You can cast Conjure Elemental once using a warlock spell slot. You can't do so again until you finish a long rest.",
        prerequisites=InvocationPrerequisite(min_level=9),
        grants_spell_once_per_rest="conjure_elemental",
    ),
    "otherworldly_leap": EldritchInvocation(
        id="otherworldly_leap",
        name="Otherworldly Leap",
        description="You can cast Jump on yourself at will, without expending a spell slot or material components.",
        prerequisites=InvocationPrerequisite(min_level=9),
        grants_spell="jump",
    ),
    "whispers_of_the_grave": EldritchInvocation(
        id="whispers_of_the_grave",
        name="Whispers of the Grave",
        description="You can cast Speak with Dead at will, without expending a spell slot.",
        prerequisites=InvocationPrerequisite(min_level=9),
        grants_spell="speak_with_dead",
    ),

    # Level 12+ invocations
    "lifedrinker": EldritchInvocation(
        id="lifedrinker",
        name="Lifedrinker",
        description="When you hit with your pact weapon, the creature takes extra necrotic damage equal to your Charisma modifier.",
        prerequisites=InvocationPrerequisite(min_level=12, pact_boon=PactBoon.BLADE),
        passive_effect="Pact weapon deals +CHA necrotic damage",
    ),

    # Level 15+ invocations
    "chains_of_carceri": EldritchInvocation(
        id="chains_of_carceri",
        name="Chains of Carceri",
        description="You can cast Hold Monster at will, targeting celestials, fiends, or elementals, without expending a spell slot.",
        prerequisites=InvocationPrerequisite(min_level=15, pact_boon=PactBoon.CHAIN),
        grants_spell="hold_monster",
    ),
    "master_of_myriad_forms": EldritchInvocation(
        id="master_of_myriad_forms",
        name="Master of Myriad Forms",
        description="You can cast Alter Self at will, without expending a spell slot.",
        prerequisites=InvocationPrerequisite(min_level=15),
        grants_spell="alter_self",
    ),
    "visions_of_distant_realms": EldritchInvocation(
        id="visions_of_distant_realms",
        name="Visions of Distant Realms",
        description="You can cast Arcane Eye at will, without expending a spell slot.",
        prerequisites=InvocationPrerequisite(min_level=15),
        grants_spell="arcane_eye",
    ),
    "witch_sight": EldritchInvocation(
        id="witch_sight",
        name="Witch Sight",
        description="You can see the true form of any shapechanger or creature concealed by illusion or transmutation magic within 30 feet.",
        prerequisites=InvocationPrerequisite(min_level=15),
        passive_effect="See true forms within 30 ft.",
    ),

    # Pact of the Tome invocations
    "book_of_ancient_secrets": EldritchInvocation(
        id="book_of_ancient_secrets",
        name="Book of Ancient Secrets",
        description="You can inscribe magical rituals in your Book of Shadows. You can cast those rituals as rituals.",
        prerequisites=InvocationPrerequisite(pact_boon=PactBoon.TOME),
        passive_effect="Learn and cast ritual spells",
    ),

    # Pact of the Chain invocations
    "voice_of_the_chain_master": EldritchInvocation(
        id="voice_of_the_chain_master",
        name="Voice of the Chain Master",
        description="You can communicate telepathically with your familiar and perceive through its senses while on the same plane.",
        prerequisites=InvocationPrerequisite(pact_boon=PactBoon.CHAIN),
        passive_effect="Telepathy with familiar, perceive through senses",
    ),
    "investment_of_the_chain_master": EldritchInvocation(
        id="investment_of_the_chain_master",
        name="Investment of the Chain Master",
        description="Your familiar gains a flying or swimming speed of 40 feet, its attacks count as magical, and when you command it to attack, it uses your spell attack modifier and spell save DC.",
        prerequisites=InvocationPrerequisite(pact_boon=PactBoon.CHAIN),
        passive_effect="Enhanced familiar (40ft fly/swim, magical attacks, your spell stats)",
    ),

    # Pact of the Talisman invocations
    "protection_of_the_talisman": EldritchInvocation(
        id="protection_of_the_talisman",
        name="Protection of the Talisman",
        description="When the wearer fails a saving throw, they can add a d4 to the roll. Proficiency bonus times per long rest.",
        prerequisites=InvocationPrerequisite(min_level=7, pact_boon=PactBoon.TALISMAN),
        passive_effect="Add d4 to failed saves (PB/long rest)",
    ),
}


# =============================================================================
# PACT MAGIC
# =============================================================================

def get_pact_magic_slots(level: int) -> Dict[str, int]:
    """
    Get Warlock Pact Magic slots.

    Warlocks have a unique spellcasting system:
    - Few slots (1-4) that are all the same level
    - Slots refresh on short rest

    Returns:
        Dict with 'slots' and 'slot_level'
    """
    if level >= 17:
        return {"slots": 4, "slot_level": 5}
    elif level >= 11:
        return {"slots": 3, "slot_level": 5}
    elif level >= 9:
        return {"slots": 2, "slot_level": 5}
    elif level >= 7:
        return {"slots": 2, "slot_level": 4}
    elif level >= 5:
        return {"slots": 2, "slot_level": 3}
    elif level >= 3:
        return {"slots": 2, "slot_level": 2}
    else:
        return {"slots": 1, "slot_level": 1}


def get_mystic_arcanum_spells(level: int) -> Dict[int, int]:
    """
    Get Mystic Arcanum spells available.

    At levels 11, 13, 15, 17, Warlocks get one spell of 6th, 7th, 8th, 9th level
    that can be cast once per long rest without a spell slot.

    Returns:
        Dict mapping spell level to uses (always 1)
    """
    arcanum = {}
    if level >= 11:
        arcanum[6] = 1
    if level >= 13:
        arcanum[7] = 1
    if level >= 15:
        arcanum[8] = 1
    if level >= 17:
        arcanum[9] = 1
    return arcanum


# =============================================================================
# PACT BOON FEATURES
# =============================================================================

@dataclass
class PactBoonInfo:
    """Information about a Pact Boon."""
    id: PactBoon
    name: str
    description: str
    features: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id.value,
            "name": self.name,
            "description": self.description,
            "features": self.features,
        }


PACT_BOONS: Dict[PactBoon, PactBoonInfo] = {
    PactBoon.BLADE: PactBoonInfo(
        id=PactBoon.BLADE,
        name="Pact of the Blade",
        description="You can use your action to create a pact weapon in your empty hand. You can choose the form. You are proficient with it while you wield it.",
        features=[
            "Create pact weapon (any form)",
            "Proficient with pact weapon",
            "Weapon counts as magical",
            "Can transform magic weapon into pact weapon",
        ],
    ),
    PactBoon.CHAIN: PactBoonInfo(
        id=PactBoon.CHAIN,
        name="Pact of the Chain",
        description="You learn the Find Familiar spell and can cast it as a ritual. Your familiar can take special forms: imp, pseudodragon, quasit, or sprite.",
        features=[
            "Learn Find Familiar (ritual)",
            "Special familiar forms (imp, pseudodragon, quasit, sprite)",
            "Command familiar to Attack as bonus action",
        ],
    ),
    PactBoon.TOME: PactBoonInfo(
        id=PactBoon.TOME,
        name="Pact of the Tome",
        description="Your patron gives you a grimoire called a Book of Shadows. Choose three cantrips from any class's spell list. They count as warlock cantrips for you.",
        features=[
            "Book of Shadows",
            "Three cantrips from any class",
            "Cantrips count as warlock cantrips",
        ],
    ),
    PactBoon.TALISMAN: PactBoonInfo(
        id=PactBoon.TALISMAN,
        name="Pact of the Talisman",
        description="Your patron gives you a special amulet. When the wearer fails an ability check, they can add a d4 to the roll, potentially turning the failure into a success.",
        features=[
            "Talisman amulet",
            "Add d4 to failed ability checks",
            "Proficiency bonus uses per long rest",
        ],
    ),
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_available_invocations(
    level: int,
    pact_boon: Optional[PactBoon] = None,
    patron: Optional[WarlockPatron] = None,
    spells_known: List[str] = None,
    cantrips_known: List[str] = None,
    current_invocations: List[str] = None
) -> List[EldritchInvocation]:
    """
    Get all Eldritch Invocations available to a Warlock.

    Args:
        level: Warlock level
        pact_boon: Selected Pact Boon (if any)
        patron: Warlock Patron subclass
        spells_known: List of spell IDs the warlock knows
        cantrips_known: List of cantrip IDs the warlock knows
        current_invocations: Already selected invocations (to exclude)

    Returns:
        List of available EldritchInvocation objects
    """
    spells_known = spells_known or []
    cantrips_known = cantrips_known or []
    current_invocations = current_invocations or []

    available = []
    for inv in ELDRITCH_INVOCATIONS.values():
        # Skip already selected
        if inv.id in current_invocations:
            continue

        # Check prerequisites
        if inv.prerequisites.check(level, pact_boon, patron, spells_known, cantrips_known):
            available.append(inv)

    return available


def get_invocation_count(level: int) -> int:
    """Get number of Eldritch Invocations known at a level."""
    if level >= 17:
        return 8
    elif level >= 15:
        return 7
    elif level >= 12:
        return 6
    elif level >= 9:
        return 5
    elif level >= 7:
        return 4
    elif level >= 5:
        return 3
    elif level >= 2:
        return 2
    return 0


def get_cantrips_known(level: int) -> int:
    """Get number of cantrips known at a level."""
    if level >= 10:
        return 4
    elif level >= 4:
        return 3
    else:
        return 2


def get_spells_known(level: int) -> int:
    """Get number of spells known at a level."""
    if level >= 19:
        return 15
    elif level >= 17:
        return 14
    elif level >= 15:
        return 13
    elif level >= 13:
        return 12
    elif level >= 11:
        return 11
    else:
        # Level 1-10: level + 1
        return level + 1


def can_select_pact_boon(level: int) -> bool:
    """Check if Warlock can select a Pact Boon (level 3+)."""
    return level >= 3


def get_eldritch_blast_beams(level: int) -> int:
    """Get number of Eldritch Blast beams."""
    if level >= 17:
        return 4
    elif level >= 11:
        return 3
    elif level >= 5:
        return 2
    return 1


def calculate_eldritch_blast_damage(
    level: int,
    charisma_mod: int,
    invocations: List[str]
) -> Dict[str, Any]:
    """
    Calculate Eldritch Blast damage with invocations.

    Returns dict with damage info per beam.
    """
    beams = get_eldritch_blast_beams(level)
    damage_per_beam = "1d10"

    # Check for Agonizing Blast
    bonus_damage = 0
    if "agonizing_blast" in invocations:
        bonus_damage = charisma_mod

    effects = []
    if "repelling_blast" in invocations:
        effects.append("Push 10 ft.")
    if "grasp_of_hadar" in invocations:
        effects.append("Pull 10 ft.")
    if "lance_of_lethargy" in invocations:
        effects.append("Speed -10 ft.")

    range_ft = 300 if "eldritch_spear" in invocations else 120

    return {
        "beams": beams,
        "damage_per_beam": damage_per_beam,
        "bonus_damage": bonus_damage,
        "total_potential": f"{beams}d10 + {beams * bonus_damage}" if bonus_damage else f"{beams}d10",
        "range": range_ft,
        "effects": effects,
    }


# Alias for backwards compatibility
get_warlock_pact_slots = get_pact_magic_slots


def has_invocation(known_invocations: List[str], invocation_id: str) -> bool:
    """Check if warlock knows a specific invocation."""
    return invocation_id in known_invocations


# =============================================================================
# PACT BOON MECHANICS
# =============================================================================

@dataclass
class PactBladeState:
    """
    Tracks Pact of the Blade state.

    Pact of the Blade (Level 3):
    - Create pact weapon as action
    - Proficient with pact weapon
    - Weapon counts as magical
    - Can bond a magic weapon (ritual)
    - Hexblade: Use CHA for attacks
    """
    summoned_weapon: Optional[str] = None  # Current weapon form
    bonded_weapon: Optional[Dict[str, Any]] = None  # Permanent bonded magic weapon
    is_summoned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summoned_weapon": self.summoned_weapon,
            "bonded_weapon": self.bonded_weapon,
            "is_summoned": self.is_summoned,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PactBladeState":
        return cls(
            summoned_weapon=data.get("summoned_weapon"),
            bonded_weapon=data.get("bonded_weapon"),
            is_summoned=data.get("is_summoned", False),
        )


PACT_WEAPON_FORMS = [
    "longsword", "shortsword", "greatsword", "rapier",
    "battleaxe", "greataxe", "handaxe",
    "warhammer", "maul", "mace",
    "glaive", "halberd", "pike", "spear",
    "shortbow", "longbow", "light_crossbow", "heavy_crossbow",
]


def summon_pact_weapon(
    state: PactBladeState,
    weapon_form: str,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Summon a pact weapon (action).

    Args:
        state: Current Pact Blade state
        weapon_form: Desired weapon form (e.g., "longsword", "greataxe")

    Returns:
        Tuple of (success, message, weapon_data)
    """
    if state.is_summoned:
        return False, "A pact weapon is already summoned. Dismiss it first.", {}

    weapon_form_lower = weapon_form.lower().replace(" ", "_")

    if weapon_form_lower not in PACT_WEAPON_FORMS:
        return False, f"Invalid weapon form: {weapon_form}", {}

    state.summoned_weapon = weapon_form_lower
    state.is_summoned = True

    weapon_data = {
        "name": f"Pact Weapon ({weapon_form_lower.replace('_', ' ').title()})",
        "weapon_type": weapon_form_lower,
        "is_magical": True,
        "is_pact_weapon": True,
        "proficient": True,
    }

    return True, f"Pact weapon summoned: {weapon_form_lower.replace('_', ' ').title()}", weapon_data


def dismiss_pact_weapon(state: PactBladeState) -> bool:
    """
    Dismiss the summoned pact weapon.

    Returns:
        True if weapon was dismissed
    """
    if not state.is_summoned:
        return False

    state.summoned_weapon = None
    state.is_summoned = False
    return True


def bond_magic_weapon(
    state: PactBladeState,
    weapon_data: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Bond a magic weapon to become your pact weapon (1 hour ritual).

    Args:
        state: Current Pact Blade state
        weapon_data: The weapon to bond

    Returns:
        Tuple of (success, message)
    """
    if not weapon_data.get("is_magical"):
        return False, "Only magic weapons can be bonded."

    if weapon_data.get("requires_attunement") and not weapon_data.get("attuned_by"):
        return False, "Weapon requires attunement before bonding."

    state.bonded_weapon = weapon_data.copy()
    state.bonded_weapon["is_pact_weapon"] = True

    return True, f"Bonded {weapon_data.get('name', 'magic weapon')} as your pact weapon."


def get_pact_weapon_attack_stat(
    patron: Optional[WarlockPatron],
    invocations: List[str]
) -> str:
    """
    Determine which ability score to use for pact weapon attacks.

    Hexblade and certain invocations allow CHA instead of STR/DEX.

    Returns:
        "charisma" if CHA-based attacks allowed, else "strength" or "dexterity"
    """
    # Hexblade always uses CHA for pact weapon
    if patron == WarlockPatron.HEXBLADE:
        return "charisma"

    # Regular pact blade uses STR/DEX
    return "strength"  # Or dexterity for finesse, handled elsewhere


@dataclass
class PactChainState:
    """
    Tracks Pact of the Chain state.

    Pact of the Chain (Level 3):
    - Find Familiar spell (ritual)
    - Special familiar forms (imp, pseudodragon, quasit, sprite)
    - Command familiar to Attack as bonus action
    """
    familiar_form: Optional[str] = None
    familiar_hp: int = 0
    familiar_max_hp: int = 0
    familiar_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "familiar_form": self.familiar_form,
            "familiar_hp": self.familiar_hp,
            "familiar_max_hp": self.familiar_max_hp,
            "familiar_active": self.familiar_active,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PactChainState":
        return cls(
            familiar_form=data.get("familiar_form"),
            familiar_hp=data.get("familiar_hp", 0),
            familiar_max_hp=data.get("familiar_max_hp", 0),
            familiar_active=data.get("familiar_active", False),
        )


CHAIN_FAMILIAR_FORMS = {
    "imp": {"hp": 10, "ac": 13, "attack_bonus": 5, "damage": "1d4+3"},
    "pseudodragon": {"hp": 7, "ac": 13, "attack_bonus": 4, "damage": "1d4+2"},
    "quasit": {"hp": 7, "ac": 13, "attack_bonus": 4, "damage": "1d4+3"},
    "sprite": {"hp": 2, "ac": 15, "attack_bonus": 6, "damage": "1"},
}


def summon_chain_familiar(
    state: PactChainState,
    form: str
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Summon a Pact of the Chain familiar.

    Args:
        state: Current Pact Chain state
        form: Familiar form (imp, pseudodragon, quasit, sprite)

    Returns:
        Tuple of (success, message, familiar_data)
    """
    form_lower = form.lower()

    if form_lower not in CHAIN_FAMILIAR_FORMS:
        return False, f"Invalid familiar form: {form}. Must be imp, pseudodragon, quasit, or sprite.", {}

    form_stats = CHAIN_FAMILIAR_FORMS[form_lower]

    state.familiar_form = form_lower
    state.familiar_hp = form_stats["hp"]
    state.familiar_max_hp = form_stats["hp"]
    state.familiar_active = True

    familiar_data = {
        "form": form_lower,
        "hp": form_stats["hp"],
        "max_hp": form_stats["hp"],
        "ac": form_stats["ac"],
        "attack_bonus": form_stats["attack_bonus"],
        "damage": form_stats["damage"],
    }

    return True, f"Summoned {form_lower} familiar!", familiar_data


def familiar_attack(
    state: PactChainState,
    invocations: List[str],
    warlock_spell_attack: int = 0,
    warlock_spell_dc: int = 0
) -> Dict[str, Any]:
    """
    Command familiar to attack (bonus action).

    Investment of the Chain Master allows using warlock's spell attack/DC.

    Returns:
        Attack data with bonus and damage
    """
    if not state.familiar_active:
        return {"error": "No familiar summoned"}

    form_stats = CHAIN_FAMILIAR_FORMS.get(state.familiar_form, {})

    # Investment of the Chain Master uses warlock's stats
    if "investment_of_the_chain_master" in invocations:
        attack_bonus = warlock_spell_attack
        damage = form_stats.get("damage", "1d4")
    else:
        attack_bonus = form_stats.get("attack_bonus", 0)
        damage = form_stats.get("damage", "1d4")

    return {
        "form": state.familiar_form,
        "attack_bonus": attack_bonus,
        "damage": damage,
        "action_type": "bonus_action",
    }


@dataclass
class PactTomeState:
    """
    Tracks Pact of the Tome state.

    Pact of the Tome (Level 3):
    - Book of Shadows
    - Three cantrips from any class
    - Ritual spells (with Book of Ancient Secrets)
    """
    extra_cantrips: List[str] = field(default_factory=list)  # Three from any class
    ritual_spells: List[str] = field(default_factory=list)   # From Book of Ancient Secrets

    def to_dict(self) -> Dict[str, Any]:
        return {
            "extra_cantrips": self.extra_cantrips,
            "ritual_spells": self.ritual_spells,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PactTomeState":
        return cls(
            extra_cantrips=data.get("extra_cantrips", []),
            ritual_spells=data.get("ritual_spells", []),
        )


def set_tome_cantrips(
    state: PactTomeState,
    cantrips: List[str]
) -> Tuple[bool, str]:
    """
    Set the three cantrips from the Book of Shadows.

    Args:
        state: Current Pact Tome state
        cantrips: List of exactly 3 cantrip IDs

    Returns:
        Tuple of (success, message)
    """
    if len(cantrips) != 3:
        return False, "Must choose exactly 3 cantrips for Book of Shadows."

    state.extra_cantrips = cantrips
    return True, f"Book of Shadows now contains: {', '.join(cantrips)}"


def add_ritual_to_tome(
    state: PactTomeState,
    spell_id: str,
    has_book_of_ancient_secrets: bool
) -> Tuple[bool, str]:
    """
    Add a ritual spell to the Book of Shadows.

    Requires Book of Ancient Secrets invocation.

    Args:
        state: Current Pact Tome state
        spell_id: The ritual spell to add
        has_book_of_ancient_secrets: Whether warlock has the invocation

    Returns:
        Tuple of (success, message)
    """
    if not has_book_of_ancient_secrets:
        return False, "Requires Book of Ancient Secrets invocation."

    if spell_id in state.ritual_spells:
        return False, f"{spell_id} is already in your Book of Shadows."

    state.ritual_spells.append(spell_id)
    return True, f"Added {spell_id} to your Book of Shadows."


@dataclass
class PactTalismanState:
    """
    Tracks Pact of the Talisman state.

    Pact of the Talisman (Level 3):
    - Talisman amulet
    - Add d4 to failed ability checks
    - Uses = proficiency bonus per long rest
    """
    max_uses: int = 2  # Proficiency bonus
    uses_remaining: int = 2
    wearer_id: Optional[str] = None  # Who is wearing the talisman

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_uses": self.max_uses,
            "uses_remaining": self.uses_remaining,
            "wearer_id": self.wearer_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PactTalismanState":
        return cls(
            max_uses=data.get("max_uses", 2),
            uses_remaining=data.get("uses_remaining", 2),
            wearer_id=data.get("wearer_id"),
        )


def initialize_talisman_state(level: int) -> PactTalismanState:
    """Create a new Pact Talisman state."""
    prof_bonus = 2 + ((level - 1) // 4)
    return PactTalismanState(
        max_uses=prof_bonus,
        uses_remaining=prof_bonus,
    )


def use_talisman_reroll(state: PactTalismanState) -> Tuple[bool, str, int]:
    """
    Use talisman to add d4 to a failed ability check.

    Returns:
        Tuple of (success, message, d4_roll)
    """
    if state.uses_remaining <= 0:
        return False, "No talisman uses remaining.", 0

    import random
    d4_roll = random.randint(1, 4)
    state.uses_remaining -= 1

    return True, f"Talisman adds +{d4_roll} to the roll!", d4_roll


def restore_talisman_uses(state: PactTalismanState, level: int) -> int:
    """
    Restore talisman uses on long rest.

    Returns:
        Number of uses restored
    """
    prof_bonus = 2 + ((level - 1) // 4)
    state.max_uses = prof_bonus
    restored = prof_bonus - state.uses_remaining
    state.uses_remaining = prof_bonus
    return restored


# =============================================================================
# MYSTIC ARCANUM STATE
# =============================================================================

@dataclass
class MysticArcanumState:
    """
    Tracks Mystic Arcanum uses.

    Mystic Arcanum (Levels 11, 13, 15, 17):
    - One 6th, 7th, 8th, 9th level spell each
    - Cast once per long rest without slot
    """
    spells_chosen: Dict[int, str] = field(default_factory=dict)  # {6: "spell_id", 7: ...}
    used_this_rest: Set[int] = field(default_factory=set)  # Which levels have been used

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spells_chosen": self.spells_chosen,
            "used_this_rest": list(self.used_this_rest),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MysticArcanumState":
        return cls(
            spells_chosen=data.get("spells_chosen", {}),
            used_this_rest=set(data.get("used_this_rest", [])),
        )


def get_mystic_arcanum_levels(level: int) -> List[int]:
    """Get which Mystic Arcanum spell levels are available."""
    levels = []
    if level >= 11:
        levels.append(6)
    if level >= 13:
        levels.append(7)
    if level >= 15:
        levels.append(8)
    if level >= 17:
        levels.append(9)
    return levels


def set_mystic_arcanum_spell(
    state: MysticArcanumState,
    spell_level: int,
    spell_id: str,
    warlock_level: int
) -> Tuple[bool, str]:
    """
    Set the Mystic Arcanum spell for a given level.

    Args:
        state: Current Mystic Arcanum state
        spell_level: The arcanum level (6-9)
        spell_id: The spell to set
        warlock_level: Warlock's current level

    Returns:
        Tuple of (success, message)
    """
    available_levels = get_mystic_arcanum_levels(warlock_level)

    if spell_level not in available_levels:
        return False, f"Level {spell_level} Mystic Arcanum not available at warlock level {warlock_level}."

    state.spells_chosen[spell_level] = spell_id
    return True, f"Set {spell_id} as your {spell_level}th level Mystic Arcanum."


def cast_mystic_arcanum(
    state: MysticArcanumState,
    spell_level: int
) -> Tuple[bool, str, Optional[str]]:
    """
    Cast a Mystic Arcanum spell.

    Args:
        state: Current Mystic Arcanum state
        spell_level: The arcanum level to cast

    Returns:
        Tuple of (success, message, spell_id)
    """
    if spell_level not in state.spells_chosen:
        return False, f"No {spell_level}th level Mystic Arcanum spell chosen.", None

    if spell_level in state.used_this_rest:
        return False, f"Already used your {spell_level}th level Mystic Arcanum this rest.", None

    spell_id = state.spells_chosen[spell_level]
    state.used_this_rest.add(spell_level)

    return True, f"Cast Mystic Arcanum: {spell_id}", spell_id


def restore_mystic_arcanum(state: MysticArcanumState) -> int:
    """
    Restore all Mystic Arcanum uses on long rest.

    Returns:
        Number of arcanums restored
    """
    restored = len(state.used_this_rest)
    state.used_this_rest.clear()
    return restored


# =============================================================================
# WARLOCK PATRON FEATURES
# =============================================================================

@dataclass
class PatronFeature:
    """A Warlock Patron feature."""
    id: str
    name: str
    level: int
    description: str
    grants_spells: List[str] = field(default_factory=list)
    passive_effect: Optional[str] = None


FIEND_FEATURES: List[PatronFeature] = [
    PatronFeature(
        id="dark_ones_blessing",
        name="Dark One's Blessing",
        level=1,
        description="When you reduce a hostile creature to 0 HP, gain temp HP equal to CHA mod + warlock level.",
        passive_effect="Temp HP on kill = CHA + level",
    ),
    PatronFeature(
        id="dark_ones_own_luck",
        name="Dark One's Own Luck",
        level=6,
        description="When you make an ability check or saving throw, add 1d10 to the roll. Once per short/long rest.",
    ),
    PatronFeature(
        id="fiendish_resilience",
        name="Fiendish Resilience",
        level=10,
        description="Choose one damage type when you finish a short or long rest. You have resistance to that type.",
        passive_effect="Resistance to chosen damage type",
    ),
    PatronFeature(
        id="hurl_through_hell",
        name="Hurl Through Hell",
        level=14,
        description="When you hit with an attack, banish target to Hell. They take 10d10 psychic damage. Once per long rest.",
    ),
]

ARCHFEY_FEATURES: List[PatronFeature] = [
    PatronFeature(
        id="fey_presence",
        name="Fey Presence",
        level=1,
        description="As an action, charm or frighten creatures in a 10-foot cube. WIS save negates. Once per short/long rest.",
    ),
    PatronFeature(
        id="misty_escape",
        name="Misty Escape",
        level=6,
        description="When you take damage, reaction to turn invisible and teleport up to 60 feet. Once per short/long rest.",
    ),
    PatronFeature(
        id="beguiling_defenses",
        name="Beguiling Defenses",
        level=10,
        description="You are immune to being charmed. When a creature tries to charm you, turn the charm back on them.",
        passive_effect="Immune to charm, reflect charm attempts",
    ),
    PatronFeature(
        id="dark_delirium",
        name="Dark Delirium",
        level=14,
        description="As an action, charm or frighten a creature for 1 minute. WIS save negates. Once per short/long rest.",
    ),
]

GREAT_OLD_ONE_FEATURES: List[PatronFeature] = [
    PatronFeature(
        id="awakened_mind",
        name="Awakened Mind",
        level=1,
        description="You can telepathically speak to any creature within 30 feet that you can see.",
        passive_effect="Telepathy 30 ft.",
    ),
    PatronFeature(
        id="entropic_ward",
        name="Entropic Ward",
        level=6,
        description="When attacked, reaction to impose disadvantage. If attack misses, gain advantage on your next attack.",
    ),
    PatronFeature(
        id="thought_shield",
        name="Thought Shield",
        level=10,
        description="Your thoughts can't be read. You have resistance to psychic damage.",
        passive_effect="Immune to mind reading, resistance to psychic",
    ),
    PatronFeature(
        id="create_thrall",
        name="Create Thrall",
        level=14,
        description="Touch an incapacitated humanoid to charm it permanently until Remove Curse is cast.",
    ),
]

CELESTIAL_FEATURES: List[PatronFeature] = [
    PatronFeature(
        id="healing_light",
        name="Healing Light",
        level=1,
        description="You have a pool of d6s equal to 1 + warlock level. As a bonus action, heal a creature within 60 feet.",
    ),
    PatronFeature(
        id="radiant_soul",
        name="Radiant Soul",
        level=6,
        description="You have resistance to radiant damage. When you cast a spell that deals fire or radiant damage, add CHA mod to one roll.",
        passive_effect="Resistance to radiant, +CHA to fire/radiant spells",
    ),
    PatronFeature(
        id="celestial_resilience",
        name="Celestial Resilience",
        level=10,
        description="You and up to 5 creatures gain temp HP equal to your warlock level + CHA mod when you finish a short/long rest.",
        passive_effect="Temp HP on rest for party",
    ),
    PatronFeature(
        id="searing_vengeance",
        name="Searing Vengeance",
        level=14,
        description="When you make a death save, regain half HP max and stand up. Creatures within 30 feet take radiant damage and are blinded.",
    ),
]

HEXBLADE_FEATURES: List[PatronFeature] = [
    PatronFeature(
        id="hexblades_curse",
        name="Hexblade's Curse",
        level=1,
        description="As a bonus action, curse a creature within 30 feet. Gain +prof damage, crits on 19-20, regain HP on its death.",
    ),
    PatronFeature(
        id="hex_warrior",
        name="Hex Warrior",
        level=1,
        description="Proficiency with medium armor, shields, and martial weapons. Use CHA for weapon attacks (one weapon, or pact weapon).",
        passive_effect="CHA for weapon attacks",
    ),
    PatronFeature(
        id="accursed_specter",
        name="Accursed Specter",
        level=6,
        description="When you slay a humanoid, raise it as a specter that serves you until your next long rest.",
    ),
    PatronFeature(
        id="armor_of_hexes",
        name="Armor of Hexes",
        level=10,
        description="If the target of your Hexblade's Curse hits you, roll a d6. On 4+, the attack misses.",
        passive_effect="50% chance for cursed target to miss",
    ),
    PatronFeature(
        id="master_of_hexes",
        name="Master of Hexes",
        level=14,
        description="When a creature cursed by your Hexblade's Curse dies, move the curse to another creature within 30 feet.",
    ),
]

PATRON_FEATURES: Dict[WarlockPatron, List[PatronFeature]] = {
    WarlockPatron.FIEND: FIEND_FEATURES,
    WarlockPatron.ARCHFEY: ARCHFEY_FEATURES,
    WarlockPatron.GREAT_OLD_ONE: GREAT_OLD_ONE_FEATURES,
    WarlockPatron.CELESTIAL: CELESTIAL_FEATURES,
    WarlockPatron.HEXBLADE: HEXBLADE_FEATURES,
}


def get_patron_features_at_level(
    patron: WarlockPatron,
    level: int
) -> List[PatronFeature]:
    """Get all patron features available at a given level."""
    features = PATRON_FEATURES.get(patron, [])
    return [f for f in features if f.level <= level]


def get_new_patron_features_at_level(
    patron: WarlockPatron,
    level: int
) -> List[PatronFeature]:
    """Get patron features gained exactly at a given level."""
    features = PATRON_FEATURES.get(patron, [])
    return [f for f in features if f.level == level]
