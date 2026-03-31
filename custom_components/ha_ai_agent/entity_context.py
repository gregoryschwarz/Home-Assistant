"""EntityContextBuilder stub — full implementation in plan 02-03."""
from __future__ import annotations

from homeassistant.core import HomeAssistant


class EntityContextBuilder:
    """Builds entity context for intent routing. Stub until plan 02-03."""

    def __init__(self, hass: HomeAssistant, allowed_domains: list[str]) -> None:
        self.hass = hass
        self.allowed_domains = allowed_domains
