"""AgentStorage — crash-safe SQLite persistence layer for habit events.

Uses aiosqlite with WAL mode for crash safety, schema versioning via meta table,
TTL purge (HABIT_TTL_DAYS days), and FIFO cap (HABIT_EVENT_CAP events).

No network imports. All data stays local (SEC-02).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import aiosqlite

from homeassistant.core import HomeAssistant

from .const import DB_FILENAME, HABIT_EVENT_CAP, HABIT_TTL_DAYS

_LOGGER = logging.getLogger(__name__)


class AgentStorage:
    """Async SQLite storage for HA habit events.

    Lifecycle:
        await storage.async_open()   # Connect, activate WAL, ensure schema
        await storage.async_record_event(...)
        await storage.async_purge_old_events()
        await storage.async_enforce_cap()
        await storage.async_close()   # Idempotent
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._db: aiosqlite.Connection | None = None
        self._db_path = os.path.join(hass.config.config_dir, DB_FILENAME)

    async def async_open(self) -> None:
        """Open the SQLite connection, enable WAL mode, and ensure schema."""
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.commit()
        await self._ensure_schema()
        _LOGGER.debug("AgentStorage opened at %s (WAL mode)", self._db_path)

    async def async_close(self) -> None:
        """Close the database connection. Safe to call multiple times."""
        if self._db is not None:
            await self._db.close()
            self._db = None
            _LOGGER.debug("AgentStorage closed")

    async def _ensure_schema(self) -> None:
        """Create tables and index if they don't exist. Insert schema_version=1."""
        assert self._db is not None

        # meta table for schema versioning
        await self._db.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        await self._db.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1')"
        )

        # events table with D-07 fields
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id        TEXT    NOT NULL,
                domain           TEXT    NOT NULL,
                service          TEXT    NOT NULL,
                timestamp        TEXT    NOT NULL,
                day_of_week      INTEGER NOT NULL,
                hour             INTEGER NOT NULL,
                persons_home     TEXT,
                weather_condition TEXT
            )
            """
        )

        # Index for efficient queries by entity + time
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_entity_ts "
            "ON events (entity_id, timestamp)"
        )
        await self._db.commit()

    async def async_record_event(
        self,
        entity_id: str,
        domain: str,
        service: str,
        persons_home: list[str] | None,
        weather_condition: str | None,
    ) -> None:
        """Insert a habit event record with D-07 fields and enforce the FIFO cap."""
        assert self._db is not None
        now = datetime.now(timezone.utc)
        await self._db.execute(
            """
            INSERT INTO events
                (entity_id, domain, service, timestamp, day_of_week, hour,
                 persons_home, weather_condition)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                domain,
                service,
                now.isoformat(),
                now.weekday(),       # 0 = Monday (D-07)
                now.hour,
                json.dumps(persons_home) if persons_home is not None else "[]",
                weather_condition,
            ),
        )
        await self._db.commit()
        await self.async_enforce_cap()

    async def async_purge_old_events(self) -> None:
        """Delete events older than HABIT_TTL_DAYS days (D-08)."""
        assert self._db is not None
        await self._db.execute(
            f"DELETE FROM events WHERE timestamp < datetime('now', '-{HABIT_TTL_DAYS} days')"
        )
        await self._db.commit()
        _LOGGER.debug("AgentStorage: TTL purge complete (TTL=%d days)", HABIT_TTL_DAYS)

    async def async_enforce_cap(self) -> None:
        """Remove the oldest events so the total count does not exceed HABIT_EVENT_CAP (D-09)."""
        assert self._db is not None
        await self._db.execute(
            f"""
            DELETE FROM events
            WHERE id IN (
                SELECT id FROM events
                ORDER BY id ASC
                LIMIT MAX(0, (SELECT COUNT(*) FROM events) - {HABIT_EVENT_CAP})
            )
            """
        )
        await self._db.commit()
