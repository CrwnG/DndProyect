"""
D&D Combat Engine - Campaign Editor Service
Provides functionality to modify campaigns before playing.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from copy import deepcopy

from app.models.campaign import Campaign, Chapter, Encounter, WorldState
from app.models.npc import NPC
from app.core.errors import CampaignError, ValidationError, ErrorCode

logger = logging.getLogger("dnd_engine.campaign_editor")


class CampaignEditorService:
    """
    Service for editing and modifying campaigns.

    Allows users to:
    - Reorder encounters
    - Add/remove encounters
    - Modify encounter details
    - Update NPC properties
    - Duplicate campaigns
    """

    def __init__(self):
        # In-memory campaign storage for editing
        # In production, this would use a database
        self._campaigns: Dict[str, Campaign] = {}
        self._edit_history: Dict[str, List[Dict]] = {}  # campaign_id -> list of changes

    def load_campaign(self, campaign_id: str, campaign: Campaign) -> None:
        """Load a campaign for editing."""
        self._campaigns[campaign_id] = deepcopy(campaign)
        self._edit_history[campaign_id] = []
        logger.info(f"Loaded campaign {campaign_id} for editing")

    def get_campaign(self, campaign_id: str) -> Campaign:
        """Get a campaign being edited."""
        if campaign_id not in self._campaigns:
            raise CampaignError(
                code=ErrorCode.CAMPAIGN_NOT_FOUND,
                message=f"Campaign {campaign_id} not found in editor"
            )
        return self._campaigns[campaign_id]

    def get_editable_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get campaign in a format suitable for frontend editing.
        Includes metadata and structure information.
        """
        campaign = self.get_campaign(campaign_id)

        return {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "theme": getattr(campaign, "theme", "adventure"),
            "difficulty": getattr(campaign, "difficulty", "medium"),
            "party_level_range": getattr(campaign, "party_level_range", [1, 5]),
            "chapters": [self._chapter_to_dict(ch) for ch in campaign.chapters],
            "npcs": [self._npc_to_dict(npc) for npc in getattr(campaign, "npcs", [])],
            "world_state": self._world_state_to_dict(campaign.world_state) if campaign.world_state else {},
            "edit_history": self._edit_history.get(campaign_id, []),
            "last_modified": datetime.utcnow().isoformat(),
        }

    def _chapter_to_dict(self, chapter: Chapter) -> Dict[str, Any]:
        """Convert a chapter to an editable dictionary."""
        return {
            "id": chapter.id,
            "name": chapter.name,
            "description": chapter.description,
            "encounters": [self._encounter_to_dict(enc) for enc in chapter.encounters],
        }

    def _encounter_to_dict(self, encounter: Encounter) -> Dict[str, Any]:
        """Convert an encounter to an editable dictionary."""
        return {
            "id": encounter.id,
            "name": encounter.name,
            "type": encounter.type,
            "description": encounter.description,
            "difficulty": getattr(encounter, "difficulty", "medium"),
            "enemies": getattr(encounter, "enemies", []),
            "rewards": getattr(encounter, "rewards", {}),
            "choices": getattr(encounter, "choices", []),
            "triggers": getattr(encounter, "triggers", {}),
            "story_text": getattr(encounter, "story_text", ""),
            "outcome_text": getattr(encounter, "outcome_text", ""),
        }

    def _npc_to_dict(self, npc: NPC) -> Dict[str, Any]:
        """Convert an NPC to an editable dictionary."""
        return {
            "id": npc.id,
            "name": npc.name,
            "role": npc.role,
            "personality": {
                "traits": npc.personality.traits if npc.personality else [],
                "quirks": npc.personality.quirks if npc.personality else [],
                "motivation": npc.personality.motivation if npc.personality else "",
                "fear": npc.personality.fear if npc.personality else "",
                "secret": npc.personality.secret if npc.personality else None,
                "humor_style": npc.personality.humor_style if npc.personality else "none",
                "speech_patterns": npc.personality.speech_patterns if npc.personality else "casual",
            } if npc.personality else {},
            "disposition": npc.disposition,
        }

    def _world_state_to_dict(self, world_state: WorldState) -> Dict[str, Any]:
        """Convert world state to an editable dictionary."""
        return {
            "flags": getattr(world_state, "flags", {}),
            "variables": getattr(world_state, "variables", {}),
            "npc_dispositions": getattr(world_state, "npc_dispositions", {}),
        }

    # ==================== Encounter Operations ====================

    def update_encounter(
        self,
        campaign_id: str,
        encounter_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an encounter's properties.

        Args:
            campaign_id: Campaign ID
            encounter_id: Encounter to update
            data: Properties to update

        Returns:
            Updated encounter data
        """
        campaign = self.get_campaign(campaign_id)
        encounter = self._find_encounter(campaign, encounter_id)

        if not encounter:
            raise CampaignError(
                code=ErrorCode.CAMPAIGN_INVALID_ENCOUNTER,
                message=f"Encounter {encounter_id} not found"
            )

        # Track changes for undo
        old_values = {}

        # Update allowed fields
        allowed_fields = [
            "name", "description", "difficulty", "enemies", "rewards",
            "choices", "story_text", "outcome_text", "triggers"
        ]

        for field in allowed_fields:
            if field in data:
                old_values[field] = getattr(encounter, field, None)
                setattr(encounter, field, data[field])

        # Record edit history
        self._record_change(campaign_id, "update_encounter", {
            "encounter_id": encounter_id,
            "old_values": old_values,
            "new_values": {k: data[k] for k in data if k in allowed_fields}
        })

        logger.info(f"Updated encounter {encounter_id} in campaign {campaign_id}")
        return self._encounter_to_dict(encounter)

    def reorder_encounters(
        self,
        campaign_id: str,
        chapter_id: str,
        new_order: List[str]
    ) -> Dict[str, Any]:
        """
        Reorder encounters within a chapter.

        Args:
            campaign_id: Campaign ID
            chapter_id: Chapter containing encounters
            new_order: List of encounter IDs in new order

        Returns:
            Updated chapter data
        """
        campaign = self.get_campaign(campaign_id)
        chapter = self._find_chapter(campaign, chapter_id)

        if not chapter:
            raise CampaignError(
                code=ErrorCode.CAMPAIGN_INVALID_STATE,
                message=f"Chapter {chapter_id} not found"
            )

        # Validate all encounter IDs exist
        encounter_map = {enc.id: enc for enc in chapter.encounters}
        for enc_id in new_order:
            if enc_id not in encounter_map:
                raise ValidationError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Encounter {enc_id} not found in chapter"
                )

        # Record old order
        old_order = [enc.id for enc in chapter.encounters]

        # Reorder encounters
        chapter.encounters = [encounter_map[enc_id] for enc_id in new_order]

        # Record edit history
        self._record_change(campaign_id, "reorder_encounters", {
            "chapter_id": chapter_id,
            "old_order": old_order,
            "new_order": new_order
        })

        logger.info(f"Reordered encounters in chapter {chapter_id}")
        return self._chapter_to_dict(chapter)

    def add_encounter(
        self,
        campaign_id: str,
        chapter_id: str,
        encounter_data: Dict[str, Any],
        position: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Add a new encounter to a chapter.

        Args:
            campaign_id: Campaign ID
            chapter_id: Chapter to add encounter to
            encounter_data: Encounter properties
            position: Index to insert at (default: end)

        Returns:
            Created encounter data
        """
        campaign = self.get_campaign(campaign_id)
        chapter = self._find_chapter(campaign, chapter_id)

        if not chapter:
            raise CampaignError(
                code=ErrorCode.CAMPAIGN_INVALID_STATE,
                message=f"Chapter {chapter_id} not found"
            )

        # Generate ID if not provided
        encounter_id = encounter_data.get("id", f"encounter_{len(chapter.encounters) + 1}")

        # Create encounter
        encounter = Encounter(
            id=encounter_id,
            name=encounter_data.get("name", "New Encounter"),
            type=encounter_data.get("type", "combat"),
            description=encounter_data.get("description", ""),
        )

        # Set optional fields
        for field in ["difficulty", "enemies", "rewards", "choices", "story_text", "outcome_text", "triggers"]:
            if field in encounter_data:
                setattr(encounter, field, encounter_data[field])

        # Insert at position
        if position is not None and 0 <= position <= len(chapter.encounters):
            chapter.encounters.insert(position, encounter)
        else:
            chapter.encounters.append(encounter)

        # Record edit history
        self._record_change(campaign_id, "add_encounter", {
            "chapter_id": chapter_id,
            "encounter_id": encounter_id,
            "position": position
        })

        logger.info(f"Added encounter {encounter_id} to chapter {chapter_id}")
        return self._encounter_to_dict(encounter)

    def remove_encounter(
        self,
        campaign_id: str,
        chapter_id: str,
        encounter_id: str
    ) -> Dict[str, Any]:
        """
        Remove an encounter from a chapter.

        Args:
            campaign_id: Campaign ID
            chapter_id: Chapter containing encounter
            encounter_id: Encounter to remove

        Returns:
            Updated chapter data
        """
        campaign = self.get_campaign(campaign_id)
        chapter = self._find_chapter(campaign, chapter_id)

        if not chapter:
            raise CampaignError(
                code=ErrorCode.CAMPAIGN_INVALID_STATE,
                message=f"Chapter {chapter_id} not found"
            )

        # Find and remove encounter
        encounter_index = None
        removed_encounter = None
        for i, enc in enumerate(chapter.encounters):
            if enc.id == encounter_id:
                encounter_index = i
                removed_encounter = enc
                break

        if removed_encounter is None:
            raise CampaignError(
                code=ErrorCode.CAMPAIGN_INVALID_ENCOUNTER,
                message=f"Encounter {encounter_id} not found in chapter"
            )

        chapter.encounters.remove(removed_encounter)

        # Record edit history (store full encounter for undo)
        self._record_change(campaign_id, "remove_encounter", {
            "chapter_id": chapter_id,
            "encounter_id": encounter_id,
            "encounter_data": self._encounter_to_dict(removed_encounter),
            "position": encounter_index
        })

        logger.info(f"Removed encounter {encounter_id} from chapter {chapter_id}")
        return self._chapter_to_dict(chapter)

    # ==================== NPC Operations ====================

    def update_npc(
        self,
        campaign_id: str,
        npc_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an NPC's properties.

        Args:
            campaign_id: Campaign ID
            npc_id: NPC to update
            data: Properties to update

        Returns:
            Updated NPC data
        """
        campaign = self.get_campaign(campaign_id)
        npc = self._find_npc(campaign, npc_id)

        if not npc:
            raise CampaignError(
                code=ErrorCode.CAMPAIGN_INVALID_STATE,
                message=f"NPC {npc_id} not found"
            )

        old_values = {}

        # Update basic fields
        basic_fields = ["name", "role", "disposition"]
        for field in basic_fields:
            if field in data:
                old_values[field] = getattr(npc, field, None)
                setattr(npc, field, data[field])

        # Update personality fields
        if "personality" in data and npc.personality:
            personality_data = data["personality"]
            old_values["personality"] = self._npc_to_dict(npc)["personality"]

            for field in ["traits", "quirks", "motivation", "fear", "secret", "humor_style", "speech_patterns"]:
                if field in personality_data:
                    setattr(npc.personality, field, personality_data[field])

        # Record edit history
        self._record_change(campaign_id, "update_npc", {
            "npc_id": npc_id,
            "old_values": old_values,
            "new_values": data
        })

        logger.info(f"Updated NPC {npc_id} in campaign {campaign_id}")
        return self._npc_to_dict(npc)

    # ==================== Campaign Operations ====================

    def update_campaign_metadata(
        self,
        campaign_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update campaign metadata (name, description, difficulty, etc.)

        Args:
            campaign_id: Campaign ID
            data: Metadata to update

        Returns:
            Updated campaign summary
        """
        campaign = self.get_campaign(campaign_id)
        old_values = {}

        allowed_fields = ["name", "description", "theme", "difficulty", "party_level_range"]
        for field in allowed_fields:
            if field in data:
                old_values[field] = getattr(campaign, field, None)
                setattr(campaign, field, data[field])

        self._record_change(campaign_id, "update_metadata", {
            "old_values": old_values,
            "new_values": {k: data[k] for k in data if k in allowed_fields}
        })

        logger.info(f"Updated campaign {campaign_id} metadata")

        return {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "theme": getattr(campaign, "theme", "adventure"),
            "difficulty": getattr(campaign, "difficulty", "medium"),
        }

    def duplicate_campaign(
        self,
        campaign_id: str,
        new_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a copy of a campaign.

        Args:
            campaign_id: Campaign to duplicate
            new_name: Name for the copy (default: "Copy of <original>")

        Returns:
            New campaign data
        """
        original = self.get_campaign(campaign_id)

        # Deep copy the campaign
        new_campaign = deepcopy(original)

        # Generate new ID
        import uuid
        new_campaign.id = str(uuid.uuid4())[:8]

        # Set name
        new_campaign.name = new_name or f"Copy of {original.name}"

        # Generate new IDs for all chapters and encounters
        for chapter in new_campaign.chapters:
            chapter.id = f"ch_{str(uuid.uuid4())[:6]}"
            for encounter in chapter.encounters:
                encounter.id = f"enc_{str(uuid.uuid4())[:6]}"

        # Store the new campaign
        self._campaigns[new_campaign.id] = new_campaign
        self._edit_history[new_campaign.id] = []

        logger.info(f"Duplicated campaign {campaign_id} as {new_campaign.id}")
        return self.get_editable_campaign(new_campaign.id)

    def save_campaign(self, campaign_id: str) -> Campaign:
        """
        Get the edited campaign for saving.

        Args:
            campaign_id: Campaign ID

        Returns:
            The edited Campaign object
        """
        return deepcopy(self.get_campaign(campaign_id))

    def discard_changes(self, campaign_id: str) -> None:
        """
        Discard all changes to a campaign.

        Args:
            campaign_id: Campaign ID
        """
        if campaign_id in self._campaigns:
            del self._campaigns[campaign_id]
        if campaign_id in self._edit_history:
            del self._edit_history[campaign_id]
        logger.info(f"Discarded changes to campaign {campaign_id}")

    # ==================== Undo/Redo Operations ====================

    def undo_last_change(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """
        Undo the last change to a campaign.

        Args:
            campaign_id: Campaign ID

        Returns:
            The undone change, or None if no changes to undo
        """
        history = self._edit_history.get(campaign_id, [])
        if not history:
            return None

        change = history.pop()
        # Implementation of undo would restore old values based on change type
        # This is a simplified version - full implementation would need
        # to handle each change type specifically

        logger.info(f"Undid {change['action']} on campaign {campaign_id}")
        return change

    def get_edit_history(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Get the edit history for a campaign."""
        return self._edit_history.get(campaign_id, [])

    # ==================== Helper Methods ====================

    def _find_chapter(self, campaign: Campaign, chapter_id: str) -> Optional[Chapter]:
        """Find a chapter by ID."""
        for chapter in campaign.chapters:
            if chapter.id == chapter_id:
                return chapter
        return None

    def _find_encounter(self, campaign: Campaign, encounter_id: str) -> Optional[Encounter]:
        """Find an encounter by ID across all chapters."""
        for chapter in campaign.chapters:
            for encounter in chapter.encounters:
                if encounter.id == encounter_id:
                    return encounter
        return None

    def _find_npc(self, campaign: Campaign, npc_id: str) -> Optional[NPC]:
        """Find an NPC by ID."""
        npcs = getattr(campaign, "npcs", [])
        for npc in npcs:
            if npc.id == npc_id:
                return npc
        return None

    def _record_change(self, campaign_id: str, action: str, data: Dict[str, Any]) -> None:
        """Record a change to the edit history."""
        if campaign_id not in self._edit_history:
            self._edit_history[campaign_id] = []

        self._edit_history[campaign_id].append({
            "action": action,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })


# Singleton instance
campaign_editor = CampaignEditorService()
