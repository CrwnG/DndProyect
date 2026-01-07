"""
D&D Combat Engine - Campaign Editor API Routes
Endpoints for modifying campaigns before playing.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services.campaign_editor import campaign_editor
from app.services.campaign_generator import campaign_generator
from app.core.errors import GameError, CampaignError, ErrorCode
from app.middleware.auth import get_current_user_optional

router = APIRouter(prefix="/api/campaign", tags=["campaign-editor"])


# ==================== Request/Response Models ====================

class UpdateEncounterRequest(BaseModel):
    """Request to update an encounter."""
    name: Optional[str] = None
    description: Optional[str] = None
    difficulty: Optional[str] = None
    enemies: Optional[List[Dict[str, Any]]] = None
    rewards: Optional[Dict[str, Any]] = None
    choices: Optional[List[Dict[str, Any]]] = None
    story_text: Optional[str] = None
    outcome_text: Optional[str] = None
    triggers: Optional[Dict[str, Any]] = None


class ReorderEncountersRequest(BaseModel):
    """Request to reorder encounters."""
    encounter_ids: List[str] = Field(..., description="Encounter IDs in new order")


class AddEncounterRequest(BaseModel):
    """Request to add a new encounter."""
    id: Optional[str] = None
    name: str = "New Encounter"
    type: str = "combat"
    description: str = ""
    difficulty: Optional[str] = "medium"
    enemies: Optional[List[Dict[str, Any]]] = None
    rewards: Optional[Dict[str, Any]] = None
    choices: Optional[List[Dict[str, Any]]] = None
    story_text: Optional[str] = None
    outcome_text: Optional[str] = None
    position: Optional[int] = None


class UpdateNPCRequest(BaseModel):
    """Request to update an NPC."""
    name: Optional[str] = None
    role: Optional[str] = None
    disposition: Optional[int] = None
    personality: Optional[Dict[str, Any]] = None


class UpdateCampaignMetadataRequest(BaseModel):
    """Request to update campaign metadata."""
    name: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[str] = None
    difficulty: Optional[str] = None
    party_level_range: Optional[List[int]] = None


class DuplicateCampaignRequest(BaseModel):
    """Request to duplicate a campaign."""
    new_name: Optional[str] = None


# ==================== Load Campaign for Editing ====================

@router.post("/{campaign_id}/edit")
async def load_campaign_for_editing(
    campaign_id: str,
    user=Depends(get_current_user_optional)
):
    """
    Load a campaign into the editor.
    Must be called before other edit operations.
    """
    try:
        # Get campaign from generator's memory or database
        # For now, we'll use the campaign generator's stored campaigns
        campaign = await campaign_generator.get_campaign(campaign_id)

        if not campaign:
            raise CampaignError(
                code=ErrorCode.CAMPAIGN_NOT_FOUND,
                message=f"Campaign {campaign_id} not found"
            )

        # Load into editor
        campaign_editor.load_campaign(campaign_id, campaign)

        return {
            "success": True,
            "message": "Campaign loaded for editing",
            "campaign": campaign_editor.get_editable_campaign(campaign_id)
        }

    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/edit")
async def get_editable_campaign(
    campaign_id: str,
    user=Depends(get_current_user_optional)
):
    """Get a campaign in editable format."""
    try:
        return {
            "success": True,
            "campaign": campaign_editor.get_editable_campaign(campaign_id)
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Encounter Operations ====================

@router.put("/{campaign_id}/encounter/{encounter_id}")
async def update_encounter(
    campaign_id: str,
    encounter_id: str,
    request: UpdateEncounterRequest,
    user=Depends(get_current_user_optional)
):
    """Update an encounter's properties."""
    try:
        # Filter out None values
        data = {k: v for k, v in request.model_dump().items() if v is not None}

        encounter = campaign_editor.update_encounter(campaign_id, encounter_id, data)

        return {
            "success": True,
            "encounter": encounter
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{campaign_id}/chapter/{chapter_id}/reorder")
async def reorder_encounters(
    campaign_id: str,
    chapter_id: str,
    request: ReorderEncountersRequest,
    user=Depends(get_current_user_optional)
):
    """Reorder encounters within a chapter."""
    try:
        chapter = campaign_editor.reorder_encounters(
            campaign_id,
            chapter_id,
            request.encounter_ids
        )

        return {
            "success": True,
            "chapter": chapter
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/chapter/{chapter_id}/encounter")
async def add_encounter(
    campaign_id: str,
    chapter_id: str,
    request: AddEncounterRequest,
    user=Depends(get_current_user_optional)
):
    """Add a new encounter to a chapter."""
    try:
        data = request.model_dump()
        position = data.pop("position", None)

        encounter = campaign_editor.add_encounter(
            campaign_id,
            chapter_id,
            data,
            position
        )

        return {
            "success": True,
            "encounter": encounter
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}/chapter/{chapter_id}/encounter/{encounter_id}")
async def remove_encounter(
    campaign_id: str,
    chapter_id: str,
    encounter_id: str,
    user=Depends(get_current_user_optional)
):
    """Remove an encounter from a chapter."""
    try:
        chapter = campaign_editor.remove_encounter(
            campaign_id,
            chapter_id,
            encounter_id
        )

        return {
            "success": True,
            "chapter": chapter
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== NPC Operations ====================

@router.put("/{campaign_id}/npc/{npc_id}")
async def update_npc(
    campaign_id: str,
    npc_id: str,
    request: UpdateNPCRequest,
    user=Depends(get_current_user_optional)
):
    """Update an NPC's properties."""
    try:
        data = {k: v for k, v in request.model_dump().items() if v is not None}

        npc = campaign_editor.update_npc(campaign_id, npc_id, data)

        return {
            "success": True,
            "npc": npc
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Campaign Operations ====================

@router.put("/{campaign_id}/metadata")
async def update_campaign_metadata(
    campaign_id: str,
    request: UpdateCampaignMetadataRequest,
    user=Depends(get_current_user_optional)
):
    """Update campaign metadata (name, description, etc.)."""
    try:
        data = {k: v for k, v in request.model_dump().items() if v is not None}

        metadata = campaign_editor.update_campaign_metadata(campaign_id, data)

        return {
            "success": True,
            "campaign": metadata
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/duplicate")
async def duplicate_campaign(
    campaign_id: str,
    request: DuplicateCampaignRequest,
    user=Depends(get_current_user_optional)
):
    """Create a copy of a campaign."""
    try:
        new_campaign = campaign_editor.duplicate_campaign(
            campaign_id,
            request.new_name
        )

        return {
            "success": True,
            "campaign": new_campaign
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/save")
async def save_campaign(
    campaign_id: str,
    user=Depends(get_current_user_optional)
):
    """
    Save changes made to a campaign.
    Persists the edited campaign back to storage.
    """
    try:
        campaign = campaign_editor.save_campaign(campaign_id)

        # In a full implementation, this would save to database
        # For now, update the campaign generator's memory
        await campaign_generator.store_campaign(campaign)

        return {
            "success": True,
            "message": "Campaign saved successfully",
            "campaign_id": campaign.id
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/discard")
async def discard_changes(
    campaign_id: str,
    user=Depends(get_current_user_optional)
):
    """Discard all unsaved changes to a campaign."""
    try:
        campaign_editor.discard_changes(campaign_id)

        return {
            "success": True,
            "message": "Changes discarded"
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Edit History Operations ====================

@router.get("/{campaign_id}/history")
async def get_edit_history(
    campaign_id: str,
    user=Depends(get_current_user_optional)
):
    """Get the edit history for a campaign."""
    try:
        history = campaign_editor.get_edit_history(campaign_id)

        return {
            "success": True,
            "history": history
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/undo")
async def undo_last_change(
    campaign_id: str,
    user=Depends(get_current_user_optional)
):
    """Undo the last change to a campaign."""
    try:
        change = campaign_editor.undo_last_change(campaign_id)

        if not change:
            return {
                "success": False,
                "message": "No changes to undo"
            }

        return {
            "success": True,
            "undone_change": change,
            "campaign": campaign_editor.get_editable_campaign(campaign_id)
        }
    except GameError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
