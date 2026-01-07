"""
Campaign Generator API Routes.

Endpoints for AI-powered campaign generation:
- Generate campaigns from prompts
- Generate individual encounters
- Generate NPCs with BG3-quality depth
- Track and trigger consequences
"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
import logging

from app.services.campaign_generator import (
    CampaignGeneratorService,
    get_campaign_generator,
)
from app.services.npc_generator import (
    NPCGeneratorService,
    get_npc_generator,
)
from app.services.campaign_parser import (
    CampaignParserService,
    get_campaign_parser,
    EnhancementLevel,
)
from app.core.consequence_tracker import ConsequenceTracker
from app.core.pacing_manager import PacingManager
from app.models.campaign import (
    Campaign, WorldState, Encounter, Act, Chapter,
    ConsequenceEffectType,
)
from app.models.npc import NPC

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory storage (would be database in production)
generated_campaigns: Dict[str, Campaign] = {}
campaign_world_states: Dict[str, WorldState] = {}


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class GenerateCampaignRequest(BaseModel):
    """Request to generate a new campaign."""
    concept: str = Field(..., description="Campaign concept/premise", min_length=10)
    level_start: int = Field(1, ge=1, le=20, description="Starting party level")
    level_end: int = Field(10, ge=1, le=20, description="Ending party level")
    length: str = Field("medium", description="Campaign length: short, medium, long, epic")
    tone: str = Field("mixed", description="Campaign tone: dark, heroic, comedic, mixed")


class GenerateCampaignResponse(BaseModel):
    """Response from campaign generation."""
    campaign_id: str
    name: str
    description: str
    acts: int
    chapters: int
    encounters: int
    npcs: int
    message: str


class GenerateEncounterRequest(BaseModel):
    """Request to generate a single encounter."""
    campaign_id: str
    encounter_type: str = Field(..., description="Type: combat, social, exploration, choice")
    act_name: str = ""
    act_theme: str = "mystery"
    chapter_name: str = ""
    story_summary: str = ""
    party_level: int = 1
    party_composition: str = ""
    recent_events: str = ""
    active_flags: List[str] = []
    pacing: str = "tension_rise"
    difficulty: str = "medium"
    callbacks: List[str] = []


class GenerateNPCRequest(BaseModel):
    """Request to generate an NPC."""
    campaign_id: Optional[str] = None
    role: str = Field(..., description="Role: companion, villain, quest_giver, merchant, ally")
    importance: str = "major"
    story_context: str = ""
    first_appearance: str = "Act 1"
    tone: str = "mixed"


class RecordChoiceRequest(BaseModel):
    """Request to record a player choice."""
    campaign_id: str
    choice_id: str
    encounter_id: str
    outcome: str
    context: Dict[str, Any] = {}


class RecordChoiceResponse(BaseModel):
    """Response from recording a choice."""
    success: bool
    immediate_effects: List[Dict[str, Any]]
    message: str


class CheckConsequencesRequest(BaseModel):
    """Request to check for triggered consequences."""
    campaign_id: str
    encounter_id: str
    current_act: Optional[str] = None
    current_chapter: Optional[str] = None


class PacingAnalysisRequest(BaseModel):
    """Request for pacing analysis."""
    encounters: List[Dict[str, Any]]


class ParseTextRequest(BaseModel):
    """Request to parse text campaign content."""
    content: str = Field(..., description="Campaign text content", min_length=50)
    title: str = Field("Untitled Campaign", description="Optional campaign title")
    enhancement: str = Field("moderate", description="Enhancement level: minimal, moderate, full")


class ParseResponse(BaseModel):
    """Response from campaign parsing."""
    campaign_id: str
    name: str
    description: str
    acts: int
    chapters: int
    encounters: int
    npcs: int
    items: int
    enhancement_level: str
    message: str


# =============================================================================
# CAMPAIGN GENERATION ENDPOINTS
# =============================================================================

@router.post("/generate", response_model=GenerateCampaignResponse)
async def generate_campaign(request: GenerateCampaignRequest):
    """
    Generate a complete BG3-quality campaign from a concept.

    This uses AI to create:
    - 3-act structure with escalating stakes
    - Chapters with varied encounters
    - Memorable NPCs with personality depth
    - Meaningful choices with consequences
    """
    generator = get_campaign_generator()

    if not generator.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaign generator not available. Check API key configuration.",
        )

    try:
        campaign = await generator.generate_campaign(
            concept=request.concept,
            party_level_range=(request.level_start, request.level_end),
            length=request.length,
            tone=request.tone,
        )

        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate campaign. Please try again.",
            )

        # Store the campaign
        generated_campaigns[campaign.id] = campaign
        campaign_world_states[campaign.id] = WorldState()

        return GenerateCampaignResponse(
            campaign_id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            acts=len(campaign.acts),
            chapters=len(campaign.chapters),
            encounters=len(campaign.encounters),
            npcs=len(campaign.npcs),
            message="Campaign generated successfully!",
        )

    except Exception as e:
        logger.error(f"Campaign generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Campaign generation failed: {str(e)}",
        )


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get a generated campaign by ID."""
    if campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    campaign = generated_campaigns[campaign_id]
    return campaign.to_dict()


