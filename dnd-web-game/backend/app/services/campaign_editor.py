"""
Campaign Editor Service.

Edits the real `app.models.campaign.Campaign` domain model (acts → chapters →
encounter-id lists, an `encounters` dict, and a plain `npcs` dict). Operations are
stateless — they mutate the passed-in `Campaign`; persistence is handled by the
route layer via `CampaignRepository` (DB-backed). The previous implementation was
coded against fields that don't exist on the model (chapter.name, encounter.
description/enemies, campaign.world_state, npcs-as-objects) and had no storage.
"""
import logging
import uuid
from typing import List, Dict, Any, Optional

from app.models.campaign import Campaign, Chapter, Encounter, Difficulty

logger = logging.getLogger("dnd_engine.campaign_editor")


class CampaignEditorService:
    """Schema-correct, stateless editing operations on a Campaign."""

    # ------------------------------------------------------------------ metadata
    def update_metadata(
        self,
        campaign: Campaign,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        author: Optional[str] = None,
        tone: Optional[str] = None,
        difficulty: Optional[str] = None,
        starting_level: Optional[int] = None,
        starting_gold: Optional[int] = None,
    ) -> Campaign:
        """Update top-level campaign metadata. Only provided fields change."""
        if name is not None:
            campaign.name = name
        if description is not None:
            campaign.description = description
        if author is not None:
            campaign.author = author
        if tone is not None:
            campaign.tone = tone
        if starting_level is not None:
            campaign.starting_level = starting_level
        if starting_gold is not None:
            campaign.starting_gold = starting_gold
        if difficulty is not None:
            campaign.settings.difficulty = Difficulty(difficulty)
        return campaign

    # ---------------------------------------------------------------- encounters
    def add_encounter(
        self,
        campaign: Campaign,
        encounter_data: Dict[str, Any],
        chapter_id: Optional[str] = None,
        position: Optional[int] = None,
    ) -> Encounter:
        """Create an encounter and (optionally) place its id in a chapter's order.

        Validates preconditions BEFORE mutating: a supplied id must not already
        exist, and a supplied chapter_id must resolve — otherwise raises ValueError
        (so the route can 400/404 without leaving an orphaned encounter)."""
        data = dict(encounter_data)
        enc_id = data.get("id") or str(uuid.uuid4())
        if enc_id in campaign.encounters:
            raise ValueError(f"Encounter id already exists: {enc_id}")

        chapter = None
        if chapter_id:
            chapter = self._chapter(campaign, chapter_id)
            if chapter is None:
                raise ValueError(f"Chapter not found: {chapter_id}")

        data["id"] = enc_id
        data.setdefault("type", "combat")
        data.setdefault("name", "New Encounter")
        encounter = Encounter.from_dict(data)
        campaign.encounters[enc_id] = encounter

        if chapter is not None:
            if position is None or position >= len(chapter.encounters):
                chapter.encounters.append(enc_id)
            else:
                chapter.encounters.insert(max(0, position), enc_id)
        return encounter

    def update_encounter(
        self, campaign: Campaign, encounter_id: str, updates: Dict[str, Any]
    ) -> Optional[Encounter]:
        """Merge partial updates into an encounter and rebuild it from the merged
        dict (so enum/nested fields are parsed correctly). Returns None if absent."""
        encounter = campaign.encounters.get(encounter_id)
        if encounter is None:
            return None
        merged = {**encounter.to_dict(), **updates, "id": encounter_id}
        rebuilt = Encounter.from_dict(merged)
        campaign.encounters[encounter_id] = rebuilt
        return rebuilt

    def remove_encounter(self, campaign: Campaign, encounter_id: str) -> bool:
        """Remove an encounter and purge every reference to it (chapter orders,
        the starting encounter, and victory/flee transitions)."""
        if encounter_id not in campaign.encounters:
            return False
        del campaign.encounters[encounter_id]

        for chapter in campaign.chapters:
            if encounter_id in chapter.encounters:
                chapter.encounters = [e for e in chapter.encounters if e != encounter_id]

        for encounter in campaign.encounters.values():
            trans = encounter.transitions
            if trans.on_victory == encounter_id:
                trans.on_victory = None
            if trans.on_flee == encounter_id:
                trans.on_flee = None

        if campaign.starting_encounter == encounter_id:
            campaign.starting_encounter = next(iter(campaign.encounters), None)
        return True

    def reorder_encounters(
        self, campaign: Campaign, chapter_id: str, encounter_ids: List[str]
    ) -> bool:
        """Set a chapter's encounter order. `encounter_ids` must be an exact
        permutation of the chapter's current encounters — no missing, unknown, or
        duplicate ids (silently dropping ids would lose data). Returns False if the
        chapter doesn't exist; raises ValueError on a non-permutation."""
        chapter = self._chapter(campaign, chapter_id)
        if chapter is None:
            return False
        if sorted(encounter_ids) != sorted(chapter.encounters):
            raise ValueError(
                "encounter_ids must be a permutation of the chapter's current encounters"
            )
        chapter.encounters = list(encounter_ids)
        return True

    # ------------------------------------------------------------------ chapters
    def add_chapter(self, campaign: Campaign, chapter_data: Dict[str, Any]) -> Chapter:
        """Append a new chapter."""
        data = dict(chapter_data)
        data.setdefault("id", str(uuid.uuid4()))
        chapter = Chapter.from_dict(data)
        campaign.chapters.append(chapter)
        return chapter

    def update_chapter(
        self, campaign: Campaign, chapter_id: str, updates: Dict[str, Any]
    ) -> Optional[Chapter]:
        """Update a chapter's title/description (not its encounter order — use
        reorder_encounters for that)."""
        chapter = self._chapter(campaign, chapter_id)
        if chapter is None:
            return None
        if "title" in updates:
            chapter.title = updates["title"]
        if "description" in updates:
            chapter.description = updates["description"]
        return chapter

    def remove_chapter(self, campaign: Campaign, chapter_id: str) -> bool:
        """Remove a chapter (its encounters stay in the campaign's encounter pool)."""
        before = len(campaign.chapters)
        campaign.chapters = [c for c in campaign.chapters if c.id != chapter_id]
        for act in campaign.acts:
            if chapter_id in act.chapters:
                act.chapters = [c for c in act.chapters if c != chapter_id]
        return len(campaign.chapters) != before

    # ---------------------------------------------------------------------- npcs
    def update_npc(
        self, campaign: Campaign, npc_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create or update an NPC (NPCs are plain dicts keyed by id)."""
        npc = dict(campaign.npcs.get(npc_id, {}))
        npc.update(updates)
        campaign.npcs[npc_id] = npc
        return npc

    def remove_npc(self, campaign: Campaign, npc_id: str) -> bool:
        """Remove an NPC."""
        return campaign.npcs.pop(npc_id, None) is not None

    # ------------------------------------------------------------ whole-campaign
    def duplicate(self, campaign: Campaign, new_name: Optional[str] = None) -> Campaign:
        """Deep-copy a campaign (via its JSON form) under a fresh id."""
        copy = Campaign.from_dict(campaign.to_dict())
        copy.id = str(uuid.uuid4())
        copy.name = new_name or f"{campaign.name} (Copy)"
        return copy

    def validate(self, campaign: Campaign) -> List[str]:
        """Return structural errors (orphan refs, bad transitions, missing start)."""
        return campaign.validate()

    # ------------------------------------------------------------------- helpers
    @staticmethod
    def _chapter(campaign: Campaign, chapter_id: str) -> Optional[Chapter]:
        return next((c for c in campaign.chapters if c.id == chapter_id), None)


# Module-level singleton used by the route layer.
campaign_editor = CampaignEditorService()
