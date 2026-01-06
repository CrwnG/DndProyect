"""
Campaign API Routes.

Endpoints for managing campaigns and game sessions:
- List/load campaigns
- Create/load game sessions
- Advance campaign state
- Save/load games

Sessions are persisted to database for durability.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import json

from app.models.campaign import Campaign, RestType
from app.models.game_session import (
    GameSession,
    SessionPhase,
    PartyMember,
    SaveGame,
)
from app.core.campaign_engine import (
    CampaignEngine,
    CampaignAction,
    load_campaign,
    list_campaigns,
)
from app.database.dependencies import get_session_repo, get_progress_repo, get_character_repo, get_savegame_repo
from app.database.repositories import GameSessionRepository, CampaignProgressRepository, CharacterRepository, SaveGameRepository
from app.database.models import GameSessionCreate, CharacterUpdate, SaveGameCreate

router = APIRouter()

# In-memory cache for active sessions (for performance)
# Database is the source of truth for persistence
active_sessions: Dict[str, CampaignEngine] = {}
loaded_campaigns: Dict[str, Campaign] = {}
save_games: Dict[str, SaveGame] = {}  # Will migrate to DB


async def _persist_session_state(
    session_repo: GameSessionRepository,
    session_id: str,
    engine: CampaignEngine,
) -> None:
    """Persist current session state to database."""
    session = engine.session
    state_dict = session.to_dict() if hasattr(session, 'to_dict') else {}

    await session_repo.update(
        session_id,
        current_scene_id=session.current_encounter_id if hasattr(session, 'current_encounter_id') else None,
        state=state_dict,
        party=[m.to_dict() for m in session.party] if hasattr(session, 'party') else [],
    )


async def _sync_party_to_characters(
    char_repo: CharacterRepository,
    session: GameSession,
) -> Dict[str, Any]:
    """
    Sync party member progress back to Character database.

    This ensures XP, gold, level, and HP persist across campaigns.
    Only syncs members that have a character_id (linked to database).

    Returns:
        Dict with sync results for each character
    """
    results = {"synced": [], "skipped": [], "errors": []}

    for member in session.party:
        if not member.character_id:
            results["skipped"].append({
                "name": member.name,
                "reason": "No character_id (not linked to database)"
            })
            continue

        try:
            # Build update with current party member state
            update = CharacterUpdate(
                experience=member.xp,
                level=member.level,
                current_hp=member.current_hp,
                gold=member.gold,
            )

            await char_repo.update(member.character_id, update)

            results["synced"].append({
                "name": member.name,
                "character_id": member.character_id,
                "xp": member.xp,
                "level": member.level,
                "gold": member.gold,
            })

            print(f"[SYNC] Synced {member.name}: XP={member.xp}, Level={member.level}, Gold={member.gold}", flush=True)

        except Exception as e:
            results["errors"].append({
                "name": member.name,
                "character_id": member.character_id,
                "error": str(e)
            })
            print(f"[SYNC ERROR] Failed to sync {member.name}: {e}", flush=True)

    return results


# =============================================================================
# Request/Response Models
# =============================================================================

class PartyMemberData(BaseModel):
    """Data for creating a party member."""
    name: str
    character_class: str
    level: int = 1
    max_hp: int = 10
    ac: int = 10
    speed: int = 30
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    equipment_data: Optional[Dict[str, Any]] = None
    weapons: Optional[List[Dict[str, Any]]] = None
    spellcasting: Optional[Dict[str, Any]] = None
    # Database link for syncing progress
    character_id: Optional[str] = None  # UUID of Character in database
    gold: int = 0  # Individual gold


class CreateSessionRequest(BaseModel):
    """Request to create a new game session."""
    campaign_id: str
    party: List[PartyMemberData]


class AdvanceRequest(BaseModel):
    """Request to advance campaign state."""
    action: str
    data: Optional[Dict[str, Any]] = None


class SaveGameRequest(BaseModel):
    """Request to save the game."""
    slot: int = Field(ge=0, le=9)
    name: str = "Save"


class LoadGameRequest(BaseModel):
    """Request to load a saved game."""
    save_id: str


# =============================================================================
# Campaign Endpoints
# =============================================================================

@router.get("/list")
async def get_campaign_list():
    """Get list of available campaigns."""
    campaigns = list_campaigns()
    return {"campaigns": campaigns}


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get campaign details."""
    # Check cache first
    if campaign_id in loaded_campaigns:
        campaign = loaded_campaigns[campaign_id]
    else:
        campaign = load_campaign(campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign not found: {campaign_id}"
            )
        loaded_campaigns[campaign_id] = campaign

    return {
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "author": campaign.author,
            "version": campaign.version,
            "settings": campaign.settings.to_dict(),
            "chapters": [c.to_dict() for c in campaign.chapters],
            "starting_level": campaign.starting_level,
        }
    }


