"""
Export API Routes for Foundry VTT.

Provides endpoints to export game content to Foundry VTT compatible format.
"""

from fastapi import APIRouter, Response, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from app.export.monster_exporter import MonsterExporter
from app.export.module_builder import (
    build_module,
    export_monsters_json,
    get_export_stats,
    MODULE_ID,
)

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/stats")
async def get_stats():
    """
    Get statistics about available content for export.

    Returns counts of monsters, spells, and items available for export.
    """
    return get_export_stats()


@router.get("/foundry/monsters")
async def export_monsters(
    format: str = Query(default="json", description="Export format: 'json' or 'nedb'"),
):
    """
    Export all monsters in Foundry VTT dnd5e format.

    Args:
        format: 'json' for formatted JSON, 'nedb' for one-line-per-document format

    Returns:
        JSON response with all monsters in Foundry format
    """
    if format == "nedb":
        from app.export.module_builder import build_monster_pack
        content = build_monster_pack()
        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=monsters.db"
            }
        )

    return export_monsters_json()


@router.get("/foundry/monster/{monster_id}")
async def export_single_monster(monster_id: str):
    """
    Export a single monster by ID in Foundry VTT format.

    Args:
        monster_id: The monster's ID (e.g., "goblin", "ancient_red_dragon")

    Returns:
        Single monster in Foundry Actor format
    """
    exporter = MonsterExporter()
    monsters = exporter.load_all_monsters()

    for monster in monsters:
        if monster.get("id") == monster_id:
            return {
                "success": True,
                "monster": exporter.export(monster),
            }

    return {
        "success": False,
        "error": f"Monster '{monster_id}' not found",
    }


@router.get("/foundry/module")
async def download_module(
    include_monsters: bool = Query(default=True, description="Include monster compendium"),
    include_spells: bool = Query(default=False, description="Include spell compendium (not yet implemented)"),
    include_items: bool = Query(default=False, description="Include item compendium (not yet implemented)"),
):
    """
    Download complete Foundry VTT module as a ZIP file.

    The ZIP contains:
    - module.json manifest
    - README.md with installation instructions
    - packs/ directory with compendium data

    To use in Foundry VTT:
    1. Extract to your modules directory
    2. Enable the module in world settings
    3. Access compendiums from the sidebar

    Note: For Foundry v11+, the included .db files serve as a backup.
    You may need to use foundryvtt-cli to convert to LevelDB format for
    native compendium use.
    """
    zip_buffer = build_module(
        include_monsters=include_monsters,
        include_spells=include_spells,
        include_items=include_items,
    )

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={MODULE_ID}.zip"
        }
    )


@router.get("/foundry/info")
async def get_foundry_info():
    """
    Get information about the Foundry export capabilities.

    Returns details about supported formats, versions, and content types.
    """
    return {
        "supported_formats": ["json", "nedb", "module_zip"],
        "compatibility": {
            "foundry_minimum": "11",
            "foundry_verified": "12",
            "dnd5e_minimum": "3.0.0",
        },
        "content_types": {
            "monsters": {
                "implemented": True,
                "description": "Full monster stat blocks with actions, traits, and legendary abilities",
            },
            "spells": {
                "implemented": False,
                "description": "Spell definitions with damage, components, and effects (coming soon)",
            },
            "items": {
                "implemented": False,
                "description": "Weapons, armor, and equipment (coming soon)",
            },
            "classes": {
                "implemented": False,
                "description": "Class features and progression (coming soon)",
            },
        },
        "endpoints": {
            "/export/stats": "Get export statistics",
            "/export/foundry/monsters": "Export all monsters as JSON",
            "/export/foundry/monster/{id}": "Export single monster by ID",
            "/export/foundry/module": "Download complete Foundry module ZIP",
        },
    }
