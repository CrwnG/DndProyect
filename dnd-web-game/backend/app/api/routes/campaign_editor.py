"""
Campaign Editor API Routes.

DB-backed editing of the real `Campaign` model. Each operation loads the campaign
from the `CampaignRepository` (seeding from the shipped JSON campaigns on first
edit), applies a `CampaignEditorService` operation, and persists the updated
`Campaign.to_dict()` back. Edits are durable across restarts.
"""
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services.campaign_editor import campaign_editor
from app.core.campaign_engine import load_campaign
from app.models.campaign import Campaign
from app.database.dependencies import get_campaign_repo
from app.database.repositories import CampaignRepository
from app.middleware.auth import get_current_user_optional

router = APIRouter(prefix="/api/campaign", tags=["campaign-editor"])


# ==================== Request Models ====================

class UpdateEncounterRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    difficulty: Optional[str] = None
    story: Optional[Dict[str, Any]] = None
    combat: Optional[Dict[str, Any]] = None
    choices: Optional[Dict[str, Any]] = None
    rewards: Optional[Dict[str, Any]] = None
    transitions: Optional[Dict[str, Any]] = None
    requires_flags: Optional[List[str]] = None


class AddEncounterRequest(BaseModel):
    id: Optional[str] = None
    name: str = "New Encounter"
    type: str = "combat"
    difficulty: Optional[str] = None
    story: Optional[Dict[str, Any]] = None
    combat: Optional[Dict[str, Any]] = None
    choices: Optional[Dict[str, Any]] = None
    rewards: Optional[Dict[str, Any]] = None
    position: Optional[int] = None


class ReorderEncountersRequest(BaseModel):
    encounter_ids: List[str] = Field(..., description="Encounter IDs in new order")


class UpdateNPCRequest(BaseModel):
    fields: Dict[str, Any] = Field(default_factory=dict, description="NPC fields to set")


class UpdateCampaignMetadataRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    tone: Optional[str] = None
    difficulty: Optional[str] = None
    starting_level: Optional[int] = None
    starting_gold: Optional[int] = None


class DuplicateCampaignRequest(BaseModel):
    new_name: Optional[str] = None


# ==================== Helpers ====================

async def _load_or_seed(campaign_id: str, repo: CampaignRepository) -> Campaign:
    """Load an editable campaign from the DB, seeding from the shipped JSON
    campaign on first edit. Raises 404 if neither source has it."""
    row = await repo.get_by_id(campaign_id)
    if row is not None:
        return Campaign.from_dict(row.data)

    seeded = load_campaign(campaign_id)
    if seeded is not None:
        return seeded

    raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}")


async def _persist(campaign: Campaign, repo: CampaignRepository) -> None:
    """Persist a campaign and commit the transaction."""
    await repo.upsert(
        campaign.id, campaign.name, campaign.author, campaign.description,
        campaign.to_dict(),
    )
    await repo.session.commit()


def _ok(campaign: Campaign, **extra) -> Dict[str, Any]:
    """Standard response: success + the full campaign + any extra payload."""
    return {"success": True, "campaign": campaign.to_dict(), **extra}


# ==================== Load / Get ====================