@router.post("/import")
async def import_campaign(campaign_data: Dict[str, Any]):
    """Import a campaign from JSON data."""
    try:
        campaign = Campaign.from_dict(campaign_data)

        # Validate the campaign
        errors = campaign.validate()
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": errors}
            )

        # Store in cache
        loaded_campaigns[campaign.id] = campaign

        return {
            "success": True,
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to import campaign: {str(e)}"
        )


# =============================================================================
# Session Endpoints
# =============================================================================

@router.post("/session/create")
async def create_session(
    request: CreateSessionRequest,
    session_repo: GameSessionRepository = Depends(get_session_repo),
    progress_repo: CampaignProgressRepository = Depends(get_progress_repo),
):
    """Create a new game session for a campaign. Persisted to database."""
    # Load campaign
    if request.campaign_id in loaded_campaigns:
        campaign = loaded_campaigns[request.campaign_id]
    else:
        campaign = load_campaign(request.campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign not found: {request.campaign_id}"
            )
        loaded_campaigns[request.campaign_id] = campaign

    # Create party members
    party = []
    party_ids = []
    for member_data in request.party:
        # DEBUG: Log what we receive from frontend
        import sys
        print(f"[CREATE_SESSION] Received: name={member_data.name}, character_class='{member_data.character_class}', level={member_data.level}, weapons={member_data.weapons}", flush=True)
        print(f"[CREATE_SESSION] Received: name={member_data.name}, character_class='{member_data.character_class}', level={member_data.level}", file=sys.stderr, flush=True)

        member_id = str(uuid.uuid4())
        member = PartyMember(
            id=member_id,
            name=member_data.name,
            character_class=member_data.character_class,
            level=member_data.level,
            character_id=member_data.character_id,  # Link to database Character
            gold=member_data.gold,  # Individual gold
            max_hp=member_data.max_hp,
            current_hp=member_data.max_hp,
            ac=member_data.ac,
            speed=member_data.speed,
            strength=member_data.strength,
            dexterity=member_data.dexterity,
            constitution=member_data.constitution,
            intelligence=member_data.intelligence,
            wisdom=member_data.wisdom,
            charisma=member_data.charisma,
            hit_dice_remaining=member_data.level,
            equipment_data=member_data.equipment_data,
            weapons=member_data.weapons or [],
            spellcasting=member_data.spellcasting,
        )
        party.append(member)
        party_ids.append(member_id)

    # Create campaign engine
    engine = CampaignEngine.create_new(campaign, party)

    # Persist to database
    db_session = await session_repo.create(GameSessionCreate(
        name=f"Session - {campaign.name}",
        campaign_id=request.campaign_id,
        party_character_ids=party_ids,
    ))

    # Update engine with database ID
    engine.session.id = db_session.id

    # Save initial state
    await _persist_session_state(session_repo, db_session.id, engine)

    # Create campaign progress tracker
    await progress_repo.create(db_session.id, request.campaign_id)

    # Cache in memory for performance
    active_sessions[db_session.id] = engine

    return {
        "success": True,
        "session_id": db_session.id,
        "state": engine.get_state().to_dict(),
        "persisted": True,
    }


