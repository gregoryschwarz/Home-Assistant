"""PatternDetector — SQL time-series frequency analysis for habit detection (HABIT-03).

Algorithm (D-03, D-04):
  - Query events table for the last 14 days
  - GROUP BY entity_id, domain, service, day_of_week, hour
  - HAVING COUNT(*) >= 3 (threshold)
  - Upsert detected patterns into the patterns table via AgentStorage

Per research pitfall 6: since only `hour` (int 0-23) is stored (not minutes),
the ±30min window is implemented as bucketing by hour — conservatively covers
events within ±30min of the same hour boundary.

No external dependencies — pure SQL GROUP BY approach (no pandas/scipy).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import AgentStorage

_LOGGER = logging.getLogger(__name__)

# Detection parameters (D-03)
PATTERN_WINDOW_DAYS = 14
PATTERN_MIN_COUNT = 3

_DETECT_SQL = """
    SELECT
        entity_id,
        domain,
        service,
        day_of_week,
        hour,
        COUNT(*) AS occurrences,
        MAX(timestamp) AS last_seen
    FROM events
    WHERE timestamp >= datetime('now', :window)
    GROUP BY entity_id, domain, service, day_of_week, hour
    HAVING COUNT(*) >= :min_count
    ORDER BY occurrences DESC
"""


class PatternDetector:
    """Detects recurring habits from the events table using SQL frequency analysis."""

    def __init__(self, storage: "AgentStorage") -> None:
        self._storage = storage

    async def async_detect_patterns(self) -> list[dict]:
        """Run pattern detection and upsert results into the patterns table.

        Returns:
            List of pattern dicts with keys:
              entity_id, domain, service, day_of_week, hour, occurrences, last_seen
        """
        assert self._storage._db is not None, "Storage not open"

        window = f"-{PATTERN_WINDOW_DAYS} days"

        async with self._storage._db.execute(
            _DETECT_SQL,
            {"window": window, "min_count": PATTERN_MIN_COUNT},
        ) as cursor:
            rows = await cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]

        patterns = [dict(zip(col_names, row)) for row in rows]

        if patterns:
            await self._storage.async_upsert_patterns(patterns)
            _LOGGER.info(
                "PatternDetector: %d pattern(s) detected and stored",
                len(patterns),
            )
        else:
            _LOGGER.debug("PatternDetector: no patterns above threshold (%d)", PATTERN_MIN_COUNT)

        return patterns

    async def async_get_patterns(self) -> list[dict]:
        """Return all stored patterns from the patterns table."""
        assert self._storage._db is not None, "Storage not open"
        async with self._storage._db.execute(
            "SELECT * FROM patterns ORDER BY occurrences DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
        return [dict(zip(col_names, row)) for row in rows]
