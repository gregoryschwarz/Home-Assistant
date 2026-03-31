"""Shared fixtures for Phase 1 tests."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_ai_agent.const import CONF_API_KEY, DOMAIN


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and add a mock config entry for ha_ai_agent."""
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