@router.get("/session/{session_id}/state")
async def get_session_state(session_id: str):
    """Get current state of a game session."""
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]
    return {"state": engine.get_state().to_dict()}


@router.post("/session/{session_id}/advance")
async def advance_session(
    session_id: str,
    request: AdvanceRequest,
    session_repo: GameSessionRepository = Depends(get_session_repo),
):
    """Advance the campaign state. State is auto-saved after each advance."""
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]

    # Validate action
    try:
        action = CampaignAction(request.action)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {request.action}"
        )

    # Advance state with error handling
    try:
        new_state, extra_data = engine.advance(action, request.data)
    except Exception as e:
        import traceback
        print(f"[Campaign API] Error in advance({action}): {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error advancing campaign: {str(e)}"
        )

    # Generate AI scene description if needed (new encounter or story intro)
    if (extra_data and extra_data.get("needs_ai_scene")) or action == CampaignAction.START_CAMPAIGN:
        try:
            ai_scene = await engine._generate_ai_scene_description()
            if ai_scene:
                engine._ai_scene_description = ai_scene
                # Update the state with AI content
                new_state = engine.get_state()
        except Exception as e:
            print(f"[Campaign API] AI scene generation failed (non-fatal): {e}")
            # Continue without AI scene

    # Auto-save state to database after each advance
    try:
        await _persist_session_state(session_repo, session_id, engine)
    except Exception as e:
        print(f"[Campaign API] Warning: Failed to persist state: {e}")
        # Don't fail the request, just log the warning

    # Build response with error handling for serialization
    try:
        response = {
            "success": True,
            "state": new_state.to_dict(),
        }

        if extra_data:
            response["extra"] = extra_data

        return response
    except Exception as e:
        import traceback
        print(f"[Campaign API] Error serializing response: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error serializing response: {str(e)}"
        )


@router.post("/session/{session_id}/rest")
async def take_rest(session_id: str, rest_type: str = "short"):
    """Take a short or long rest (legacy endpoint)."""
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]

    # Advance with rest action
    rest_data = {"rest_type": rest_type}
    action = CampaignAction.REST
    new_state, extra_data = engine.advance(action, rest_data)

    return {
        "success": True,
        "state": new_state.to_dict(),
        "rest_results": extra_data,
    }


class ShortRestRequest(BaseModel):
    """Request for short rest with hit dice allocation."""
    hit_dice_allocation: Dict[str, int] = {}  # character_id -> dice to spend


@router.post("/session/{session_id}/rest/short")
async def take_short_rest(session_id: str, request: ShortRestRequest):
    """
    Take a short rest with optional hit dice allocation.

    Short rest benefits (D&D 5e 2024):
    - Takes 1 hour
    - Can spend any number of available hit dice for healing
    - Each die heals 1d[hit_die] + CON modifier
    - Warlock spell slots restore
    - Short rest class abilities restore
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]
    session = engine.session

    from app.core.rest_system import party_short_rest

    # Perform the short rest
    rest_result = party_short_rest(session, request.hit_dice_allocation)

    # Update session
    session.updated_at = datetime.utcnow().isoformat()

    return {
        "success": True,
        "rest_result": rest_result.to_dict(),
        "session": session.to_dict(),
    }


@router.post("/session/{session_id}/rest/long")
async def take_long_rest(session_id: str):
    """
    Take a long rest.

    Long rest benefits (D&D 5e 2024):
    - Takes 8 hours
    - Restores all HP
    - Restores half of max hit dice (minimum 1)
    - Restores all spell slots
    - Restores all class abilities
    - Reduces exhaustion by 1
    - Clears most conditions
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]
    session = engine.session

    from app.core.rest_system import party_long_rest

    # Perform the long rest
    rest_result = party_long_rest(session)

    # Update session
    session.updated_at = datetime.utcnow().isoformat()

    return {
        "success": True,
        "rest_result": rest_result.to_dict(),
        "session": session.to_dict(),
    }


