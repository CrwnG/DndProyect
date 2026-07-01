"""Batch 61 (B3b): the SRD-compliance scanner and its canonical data stay healthy.

The audit's conclusions (SRD_COMPLIANCE_AUDIT.md) depend on scripts/srd_521_content.json
being a faithful extraction of the SRD 5.2.1 lists and on the scanner's rename map
pointing at real SRD names — guard both so a bad edit doesn't silently skew the audit.
"""
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _srd():
    return json.loads((SCRIPTS / "srd_521_content.json").read_text(encoding="utf-8"))


def test_srd_lists_have_the_expected_shape():
    srd = _srd()
    assert len(srd["spells"]) == 339         # headers validated by their metadata line
    assert len(srd["subclasses"]) == 12      # exactly one per class in the SRD
    assert set(srd["backgrounds"]) == {"acolyte", "criminal", "sage", "soldier"}
    assert len(srd["species"]) == 9
    # Spot checks — incl. apostrophe normalization and non-spell-header exclusion
    assert "fireball" in srd["spells"] and "arcane_hand" in srd["spells"]
    assert "hunters_mark" in srd["spells"]   # "Hunter's Mark" — apostrophe stripped
    for not_a_spell in ("actions", "traits", "bonus_actions", "animated_object"):
        assert not_a_spell not in srd["spells"]
    assert "champion" in srd["subclasses"] and "life_domain" in srd["subclasses"]


def test_rename_map_targets_are_all_real_srd_names():
    import sys
    sys.path.insert(0, str(SCRIPTS))
    import srd_audit
    srd_spells = set(_srd()["spells"])
    for src, dst in srd_audit.SPELL_RENAMES.items():
        assert dst in srd_spells, f"{src} maps to {dst}, which is not an SRD spell"
