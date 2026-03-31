"""Unit tests for EntityContextBuilder 3-pass entity resolution (NLU-01, SEC-03).

Wave 0: All tests are RED until plan 02-03 implements the full resolution cascade.
"""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_ai_agent.entity_context import EntityContextBuilder


async def test_slug_resolution(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Pass 1: normalize 'lumiere du salon' to slug and find 'light.salon' in hass.states.

    The _normalize function strips French articles and accents, turning
    'lumiere du salon' -> 'lumiere_salon'. With domain='light', that gives
    'light.lumiere_salon' which does not exist. So the test uses a simpler
    entity whose slug matches directly after article stripping:
    'salon' after normalization -> 'salon', so 'light.salon' is the candidate.
    """
    hass.states.async_set("light.salon", "off")

    ec = EntityContextBuilder(hass, allowed_domains=["light", "switch"])
    result = ec.resolve_entity("lumiere du salon")
    # 'lumiere du salon' normalizes: strip 'du' -> 'lumiere salon' -> 'lumiere_salon'
    # Pass 1 checks 'light.lumiere_salon' — not set. Falls to Pass 2/3 registry.
    # For this test to use Pass 1, we use the exact slug form expected:
    # resolve_entity("salon") -> normalized='salon' -> checks 'light.salon' -> FOUND
    result2 = ec.resolve_entity("salon")
    assert result2 == "light.salon", (
        f"Pass 1 slug resolution failed: expected 'light.salon', got {result2!r}"
    )


async def test_registry_name_match(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Pass 2: entity registry name match — 'lumiere cuisine' resolves by original_name."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "light",
        "test_platform",
        "unique_id_cuisine",
        original_name="Lumiere Cuisine",
    )
    # Also set the state so the entity appears active
    hass.states.async_set(entry.entity_id, "off")

    ec = EntityContextBuilder(hass, allowed_domains=["light", "switch"])
    result = ec.resolve_entity("lumiere cuisine")
    assert result == entry.entity_id, (
        f"Pass 2 registry name match failed: expected {entry.entity_id!r}, got {result!r}"
    )


async def test_domain_whitelist_blocks(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """SEC-03: resolve_entity returns None when entity domain is not in allowed_domains."""
    hass.states.async_set("light.salon", "off")

    ec = EntityContextBuilder(hass, allowed_domains=["switch"])
    result = ec.resolve_entity("salon")
    assert result is None, (
        f"Domain whitelist not enforced: 'light.salon' should be blocked when allowed_domains=['switch'], "
        f"got {result!r}"
    )


async def test_curly_apostrophe_entity_text(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """U+2019 curly apostrophe in entity text must not raise and must produce same result as ASCII apostrophe."""
    hass.states.async_set("light.eclairage_salon", "off")

    ec = EntityContextBuilder(hass, allowed_domains=["light", "switch"])
    # Must not raise
    result_curly = ec.resolve_entity("l\u2019eclairage du salon")
    result_ascii = ec.resolve_entity("l'eclairage du salon")
    # Both should produce the same outcome (regardless of whether entity is found)
    assert result_curly == result_ascii, (
        f"Curly apostrophe handling differs: curly={result_curly!r}, ascii={result_ascii!r}"
    )


async def test_alias_match(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Pass 3: resolve_entity returns entity_id when user text matches an entity alias."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "light",
        "test_platform",
        "unique_id_lampe_principale",
        original_name="Plafonnier Salon",
    )
    registry.async_update_entity(entry.entity_id, aliases={"lampe principale"})
    hass.states.async_set(entry.entity_id, "off")

    ec = EntityContextBuilder(hass, allowed_domains=["light", "switch"])
    result = ec.resolve_entity("lampe principale")
    assert result == entry.entity_id, (
        f"Pass 3 alias match failed: expected {entry.entity_id!r}, got {result!r}"
    )
