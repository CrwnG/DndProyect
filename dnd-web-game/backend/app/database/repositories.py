"""
Repository pattern for database access.

Provides clean abstractions for CRUD operations on database models.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Character,
    CharacterCreate,
    CharacterUpdate,
    GameSession,
    GameSessionCreate,
    CombatState,
    CombatStateCreate,
    CombatLog,
    CampaignProgress,
    SaveGameDB,
    SaveGameCreate,
)


# =============================================================================
# CHARACTER REPOSITORY
# =============================================================================

class CharacterRepository:
    """Repository for Character CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: CharacterCreate) -> Character:
        """Create a new character."""
        character = Character(
            name=data.name,
            species=data.species,
            character_class=data.character_class,
            subclass=data.subclass,
            level=data.level,
            background=data.background,
            abilities=data.abilities or {
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            },
        )
        self.session.add(character)
        await self.session.flush()
        return character

    async def get_by_id(self, character_id: str) -> Optional[Character]:
        """Get a character by ID."""
        result = await self.session.execute(
            select(Character).where(Character.id == character_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, user_id: Optional[str] = None, limit: int = 100) -> List[Character]:
        """Get all characters, optionally filtered by user."""
        query = select(Character).where(Character.is_active == True)
        if user_id:
            query = query.where(Character.user_id == user_id)
        query = query.order_by(Character.updated_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, character_id: str, data: CharacterUpdate) -> Optional[Character]:
        """Update a character."""
        character = await self.get_by_id(character_id)
        if not character:
            return None

        update_data = data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        for key, value in update_data.items():
            setattr(character, key, value)

        await self.session.flush()
        return character

    async def delete(self, character_id: str) -> bool:
        """Soft delete a character."""
        character = await self.get_by_id(character_id)
        if not character:
            return False

        character.is_active = False
        character.updated_at = datetime.utcnow()
        await self.session.flush()
        return True

    async def hard_delete(self, character_id: str) -> bool:
        """Permanently delete a character."""
        result = await self.session.execute(
            delete(Character).where(Character.id == character_id)
        )
        return result.rowcount > 0

    async def update_hp(
        self,
        character_id: str,
        current_hp: Optional[int] = None,
        temp_hp: Optional[int] = None,
        max_hp: Optional[int] = None,
    ) -> Optional[Character]:
        """Update character HP values."""
        character = await self.get_by_id(character_id)
        if not character:
            return None

        if current_hp is not None:
            character.current_hp = current_hp
        if temp_hp is not None:
            character.temp_hp = temp_hp
        if max_hp is not None:
            character.max_hp = max_hp
        character.updated_at = datetime.utcnow()

        await self.session.flush()
        return character

    async def grant_xp(self, character_id: str, xp_amount: int) -> Optional[Character]:
        """Grant XP to a character."""
        character = await self.get_by_id(character_id)
        if not character:
            return None

        character.experience += xp_amount
        character.updated_at = datetime.utcnow()

        # Check for level up
        from app.core.progression import get_new_level_from_xp
        new_level = get_new_level_from_xp(character.experience, character.level)
        if new_level:
            character.level = new_level

        await self.session.flush()
        return character


# =============================================================================
# GAME SESSION REPOSITORY
# =============================================================================

class GameSessionRepository:
    """Repository for GameSession CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: GameSessionCreate) -> GameSession:
        """Create a new game session."""
        game_session = GameSession(
            name=data.name,
            campaign_id=data.campaign_id,
            party_character_ids=data.party_character_ids,
        )
        self.session.add(game_session)
        await self.session.flush()
        return game_session

    async def get_by_id(self, session_id: str) -> Optional[GameSession]:
        """Get a game session by ID."""
        result = await self.session.execute(
            select(GameSession).where(GameSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 50) -> List[GameSession]:
        """Get all active game sessions."""
        query = (
            select(GameSession)
            .where(GameSession.is_active == True)
            .order_by(GameSession.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, session_id: str, **kwargs) -> Optional[GameSession]:
        """Update a game session."""
        game_session = await self.get_by_id(session_id)
        if not game_session:
            return None

        kwargs["updated_at"] = datetime.utcnow()
        for key, value in kwargs.items():
            if hasattr(game_session, key):
                setattr(game_session, key, value)

        await self.session.flush()
        return game_session

    async def update_party(
        self,
        session_id: str,
        party: List[Dict[str, Any]],
    ) -> Optional[GameSession]:
        """Update the party in a session."""
        return await self.update(session_id, party=party)

    async def set_active_combat(
        self,
        session_id: str,
        combat_id: Optional[str],
    ) -> Optional[GameSession]:
        """Set the active combat for a session."""
        return await self.update(session_id, active_combat_id=combat_id)

    async def delete(self, session_id: str) -> bool:
        """Soft delete a game session."""
        game_session = await self.get_by_id(session_id)
        if not game_session:
            return False

        game_session.is_active = False
        game_session.updated_at = datetime.utcnow()
        await self.session.flush()
        return True


# =============================================================================
# COMBAT STATE REPOSITORY
# =============================================================================

class CombatStateRepository:
    """Repository for CombatState CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: CombatStateCreate) -> CombatState:
        """Create a new combat state."""
        combat_state = CombatState(
            session_id=data.session_id,
            combatants=data.combatants,
        )
        self.session.add(combat_state)
        await self.session.flush()
        return combat_state

    async def get_by_id(self, combat_id: str) -> Optional[CombatState]:
        """Get a combat state by ID."""
        result = await self.session.execute(
            select(CombatState).where(CombatState.id == combat_id)
        )
        return result.scalar_one_or_none()

    async def get_active_for_session(self, session_id: str) -> Optional[CombatState]:
        """Get the active combat for a session."""
        result = await self.session.execute(
            select(CombatState)
            .where(CombatState.session_id == session_id)
            .where(CombatState.is_active == True)
            .order_by(CombatState.started_at.desc())
        )
        return result.scalar_one_or_none()

    async def update(self, combat_id: str, **kwargs) -> Optional[CombatState]:
        """Update a combat state."""
        combat_state = await self.get_by_id(combat_id)
        if not combat_state:
            return None

        for key, value in kwargs.items():
            if hasattr(combat_state, key):
                setattr(combat_state, key, value)

        await self.session.flush()
        return combat_state

    async def update_full_state(
        self,
        combat_id: str,
        phase: str,
        round_number: int,
        current_turn_index: int,
        combatant_stats: Dict[str, Any],
        current_turn: Optional[Dict[str, Any]],
        positions: Dict[str, Any],
        initiative_order: List[Dict[str, Any]],
        active_effects: List[Dict[str, Any]],
    ) -> Optional[CombatState]:
        """Update full combat state."""
        return await self.update(
            combat_id,
            phase=phase,
            round_number=round_number,
            current_turn_index=current_turn_index,
            combatant_stats=combatant_stats,
            current_turn=current_turn,
            positions=positions,
            initiative_order=initiative_order,
            active_effects=active_effects,
        )

    async def end_combat(
        self,
        combat_id: str,
        result: str,
        xp_awarded: int = 0,
    ) -> Optional[CombatState]:
        """End a combat encounter."""
        return await self.update(
            combat_id,
            phase="ended",
            is_active=False,
            result=result,
            xp_awarded=xp_awarded,
            ended_at=datetime.utcnow(),
        )