@router.get("/session/{session_id}/rest/preview")
async def get_rest_preview(session_id: str, rest_type: str = "short"):
    """
    Get a preview of what a rest would provide.

    Useful for UI to show potential healing before committing to rest.
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]
    session = engine.session

    from app.core.rest_system import get_rest_preview, RestType, calculate_recommended_hit_dice

    previews = []
    for member in session.party:
        if not member.is_active or member.is_dead:
            continue

        rt = RestType.SHORT if rest_type == "short" else RestType.LONG
        preview = get_rest_preview(member, rt, 0)
        preview["character_id"] = member.id
        preview["character_name"] = member.name
        preview["current_hp"] = member.current_hp
        preview["max_hp"] = member.max_hp

        if rest_type == "short":
            preview["recommended_dice"] = calculate_recommended_hit_dice(member)

        previews.append(preview)

    return {
        "rest_type": rest_type,
        "member_previews": previews,
    }


# =============================================================================
# Level-Up Endpoints
# =============================================================================

@router.get("/session/{session_id}/level-up/check")
async def check_level_ups(session_id: str):
    """
    Check which party members can level up.

    Returns list of members with enough XP to level up.
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]
    session = engine.session

    from app.core.level_up import check_level_up
    from app.core.progression import get_progression_info

    level_ups = []
    for member in session.party:
        if member.is_dead:
            continue

        new_level = check_level_up(member)
        if new_level:
            level_ups.append({
                "member_id": member.id,
                "member_name": member.name,
                "current_level": member.level,
                "new_level": new_level,
                "class": member.character_class,
            })

    # Also return progression info for all members
    progression = []
    for member in session.party:
        if member.is_dead:
            continue
        info = get_progression_info(member.xp, member.level)
        progression.append({
            "member_id": member.id,
            "member_name": member.name,
            **info.to_dict()
        })

    return {
        "level_ups_available": level_ups,
        "party_progression": progression,
    }


@router.get("/session/{session_id}/level-up/preview/{member_id}")
async def preview_level_up(session_id: str, member_id: str):
    """
    Get a preview of what a character will gain from leveling up.

    Shows HP options, new features, choices required, etc.
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]
    session = engine.session

    # Find the member
    member = next((m for m in session.party if m.id == member_id), None)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Party member not found: {member_id}"
        )

    from app.core.level_up import check_level_up, get_level_up_preview

    new_level = check_level_up(member)
    if not new_level:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character does not have enough XP to level up"
        )

    preview = get_level_up_preview(member, new_level)

    return {
        "member_id": member_id,
        "member_name": member.name,
        "preview": preview.to_dict(),
    }


class LevelUpRequest(BaseModel):
    """Request to apply a level-up."""
    hp_choice: str = "average"  # "average" or "roll"
    hp_roll_result: Optional[int] = None
    asi_choice: Optional[Dict[str, int]] = None  # e.g., {"strength": 2}
    feat_choice: Optional[str] = None
    subclass_choice: Optional[str] = None


@router.post("/session/{session_id}/level-up/apply/{member_id}")
async def apply_level_up(session_id: str, member_id: str, request: LevelUpRequest):
    """
    Apply a level-up to a party member with the player's choices.
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]
    session = engine.session

    # Find the member
    member = next((m for m in session.party if m.id == member_id), None)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Party member not found: {member_id}"
        )

    from app.core.level_up import check_level_up, apply_level_up

    new_level = check_level_up(member)
    if not new_level:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character does not have enough XP to level up"
        )

    result = apply_level_up(
        member=member,
        new_level=new_level,
        hp_choice=request.hp_choice,
        hp_roll_result=request.hp_roll_result,
        asi_choice=request.asi_choice,
        feat_choice=request.feat_choice,
        subclass_choice=request.subclass_choice,
    )

    session.updated_at = datetime.utcnow().isoformat()

    response = {
        "success": result.success,
        "result": result.to_dict(),
        "member": member.to_dict(),
    }

    # Include warnings if there were any issues during level-up
    if result.errors:
        response["warnings"] = result.errors
        response["message"] = "Level up completed with warnings"

    return response


