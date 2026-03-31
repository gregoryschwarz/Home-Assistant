"""Tests for setup/unload lifecycle (HA-01, HA-03)."""
from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_ai_agent.const import DOMAIN


async def test_setup_entry_returns_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """async_setup_entry must return True and transition entry to LOADED state (HA-01)."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_stores_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setup must store entry data in hass.data[DOMAIN][entry.entry_id]."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_unload_entry_returns_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """async_unload_entry must transition entry to NOT_LOADED state (HA-03)."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_entry_clears_domain_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """async_unload_entry must remove entry_id from hass.data[DOMAIN] (HA-03)."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})
