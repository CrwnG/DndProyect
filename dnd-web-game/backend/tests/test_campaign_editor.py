"""R1: DB-backed campaign editor — persistence + schema-correct editing.

The old editor was coded against a campaign schema that doesn't exist and had no
storage at all. These tests drive a CampaignRepository (stores the full
Campaign.to_dict() JSON) and a CampaignEditorService that edits the real
app.models.campaign.Campaign object.
"""
import pytest
import pytest_asyncio
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database.models  # noqa: F401 — register tables


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def _sample_campaign():
    """A minimal but real Campaign with one chapter + two encounters + an NPC."""
    from app.models.campaign import Campaign

    return Campaign.from_dict({
        "campaign": {"id": "demo", "name": "Demo Quest", "author": "Tester",
                     "description": "A short test campaign."},
        "chapters": [{"id": "ch1", "title": "Chapter 1", "encounters": ["enc1", "enc2"]}],
        "encounters": {
            "enc1": {"id": "enc1", "type": "combat", "name": "Goblin Ambush"},
            "enc2": {"id": "enc2", "type": "social", "name": "The Crossroads"},
        },
        "npcs": {"npc1": {"name": "Old Hermit", "role": "guide", "disposition": 50}},
        "starting_encounter": "enc1",
    })


async def test_campaign_repository_round_trips_full_campaign(db_session):
    """A campaign stored as JSON must reload and reconstruct identically."""
    from app.database.repositories import CampaignRepository
    from app.models.campaign import Campaign

    repo = CampaignRepository(db_session)
    campaign = _sample_campaign()
    await repo.upsert(campaign.id, campaign.name, campaign.author,
                      campaign.description, campaign.to_dict())
    await db_session.commit()

    row = await repo.get_by_id("demo")
    assert row is not None
    restored = Campaign.from_dict(row.data)
    assert restored.id == "demo"
    assert restored.name == "Demo Quest"
    assert set(restored.encounters.keys()) == {"enc1", "enc2"}
    assert restored.chapters[0].title == "Chapter 1"
    assert restored.npcs["npc1"]["name"] == "Old Hermit"


async def test_campaign_repository_upsert_updates_existing(db_session):
    """Upserting an existing id updates it in place (no duplicate row)."""
    from app.database.repositories import CampaignRepository

    repo = CampaignRepository(db_session)
    campaign = _sample_campaign()
    await repo.upsert(campaign.id, campaign.name, campaign.author,
                      campaign.description, campaign.to_dict())
    campaign.name = "Renamed Quest"
    await repo.upsert(campaign.id, campaign.name, campaign.author,
                      campaign.description, campaign.to_dict())
    await db_session.commit()

    rows = await repo.get_all()
    assert len(rows) == 1
    assert rows[0].name == "Renamed Quest"


# ---------------------------------------------------------------------------
# Editor service — operates on the real Campaign model (no DB).
# ---------------------------------------------------------------------------

def test_add_encounter_inserts_into_encounters_and_chapter():
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    enc = svc.add_encounter(
        c, {"type": "combat", "name": "Bridge Battle"}, chapter_id="ch1", position=1,
    )
    assert enc.id in c.encounters
    assert c.encounters[enc.id].name == "Bridge Battle"
    # Inserted at position 1 of the chapter's ordered encounter ids.
    assert c.chapters[0].encounters[1] == enc.id
    assert c.chapters[0].encounters == ["enc1", enc.id, "enc2"]


def test_add_encounter_rejects_unknown_chapter_without_orphaning():
    """QA-F1: a bad chapter_id must not leave an encounter orphaned in the pool."""
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    before = set(c.encounters.keys())
    with pytest.raises(ValueError):
        svc.add_encounter(c, {"name": "Orphan"}, chapter_id="no-such-chapter")
    assert set(c.encounters.keys()) == before   # nothing added


def test_add_encounter_rejects_duplicate_id():
    """QA-F2: supplying an existing encounter id must not overwrite it."""
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    with pytest.raises(ValueError):
        svc.add_encounter(c, {"id": "enc1", "name": "Dup"}, chapter_id="ch1")
    assert c.encounters["enc1"].name == "Goblin Ambush"   # original intact


def test_reorder_rejects_non_permutation():
    """QA-F3: reorder must be an exact permutation — no dropped/unknown ids."""
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    with pytest.raises(ValueError):
        svc.reorder_encounters(c, "ch1", ["enc1"])               # missing enc2
    with pytest.raises(ValueError):
        svc.reorder_encounters(c, "ch1", ["enc1", "enc2", "x"])  # unknown id
    assert c.chapters[0].encounters == ["enc1", "enc2"]          # unchanged


