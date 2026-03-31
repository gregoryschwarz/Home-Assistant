"""HA Autonomous AI Agent — integration entry point."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS, DOMAIN
from .entity_context import EntityContextBuilder
from .intent_router import IntentRouter

PLATFORMS: list[str] = ["conversation"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA AI Agent from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    allowed_domains = entry.options.get(CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS)
    router = IntentRouter(hass, allowed_domains=allowed_domains)
    entity_context = EntityContextBuilder(hass, allowed_domains=allowed_domains)
    hass.data[DOMAIN][entry.entry_id] = {
        "entry": entry,
        "router": router,
        "entity_context": entity_context,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry — enables UI reload without HA restart (HA-03)."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
