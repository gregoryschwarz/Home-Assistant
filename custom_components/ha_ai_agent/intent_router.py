"""IntentRouter stub — full implementation in plan 02-02."""
from __future__ import annotations

from homeassistant.core import HomeAssistant


class IntentRouter:
    """Routes natural language text to HA intents. Stub until plan 02-02."""

    def __init__(self, hass: HomeAssistant, allowed_domains: list[str]) -> None:
        self.hass = hass
        self.allowed_domains = allowed_domains

    async def async_route(self, text: str, language: str) -> str:
        """Route text to an intent. Returns response text. Stub implementation."""
        return f"[stub] {text}"
