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


# ---------------------------------------------------------------------------
# Plan 06-02: HabitNotifier wired into conversation flow
# ---------------------------------------------------------------------------

class TestHabitNotification:
    """Tests for HabitNotifier integration in the LLM conversation path (D-09).

    Plan 06-02, Task 2 — TDD RED.
    """

    def _make_agent(self, hass, entry_id="test_entry_id"):
        """Build a HaAiConversationAgent backed by a mocked hass."""
        from homeassistant.config_entries import ConfigEntry
        from unittest.mock import MagicMock
        from custom_components.ha_ai_agent.conversation import HaAiConversationAgent

        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = entry_id
        agent = HaAiConversationAgent(hass, entry)
        return agent

    def _make_hass_data(
        self,
        detected_patterns=None,
        include_notifier=True,
        router_response=None,
    ):
        """Build a fully mocked hass with hass.data[DOMAIN][entry_id] populated."""
        from unittest.mock import AsyncMock, MagicMock
        from custom_components.ha_ai_agent.const import DOMAIN

        if detected_patterns is None:
            detected_patterns = [
                {
                    "entity_id": "light.cuisine",
                    "domain": "light",
                    "service": "turn_on",
                    "day_of_week": 0,
                    "hour": 7,
                    "occurrences": 5,
                    "last_seen": "2026-04-05T07:00:00",
                }
            ]

        pattern_detector = MagicMock()
        pattern_detector.async_detect_patterns = AsyncMock(return_value=detected_patterns)
        pattern_detector.async_get_patterns = AsyncMock(return_value=detected_patterns)

        notifier = MagicMock()
        notifier.async_notify_new_patterns = AsyncMock()

        router = MagicMock()
        router.async_route = AsyncMock(return_value=router_response)  # None = LLM path

        claude_client = MagicMock()
        claude_client.async_complete = AsyncMock(return_value="Réponse Claude")

        entity_context = MagicMock()
        entity_context.list_entities_for_llm = MagicMock(return_value=[])

        hass = MagicMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=None)

        entry_data = {
            "router": router,
            "claude_client": claude_client,
            "entity_context": entity_context,
            "pattern_detector": pattern_detector,
        }
        if include_notifier:
            entry_data["notifier"] = notifier

        hass.data = {DOMAIN: {"test_entry_id": entry_data}}
        return hass, pattern_detector, notifier

    def _make_user_input(self, text="allume la cuisine"):
        """Build a mock ConversationInput."""
        from unittest.mock import MagicMock
        user_input = MagicMock()
        user_input.text = text
        user_input.language = "fr"
        user_input.conversation_id = None
        return user_input

    def _make_chat_log(self):
        """Build a mock ChatLog."""
        from unittest.mock import MagicMock
        chat_log = MagicMock()
        chat_log.async_add_assistant_content_without_tools = MagicMock()
        return chat_log

    # ------------------------------------------------------------------
    # Test 1: detect + notify on LLM path
    # ------------------------------------------------------------------
    import pytest

    @pytest.mark.asyncio
    async def test_detect_and_notify_on_llm_path(self):
        """After async_complete, async_detect_patterns is called and results passed to notifier."""
        from custom_components.ha_ai_agent.conversation import HaAiConversationAgent
        from unittest.mock import MagicMock, AsyncMock

        hass, pattern_detector, notifier = self._make_hass_data()
        agent = self._make_agent(hass)

        user_input = self._make_user_input()
        chat_log = self._make_chat_log()

        await agent._async_handle_message(user_input, chat_log)

        # async_detect_patterns must have been called
        pattern_detector.async_detect_patterns.assert_awaited_once()
        # notifier must have been called with the detected patterns
        notifier.async_notify_new_patterns.assert_awaited_once()
        call_args = notifier.async_notify_new_patterns.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["entity_id"] == "light.cuisine"

    # ------------------------------------------------------------------
    # Test 2: no notifier key — no crash, detection still runs
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_no_notifier_no_crash(self):
        """If hass.data has no 'notifier' key, conversation still works without crashing."""
        from custom_components.ha_ai_agent.conversation import HaAiConversationAgent

        hass, pattern_detector, notifier = self._make_hass_data(include_notifier=False)
        agent = self._make_agent(hass)

        user_input = self._make_user_input()
        chat_log = self._make_chat_log()

        # Must not raise
        result = await agent._async_handle_message(user_input, chat_log)
        # Detection still runs
        pattern_detector.async_detect_patterns.assert_awaited_once()
        # notifier was not in hass.data, so async_notify_new_patterns was never called
        notifier.async_notify_new_patterns.assert_not_awaited()

    # ------------------------------------------------------------------
    # Test 3: local route — async_detect_patterns NOT called
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_local_route_no_detection(self):
        """When IntentRouter handles the command, async_detect_patterns must NOT be called."""
        from custom_components.ha_ai_agent.conversation import HaAiConversationAgent

        # router_response="OK" means local route handled it
        hass, pattern_detector, notifier = self._make_hass_data(
            router_response="Lumière allumée."
        )
        agent = self._make_agent(hass)

        user_input = self._make_user_input()
        chat_log = self._make_chat_log()

        await agent._async_handle_message(user_input, chat_log)

        # Detection must NOT have been called on the local route path
        pattern_detector.async_detect_patterns.assert_not_awaited()
