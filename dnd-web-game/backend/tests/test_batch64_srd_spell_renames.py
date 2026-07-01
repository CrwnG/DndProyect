"""Batch 64 (B3c): wizard-named spells now ship under their SRD de-branded ids.

The SRD 5.2.1 includes these spells but drops the Product-Identity wizard names
(Bigby's Hand -> Arcane Hand, ...). We shipped 15 under the PI names — one of them
(mordenkainens_faithful_hound) even duplicated an existing faithful_hound entry.
Renamed the 14, deleted the duplicate, and updated every reference (class spell
lists, wild_shape, subclasses, condition maps).
"""
import json
from pathlib import Path

from app.core.spell_system import SpellRegistry

DATA = Path(__file__).resolve().parent.parent / "app" / "data"

OLD_IDS = [
    "melfs_acid_arrow", "bigbys_hand", "tashas_hideous_laughter", "leomunds_tiny_hut",
    "leomunds_secret_chest", "drawmijs_instant_summons", "evards_black_tentacles",
    "mordenkainens_sword", "mordenkainens_faithful_hound",
    "mordenkainens_magnificent_mansion", "mordenkainens_private_sanctum",
    "otilukes_freezing_sphere", "otilukes_resilient_sphere",
    "ottos_irresistible_dance", "rarys_telepathic_bond",
]
NEW_IDS = [
    "acid_arrow", "arcane_hand", "hideous_laughter", "tiny_hut", "secret_chest",
    "instant_summons", "black_tentacles", "arcane_sword", "faithful_hound",
    "magnificent_mansion", "private_sanctum", "freezing_sphere", "resilient_sphere",
    "irresistible_dance", "telepathic_bond",
]


def _registry_ids():
    return {s.id for s in SpellRegistry.get_instance().get_all_spells()}


def test_srd_names_present_and_pi_names_gone():
    ids = _registry_ids()
    for new in NEW_IDS:
        assert new in ids, f"missing SRD-named spell {new}"
    for old in OLD_IDS:
        assert old not in ids, f"Product-Identity spell id still shipped: {old}"


def test_no_data_file_references_the_old_ids():
    for path in DATA.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        for old in OLD_IDS:
            assert old not in text, f"{path.name} still references {old}"


def test_no_duplicate_spell_entries():
    all_spells = SpellRegistry.get_instance().get_all_spells()
    ids = [s.id for s in all_spells]
    assert len(ids) == len(set(ids))
    # The old duplicate pair collapsed into one spell
    assert ids.count("faithful_hound") == 1
