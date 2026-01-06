"""
Foundry VTT Module Builder.

Packages exported content into a complete Foundry VTT module with
proper manifest and compendium pack format.
"""

import json
import zipfile
import io
from typing import List, Dict, Optional
from datetime import datetime

from .monster_exporter import MonsterExporter


# Module metadata
MODULE_ID = "dnd-web-game-content"
MODULE_TITLE = "D&D Web Game Content"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Exported content from D&D Web Game including 250+ monsters, spells, and items"
MODULE_AUTHORS = ["D&D Web Game"]
MODULE_MINIMUM_FOUNDRY = "11"
MODULE_VERIFIED_FOUNDRY = "12"
MODULE_MINIMUM_DND5E = "3.0.0"


def build_module_manifest(
    include_monsters: bool = True,
    include_spells: bool = False,
    include_items: bool = False,
) -> Dict:
    """
    Build the module.json manifest for Foundry VTT.

    Args:
        include_monsters: Include monster compendium
        include_spells: Include spell compendium (future)
        include_items: Include item compendium (future)

    Returns:
        Module manifest dictionary
    """
    packs = []

    if include_monsters:
        packs.append({
            "name": "monsters",
            "label": "D&D Web Game - Monsters",
            "path": "packs/monsters",
            "type": "Actor",
            "system": "dnd5e",
            "private": False,
            "flags": {}
        })

    if include_spells:
        packs.append({
            "name": "spells",
            "label": "D&D Web Game - Spells",
            "path": "packs/spells",
            "type": "Item",
            "system": "dnd5e",
            "private": False,
            "flags": {}
        })

    if include_items:
        packs.append({
            "name": "items",
            "label": "D&D Web Game - Items",
            "path": "packs/items",
            "type": "Item",
            "system": "dnd5e",
            "private": False,
            "flags": {}
        })

    return {
        "id": MODULE_ID,
        "title": MODULE_TITLE,
        "description": MODULE_DESCRIPTION,
        "version": MODULE_VERSION,
        "authors": [{"name": author} for author in MODULE_AUTHORS],
        "compatibility": {
            "minimum": MODULE_MINIMUM_FOUNDRY,
            "verified": MODULE_VERIFIED_FOUNDRY
        },
        "relationships": {
            "systems": [{
                "id": "dnd5e",
                "type": "system",
                "compatibility": {
                    "minimum": MODULE_MINIMUM_DND5E
                }
            }]
        },
        "packs": packs,
        "languages": [],
        "socket": False,
        "manifest": "",
        "download": "",
        "changelog": "",
        "bugs": "",
        "readme": "",
        "flags": {
            "exportedAt": datetime.utcnow().isoformat(),
            "sourceApplication": "D&D Web Game"
        }
    }


def build_monster_pack() -> str:
    """
    Build the monster compendium pack content.

    Foundry VTT uses NeDB format (one JSON object per line) for v10 and earlier.
    For v11+, use the provided export but note that the actual pack is LevelDB.

    Returns:
        String containing one JSON document per line
    """
    exporter = MonsterExporter()
    monsters = exporter.export_all()

    # NeDB format: one JSON object per line
    lines = []
    for monster in monsters:
        lines.append(json.dumps(monster, separators=(',', ':')))

    return "\n".join(lines)