# =============================================================================
# COMBAT LOG REPOSITORY
# =============================================================================

class CombatLogRepository:
    """Repository for CombatLog operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        combat_state_id: str,
        event_type: str,
        description: str,
        round_number: int = 1,
        turn_number: int = 1,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> CombatLog:
        """Create a new combat log entry."""
        log = CombatLog(
            combat_state_id=combat_state_id,
            session_id=session_id,
            event_type=event_type,
            description=description,
            round_number=round_number,
            turn_number=turn_number,
            actor_id=actor_id,
            actor_name=actor_name,
            target_id=target_id,
            target_name=target_name,
            data=data or {},
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_for_combat(
        self,
        combat_state_id: str,
        limit: int = 100,
    ) -> List[CombatLog]:
        """Get all logs for a combat."""
        result = await self.session.execute(
            select(CombatLog)
            .where(CombatLog.combat_state_id == combat_state_id)
            .order_by(CombatLog.timestamp.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_for_round(
        self,
        combat_state_id: str,
        round_number: int,
    ) -> List[CombatLog]:
        """Get all logs for a specific round."""
        result = await self.session.execute(
            select(CombatLog)
            .where(CombatLog.combat_state_id == combat_state_id)
            .where(CombatLog.round_number == round_number)
            .order_by(CombatLog.timestamp.asc())
        )
        return list(result.scalars().all())


# =============================================================================
# CAMPAIGN PROGRESS REPOSITORY
# =============================================================================

class CampaignProgressRepository:
    """Repository for CampaignProgress operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        session_id: str,
        campaign_id: str,
    ) -> CampaignProgress:
        """Create a new campaign progress tracker."""
        progress = CampaignProgress(
            session_id=session_id,
            campaign_id=campaign_id,
        )
        self.session.add(progress)
        await self.session.flush()
        return progress

    async def get_for_session(
        self,
        session_id: str,
        campaign_id: str,
    ) -> Optional[CampaignProgress]:
        """Get campaign progress for a session."""
        result = await self.session.execute(
            select(CampaignProgress)
            .where(CampaignProgress.session_id == session_id)
            .where(CampaignProgress.campaign_id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def complete_scene(
        self,
        progress_id: str,
        scene_id: str,
    ) -> Optional[CampaignProgress]:
        """Mark a scene as completed."""
        result = await self.session.execute(
            select(CampaignProgress).where(CampaignProgress.id == progress_id)
        )
        progress = result.scalar_one_or_none()
        if not progress:
            return None

        if scene_id not in progress.completed_scenes:
            progress.completed_scenes = progress.completed_scenes + [scene_id]
        progress.updated_at = datetime.utcnow()

        await self.session.flush()
        return progress

    async def set_flag(
        self,
        progress_id: str,
        flag_name: str,
        flag_value: Any,
    ) -> Optional[CampaignProgress]:
        """Set a story flag."""
        result = await self.session.execute(
            select(CampaignProgress).where(CampaignProgress.id == progress_id)
        )
        progress = result.scalar_one_or_none()
        if not progress:
            return None

        progress.flags = {**progress.flags, flag_name: flag_value}
        progress.updated_at = datetime.utcnow()

        await self.session.flush()
        return progress


# =============================================================================
# SAVE GAME REPOSITORY
# =============================================================================

class SaveGameRepository:
    """Repository for SaveGameDB operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: SaveGameCreate) -> SaveGameDB:
        """Create a new save game."""
        save = SaveGameDB(
            session_id=data.session_id,
            slot_number=data.slot_number,
            name=data.name,
            session_data=data.session_data,
            combat_data=data.combat_data,
            campaign_name=data.campaign_name,
            encounter_name=data.encounter_name,
            party_summary=data.party_summary,
            playtime_minutes=data.playtime_minutes,
        )
        self.session.add(save)
        await self.session.flush()
        return save

    async def get_by_id(self, save_id: str) -> Optional[SaveGameDB]:
        """Get a save game by ID."""
        result = await self.session.execute(
            select(SaveGameDB).where(SaveGameDB.id == save_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100) -> List[SaveGameDB]:
        """Get all save games, ordered by creation date (newest first)."""
        result = await self.session.execute(
            select(SaveGameDB)
            .order_by(SaveGameDB.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_session(self, session_id: str) -> List[SaveGameDB]:
        """Get all saves for a specific session."""
        result = await self.session.execute(
            select(SaveGameDB)
            .where(SaveGameDB.session_id == session_id)
            .order_by(SaveGameDB.slot_number.asc())
        )
        return list(result.scalars().all())

    async def get_by_slot(self, session_id: str, slot_number: int) -> Optional[SaveGameDB]:
        """Get save game by session and slot number."""
        result = await self.session.execute(
            select(SaveGameDB)
            .where(SaveGameDB.session_id == session_id)
            .where(SaveGameDB.slot_number == slot_number)
        )
        return result.scalar_one_or_none()

    async def delete(self, save_id: str) -> bool:
        """Delete a save game."""
        result = await self.session.execute(
            delete(SaveGameDB).where(SaveGameDB.id == save_id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def update_slot(
        self,
        session_id: str,
        slot_number: int,
        data: SaveGameCreate,
    ) -> SaveGameDB:
        """
        Update or create a save in a specific slot.

        If a save exists in this slot, it is replaced.
        """
        # Check for existing save in this slot
        existing = await self.get_by_slot(session_id, slot_number)
        if existing:
            # Delete existing save
            await self.delete(existing.id)

        # Create new save
        return await self.create(data)
