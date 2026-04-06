"""Tests for PatternDetector — SQL frequency analysis and patterns table (HABIT-03).

Covers:
  - Pattern detected when COUNT(*) >= 3 in last 14 days (D-03)
  - No pattern when COUNT(*) < 3 (below threshold)
  - Pattern groups correctly on entity_id + service + day_of_week + hour (D-04)
  - async_detect_patterns() returns list of pattern dicts
  - Detected patterns are upserted into patterns table via storage
  - Events outside 14-day window don't count toward threshold
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class _FakeHass:
    def __init__(self, config_dir: str) -> None:
        self.config = MagicMock()
        self.config.config_dir = config_dir


@pytest.fixture
async def storage(tmp_path: Path):
    """AgentStorage with real SQLite db in tmp_path."""
    from custom_components.ha_ai_agent.storage import AgentStorage

    hass = _FakeHass(str(tmp_path))
    store = AgentStorage(hass)
    await store.async_open()
    yield store
    await store.async_close()


# ---------------------------------------------------------------------------
# Helper: insert events directly into DB
# ---------------------------------------------------------------------------


async def _insert_events(storage, entity_id: str, domain: str, service: str,
                          day_of_week: int, hour: int, count: int,
                          days_ago: int = 0) -> None:
    """Insert `count` events for the given entity/service/day/hour."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    await storage._db.executemany(
        "INSERT INTO events (entity_id, domain, service, timestamp, day_of_week, hour) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(entity_id, domain, service, ts, day_of_week, hour)] * count,
    )
    await storage._db.commit()


# ---------------------------------------------------------------------------
# Pattern detection tests
# ---------------------------------------------------------------------------


async def test_pattern_detected_at_threshold(storage) -> None:
    """3 occurrences in 14 days → pattern detected (D-03)."""
    from custom_components.ha_ai_agent.pattern_detector import PatternDetector

    await _insert_events(storage, "light.salon", "light", "turn_on", 0, 7, count=3)

    detector = PatternDetector(storage)
    patterns = await detector.async_detect_patterns()

    assert len(patterns) == 1
    p = patterns[0]
    assert p["entity_id"] == "light.salon"
    assert p["service"] == "turn_on"
    assert p["day_of_week"] == 0
    assert p["hour"] == 7
    assert p["occurrences"] >= 3


async def test_no_pattern_below_threshold(storage) -> None:
    """2 occurrences in 14 days → no pattern detected (D-03 threshold = 3)."""
    from custom_components.ha_ai_agent.pattern_detector import PatternDetector

    await _insert_events(storage, "light.salon", "light", "turn_on", 0, 7, count=2)

    detector = PatternDetector(storage)
    patterns = await detector.async_detect_patterns()

    assert patterns == [], f"Expected no patterns, got {patterns}"


async def test_pattern_groups_correctly(storage) -> None:
    """Different entity/service/day/hour combos yield separate patterns (D-04)."""
    from custom_components.ha_ai_agent.pattern_detector import PatternDetector

    # Group 1: light.salon, turn_on, Monday, 7h — 3 times
    await _insert_events(storage, "light.salon", "light", "turn_on", 0, 7, count=3)
    # Group 2: light.cuisine, turn_on, Monday, 7h — 3 times
    await _insert_events(storage, "light.cuisine", "light", "turn_on", 0, 7, count=3)
    # Group 3: light.salon, turn_off, Monday, 23h — only 2 times (below threshold)
    await _insert_events(storage, "light.salon", "light", "turn_off", 0, 23, count=2)

    detector = PatternDetector(storage)
    patterns = await detector.async_detect_patterns()

    entity_ids = {p["entity_id"] for p in patterns}
    assert "light.salon" in entity_ids
    assert "light.cuisine" in entity_ids
    assert len(patterns) == 2, f"Expected 2 patterns, got {len(patterns)}: {patterns}"


async def test_old_events_outside_window_excluded(storage) -> None:
    """Events older than 14 days must not count toward the threshold (D-03)."""
    from custom_components.ha_ai_agent.pattern_detector import PatternDetector

    # 3 events from 20 days ago → outside 14-day window
    await _insert_events(storage, "light.salon", "light", "turn_on", 0, 7, count=3, days_ago=20)
    # 1 event from today → inside window but below threshold alone
    await _insert_events(storage, "light.salon", "light", "turn_on", 0, 7, count=1, days_ago=0)

    detector = PatternDetector(storage)
    patterns = await detector.async_detect_patterns()

    assert patterns == [], f"Old events must not contribute to threshold: {patterns}"


async def test_patterns_upserted_to_table(storage) -> None:
    """async_detect_patterns() must upsert detected patterns into the patterns table."""
    from custom_components.ha_ai_agent.pattern_detector import PatternDetector

    await _insert_events(storage, "light.salon", "light", "turn_on", 0, 7, count=3)

    detector = PatternDetector(storage)
    await detector.async_detect_patterns()

    async with storage._db.execute("SELECT * FROM patterns") as cursor:
        rows = await cursor.fetchall()

    assert len(rows) >= 1
    col_names = [desc[0] for desc in cursor.description]
    row_dict = dict(zip(col_names, rows[0]))
    assert row_dict["entity_id"] == "light.salon"
    assert row_dict["occurrences"] >= 3


async def test_pattern_detect_returns_list(storage) -> None:
    """async_detect_patterns() must always return a list (empty if no patterns)."""
    from custom_components.ha_ai_agent.pattern_detector import PatternDetector

    detector = PatternDetector(storage)
    result = await detector.async_detect_patterns()

    assert isinstance(result, list)


async def test_multiple_events_same_slot(storage) -> None:
    """5 events in same slot → pattern with occurrences=5."""
    from custom_components.ha_ai_agent.pattern_detector import PatternDetector

    await _insert_events(storage, "switch.fan", "switch", "turn_on", 5, 8, count=5)

    detector = PatternDetector(storage)
    patterns = await detector.async_detect_patterns()

    assert len(patterns) == 1
    assert patterns[0]["occurrences"] == 5
    assert patterns[0]["entity_id"] == "switch.fan"
