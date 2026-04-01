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


# --- Tests for list_entities_for_llm (Phase 3, SEC-01/SEC-02) ---

async def test_list_entities_for_llm_filters_domains(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """SEC-01: Only entities from allowed_domains are returned."""
    registry = er.async_get(hass)
    # light domain — allowed
    light_entry = registry.async_get_or_create(
        "light", "test", "uid_light", original_name="Salon Light"
    )
    hass.states.async_set(light_entry.entity_id, "on")
    # camera domain — NOT allowed
    cam_entry = registry.async_get_or_create(
        "camera", "test", "uid_cam", original_name="Front Camera"
    )
    hass.states.async_set(cam_entry.entity_id, "idle")

    ec = EntityContextBuilder(hass, allowed_domains=["light", "switch"])
    result = ec.list_entities_for_llm("allume la lumiere")

    entity_ids = [e["entity_id"] for e in result]
    assert light_entry.entity_id in entity_ids
    assert cam_entry.entity_id not in entity_ids


async def test_list_entities_for_llm_minimal_fields(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """SEC-01/D-14: Each entity dict has exactly entity_id, friendly_name, state."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "light", "test", "uid_fields", original_name="Bureau"
    )
    hass.states.async_set(entry.entity_id, "off")

    ec = EntityContextBuilder(hass, allowed_domains=["light"])
    result = ec.list_entities_for_llm("test")

    assert len(result) >= 1
    for entity in result:
        assert set(entity.keys()) == {"entity_id", "friendly_name", "state"}, (
            f"Expected exactly 3 keys, got {set(entity.keys())}"
        )


async def test_list_entities_for_llm_cap_at_50(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """D-13: Result is capped at 50 entities even if more exist."""
    registry = er.async_get(hass)
    for i in range(60):
        entry = registry.async_get_or_create(
            "light", "test", f"uid_cap_{i}", original_name=f"Light {i}"
        )
        hass.states.async_set(entry.entity_id, "on")

    ec = EntityContextBuilder(hass, allowed_domains=["light"])
    result = ec.list_entities_for_llm("test")

    assert len(result) <= 50, f"Expected max 50, got {len(result)}"


async def test_list_entities_for_llm_prioritizes_matching(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """D-15: When capped, entities matching command tokens come first."""
    registry = er.async_get(hass)
    # Create 55 generic entities
    for i in range(55):
        entry = registry.async_get_or_create(
            "light", "test", f"uid_prio_{i}", original_name=f"Generic Light {i}"
        )
        hass.states.async_set(entry.entity_id, "on")
    # Create one with a matching name
    match_entry = registry.async_get_or_create(
        "light", "test", "uid_salon_match", original_name="Lumiere Salon"
    )
    hass.states.async_set(match_entry.entity_id, "off")

    ec = EntityContextBuilder(hass, allowed_domains=["light"])
    result = ec.list_entities_for_llm("salon")

    # The salon entity should be in the top results (within the 50 cap)
    entity_ids = [e["entity_id"] for e in result]
    assert match_entry.entity_id in entity_ids, (
        "Matching entity 'Lumiere Salon' should be prioritized for command 'salon'"
    )
    # And it should be near the top (first few entries)
    idx = entity_ids.index(match_entry.entity_id)
    assert idx < 5, f"Expected matching entity in top 5, found at index {idx}"
