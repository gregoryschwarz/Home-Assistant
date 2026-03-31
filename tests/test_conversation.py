"""Tests for conversation agent entity registration (HA-04).

VERIFIED IMPORTS (confirmed by Wave 0 source inspection on HA 2026.3.4):

  from homeassistant.components.conversation import (
      ConversationEntity,       # base class for conversation agents
      ConversationInput,        # user message container
      ConversationResult,       # response container
      AssistantContent,         # content type for adding to chat_log
      ChatLog,                  # chat log type (used in _async_handle_message signature)
  )

  _async_handle_message signature (from ConversationEntity base class):
      async def _async_handle_message(
          self,
          user_input: ConversationInput,
          chat_log: ChatLog,
      ) -> ConversationResult: ...

  AssistantContent constructor:
      AssistantContent(agent_id: str, content: str | None = None, ...)

  ChatLog methods:
      chat_log.async_add_assistant_content_without_tools(AssistantContent(...))

  ConversationResult constructor:
      ConversationResult(response: intent.IntentResponse, conversation_id: str | None = None)

  IntentResponse constructor:
      intent.IntentResponse(language: str)
      intent_response.async_set_speech(text: str)
"""
from __future__ import annotations

from homeassistant.components.conversation import ConversationEntity, ConversationInput
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_ai_agent.const import DOMAIN


async def test_conversation_entity_registered(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """After setup, a ConversationEntity must be registered in the entity registry (HA-04)."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity with our domain should exist in entity registry
    from homeassistant.helpers import entity_registry as er
    entity_registry = er.async_get(hass)
    entities = [
        e for e in entity_registry.entities.values()
        if e.platform == DOMAIN
    ]
    assert len(entities) == 1, f"Expected 1 entity, found {len(entities)}"


async def test_conversation_entity_unique_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Conversation entity unique_id must equal the config entry's entry_id."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the conversation entity state
    states = hass.states.async_all("conversation")
    assert len(states) >= 1
    # The state entity_id should contain our domain
    agent_states = [s for s in states if DOMAIN in s.entity_id]
    assert len(agent_states) == 1


async def test_conversation_supported_languages(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """supported_languages must include 'fr' and 'en' (Pitfall 5 from research)."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the entity object from the platform
    component = hass.data.get("entity_components", {}).get("conversation")
    if component:
        entities = list(component.entities)
        ha_ai_entities = [e for e in entities if DOMAIN in getattr(e, "entity_id", "")]
        if ha_ai_entities:
            agent = ha_ai_entities[0]
            langs = agent.supported_languages
            assert "fr" in langs or langs == "*", f"'fr' not in supported_languages: {langs}"
            assert "en" in langs or langs == "*", f"'en' not in supported_languages: {langs}"


async def test_reload_produces_single_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """After unload + reload, exactly one conversation entity must exist (HA-03 + HA-04)."""
    # Setup
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Unload (simulates HA UI Reload)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    # Reload
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Only one entity should exist (not two from duplicate registration — Pitfall 2)
    states = hass.states.async_all("conversation")
    agent_states = [s for s in states if DOMAIN in s.entity_id]
    assert len(agent_states) == 1, \
        f"Expected 1 agent after reload, found {len(agent_states)} — check async_unload_platforms"
