"""Tests for config flow (HA-02)."""
from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_ai_agent.const import CONF_API_KEY, DOMAIN

TEST_API_KEY = "sk-ant-test-key-12345-valid"


async def test_flow_user_step_shows_form(
    hass_with_homeassistant: HomeAssistant,
) -> None:
    """Initiating user step with no input must show the API key form."""
    result = await hass_with_homeassistant.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result.get("errors")


async def test_flow_user_step_success(
    hass_with_homeassistant: HomeAssistant,
) -> None:
    """Submitting a valid API key must create a config entry with the key in entry.data."""
    hass = hass_with_homeassistant
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: TEST_API_KEY},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HA AI Agent"
    assert result["data"][CONF_API_KEY] == TEST_API_KEY


async def test_flow_already_configured(
    hass_with_homeassistant: HomeAssistant,
) -> None:
    """A second setup attempt must abort with 'already_configured'."""
    hass = hass_with_homeassistant
    # Create an existing entry with the same unique_id
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "existing-key"},
        unique_id=DOMAIN,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: TEST_API_KEY},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_stores_key_in_data_not_options(
    hass_with_homeassistant: HomeAssistant,
) -> None:
    """API key MUST be stored in entry.data, not entry.options (security convention)."""
    hass = hass_with_homeassistant
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: TEST_API_KEY},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Key must be in data
    assert CONF_API_KEY in result["data"]
    # Key must NOT be in options (options is for user-tunable runtime settings, not credentials)
    assert CONF_API_KEY not in result.get("options", {})
