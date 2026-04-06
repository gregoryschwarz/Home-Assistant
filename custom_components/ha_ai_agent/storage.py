"""AgentStorage — crash-safe local SQLite storage for habit events (HABIT-01, SEC-02).

Uses aiosqlite for non-blocking async SQLite access.
WAL mode + NORMAL synchronous for crash resistance (D-10).
Schema versioning via meta table.
TTL purge: events older than HABIT_TTL_DAYS are deleted (D-08).
FIFO cap: oldest events deleted when count > HABIT_CAP (D-09).
No network calls — all data stays local (SEC-02).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import aiosqlite

from .const import DB_FILENAME, HABIT_CAP, HABIT_SCHEMA_VERSION, HABIT_TTL_DAYS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class AgentStorage:
    """Async SQLite storage layer for HA AI Agent habit data."""

    def __init__(self, hass: "HomeAssistant") -> None:
        self.hass = hass
        self._db: aiosqlite.Connection | None = None
        self._db_path: str = os.path.join(hass.config.config_dir, DB_FILENAME)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_open(self) -> None:
        """Open the SQLite connection, enable WAL mode, and ensure schema."""
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.commit()
        await self._ensure_schema()
        _LOGGER.debug("AgentStorage opened at %s", self._db_path)

    async def async_close(self) -> None:
        """Close the SQLite connection cleanly."""
        if self._db is not None:
            await self._db.close()
            self._db = None
            _LOGGER.debug("AgentStorage closed")

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def _ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist; set schema_version."""
        assert self._db is not None

        # meta table for schema versioning (D-10)
        await self._db.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        await self._db.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(HABIT_SCHEMA_VERSION),),
        )

        # events table (D-07)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                service TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                day_of_week INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                persons_home TEXT,
                weather_condition TEXT
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_entity_ts "
            "ON events (entity_id, timestamp)"
        )

        # patterns table (HABIT-03)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                service TEXT NOT NULL,
                day_of_week INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                occurrences INTEGER NOT NULL,
                last_seen TEXT NOT NULL,
                UNIQUE(entity_id, service, day_of_week, hour)
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_patterns_entity "
            "ON patterns (entity_id)"
        )

        await self._db.commit()

    # ------------------------------------------------------------------
    # Event recording
    # ------------------------------------------------------------------

    async def async_record_event(
        self,
        entity_id: str,
        domain: str,
        service: str,
        persons_home: list[str] | None,
        weather_condition: str | None,
    ) -> None:
        """Insert one habit event row with all D-07 fields."""
        assert self._db is not None

        now = datetime.now(timezone.utc)
        persons_json = json.dumps(persons_home) if persons_home is not None else None

        await self._db.execute(
            """INSERT INTO events
               (entity_id, domain, service, timestamp, day_of_week, hour, persons_home, weather_condition)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                domain,
                service,
                now.isoformat(),
                now.weekday(),   # 0=Monday per D-07
                now.hour,
                persons_json,
                weather_condition,
            ),
        )
        await self._db.commit()
        await self.async_enforce_cap()

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def async_purge_old_events(self) -> None:
        """Delete events older than HABIT_TTL_DAYS (D-08)."""
        assert self._db is not None

        await self._db.execute(
            "DELETE FROM events WHERE timestamp < datetime('now', ?)",
            (f"-{HABIT_TTL_DAYS} days",),
        )
        await self._db.commit()
        _LOGGER.debug("TTL purge completed (retention: %d days)", HABIT_TTL_DAYS)

    async def async_enforce_cap(self) -> None:
        """Delete oldest events when total count exceeds HABIT_CAP (D-09 FIFO)."""
        assert self._db is not None

        await self._db.execute(
            """DELETE FROM events WHERE id IN (
                SELECT id FROM events ORDER BY id ASC
                LIMIT MAX(0, (SELECT COUNT(*) FROM events) - ?)
            )""",
            (HABIT_CAP,),
        )
        await self._db.commit()
        _LOGGER.debug("Cap enforcement completed (max: %d events)", HABIT_CAP)

    # ------------------------------------------------------------------
    # Pattern storage
    # ------------------------------------------------------------------

    async def async_upsert_patterns(self, patterns: list[dict]) -> None:
        """Upsert detected patterns into the patterns table."""
        assert self._db is not None

        for p in patterns:
            await self._db.execute(
                """INSERT INTO patterns
                   (entity_id, domain, service, day_of_week, hour, occurrences, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(entity_id, service, day_of_week, hour)
                   DO UPDATE SET occurrences=excluded.occurrences, last_seen=excluded.last_seen""",
                (
                    p["entity_id"],
                    p["domain"],
                    p["service"],
                    p["day_of_week"],
                    p["hour"],
                    p["occurrences"],
                    p["last_seen"],
                ),
            )
        await self._db.commit()
