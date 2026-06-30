"""Batch 49 (B2): the shipped bestiary must not contain TIER-1 Product-Identity creatures.

SRD 5.2.1 / CC-BY-4.0 excludes WotC Product Identity. The audit (SRD_COMPLIANCE_AUDIT.md)
flagged beholder-kin and illithids as high-confidence PI shipped under
`rules/2024/monsters/`. They are reference-bestiary only (the live `data/enemies/` templates
don't include them and no campaign references them), so removing them changes no gameplay.
"""
from app.export.monster_exporter import MonsterExporter

PRODUCT_IDENTITY = {
    # Beholder-kin
    "beholder", "gauth", "gazer", "spectator", "beholder_zombie",
    # Mind flayer / illithid
    "mind_flayer", "mind_flayer_arcanist", "elder_brain",
    "intellect_devourer", "cranium_rat", "neothelid",
}


def test_no_tier1_product_identity_monsters_shipped():
    ids = {m.get("id") for m in MonsterExporter().load_all_monsters()}
    leaked = PRODUCT_IDENTITY & ids
    assert not leaked, f"Product-Identity monsters still in the bestiary: {sorted(leaked)}"


def test_no_product_identity_in_monster_names():
    names = {(m.get("name") or "").lower() for m in MonsterExporter().load_all_monsters()}
    banned_substrings = ["beholder", "mind flayer", "illithid", "elder brain",
                         "intellect devourer", "cranium rat", "neothelid", "spectator", "gauth"]
    leaked = sorted(n for n in names for b in banned_substrings if b in n)
    assert not leaked, f"Product-Identity names still present: {leaked}"