# =============================================================================
# Save/Load Endpoints
# =============================================================================

@router.post("/session/{session_id}/save")
async def save_game(
    session_id: str,
    request: SaveGameRequest,
    save_repo: SaveGameRepository = Depends(get_savegame_repo),
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """Save the current game state. Persisted to database for durability."""
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]
    session = engine.session
    campaign = engine.campaign

    # Get current encounter name
    encounter = session.get_current_encounter()
    encounter_name = encounter.name if encounter else "Unknown"

    # Build party summary
    party_parts = []
    for member in session.party[:3]:
        party_parts.append(f"Lv{member.level} {member.character_class}")
    if len(session.party) > 3:
        party_parts.append(f"+{len(session.party) - 3} more")
    party_summary = ", ".join(party_parts)

    # Create save in database
    save_data = SaveGameCreate(
        session_id=session_id,
        slot_number=request.slot,
        name=request.name,
        session_data=session.to_dict(),
        campaign_name=campaign.name,
        encounter_name=encounter_name,
        party_summary=party_summary,
    )

    # Use update_slot to replace existing save in this slot
    db_save = await save_repo.update_slot(session_id, request.slot, save_data)

    # Also sync party progress to character database
    try:
        await _sync_party_to_characters(char_repo, session)
        print(f"[SAVE] Synced party progress on save", flush=True)
    except Exception as e:
        print(f"[SAVE] Warning: Failed to sync party on save: {e}", flush=True)

    # Also store in memory for backwards compatibility
    save = SaveGame.create_from_session(
        session=session,
        slot=request.slot,
        name=request.name,
        campaign_name=campaign.name,
        encounter_name=encounter_name,
    )
    save_games[save.id] = save

    return {
        "success": True,
        "save_id": db_save.id,
        "save_name": db_save.name,
        "slot": db_save.slot_number,
        "persisted_to_db": True,
    }


@router.get("/saves")
async def list_saves(
    save_repo: SaveGameRepository = Depends(get_savegame_repo),
):
    """List all saved games from database."""
    db_saves = await save_repo.get_all()

    saves = []
    for save in db_saves:
        saves.append({
            "id": save.id,
            "name": save.name,
            "slot": save.slot_number,
            "campaign_name": save.campaign_name,
            "encounter_name": save.encounter_name,
            "party_summary": save.party_summary,
            "created_at": save.created_at.isoformat() if save.created_at else None,
        })

    # Sort by slot
    saves.sort(key=lambda s: s["slot"])

    return {"saves": saves}


@router.post("/saves/load")
async def load_save(
    request: LoadGameRequest,
    save_repo: SaveGameRepository = Depends(get_savegame_repo),
):
    """Load a saved game from database."""
    # Try database first
    db_save = await save_repo.get_by_id(request.save_id)

    if not db_save:
        # Fallback to in-memory for backwards compatibility
        if request.save_id not in save_games:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Save not found: {request.save_id}"
            )
        session_data = save_games[request.save_id].session_data
    else:
        session_data = db_save.session_data

    # Load the campaign
    campaign_id = session_data.get("campaign_id")
    if campaign_id in loaded_campaigns:
        campaign = loaded_campaigns[campaign_id]
    else:
        campaign = load_campaign(campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign not found: {campaign_id}"
            )
        loaded_campaigns[campaign_id] = campaign

    # Restore session
    engine = CampaignEngine.from_save(campaign, session_data)

    # Store session
    active_sessions[engine.session.id] = engine

    return {
        "success": True,
        "session_id": engine.session.id,
        "state": engine.get_state().to_dict(),
        "loaded_from_db": db_save is not None,
    }


