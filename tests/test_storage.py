"""Tests for AgentStorage — SQLite persistence layer (Phase 5, Plan 01).

Tests cover:
- WAL mode activation on open
- Schema creation (meta + events tables)
- Index creation
- Event recording with D-07 fields
- TTL purge (90 days)
- FIFO cap (10 000 events)
- Idempotent close
- No network imports in storage.py (SEC-02)
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helper: instantiate AgentStorage without a hass object (inject db_path)
# ---------------------------------------------------------------------------

def make_storage(db_path: str):
    """Create an AgentStorage bypassing hass dependency by injecting _db_path."""
    from custom_components.ha_ai_agent.storage import AgentStorage

    storage = AgentStorage.__new__(AgentStorage)
    storage._db = None
    storage._db_path = db_path
    return storage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def storage(tmp_path: Path):
    """Open a fresh AgentStorage backed by a temporary file, yield, then close."""
    s = make_storage(str(tmp_path / "habits.db"))
    await s.async_open()
    yield s
    await s.async_close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_open_creates_db_with_wal(tmp_path: Path) -> None:
    """async_open creates the DB file and activates WAL journal mode."""
    db_path = str(tmp_path / "habits.db")
    s = make_storage(db_path)
    await s.async_open()
    try:
        assert os.path.exists(db_path), "DB file should exist after async_open"
        async with s._db.execute("PRAGMA journal_mode") as cursor:
            row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "wal", f"Expected 'wal', got {row[0]!r}"
    finally:
        await s.async_close()


@pytest.mark.asyncio
async def test_schema_has_meta_table(storage) -> None:
    """_ensure_schema inserts schema_version=1 into the meta table."""
    async with storage._db.execute(
        "SELECT value FROM meta WHERE key='schema_version'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None, "meta table row schema_version should exist"
    assert row[0] == "1", f"Expected schema_version '1', got {row[0]!r}"


@pytest.mark.asyncio
async def test_schema_has_events_table_columns(storage) -> None:
    """_ensure_schema creates the events table with all D-07 columns."""
    required_columns = {
        "id", "entity_id", "domain", "service",
        "timestamp", "day_of_week", "hour",
        "persons_home", "weather_condition",
    }
    async with storage._db.execute("PRAGMA table_info(events)") as cursor:
        rows = await cursor.fetchall()
    column_names = {row[1] for row in rows}
    missing = required_columns - column_names
    assert not missing, f"Missing columns in events table: {missing}"


@pytest.mark.asyncio
async def test_schema_has_index(storage) -> None:
    """_ensure_schema creates idx_events_entity_ts on events(entity_id, timestamp)."""
    async with storage._db.execute("PRAGMA index_list(events)") as cursor:
        rows = await cursor.fetchall()
    index_names = {row[1] for row in rows}
    assert "idx_events_entity_ts" in index_names, (
        f"Expected idx_events_entity_ts, found: {index_names}"
    )


@pytest.mark.asyncio
async def test_record_event(storage) -> None:
    """async_record_event inserts a row with all D-07 fields correctly populated."""
    await storage.async_record_event(
        entity_id="light.salon",
        domain="light",
        service="turn_on",
        persons_home=["greg", "pam"],
        weather_condition="sunny",
    )
    async with storage._db.execute(
        "SELECT entity_id, domain, service, day_of_week, hour, persons_home, weather_condition "
        "FROM events"
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None, "Expected one event row after record_event"
    entity_id, domain, service, day_of_week, hour, persons_home, weather_condition = row
    assert entity_id == "light.salon"
    assert domain == "light"
    assert service == "turn_on"
    assert isinstance(day_of_week, int) and 0 <= day_of_week <= 6
    assert isinstance(hour, int) and 0 <= hour <= 23
    import json
    assert json.loads(persons_home) == ["greg", "pam"]
    assert weather_condition == "sunny"


@pytest.mark.asyncio
async def test_purge_old_events(storage) -> None:
    """async_purge_old_events removes events older than HABIT_TTL_DAYS (90 days)."""
    old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

    # Insert old event manually
    await storage._db.execute(
        "INSERT INTO events (entity_id, domain, service, timestamp, day_of_week, hour, persons_home, weather_condition) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("light.old", "light", "turn_on", old_ts, 0, 7, "[]", None),
    )
    # Insert recent event
    await storage._db.execute(
        "INSERT INTO events (entity_id, domain, service, timestamp, day_of_week, hour, persons_home, weather_condition) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("light.recent", "light", "turn_on", recent_ts, 0, 7, "[]", None),
    )
    await storage._db.commit()

    await storage.async_purge_old_events()

    async with storage._db.execute("SELECT entity_id FROM events ORDER BY id") as cursor:
        rows = await cursor.fetchall()

    entity_ids = [r[0] for r in rows]
    assert "light.old" not in entity_ids, "Old event (100 days ago) should have been purged"
    assert "light.recent" in entity_ids, "Recent event (10 days ago) should remain"


@pytest.mark.asyncio
async def test_enforce_cap(storage) -> None:
    """async_enforce_cap keeps only the 10000 newest events when exceeded."""
    from custom_components.ha_ai_agent.const import HABIT_CAP

    # Insert HABIT_CAP + 5 events
    total = HABIT_CAP + 5
    ts = datetime.now(timezone.utc).isoformat()
    rows = [
        (f"light.e{i}", "light", "turn_on", ts, 0, 7, "[]", None)
        for i in range(total)
    ]
    await storage._db.executemany(
        "INSERT INTO events (entity_id, domain, service, timestamp, day_of_week, hour, persons_home, weather_condition) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    await storage._db.commit()

    await storage.async_enforce_cap()

    async with storage._db.execute("SELECT COUNT(*) FROM events") as cursor:
        count_row = await cursor.fetchone()
    count = count_row[0]
    assert count == HABIT_CAP, (
        f"Expected exactly {HABIT_CAP} events after cap, got {count}"
    )

    # Verify the oldest 5 were removed (entity_id light.e0..light.e4 gone)
    async with storage._db.execute(
        "SELECT entity_id FROM events ORDER BY id ASC LIMIT 1"
    ) as cursor:
        first_row = await cursor.fetchone()
    # The first remaining should be light.e5
    assert first_row[0] == "light.e5", (
        f"Oldest remaining should be light.e5, got {first_row[0]!r}"
    )


@pytest.mark.asyncio
async def test_close_idempotent(tmp_path: Path) -> None:
    """async_close can be called twice without raising an exception."""
    s = make_storage(str(tmp_path / "habits_close.db"))
    await s.async_open()
    await s.async_close()
    # Second close — must not raise
    await s.async_close()
    assert s._db is None


def test_no_network_imports() -> None:
    """storage.py must not import httpx, requests, aiohttp, or urllib (SEC-02)."""
    import pathlib
    storage_path = (
        pathlib.Path(__file__).parent.parent
        / "custom_components" / "ha_ai_agent" / "storage.py"
    )
    source = storage_path.read_text(encoding="utf-8")
    forbidden = ["import httpx", "import requests", "import aiohttp", "from urllib"]
    for pattern in forbidden:
        assert pattern not in source, (
            f"SEC-02 violation: found '{pattern}' in storage.py"
        )
