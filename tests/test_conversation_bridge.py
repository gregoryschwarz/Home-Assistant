"""Tests for conversation bridge — IntentRouter wiring (NLU-01, NLU-04).

Wave 0: Tests 1-2 are RED until plan 02-01 implementation.
Tests 3-4 are skipped placeholders for plan 02-02 (entity control).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.conversation import (
    ConversationInput,
    intent as conversation_intent,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_ai_agent.const import DOMAIN


async def test_message_routed_via_intent_router(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """_async_handle_message must route to IntentRouter.async_route, not echo.

    RED until plan 02-01 wires conversation.py to IntentRouter.
    """
    import importlib
    import types

    # Create a mock intent_router module so the patch path resolves even before
    # plan 02-02 creates the real file. This is removed after the test.
    mock_router_instance = MagicMock()
    mock_router_instance.async_route = AsyncMock(return_value="OK")
    mock_router_class = MagicMock(return_value=mock_router_instance)

    mock_module = types.ModuleType("custom_components.ha_ai_agent.intent_router")
    mock_module.IntentRouter = mock_router_class

    import sys
    sys.modules.setdefault("custom_components.ha_ai_agent.intent_router", mock_module)

    # Also inject into the package namespace so attribute lookup works
    import custom_components.ha_ai_agent as pkg
    had_attr = hasattr(pkg, "intent_router")
    if not had_attr:
        pkg.intent_router = mock_module

    try:
        with patch(
            "custom_components.ha_ai_agent.intent_router.IntentRouter",
            mock_router_class,
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Get the conversation entity
            component = hass.data.get("entity_components", {}).get("conversation")
            assert component is not None, "conversation component not found in hass.data"
            entities = list(component.entities)
            ha_ai_entities = [e for e in entities if DOMAIN in getattr(e, "entity_id", "")]
            assert len(ha_ai_entities) == 1, f"Expected 1 HA AI entity, got {len(ha_ai_entities)}"

            agent = ha_ai_entities[0]

            # Build a ConversationInput (HA 2026.3.4 requires device_id + satellite_id)
            user_input = ConversationInput(
                text="turn on the lights",
                conversation_id=None,
                context=MagicMock(),
                agent_id=agent.entity_id,
                language="en",
                device_id=None,
                satellite_id=None,
            )

            # Build a minimal ChatLog mock so async_add_assistant_content_without_tools succeeds
            chat_log = MagicMock()
            chat_log.async_add_assistant_content_without_tools = MagicMock()

            result = await agent._async_handle_message(user_input, chat_log)

            # The response text must be the router's return value, not the echo stub
            speech = result.response.speech.get("plain", {}).get("speech", "")
            assert speech == "OK", (
                f"Expected 'OK' from IntentRouter mock, got {speech!r}. "
                "Echo stub is still in place — plan 02-01 not yet wired."
            )
    finally:
        # Clean up injected attributes to avoid test pollution
        if not had_attr and hasattr(pkg, "intent_router"):
            del pkg.intent_router


async def test_router_stored_in_hass_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """async_setup_entry must store IntentRouter instance in hass.data[DOMAIN][entry_id]['router'].

    RED until plan 02-01 updates __init__.py to instantiate IntentRouter.
    """
    try:
        from custom_components.ha_ai_agent.intent_router import IntentRouter
    except ImportError:
        pytest.skip("intent_router not yet implemented")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry_data = hass.data.get(DOMAIN, {}).get(mock_config_entry.entry_id, {})
    assert "router" in entry_data, (
        f"'router' key not found in hass.data[DOMAIN][entry_id]. "
        f"Keys present: {list(entry_data.keys())}"
    )
    router = entry_data["router"]
    assert isinstance(router, IntentRouter), (
        f"Expected IntentRouter instance, got {type(router)}"
    )


@pytest.mark.skip(reason="Requires IntentRouter entity control — plan 02-02")
async def test_confirmation_message_after_turn_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """After a turn_on command, response must confirm the action was taken.

    Placeholder for plan 02-02 (entity control via HA services).
    """
    pass


@pytest.mark.skip(reason="Requires IntentRouter entity resolution — plan 02-02")
async def test_entity_not_found_returns_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """When entity referenced in command is not found, response must indicate error.

    Placeholder for plan 02-02 (entity resolution and error handling).
    """
    pass
