"""
Character Import API Routes

Handles character import from PDF and JSON files.
Persists characters to database while maintaining in-memory cache for performance.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import tempfile
import json
import os
import uuid

from app.services.pdf_parser import DnDBeyondPDFParser
from app.services.json_parser import DnDBeyondJSONParser
from app.services.character_service import (
    to_combatant_data,
    validate_character,
    create_demo_combatant,
)
from app.database.dependencies import get_character_repo
from app.database.repositories import CharacterRepository
from app.database.models import CharacterCreate, CharacterUpdate

router = APIRouter()

# In-memory cache for quick access to imported characters
# Database is the source of truth, this is for performance
imported_characters: Dict[str, Dict[str, Any]] = {}


def _extract_abilities(character: Dict[str, Any]) -> Dict[str, int]:
    """Extract ability scores from character data."""
    abilities = character.get('abilities', {})
    if not abilities:
        # Try alternate formats
        abilities = {
            'strength': character.get('strength', character.get('str', 10)),
            'dexterity': character.get('dexterity', character.get('dex', 10)),
            'constitution': character.get('constitution', character.get('con', 10)),
            'intelligence': character.get('intelligence', character.get('int', 10)),
            'wisdom': character.get('wisdom', character.get('wis', 10)),
            'charisma': character.get('charisma', character.get('cha', 10)),
        }

    # Handle nested format: {'str': {'score': 13, 'mod': 1}} -> {'str': 13}
    result = {}
    for key, value in abilities.items():
        if isinstance(value, dict):
            result[key] = value.get('score', 10)
        else:
            result[key] = value
    return result


async def _persist_character(
    char_repo: CharacterRepository,
    character: Dict[str, Any],
    combatant: Dict[str, Any],
    source: str,
) -> str:
    """Persist character to database and return ID."""
    # Extract class name from various formats
    class_name = character.get('class', 'fighter')
    if isinstance(character.get('classes'), list) and character['classes']:
        class_name = character['classes'][0].get('name', 'fighter')

    # Extract structured data for database model
    char_create = CharacterCreate(
        name=character.get('name', combatant.get('name', 'Unknown')),
        species=character.get('race', character.get('species', 'human')),
        character_class=class_name,
        subclass=character.get('subclass'),
        level=character.get('level', 1),
        background=character.get('background'),
        abilities=_extract_abilities(character),
    )

    # Create in database
    db_character = await char_repo.create(char_create)

    # Update with additional data
    update_data = CharacterUpdate(
        current_hp=character.get('hp', combatant.get('hp', 10)),
        equipment=combatant.get('equipment', {}),
        inventory=character.get('inventory', []),
        gold=character.get('gold', 0),
        spellcasting=character.get('spellcasting', combatant.get('spellcasting')),
    )

    await char_repo.update(db_character.id, update_data)

    return db_character.id


@router.post("/import/pdf")
async def import_pdf(
    file: UploadFile = File(...),
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Import character from D&D Beyond PDF character sheet.

    Accepts a PDF file and parses it to extract character data.
    Returns both the raw parsed data and the combat-ready format.
    Character is persisted to database for future sessions.

    Args:
        file: PDF file upload

    Returns:
        Character data including raw parsed data and combatant format
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Save to temporary file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Parse PDF
    try:
        parser = DnDBeyondPDFParser()
        character = parser.parse(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Validate character data
    warnings = validate_character(character)

    # Convert to combatant format
    combatant = to_combatant_data(character)

    # Persist to database and get ID
    char_id = await _persist_character(char_repo, character, combatant, 'pdf')

    # Cache for quick access during session
    imported_characters[char_id] = {
        'raw': character,
        'combatant': combatant,
        'source': 'pdf',
        'filename': file.filename,
    }

    return {
        "success": True,
        "character_id": char_id,
        "character": character,
        "combatant": combatant,
        "warnings": warnings,
        "persisted": True,
        "message": f"Successfully imported {character.get('name', 'Unknown')} from PDF"
    }


@router.post("/import/json")
async def import_json(
    file: UploadFile = File(...),
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Import character from JSON file.

    Accepts JSON files from D&D Beyond exports (via browser extensions)
    or custom character JSON files.
    Character is persisted to database for future sessions.

    Args:
        file: JSON file upload

    Returns:
        Character data including raw parsed data and combatant format
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be a JSON file")

    # Read and parse JSON
    try:
        content = await file.read()
        json_data = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Parse JSON character data
    try:
        parser = DnDBeyondJSONParser()
        character = parser.parse(json_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse character data: {str(e)}")

    # Validate character data
    warnings = validate_character(character)

    # Convert to combatant format
    combatant = to_combatant_data(character)

    # Persist to database and get ID
    char_id = await _persist_character(char_repo, character, combatant, 'json')

    # Cache for quick access during session
    imported_characters[char_id] = {
        'raw': character,
        'combatant': combatant,
        'source': 'json',
        'filename': file.filename,
    }

    return {
        "success": True,
        "character_id": char_id,
        "character": character,
        "combatant": combatant,
        "warnings": warnings,
        "persisted": True,
        "message": f"Successfully imported {character.get('name', 'Unknown')} from JSON"
    }


@router.get("/list")
async def list_characters(
    char_repo: CharacterRepository = Depends(get_character_repo),
    include_db: bool = True,
):
    """
    List all characters.

    Returns a summary of all characters from both cache and database.
    Set include_db=false to only return cached characters from current session.
    """
    characters = []
    seen_ids = set()

    # First, add cached characters (most recently used)
    for char_id, data in imported_characters.items():
        char = data.get('raw', {})
        combatant = data.get('combatant', {})
        characters.append({
            "id": char_id,
            "name": char.get('name', combatant.get('name', 'Unknown')),
            "class": char.get('class', 'Unknown'),
            "level": char.get('level', 1),
            "hp": char.get('hp', combatant.get('hp', 10)),
            "ac": char.get('ac', combatant.get('ac', 10)),
            "source": data.get('source', 'unknown'),
            "filename": data.get('filename', ''),
            "cached": True,
        })
        seen_ids.add(char_id)

    # Then add characters from database that aren't cached
    if include_db:
        db_characters = await char_repo.get_all(limit=100)
        for db_char in db_characters:
            if db_char.id not in seen_ids:
                characters.append({
                    "id": db_char.id,
                    "name": db_char.name,
                    "class": db_char.character_class,
                    "level": db_char.level,
                    "hp": db_char.current_hp,
                    "ac": 10,  # Would need to calculate from equipment
                    "source": "database",
                    "filename": "",
                    "cached": False,
                })

    return {
        "success": True,
        "characters": characters,
        "count": len(characters)
    }


@router.get("/{character_id}")
async def get_character(
    character_id: str,
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Get a specific character by ID.

    Checks cache first, then database.

    Args:
        character_id: UUID of the character

    Returns:
        Full character data including raw and combatant formats
    """
    import traceback
    print(f"[CHARACTER] get_character called for {character_id}", flush=True)

    try:
        # Check cache first
        if character_id in imported_characters:
            data = imported_characters[character_id]
            raw = data.get('raw')

            # ALWAYS regenerate combatant from raw data to ensure all fields are current
            # This fixes issues where cached combatants are missing fields added in later updates
            if raw:
                combatant = to_combatant_data(raw)
                data['combatant'] = combatant  # Update cache
                print(f"[GET_CHARACTER] Regenerated combatant for {character_id}: class='{combatant.get('class')}', character_class='{combatant.get('character_class')}', stats.class='{combatant.get('stats', {}).get('class')}'", flush=True)
            else:
                combatant = data.get('combatant')

            return {
                "success": True,
                "character_id": character_id,
                "character": raw,
                "combatant": combatant,
                "source": data.get('source'),
            }

        # Try database
        print(f"[CHARACTER] Not in cache, trying database...", flush=True)
        db_char = await char_repo.get_by_id(character_id)
        print(f"[CHARACTER] Database result: {db_char}", flush=True)

        if not db_char:
            raise HTTPException(status_code=404, detail="Character not found")

        # Convert database character to response format
        character = {
            "name": db_char.name,
            "race": db_char.species,
            "class": db_char.character_class,
            "subclass": db_char.subclass,
            "level": db_char.level,
            "background": db_char.background,
            "abilities": db_char.abilities,
            "hp": db_char.current_hp,
            "max_hp": db_char.max_hp,
            "experience": db_char.experience,
            "equipment": db_char.equipment,
            "inventory": db_char.inventory,
            "gold": db_char.gold,
            "spellcasting": db_char.spellcasting,
        }

        # Generate combatant data
        combatant = to_combatant_data(character)

        # Cache for future requests
        imported_characters[character_id] = {
            'raw': character,
            'combatant': combatant,
            'source': 'database',
        }

        return {
            "success": True,
            "character_id": character_id,
            "character": character,
            "combatant": combatant,
            "source": "database",
            "cached": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error in get_character: {type(e).__name__}: {str(e)}"
        print(f"[CHARACTER ERROR] {error_msg}", flush=True)
        traceback.print_exc()
        # Return error in response so we can see it in browser
        return JSONResponse(
            status_code=500,
            content={"error": error_msg, "traceback": traceback.format_exc()}
        )


@router.get("/{character_id}/combatant")
async def get_combatant(
    character_id: str,
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Get combat-ready format for a character.

    This returns only the combatant data suitable for use
    in the combat system. Checks cache first, then database.

    Args:
        character_id: UUID of the character

    Returns:
        CombatantData format for the character
    """
    # Check cache first
    if character_id in imported_characters:
        data = imported_characters[character_id]
        return {
            "success": True,
            "combatant": data.get('combatant'),
        }

    # Try database
    db_char = await char_repo.get_by_id(character_id)
    if not db_char:
        raise HTTPException(status_code=404, detail="Character not found")

    # Convert database character to combatant format
    character = {
        "name": db_char.name,
        "race": db_char.species,
        "class": db_char.character_class,
        "level": db_char.level,
        "abilities": db_char.abilities,
        "hp": db_char.current_hp,
        "max_hp": db_char.max_hp,
        "equipment": db_char.equipment,
        "spellcasting": db_char.spellcasting,
    }

    combatant = to_combatant_data(character)

    return {
        "success": True,
        "combatant": combatant,
    }


@router.delete("/{character_id}")
async def delete_character(
    character_id: str,
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Delete a character.

    Removes from both cache and database (soft delete in DB).

    Args:
        character_id: UUID of the character to delete

    Returns:
        Success message
    """
    # Remove from cache
    if character_id in imported_characters:
        del imported_characters[character_id]

    # Soft delete from database
    deleted = await char_repo.delete(character_id)

    if not deleted and character_id not in imported_characters:
        raise HTTPException(status_code=404, detail="Character not found")

    return {
        "success": True,
        "message": "Character deleted"
    }


@router.post("/demo")
async def create_demo(
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Create a demo character for testing.

    Creates a level 5 Fighter with standard equipment.
    Useful for testing the combat system.
    Character is persisted to database.

    Returns:
        Demo character in combatant format
    """
    combatant = create_demo_combatant("Demo Fighter")

    character = {
        'name': 'Demo Fighter',
        'class': 'Fighter',
        'level': 5,
        'hp': combatant.get('hp', 44),
        'abilities': {
            'strength': 16,
            'dexterity': 14,
            'constitution': 14,
            'intelligence': 10,
            'wisdom': 12,
            'charisma': 10,
        }
    }

    # Persist to database
    char_id = await _persist_character(char_repo, character, combatant, 'demo')

    # Cache for quick access
    imported_characters[char_id] = {
        'raw': character,
        'combatant': combatant,
        'source': 'demo',
    }

    return {
        "success": True,
        "character_id": char_id,
        "combatant": combatant,
        "persisted": True,
        "message": "Demo character created"
    }


@router.post("/validate")
async def validate_character_data(character: Dict[str, Any]):
    """
    Validate character data without importing.

    Useful for checking if character data is valid before
    attempting to use it in combat.

    Args:
        character: Character data to validate

    Returns:
        Validation results with warnings
    """
    warnings = validate_character(character)

    return {
        "success": len(warnings) == 0,
        "valid": len(warnings) == 0,
        "warnings": warnings,
    }


# =============================================================================
# Character Export Endpoints
# =============================================================================

@router.get("/{character_id}/export")
async def export_character_json(
    character_id: str,
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Export character data as JSON for backup or sharing.

    This format can be re-imported using the /character/import/export endpoint.
    Includes all character data: stats, inventory, gold, equipment, etc.

    Args:
        character_id: UUID of the character

    Returns:
        Full character export in JSON format with download headers
    """
    from datetime import datetime

    # Check cache first
    if character_id in imported_characters:
        data = imported_characters[character_id]
        raw = data.get('raw', {})
        combatant = data.get('combatant', {})
        source = data.get('source', 'cache')
    else:
        # Load from database
        db_char = await char_repo.get_by_id(character_id)
        if not db_char:
            raise HTTPException(status_code=404, detail="Character not found")

        raw = {
            "name": db_char.name,
            "race": db_char.species,
            "species": db_char.species,
            "class": db_char.character_class,
            "subclass": db_char.subclass,
            "level": db_char.level,
            "background": db_char.background,
            "abilities": db_char.abilities or {},
            "hp": db_char.current_hp,
            "max_hp": db_char.max_hp,
            "experience": db_char.experience,
            "equipment": db_char.equipment or {},
            "inventory": db_char.inventory or [],
            "gold": db_char.gold,
            "spellcasting": db_char.spellcasting,
            "class_features": db_char.class_features or [],
            "skill_proficiencies": db_char.skill_proficiencies or [],
        }
        combatant = to_combatant_data(raw)
        source = "database"

    # Build export data with version for future compatibility
    export_data = {
        "version": "1.0",
        "format": "dnd-web-game-export",
        "exported_at": datetime.utcnow().isoformat(),
        "character_id": character_id,
        "character": {
            "name": raw.get("name", "Unknown"),
            "species": raw.get("race", raw.get("species", "human")),
            "character_class": raw.get("class", "fighter"),
            "subclass": raw.get("subclass"),
            "level": raw.get("level", 1),
            "background": raw.get("background"),
            "abilities": raw.get("abilities", {
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            }),
            "max_hp": raw.get("max_hp", raw.get("hp", 10)),
            "current_hp": raw.get("hp", 10),
            "experience": raw.get("experience", 0),
            "gold": raw.get("gold", 0),
            "inventory": raw.get("inventory", []),
            "equipment": raw.get("equipment", {}),
            "spellcasting": raw.get("spellcasting"),
            "class_features": raw.get("class_features", []),
            "skill_proficiencies": raw.get("skill_proficiencies", []),
        },
        "combatant": combatant,
        "source": source,
    }

    char_name = raw.get("name", "character").replace(" ", "_")

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="{char_name}_export.json"'
        }
    )


@router.get("/{character_id}/export/summary")
async def export_character_summary(
    character_id: str,
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Export character as a text summary for easy sharing.

    Returns a human-readable text summary of the character that
    can be copied and shared in chats, forums, etc.

    Args:
        character_id: UUID of the character

    Returns:
        Plain text summary of the character
    """
    # Check cache first
    if character_id in imported_characters:
        data = imported_characters[character_id]
        raw = data.get('raw', {})
    else:
        # Load from database
        db_char = await char_repo.get_by_id(character_id)
        if not db_char:
            raise HTTPException(status_code=404, detail="Character not found")

        raw = {
            "name": db_char.name,
            "race": db_char.species,
            "class": db_char.character_class,
            "subclass": db_char.subclass,
            "level": db_char.level,
            "background": db_char.background,
            "abilities": db_char.abilities or {},
            "hp": db_char.current_hp,
            "max_hp": db_char.max_hp,
            "experience": db_char.experience,
            "equipment": db_char.equipment or {},
            "inventory": db_char.inventory or [],
            "gold": db_char.gold,
            "spellcasting": db_char.spellcasting,
        }

    # Build text summary
    name = raw.get("name", "Unknown")
    species = raw.get("race", raw.get("species", "Unknown"))
    char_class = raw.get("class", "Unknown")
    subclass = raw.get("subclass", "")
    level = raw.get("level", 1)
    background = raw.get("background", "Unknown")

    abilities = raw.get("abilities", {})
    str_val = abilities.get("strength", 10)
    dex_val = abilities.get("dexterity", 10)
    con_val = abilities.get("constitution", 10)
    int_val = abilities.get("intelligence", 10)
    wis_val = abilities.get("wisdom", 10)
    cha_val = abilities.get("charisma", 10)

    max_hp = raw.get("max_hp", raw.get("hp", 10))
    current_hp = raw.get("hp", max_hp)
    xp = raw.get("experience", 0)
    gold = raw.get("gold", 0)

    # Calculate modifiers
    def mod(score):
        m = (score - 10) // 2
        return f"+{m}" if m >= 0 else str(m)

    class_display = f"{char_class}"
    if subclass:
        class_display = f"{char_class} ({subclass})"

    summary_lines = [
        f"=== {name} ===",
        f"Level {level} {species} {class_display}",
        f"Background: {background}" if background else "",
        "",
        f"HP: {current_hp}/{max_hp}",
        f"XP: {xp:,}",
        f"Gold: {gold:,} gp",
        "",
        "ABILITIES:",
        f"  STR: {str_val} ({mod(str_val)})",
        f"  DEX: {dex_val} ({mod(dex_val)})",
        f"  CON: {con_val} ({mod(con_val)})",
        f"  INT: {int_val} ({mod(int_val)})",
        f"  WIS: {wis_val} ({mod(wis_val)})",
        f"  CHA: {cha_val} ({mod(cha_val)})",
    ]

    # Add inventory if present
    inventory = raw.get("inventory", [])
    if inventory:
        summary_lines.append("")
        summary_lines.append("INVENTORY:")
        for item in inventory[:10]:  # Limit to first 10 items
            if isinstance(item, dict):
                item_name = item.get("name", "Unknown Item")
                quantity = item.get("quantity", 1)
                if quantity > 1:
                    summary_lines.append(f"  - {item_name} x{quantity}")
                else:
                    summary_lines.append(f"  - {item_name}")
            else:
                summary_lines.append(f"  - {item}")
        if len(inventory) > 10:
            summary_lines.append(f"  ... and {len(inventory) - 10} more items")

    # Add equipment if present
    equipment = raw.get("equipment", {})
    if equipment:
        summary_lines.append("")
        summary_lines.append("EQUIPMENT:")
        for slot, item in equipment.items():
            if item:
                if isinstance(item, dict):
                    item_name = item.get("name", "Unknown")
                    summary_lines.append(f"  {slot.title()}: {item_name}")
                else:
                    summary_lines.append(f"  {slot.title()}: {item}")

    # Add spellcasting if present
    spellcasting = raw.get("spellcasting")
    if spellcasting:
        summary_lines.append("")
        summary_lines.append("SPELLCASTING:")
        ability = spellcasting.get("ability", "Unknown")
        summary_lines.append(f"  Spellcasting Ability: {ability.title()}")
        spells_known = spellcasting.get("spells_known", [])
        if spells_known:
            summary_lines.append(f"  Spells Known: {len(spells_known)}")

    summary_lines.append("")
    summary_lines.append("---")
    summary_lines.append("Exported from D&D 5e 2024 Web Game")

    summary = "\n".join(line for line in summary_lines if line is not None)

    return {
        "success": True,
        "character_id": character_id,
        "character_name": name,
        "summary": summary,
    }


@router.post("/import/export")
async def import_from_export(
    file: UploadFile = File(...),
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """
    Import a character from a previously exported JSON file.

    Accepts JSON files created by the /character/{id}/export endpoint.
    Creates a new character in the database with the exported data.

    Args:
        file: JSON export file

    Returns:
        New character data with assigned ID
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be a JSON file")

    # Read and parse JSON
    try:
        content = await file.read()
        export_data = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Validate export format
    if export_data.get("format") != "dnd-web-game-export":
        raise HTTPException(
            status_code=400,
            detail="Invalid export format. This endpoint only accepts files exported from this system."
        )

    version = export_data.get("version", "1.0")
    if version not in ["1.0"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export version: {version}"
        )

    char_data = export_data.get("character", {})
    if not char_data:
        raise HTTPException(status_code=400, detail="No character data in export file")

    # Create character in database
    char_create = CharacterCreate(
        name=char_data.get("name", "Imported Character"),
        species=char_data.get("species", "human"),
        character_class=char_data.get("character_class", "fighter"),
        subclass=char_data.get("subclass"),
        level=char_data.get("level", 1),
        background=char_data.get("background"),
        abilities=char_data.get("abilities", {
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }),
    )

    db_char = await char_repo.create(char_create)

    # Update with additional fields
    update_data = CharacterUpdate(
        max_hp=char_data.get("max_hp", 10),
        current_hp=char_data.get("current_hp", char_data.get("max_hp", 10)),
        experience=char_data.get("experience", 0),
        gold=char_data.get("gold", 0),
        inventory=char_data.get("inventory", []),
        equipment=char_data.get("equipment", {}),
        spellcasting=char_data.get("spellcasting"),
        class_features=char_data.get("class_features", []),
        skill_proficiencies=char_data.get("skill_proficiencies", []),
    )

    await char_repo.update(db_char.id, update_data)

    # Build response character data
    character = {
        "name": char_data.get("name"),
        "race": char_data.get("species"),
        "class": char_data.get("character_class"),
        "subclass": char_data.get("subclass"),
        "level": char_data.get("level", 1),
        "background": char_data.get("background"),
        "abilities": char_data.get("abilities", {}),
        "hp": char_data.get("current_hp", 10),
        "max_hp": char_data.get("max_hp", 10),
        "experience": char_data.get("experience", 0),
        "gold": char_data.get("gold", 0),
        "inventory": char_data.get("inventory", []),
        "equipment": char_data.get("equipment", {}),
        "spellcasting": char_data.get("spellcasting"),
    }

    combatant = to_combatant_data(character)

    # Cache for quick access
    imported_characters[db_char.id] = {
        'raw': character,
        'combatant': combatant,
        'source': 'import-export',
        'filename': file.filename,
    }

    return {
        "success": True,
        "character_id": db_char.id,
        "character": character,
        "combatant": combatant,
        "imported_from": file.filename,
        "original_character_id": export_data.get("character_id"),
        "exported_at": export_data.get("exported_at"),
        "persisted": True,
        "message": f"Successfully imported {character.get('name', 'Unknown')} from export file"
    }
