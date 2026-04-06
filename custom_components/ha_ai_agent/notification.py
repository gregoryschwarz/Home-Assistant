"""HabitNotifier — proactive HA persistent_notification for detected patterns (D-06 to D-09).

Design:
  - Anti-spam: 1 notification per pattern per 24h (D-06), tracked in-memory only (v1).
  - notification_id format: ha_ai_agent_habit_{entity_id}_{day_of_week}_{hour} (D-07).
  - Message format: D-08 (friendly_name, French day name, hour, occurrences).
  - Triggered after async_detect_patterns() in the conversation LLM path (D-09).
"""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Anti-spam: 1 notification per pattern per 24h (D-06)
_ANTI_SPAM_SECONDS = 86400  # 24 hours

_DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


class HabitNotifier:
    """Sends HA persistent notifications when new habit patterns are detected."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the notifier."""
        self._hass = hass
        self._last_notified: dict[str, float] = {}  # notification_id -> monotonic timestamp

    async def async_notify_new_patterns(self, patterns: list[dict]) -> None:
        """Send persistent_notification for each pattern not notified in the last 24h.

        Skips patterns whose notification_id was sent within the last 24h (D-06 anti-spam).
        Updates the in-memory tracking after sending.

        Args:
            patterns: List of pattern dicts (entity_id, day_of_week, hour, occurrences, ...).
        """
        now = time.monotonic()
        for p in patterns:
            nid = (
                f"ha_ai_agent_habit_"
                f"{p['entity_id']}_"
                f"{p['day_of_week']}_"
                f"{p['hour']}"
            )
            last = self._last_notified.get(nid, 0.0)
            if (now - last) < _ANTI_SPAM_SECONDS:
                _LOGGER.debug("Habit notification suppressed (anti-spam): %s", nid)
                continue

            # Resolve friendly_name from HA state registry; fall back to entity_id
            friendly_name: str = p["entity_id"]
            state = self._hass.states.get(p["entity_id"])
            if state is not None:
                friendly_name = state.attributes.get("friendly_name", p["entity_id"])

            day = _DAYS_FR[int(p["day_of_week"])]
            message = (
                f"Habitude detectee : tu allumes {friendly_name} "
                f"tous les {day} a {p['hour']}h "
                f"({p['occurrences']} fois en 14 jours).\n"
                f"Creer une automatisation ?"
            )

            await self._hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Nouvelle habitude detectee",
                    "message": message,
                    "notification_id": nid,
                },
            )
            self._last_notified[nid] = now
            _LOGGER.info("Habit notification sent: %s", nid)
