"""B3b SRD 5.2.1 compliance scanner.

Diffs the repo's shipped content (spells, subclasses, backgrounds, species) against the
official SRD 5.2.1 name lists (srd_521_content.json, extracted from the CC-BY-4.0 SRD).
Anything listed as NOT in the SRD is likely sourced from the full 2024 PHB and is the
project's licensing exposure — see SRD_COMPLIANCE_AUDIT.md and root CLAUDE.md §6.

Run from backend/:  python scripts/srd_audit.py
Not legal advice. Name-matching only — verbatim-text similarity is out of scope here.
"""
import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

SRD = json.loads((Path(__file__).parent / "srd_521_content.json").read_text(encoding="utf-8"))


def norm(s: str) -> str:
    # Apostrophes are stripped (not underscored) so "Hunter's Mark" == hunters_mark.
    s = (s or "").strip().lower().replace("’", "").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


# Spells whose mechanics ARE in the SRD but under a de-branded name (the SRD drops the
# wizard names, which are Product Identity). Remediation = RENAME, not remove.
SPELL_RENAMES = {
    "melfs_acid_arrow": "acid_arrow",
    "bigbys_hand": "arcane_hand",
    "tashas_hideous_laughter": "hideous_laughter",
    "leomunds_tiny_hut": "tiny_hut",
    "leomunds_secret_chest": "secret_chest",
    "drawmijs_instant_summons": "instant_summons",
    "evards_black_tentacles": "black_tentacles",
    "mordenkainens_sword": "arcane_sword",
    "mordenkainens_faithful_hound": "faithful_hound",
    "mordenkainens_magnificent_mansion": "magnificent_mansion",
    "mordenkainens_private_sanctum": "private_sanctum",
    "otilukes_freezing_sphere": "freezing_sphere",
    "otilukes_resilient_sphere": "resilient_sphere",
    "ottos_irresistible_dance": "irresistible_dance",
    "rarys_telepathic_bond": "telepathic_bond",
    "nystuls_magic_aura": "arcanists_magic_aura",
    "tensers_floating_disk": "floating_disk",
}


def repo_spells():
    from app.core.spell_system import SpellRegistry
    return sorted(norm(s.id) for s in SpellRegistry.get_instance().get_all_spells())


def repo_from_json(subdir, key):
    out = set()
    for path in (BACKEND / "app" / "data" / "rules" / "2024" / subdir).glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if key in node and isinstance(node[key], list):
                    for entry in node[key]:
                        if isinstance(entry, dict) and entry.get("id"):
                            out.add(norm(entry["id"]))
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        # Files whose top level IS the entry (one background/species per file)
        if isinstance(data, dict) and data.get("id") and key not in data:
            out.add(norm(data["id"]))
    return sorted(out)


def diff(label, repo, srd):
    srd_set = set(srd)
    extra = [x for x in repo if x not in srd_set]
    matched = len(repo) - len(extra)
    print(f"\n## {label}: {len(repo)} shipped = {matched} matching SRD names "
          f"+ {len(extra)} NOT in SRD (SRD list has {len(srd)})")
    for x in extra:
        print(f"   NOT-SRD  {x}")
    return extra


def main():
    total = 0
    spells = repo_spells()
    renames = [s for s in spells if SPELL_RENAMES.get(s) in set(SRD["spells"])]
    rest = [s for s in spells if s not in renames]
    if renames:
        print(f"\n## Spells shipped under a Product-Identity name — RENAME to the SRD "
              f"name ({len(renames)}):")
        for s in renames:
            print(f"   RENAME   {s} -> {SPELL_RENAMES[s]}")
    total += len(diff("Spells", rest, SRD["spells"]))
    total += len(diff("Subclasses", repo_from_json("classes", "subclasses"), SRD["subclasses"]))
    total += len(diff("Backgrounds", repo_from_json("backgrounds", "backgrounds"), SRD["backgrounds"]))
    total += len(diff("Species", repo_from_json("species", "species"), SRD["species"]))
    print(f"\nTOTAL entries not in SRD 5.2.1: {total}")
    print("Cross-check names against the official SRD PDF before acting; not legal advice.")


if __name__ == "__main__":
    main()
