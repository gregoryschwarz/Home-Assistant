"""HabitEngine — observes HA state changes and records habit events.

Subscribes to the state_changed event bus, filters for human-initiated actions
(D-01: context.user_id not None) on allowed domains (D-02), gathers presence
and weather context (D-05, D-06), infers the service from state transitions,
and writes event records to AgentStorage.

Daily TTL purge is scheduled via async_track_time_interval (HA lifecycle-safe).

No network imports — all data stays local (SEC-02).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

if TYPE_CHECKING:
    from .storage import AgentStorage

_LOGGER = logging.getLogger(__name__)


class HabitEngine:
    """Listens for state_changed events and persists habit records to AgentStorage.

    Lifecycle:
        await engine.async_start()   # Subscribe and run initial purge
        # ... engine observes state changes ...
        await engine.async_stop()    # Unsubscribe and cancel daily purge
    """

    def __init__(
        self,
        hass: HomeAssistant,
        storage: "AgentStorage",
        allowed_domains: list[str],
    ) -> None:
        self.hass = hass
        self._storage = storage
        self._allowed_domains = allowed_domains
        self._unsub_state: object | None = None
        self._cancel_purge: object | None = None

    async def async_start(self) -> None:
        """Subscribe to state_changed, run initial TTL purge, schedule daily purge."""
        # Run initial purge on startup (D-08)
        await self._storage.async_purge_old_events()

        # Subscribe to state_changed event bus
        self._unsub_state = self.hass.bus.async_listen(
            "state_changed", self._handle_state_changed
        )

        # Schedule daily TTL purge via HA helpers (cancel_callback registered separately)
        self._cancel_purge = async_track_time_interval(
            self.hass,
            self._async_daily_purge,
            timedelta(hours=24),
        )
        _LOGGER.debug("HabitEngine started — subscribed to state_changed events")

    async def async_stop(self) -> None:
        """Unsubscribe from state_changed and cancel daily purge timer."""
        if self._unsub_state is not None:
            self._unsub_state()  # synchronous cancel callback
            self._unsub_state = None

        if self._cancel_purge is not None:
            self._cancel_purge()  # synchronous cancel callback
            self._cancel_purge = None

        _LOGGER.debug("HabitEngine stopped")

    async def _handle_state_changed(self, event: Event) -> None:
        """Process a state_changed event and record if human-initiated on allowed domain."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        old_state = event.data.get("old_state")
        if old_state is None:
            # Entity creation (no prior state) — not a user transition
            return

        # D-01: ignore automation-triggered events (user_id is None)
        if new_state.context.user_id is None:
            return

        entity_id: str = new_state.entity_id
        domain = entity_id.split(".")[0]

        # D-02: only track allowed domains
        if domain not in self._allowed_domains:
            return

        service = self._infer_service(domain, old_state, new_state)
        persons_home = self._get_persons_home()
        weather_condition = self._get_weather_condition()

        await self._storage.async_record_event(
            entity_id,
            domain,
            service,
            persons_home,
            weather_condition,
        )

    def _infer_service(self, domain: str, old_state: object, new_state: object) -> str:
        """Infer the HA service from old_state → new_state transition.

        Returns one of: turn_on, turn_off, media_play, media_pause,
        set_temperature, state_change (fallback).
        """
        old_val = old_state.state
        new_val = new_state.state

        if domain in ("light", "switch"):
            if old_val == "off" and new_val == "on":
                return "turn_on"
            if old_val == "on" and new_val == "off":
                return "turn_off"

        elif domain == "media_player":
            if old_val in ("paused", "idle", "off") and new_val == "playing":
                return "media_play"
            if new_val in ("paused", "idle"):
                return "media_pause"
            if old_val == "off" and new_val == "on":
                return "turn_on"
            if old_val == "on" and new_val == "off":
                return "turn_off"

        elif domain == "climate":
            old_temp = old_state.attributes.get("temperature")
            new_temp = new_state.attributes.get("temperature")
            if old_temp != new_temp:
                return "set_temperature"
            if old_val == "off" and new_val != "off":
                return "turn_on"
            if old_val != "off" and new_val == "off":
                return "turn_off"

        return "state_change"

    def _get_persons_home(self) -> list[str] | None:
        """Return lowercase friendly_names of persons currently home (D-05).

        Returns None if no person.* entities exist in HA.
        """
        person_states = self.hass.states.async_all("person")
        if not person_states:
            return None
        home = [
            s.attributes.get("friendly_name", s.entity_id).lower()
            for s in person_states
            if s.state == "home"
        ]
        return home

    def _get_weather_condition(self) -> str | None:
        """Return the state of the first weather.* entity found (D-06).

        Returns None if no weather.* entities exist in HA.
        """
        weather_states = self.hass.states.async_all("weather")
        if not weather_states:
            return None
        return weather_states[0].state

    async def _async_daily_purge(self, _now: object = None) -> None:
        """Daily callback: run TTL purge on the events table (D-08)."""
        _LOGGER.debug("HabitEngine: running scheduled daily TTL purge")
        await self._storage.async_purge_old_events()