@router.post("/{campaign_id}/edit")
async def load_campaign_for_editing(
    campaign_id: str,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Load a campaign into the editor (seeding + persisting on first edit)."""
    campaign = await _load_or_seed(campaign_id, repo)
    await _persist(campaign, repo)   # materialize the editable copy in the DB
    return _ok(campaign, message="Campaign loaded for editing")


@router.get("/{campaign_id}/edit")
async def get_editable_campaign(
    campaign_id: str,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Get the current editable campaign."""
    campaign = await _load_or_seed(campaign_id, repo)
    return _ok(campaign)


# ==================== Encounter Operations ====================

@router.post("/{campaign_id}/chapter/{chapter_id}/encounter")
async def add_encounter(
    campaign_id: str,
    chapter_id: str,
    request: AddEncounterRequest,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Add a new encounter to a chapter."""
    campaign = await _load_or_seed(campaign_id, repo)
    data = {k: v for k, v in request.model_dump().items() if v is not None}
    position = data.pop("position", None)
    encounter = campaign_editor.add_encounter(campaign, data, chapter_id, position)
    await _persist(campaign, repo)
    return _ok(campaign, encounter=encounter.to_dict())


@router.put("/{campaign_id}/encounter/{encounter_id}")
async def update_encounter(
    campaign_id: str,
    encounter_id: str,
    request: UpdateEncounterRequest,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Update an encounter's properties."""
    campaign = await _load_or_seed(campaign_id, repo)
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    encounter = campaign_editor.update_encounter(campaign, encounter_id, updates)
    if encounter is None:
        raise HTTPException(status_code=404, detail=f"Encounter not found: {encounter_id}")
    await _persist(campaign, repo)
    return _ok(campaign, encounter=encounter.to_dict())


@router.delete("/{campaign_id}/encounter/{encounter_id}")
async def remove_encounter(
    campaign_id: str,
    encounter_id: str,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Remove an encounter and purge all references to it."""
    campaign = await _load_or_seed(campaign_id, repo)
    if not campaign_editor.remove_encounter(campaign, encounter_id):
        raise HTTPException(status_code=404, detail=f"Encounter not found: {encounter_id}")
    await _persist(campaign, repo)
    return _ok(campaign)


@router.put("/{campaign_id}/chapter/{chapter_id}/reorder")
async def reorder_encounters(
    campaign_id: str,
    chapter_id: str,
    request: ReorderEncountersRequest,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Reorder the encounters within a chapter."""
    campaign = await _load_or_seed(campaign_id, repo)
    if not campaign_editor.reorder_encounters(campaign, chapter_id, request.encounter_ids):
        raise HTTPException(status_code=404, detail=f"Chapter not found: {chapter_id}")
    await _persist(campaign, repo)
    return _ok(campaign)


# ==================== NPC Operations ====================

@router.put("/{campaign_id}/npc/{npc_id}")
async def update_npc(
    campaign_id: str,
    npc_id: str,
    request: UpdateNPCRequest,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Create or update an NPC."""
    campaign = await _load_or_seed(campaign_id, repo)
    npc = campaign_editor.update_npc(campaign, npc_id, request.fields)
    await _persist(campaign, repo)
    return _ok(campaign, npc=npc)


# ==================== Campaign Operations ====================

@router.put("/{campaign_id}/metadata")
async def update_campaign_metadata(
    campaign_id: str,
    request: UpdateCampaignMetadataRequest,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Update campaign metadata (name, description, difficulty, …)."""
    campaign = await _load_or_seed(campaign_id, repo)
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    campaign_editor.update_metadata(campaign, **updates)
    await _persist(campaign, repo)
    return _ok(campaign)


@router.get("/{campaign_id}/validate")
async def validate_campaign(
    campaign_id: str,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Validate a campaign's structure; returns the list of errors (empty = valid)."""
    campaign = await _load_or_seed(campaign_id, repo)
    errors = campaign_editor.validate(campaign)
    return {"success": True, "valid": len(errors) == 0, "errors": errors}


@router.post("/{campaign_id}/duplicate")
async def duplicate_campaign(
    campaign_id: str,
    request: DuplicateCampaignRequest,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Create an independent copy of a campaign under a new id."""
    campaign = await _load_or_seed(campaign_id, repo)
    copy = campaign_editor.duplicate(campaign, request.new_name)
    await _persist(copy, repo)
    return _ok(copy, message="Campaign duplicated")


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    repo: CampaignRepository = Depends(get_campaign_repo),
    user=Depends(get_current_user_optional),
):
    """Delete a stored (edited) campaign. The shipped JSON original is untouched."""
    deleted = await repo.delete(campaign_id)
    await repo.session.commit()
    return {"success": deleted}
