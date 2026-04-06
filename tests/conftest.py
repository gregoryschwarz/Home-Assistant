"""Shared fixtures for Phase 1–5 tests."""
from __future__ import annotations

import asyncio
import pathlib
import sys

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_ai_agent.const import CONF_API_KEY, DOMAIN
from custom_components.ha_ai_agent.storage import AgentStorage

# Windows: use SelectorEventLoop so pytest-socket does not block internal socket pairs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Project root — parent of the tests/ directory
PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent)


@pytest.fixture
def hass_config_dir() -> str:
    """Override config dir so HA can discover custom_components/ha_ai_agent."""
    return PROJECT_ROOT


@pytest.fixture
async def hass_with_homeassistant(hass: HomeAssistant, enable_custom_integrations) -> HomeAssistant:
    """Provide a hass instance with homeassistant core component loaded.

    Required for config flow tests: the conversation dependency needs
    exposed_entities from the homeassistant core component.
    """
    await async_setup_component(hass, "homeassistant", {})
    return hass


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant, enable_custom_integrations) -> MockConfigEntry:
    """Create and add a mock config entry for ha_ai_agent.

    Sets up the homeassistant core component first so that the conversation
    integration can find its exposed_entities data (required by HA 2026.x).
    """
    # conversation depends on homeassistant core component being set up
    await async_setup_component(hass, "homeassistant", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "sk-ant-test-key-for-testing"},
        entry_id="test_entry_id",
        title="HA AI Agent",
        version=1,
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def tmp_storage(tmp_path):
    """Create an AgentStorage backed by a tmp_path database for Phase 5 tests."""
    storage = AgentStorage.__new__(AgentStorage)
    storage._db = None
    storage._db_path = str(tmp_path / "test_habits.db")
    await storage.async_open()
    yield storage
    await storage.async_close()
