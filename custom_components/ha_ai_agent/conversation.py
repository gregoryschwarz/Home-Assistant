"""Conversation platform stub — replaced by Plan 01-03."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Stub — Plan 01-03 will add the ConversationEntity here."""
    pass