@router.get("/{campaign_id}/structure")
async def get_campaign_structure(campaign_id: str):
    """Get the high-level structure of a campaign (acts and chapters)."""
    if campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    campaign = generated_campaigns[campaign_id]

    return {
        "campaign_id": campaign.id,
        "name": campaign.name,
        "central_conflict": campaign.central_conflict,
        "tone": campaign.tone,
        "acts": [
            {
                "id": act.id,
                "name": act.name,
                "theme": act.theme.value,
                "description": act.description,
                "emotional_arc": act.emotional_arc,
                "chapters": act.chapters,
                "key_revelations": act.key_revelations,
            }
            for act in campaign.acts
        ],
        "chapters": [
            {
                "id": chapter.id,
                "title": chapter.title,
                "description": chapter.description,
                "encounter_count": len(chapter.encounters),
            }
            for chapter in campaign.chapters
        ],
    }


# =============================================================================
# DOCUMENT PARSING ENDPOINTS
# =============================================================================

@router.post("/parse/pdf", response_model=ParseResponse)
async def parse_pdf_campaign(
    file: UploadFile = File(..., description="PDF campaign document"),
    enhancement: str = Form("moderate", description="Enhancement level: minimal, moderate, full"),
):
    """
    Parse a PDF campaign document into a playable campaign.

    Upload a D&D campaign PDF (official modules, homebrew, etc.)
    and convert it into a structured campaign with encounters, NPCs, and choices.

    Enhancement levels:
    - minimal: Just parse structure, no AI enhancement
    - moderate: Fill in gaps with AI (recommended)
    - full: Rich BG3-quality AI enhancement
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF document",
        )

    parser = get_campaign_parser()

    try:
        # Save uploaded file temporarily
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Parse the PDF
            doc = await parser.parse_pdf(tmp_path)

            # Extract structure
            structure = await parser.extract_structure(doc)

            # Convert to campaign with enhancement
            try:
                level = EnhancementLevel(enhancement)
            except ValueError:
                level = EnhancementLevel.MODERATE

            campaign = await parser.convert_to_campaign(structure, level)

            # Store the campaign
            generated_campaigns[campaign.id] = campaign
            campaign_world_states[campaign.id] = WorldState()

            return ParseResponse(
                campaign_id=campaign.id,
                name=campaign.name,
                description=campaign.description[:500] if campaign.description else "",
                acts=len(campaign.acts),
                chapters=len(campaign.chapters),
                encounters=len(campaign.encounters),
                npcs=len(campaign.npcs),
                items=len(structure.items),
                enhancement_level=level.value,
                message=f"Successfully parsed '{file.filename}' into playable campaign!",
            )

        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF parsing requires pdfplumber. Please install: pip install pdfplumber",
        )

    except Exception as e:
        logger.error(f"PDF parsing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse PDF: {str(e)}",
        )


@router.post("/parse/text", response_model=ParseResponse)
async def parse_text_campaign(request: ParseTextRequest):
    """
    Parse text campaign content into a playable campaign.

    Paste campaign text (copied from PDFs, homebrew documents, etc.)
    and convert it into a structured campaign with encounters, NPCs, and choices.

    Enhancement levels:
    - minimal: Just parse structure, no AI enhancement
    - moderate: Fill in gaps with AI (recommended)
    - full: Rich BG3-quality AI enhancement
    """
    parser = get_campaign_parser()

    try:
        # Parse the text
        doc = await parser.parse_text(request.content, request.title)

        # Extract structure
        structure = await parser.extract_structure(doc)

        # Convert to campaign with enhancement
        try:
            level = EnhancementLevel(request.enhancement)
        except ValueError:
            level = EnhancementLevel.MODERATE

        campaign = await parser.convert_to_campaign(structure, level)

        # Store the campaign
        generated_campaigns[campaign.id] = campaign
        campaign_world_states[campaign.id] = WorldState()

        return ParseResponse(
            campaign_id=campaign.id,
            name=campaign.name,
            description=campaign.description[:500] if campaign.description else "",
            acts=len(campaign.acts),
            chapters=len(campaign.chapters),
            encounters=len(campaign.encounters),
            npcs=len(campaign.npcs),
            items=len(structure.items),
            enhancement_level=level.value,
            message="Successfully parsed text into playable campaign!",
        )

    except Exception as e:
        logger.error(f"Text parsing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse text: {str(e)}",
        )


@router.get("/parse/status")
async def get_parser_status():
    """Check if the campaign parser is available."""
    parser = get_campaign_parser()

    return {
        "available": True,
        "ai_enhancement_available": parser.is_available,
        "supported_formats": ["pdf", "text"],
        "enhancement_levels": ["minimal", "moderate", "full"],
    }


# =============================================================================
# ENCOUNTER GENERATION ENDPOINTS
# =============================================================================

@router.post("/encounter/generate")
async def generate_encounter(request: GenerateEncounterRequest):
    """Generate a single encounter for a campaign."""
    generator = get_campaign_generator()

    if not generator.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generator not available",
        )

    campaign = generated_campaigns.get(request.campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {request.campaign_id} not found",
        )

    try:
        encounter = await generator.generate_encounter(
            campaign=campaign,
            encounter_type=request.encounter_type,
            context={
                "act_name": request.act_name,
                "act_theme": request.act_theme,
                "chapter_name": request.chapter_name,
                "story_summary": request.story_summary,
                "party_level": request.party_level,
                "party_composition": request.party_composition,
                "recent_events": request.recent_events,
                "active_flags": request.active_flags,
                "pacing": request.pacing,
                "difficulty": request.difficulty,
                "callbacks": request.callbacks,
            },
        )

        if not encounter:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate encounter",
            )

        # Add to campaign
        campaign.encounters[encounter.id] = encounter

        return encounter.to_dict()

    except Exception as e:
        logger.error(f"Encounter generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encounter generation failed: {str(e)}",
        )


@router.get("/{campaign_id}/encounters")
async def list_encounters(campaign_id: str):
    """List all encounters in a campaign."""
    if campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    campaign = generated_campaigns[campaign_id]

    return {
        "campaign_id": campaign_id,
        "encounters": [
            {
                "id": enc.id,
                "name": enc.name,
                "type": enc.type.value,
            }
            for enc in campaign.encounters.values()
        ],
    }


@router.get("/{campaign_id}/encounter/{encounter_id}")
async def get_encounter(campaign_id: str, encounter_id: str):
    """Get a specific encounter."""
    if campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    campaign = generated_campaigns[campaign_id]
    encounter = campaign.encounters.get(encounter_id)

    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encounter {encounter_id} not found",
        )

    return encounter.to_dict()


# =============================================================================
# NPC GENERATION ENDPOINTS
# =============================================================================

@router.post("/npc/generate")
async def generate_npc(request: GenerateNPCRequest):
    """Generate a BG3-quality NPC."""
    generator = get_npc_generator()

    campaign_name = "Adventure"
    if request.campaign_id and request.campaign_id in generated_campaigns:
        campaign = generated_campaigns[request.campaign_id]
        campaign_name = campaign.name

    try:
        npc = await generator.generate_npc(
            role=request.role,
            context={
                "campaign_name": campaign_name,
                "tone": request.tone,
                "story_context": request.story_context,
                "importance": request.importance,
                "first_appearance": request.first_appearance,
            },
        )

        if not npc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate NPC",
            )

        # Add to campaign if specified
        if request.campaign_id and request.campaign_id in generated_campaigns:
            campaign = generated_campaigns[request.campaign_id]
            campaign.npcs[npc.id] = npc.to_dict()

        return npc.to_dict()

    except Exception as e:
        logger.error(f"NPC generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"NPC generation failed: {str(e)}",
        )


@router.get("/{campaign_id}/npcs")
async def list_npcs(campaign_id: str):
    """List all NPCs in a campaign with their current dispositions."""
    if campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    campaign = generated_campaigns[campaign_id]
    world_state = campaign_world_states.get(campaign_id, WorldState())

    npcs = []
    for npc_id, npc_data in campaign.npcs.items():
        npc_info = {
            "id": npc_id,
            "name": npc_data.get("name", "Unknown"),
            "role": npc_data.get("role", "neutral"),
            "disposition": world_state.get_npc_disposition(npc_id),
        }
        npcs.append(npc_info)

    return {
        "campaign_id": campaign_id,
        "npcs": npcs,
    }


@router.post("/npc/{npc_id}/dialogue")
async def generate_dialogue(npc_id: str, topic: str = "greeting", campaign_id: str = None):
    """Generate a dialogue tree for an NPC."""
    generator = get_npc_generator()

    # Get NPC data
    npc_data = None
    if campaign_id and campaign_id in generated_campaigns:
        campaign = generated_campaigns[campaign_id]
        npc_data = campaign.npcs.get(npc_id)

    if not npc_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC {npc_id} not found",
        )

    try:
        # Convert dict to NPC object
        npc = NPC.from_dict(npc_data) if isinstance(npc_data, dict) else npc_data

        dialogue_tree = await generator.generate_dialogue_tree(
            npc=npc,
            topic=topic,
            context={
                "encounter_name": "",
                "npc_knowledge": "",
                "npc_wants": "",
                "player_goal": "",
                "available_flags": [],
            },
        )

        if not dialogue_tree:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate dialogue",
            )

        return dialogue_tree.to_dict()

    except Exception as e:
        logger.error(f"Dialogue generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dialogue generation failed: {str(e)}",
        )


# =============================================================================
# CONSEQUENCE TRACKING ENDPOINTS
# =============================================================================

@router.post("/choice", response_model=RecordChoiceResponse)
async def record_choice(request: RecordChoiceRequest):
    """
    Record a player choice and get immediate consequences.

    This is called after the player makes a significant decision
    in the campaign to track consequences.
    """
    if request.campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {request.campaign_id} not found",
        )

    world_state = campaign_world_states.get(request.campaign_id, WorldState())
    tracker = ConsequenceTracker(world_state)

    effects = tracker.record_choice(
        choice_id=request.choice_id,
        encounter_id=request.encounter_id,
        outcome=request.outcome,
        context=request.context,
    )

    # Update stored world state
    campaign_world_states[request.campaign_id] = world_state

    return RecordChoiceResponse(
        success=True,
        immediate_effects=[
            {
                "type": e.effect_type.value,
                "target": e.target,
                "narrative": e.narrative_text,
            }
            for e in effects
        ],
        message=f"Choice recorded. {len(effects)} immediate effects applied.",
    )


@router.post("/consequences/check")
async def check_consequences(request: CheckConsequencesRequest):
    """
    Check for triggered consequences before an encounter.

    Returns any delayed consequences that should trigger now.
    """
    if request.campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {request.campaign_id} not found",
        )

    world_state = campaign_world_states.get(request.campaign_id, WorldState())
    tracker = ConsequenceTracker(world_state)

    triggered = tracker.check_triggers(
        encounter_id=request.encounter_id,
        current_act=request.current_act,
        current_chapter=request.current_chapter,
    )

    # Update stored world state
    campaign_world_states[request.campaign_id] = world_state

    return {
        "triggered_count": len(triggered),
        "consequences": [
            {
                "type": e.effect_type.value,
                "target": e.target,
                "narrative": e.narrative_text,
                "source_choice": e.source_choice_id,
            }
            for e in triggered
        ],
    }


@router.get("/{campaign_id}/choices/summary")
async def get_choice_summary(campaign_id: str):
    """Get a summary of all choices made in a campaign."""
    if campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    world_state = campaign_world_states.get(campaign_id, WorldState())
    tracker = ConsequenceTracker(world_state)

    return tracker.get_choice_summary()


@router.get("/{campaign_id}/world-state")
async def get_world_state(campaign_id: str):
    """Get the current world state (flags, NPC dispositions, etc.)."""
    if campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    world_state = campaign_world_states.get(campaign_id, WorldState())
    return world_state.to_dict()


# =============================================================================
# PACING ANALYSIS ENDPOINTS
# =============================================================================

@router.post("/pacing/analyze")
async def analyze_pacing(request: PacingAnalysisRequest):
    """Analyze the pacing of a sequence of encounters."""
    pacing_manager = PacingManager()

    analysis = pacing_manager.analyze_pacing(request.encounters)

    return {
        "combat_ratio": analysis.combat_ratio,
        "social_ratio": analysis.social_ratio,
        "exploration_ratio": analysis.exploration_ratio,
        "consecutive_combats": analysis.consecutive_combats,
        "needs_relief": analysis.needs_relief,
        "tension_curve": analysis.tension_curve,
        "suggestions": analysis.suggestions,
    }


@router.post("/pacing/suggest")
async def suggest_next_encounter(
    recent_types: List[str],
    chapter_position: float = 0.5,
    chapter_theme: str = "standard",
):
    """Suggest what type of encounter should come next."""
    pacing_manager = PacingManager()

    suggested_type, pacing_role = pacing_manager.suggest_next_type(
        recent_encounters=recent_types,
        chapter_position=chapter_position,
        chapter_theme=chapter_theme,
    )

    return {
        "suggested_type": suggested_type,
        "pacing_role": pacing_role.value,
        "reason": f"Based on {len(recent_types)} recent encounters and position {chapter_position:.0%} through chapter",
    }


@router.get("/pacing/budget")
async def get_encounter_budget(
    total_encounters: int = 10,
    chapter_type: str = "standard",
):
    """Get target encounter type distribution for a chapter."""
    pacing_manager = PacingManager()

    budget = pacing_manager.get_encounter_budget(
        total_encounters=total_encounters,
        chapter_type=chapter_type,
    )

    return {
        "total": total_encounters,
        "chapter_type": chapter_type,
        "budget": budget,
    }


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================

@router.get("/status")
async def get_generator_status():
    """Check if the campaign generator is available."""
    campaign_gen = get_campaign_generator()
    npc_gen = get_npc_generator()

    return {
        "campaign_generator": {
            "available": campaign_gen.is_available,
        },
        "npc_generator": {
            "available": npc_gen.is_available,
        },
        "stored_campaigns": len(generated_campaigns),
    }


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: str):
    """Delete a generated campaign."""
    if campaign_id not in generated_campaigns:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    del generated_campaigns[campaign_id]
    if campaign_id in campaign_world_states:
        del campaign_world_states[campaign_id]

    return {"message": f"Campaign {campaign_id} deleted"}
