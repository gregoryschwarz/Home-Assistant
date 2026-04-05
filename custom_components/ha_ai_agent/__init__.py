"""HA Autonomous AI Agent — integration entry point."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .claude_client import ClaudeClient
from .const import CONF_ALLOWED_DOMAINS, CONF_API_KEY, DEFAULT_ALLOWED_DOMAINS, DOMAIN
from .entity_context import EntityContextBuilder
from .habit_engine import HabitEngine
from .intent_router import IntentRouter
from .notification import HabitNotifier
from .pattern_detector import PatternDetector
from .storage import AgentStorage

PLATFORMS: list[str] = ["conversation"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA AI Agent from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    allowed_domains = entry.options.get(CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS)
    router = IntentRouter(hass, allowed_domains=allowed_domains)
    entity_context = EntityContextBuilder(hass, allowed_domains=allowed_domains)
    claude_client = ClaudeClient(
        hass=hass,
        api_key=entry.data[CONF_API_KEY],
        allowed_domains=allowed_domains,
    )

    # Habit engine — Phase 5 (HABIT-01, HABIT-02, HABIT-03, SEC-02)
    storage = AgentStorage(hass)
    await storage.async_open()
    await storage.async_purge_old_events()  # TTL purge at startup (D-08)

    habit_engine = HabitEngine(hass, storage, allowed_domains=allowed_domains)
    await habit_engine.async_start()

    pattern_detector = PatternDetector(storage)
    notifier = HabitNotifier(hass)

    hass.data[DOMAIN][entry.entry_id] = {
        "entry": entry,
        "router": router,
        "entity_context": entity_context,
        "claude_client": claude_client,
        "storage": storage,
        "habit_engine": habit_engine,
        "pattern_detector": pattern_detector,
        "notifier": notifier,
    }

    # Teardown — close storage and stop habit engine on unload (HA-03)
    entry.async_on_unload(habit_engine.async_stop)
    entry.async_on_unload(storage.async_close)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry — enables UI reload without HA restart (HA-03)."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
        claude_client = entry_data.get("claude_client")
        if claude_client is not None:
            await claude_client.async_close()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