@router.delete("/saves/{save_id}")
async def delete_save(
    save_id: str,
    save_repo: SaveGameRepository = Depends(get_savegame_repo),
):
    """Delete a saved game from database."""
    # Try database first
    deleted = await save_repo.delete(save_id)

    if not deleted:
        # Fallback to in-memory for backwards compatibility
        if save_id not in save_games:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Save not found: {save_id}"
            )
        del save_games[save_id]
        return {"success": True, "deleted_from": "memory"}

    # Also clean up from memory cache if present
    if save_id in save_games:
        del save_games[save_id]

    return {"success": True, "deleted_from": "database"}


# =============================================================================
# Combat Integration
# =============================================================================

@router.get("/session/{session_id}/combat")
async def get_combat_state(session_id: str):
    """Get current combat state if in combat."""
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]

    if engine.session.phase != SessionPhase.COMBAT:
        return {"in_combat": False}

    combat_engine = engine.get_combat_engine()
    if not combat_engine:
        return {"in_combat": False}

    return {
        "in_combat": True,
        "combat_id": engine.session.combat_id,
        "combat_state": combat_engine.get_combat_state(),
    }


@router.post("/session/{session_id}/combat/end")
async def end_combat(
    session_id: str,
    victory: bool,
    session_repo: GameSessionRepository = Depends(get_session_repo),
    char_repo: CharacterRepository = Depends(get_character_repo),
):
    """End combat and return to campaign flow with combat summary."""
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]

    # Idempotent: If not in COMBAT phase, combat already ended - return cached summary
    # This handles ALL post-combat phases (COMBAT_RESOLUTION, STORY_OUTCOME, VICTORY,
    # GAME_OVER, EXPLORATION, etc.) without raising 400 errors
    if engine.session.phase != SessionPhase.COMBAT:
        cached_summary = getattr(engine, '_last_combat_summary', {})
        return {
            "success": True,
            "state": engine.get_state().to_dict(),
            "victory": victory,
            "already_ended": True,
            "combat_summary": cached_summary,
        }

    # End combat - extra_data contains combat summary (XP, loot, level-ups)
    print(f"[Campaign] Ending combat with victory={victory}")
    new_state, extra_data = engine.advance(
        CampaignAction.END_COMBAT,
        {"victory": victory}
    )
    print(f"[Campaign] _end_combat returned extra_data: {extra_data}")

    # Build combat summary response
    combat_summary = extra_data or {}

    # Build formatted summary
    formatted_summary = {
        "combat_id": combat_summary.get("combat_id"),
        "enemies_defeated": combat_summary.get("enemies_defeated", []),
        "xp_earned": combat_summary.get("xp_earned", 0),
        "xp_per_player": combat_summary.get("xp_per_player", 0),
        "level_ups": combat_summary.get("level_ups", []),
        "loot": combat_summary.get("loot"),
    }

    # Cache summary for potential duplicate calls (idempotent)
    engine._last_combat_summary = formatted_summary

    # AUTO-SYNC: Persist party progress (XP, gold, level) back to Character database
    # This ensures progress carries over to future campaigns
    try:
        sync_results = await _sync_party_to_characters(char_repo, engine.session)
        print(f"[Campaign] Auto-sync after combat: {sync_results}")
        formatted_summary["sync_results"] = sync_results
    except Exception as e:
        print(f"[Campaign] Warning: Auto-sync failed: {e}")
        # Don't fail the request, just log the warning

    # Persist session state to database
    try:
        await _persist_session_state(session_repo, session_id, engine)
    except Exception as e:
        print(f"[Campaign] Warning: Failed to persist state: {e}")

    print(f"[Campaign] Returning combat_summary: {formatted_summary}")
    return {
        "success": True,
        "state": new_state.to_dict(),
        "victory": victory,
        "combat_summary": formatted_summary,
    }