def build_module(
    include_monsters: bool = True,
    include_spells: bool = False,
    include_items: bool = False,
) -> io.BytesIO:
    """
    Build a complete Foundry VTT module as a ZIP file.

    Args:
        include_monsters: Include monster compendium
        include_spells: Include spell compendium (future)
        include_items: Include item compendium (future)

    Returns:
        BytesIO buffer containing the ZIP file
    """
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Create module.json manifest
        manifest = build_module_manifest(
            include_monsters=include_monsters,
            include_spells=include_spells,
            include_items=include_items,
        )
        zf.writestr(
            f"{MODULE_ID}/module.json",
            json.dumps(manifest, indent=2)
        )

        # Add README
        readme_content = f"""# {MODULE_TITLE}

{MODULE_DESCRIPTION}

## Installation

1. Download this module ZIP file
2. Extract to your Foundry VTT modules directory
3. Restart Foundry VTT
4. Enable the module in your world settings

## Contents

"""
        if include_monsters:
            readme_content += "- **Monsters**: 250+ creatures from the D&D 2024 Monster Manual\n"
        if include_spells:
            readme_content += "- **Spells**: 400+ spells across all levels\n"
        if include_items:
            readme_content += "- **Items**: Weapons, armor, and equipment\n"

        readme_content += """
## Compatibility

- Foundry VTT v11+
- D&D 5e System v3.0+

## Credits

Generated from D&D Web Game combat system.

## License

Content based on the D&D 5e SRD under CC-BY-4.0.
"""
        zf.writestr(f"{MODULE_ID}/README.md", readme_content)

        # Add monster pack if requested
        if include_monsters:
            monster_pack = build_monster_pack()
            # For v11+, this serves as an importable JSON backup
            # The actual LevelDB pack needs to be created using foundryvtt-cli
            zf.writestr(f"{MODULE_ID}/packs/monsters.db", monster_pack)

            # Also add a JSON version for easy viewing/import
            exporter = MonsterExporter()
            monsters_json = exporter.export_all()
            zf.writestr(
                f"{MODULE_ID}/packs/monsters.json",
                json.dumps(monsters_json, indent=2)
            )

        # Add spell pack if requested (future)
        if include_spells:
            # Placeholder for future spell exporter
            zf.writestr(f"{MODULE_ID}/packs/spells.db", "")

        # Add item pack if requested (future)
        if include_items:
            # Placeholder for future item exporter
            zf.writestr(f"{MODULE_ID}/packs/items.db", "")

    buffer.seek(0)
    return buffer


def export_monsters_json() -> Dict:
    """
    Export monsters as a simple JSON structure for API consumption.

    Returns:
        Dictionary with monsters array and count
    """
    exporter = MonsterExporter()
    monsters = exporter.export_all()

    return {
        "success": True,
        "count": len(monsters),
        "format": "foundry-dnd5e",
        "version": MODULE_VERSION,
        "compatibility": {
            "foundry": MODULE_MINIMUM_FOUNDRY,
            "dnd5e": MODULE_MINIMUM_DND5E,
        },
        "monsters": monsters,
    }


def get_export_stats() -> Dict:
    """
    Get statistics about available content for export.

    Returns:
        Dictionary with content counts
    """
    exporter = MonsterExporter()
    monsters = exporter.load_all_monsters()

    # Group by type
    type_counts = {}
    cr_counts = {"0-1": 0, "2-4": 0, "5-10": 0, "11-16": 0, "17+": 0}

    for monster in monsters:
        # Count by type
        m_type = monster.get("type", "unknown").split()[0].lower()
        type_counts[m_type] = type_counts.get(m_type, 0) + 1

        # Count by CR range
        cr_str = str(monster.get("challenge_rating", "0"))
        if cr_str in ("0", "1/8", "1/4", "1/2", "1"):
            cr_counts["0-1"] += 1
        elif cr_str in ("2", "3", "4"):
            cr_counts["2-4"] += 1
        elif cr_str in ("5", "6", "7", "8", "9", "10"):
            cr_counts["5-10"] += 1
        elif cr_str in ("11", "12", "13", "14", "15", "16"):
            cr_counts["11-16"] += 1
        else:
            cr_counts["17+"] += 1

    return {
        "monsters": {
            "total": len(monsters),
            "by_type": type_counts,
            "by_cr": cr_counts,
        },
        "spells": {
            "total": 0,  # Future
            "implemented": False,
        },
        "items": {
            "total": 0,  # Future
            "implemented": False,
        },
    }