def test_update_encounter_merges_fields():
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    updated = svc.update_encounter(c, "enc1", {"name": "Goblin Camp", "difficulty": "hard"})
    assert updated.name == "Goblin Camp"
    assert c.encounters["enc1"].difficulty.value == "hard"
    # Unspecified fields are preserved.
    assert c.encounters["enc1"].type.value == "combat"


def test_remove_encounter_purges_refs_and_starting():
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    assert svc.remove_encounter(c, "enc1") is True
    assert "enc1" not in c.encounters
    assert "enc1" not in c.chapters[0].encounters
    # starting_encounter pointed at enc1 -> reassigned to a remaining encounter.
    assert c.starting_encounter != "enc1"
    assert c.starting_encounter in c.encounters


def test_reorder_encounters_sets_chapter_order():
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    svc.reorder_encounters(c, "ch1", ["enc2", "enc1"])
    assert c.chapters[0].encounters == ["enc2", "enc1"]


def test_update_metadata_and_npc():
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    svc.update_metadata(c, name="Epic Demo", difficulty="deadly", starting_level=3)
    assert c.name == "Epic Demo"
    assert c.settings.difficulty.value == "deadly"
    assert c.starting_level == 3

    npc = svc.update_npc(c, "npc1", {"disposition": 90})
    assert npc["disposition"] == 90
    assert c.npcs["npc1"]["name"] == "Old Hermit"   # preserved


def test_duplicate_creates_new_id_same_content():
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    copy = svc.duplicate(c, new_name="Demo Quest (Copy)")
    assert copy.id != c.id
    assert copy.name == "Demo Quest (Copy)"
    assert set(copy.encounters.keys()) == set(c.encounters.keys())
    # Independent object: editing the copy doesn't touch the original.
    svc.update_metadata(copy, name="Changed")
    assert c.name == "Demo Quest"


def test_validate_reports_orphan_reference():
    from app.services.campaign_editor import CampaignEditorService

    svc = CampaignEditorService()
    c = _sample_campaign()
    c.chapters[0].encounters.append("ghost")   # references a missing encounter
    errors = svc.validate(c)
    assert any("ghost" in e for e in errors)


# ---------------------------------------------------------------------------
# Route handlers — DB-backed load -> edit -> persist (called directly, no
# TestClient, so we avoid app-lifespan/DB-file coupling).
# ---------------------------------------------------------------------------

async def test_route_edit_persists_metadata(db_session):
    from app.api.routes.campaign_editor import (
        update_campaign_metadata, UpdateCampaignMetadataRequest,
    )
    from app.database.repositories import CampaignRepository
    from app.models.campaign import Campaign

    repo = CampaignRepository(db_session)
    c = _sample_campaign()
    await repo.upsert(c.id, c.name, c.author, c.description, c.to_dict())
    await db_session.commit()

    resp = await update_campaign_metadata(
        "demo",
        UpdateCampaignMetadataRequest(name="Renamed", difficulty="hard"),
        repo=repo, user=None,
    )
    assert resp["success"]
    assert resp["campaign"]["campaign"]["name"] == "Renamed"

    row = await repo.get_by_id("demo")          # change is durable
    assert row.name == "Renamed"
    assert Campaign.from_dict(row.data).settings.difficulty.value == "hard"


async def test_route_unknown_campaign_404(db_session):
    from fastapi import HTTPException
    from app.api.routes.campaign_editor import get_editable_campaign
    from app.database.repositories import CampaignRepository

    repo = CampaignRepository(db_session)
    with pytest.raises(HTTPException) as exc:
        await get_editable_campaign("does-not-exist", repo=repo, user=None)
    assert exc.value.status_code == 404


async def test_route_bad_difficulty_returns_400_not_500(db_session):
    """QA-F4: invalid enum input must be a 400, not an uncaught 500."""
    from fastapi import HTTPException
    from app.api.routes.campaign_editor import (
        update_campaign_metadata, UpdateCampaignMetadataRequest,
    )
    from app.database.repositories import CampaignRepository

    repo = CampaignRepository(db_session)
    c = _sample_campaign()
    await repo.upsert(c.id, c.name, c.author, c.description, c.to_dict())
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await update_campaign_metadata(
            "demo", UpdateCampaignMetadataRequest(difficulty="bogus"), repo=repo, user=None,
        )
    assert exc.value.status_code == 400
