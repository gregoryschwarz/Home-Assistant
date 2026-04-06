"""Tests for voice pipeline compatibility (VOICE-01, VOICE-02).

Proves that HaAiConversationAgent:
  - Is discoverable by assist_pipeline via entity_id "conversation.ha_ai_agent" (VOICE-01)
  - Produces TTS-compatible output via IntentResponse.speech (VOICE-02)

VOICE-01: assist_pipeline discovers agents by entity_id with "conversation." prefix.
VOICE-02: Pipeline's TTS stage reads result.response.speech["plain"]["speech"].
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.conversation import (
    ChatLog,
    ConversationInput,
    async_get_agent_info,
    intent as conversation_intent,
)
from homeassistant.core import Context, HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_ai_agent.const import DOMAIN


async def test_agent_discoverable_by_pipeline(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """async_get_agent_info must return non-None AgentInfo with correct id (VOICE-01).

    assist_pipeline selects an agent by entity_id. If async_get_agent_info returns None,
    the pipeline cannot route to our agent and voice commands will fall through to the
    built-in Assist agent.
    """
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    agent_info = async_get_agent_info(hass, "conversation.ha_ai_agent")

    assert agent_info is not None, (
        "async_get_agent_info returned None for 'conversation.ha_ai_agent'. "
        "The agent entity may not be registered or entity_id may differ. "
        "Check _attr_name and unique_id in HaAiConversationAgent."
    )
    assert agent_info.id == "conversation.ha_ai_agent", (
        f"Expected agent id 'conversation.ha_ai_agent', got {agent_info.id!r}. "
        "Pipeline routing uses this exact id."
    )


async def test_agent_entity_id_format(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Entity id must start with 'conversation.' for pipeline dot-notation routing (VOICE-01).

    assist_pipeline selects agents by entity_id with domain prefix. Without the
    'conversation.' prefix, the pipeline cannot route to the agent.
    """
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all("conversation")
    agent_states = [s for s in states if DOMAIN in s.entity_id]

    assert len(agent_states) == 1, (
        f"Expected exactly 1 ha_ai_agent state in 'conversation' domain, "
        f"found {len(agent_states)}: {[s.entity_id for s in agent_states]}"
    )
    assert agent_states[0].entity_id.startswith("conversation."), (
        f"entity_id {agent_states[0].entity_id!r} does not start with 'conversation.'. "
        "Pipeline routing requires the dot-notation prefix."
    )


async def test_response_speech_set(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """_async_handle_message must set speech text on IntentResponse (VOICE-02).

    The voice pipeline TTS stage reads result.response.speech["plain"]["speech"].
    If this is empty, TTS has nothing to speak aloud.
    """
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.ha_ai_agent.intent_router.IntentRouter.async_route",
        new=AsyncMock(return_value="Salon allume."),
    ):
        component = hass.data.get("entity_components", {}).get("conversation")
        assert component is not None, "conversation entity_components not found in hass.data"
        entity = next(
            (e for e in component.entities if DOMAIN in getattr(e, "entity_id", "")),
            None,
        )
        assert entity is not None, "HaAiConversationAgent entity not found after setup"

        user_input = ConversationInput(
            text="allume le salon",
            context=Context(),
            conversation_id=None,
            device_id=None,
            language="fr",
            agent_id=None,
            satellite_id=None,
        )
        chat_log = MagicMock(spec=ChatLog)
        chat_log.async_add_assistant_content_without_tools = MagicMock()

        result = await entity._async_handle_message(user_input, chat_log)

        assert result.response.speech["plain"]["speech"] == "Salon allume.", (
            f"Expected speech 'Salon allume.', "
            f"got {result.response.speech.get('plain', {}).get('speech', '')!r}. "
            "TTS stage requires this field to be populated."
        )


async def test_conversation_result_has_speech(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """ConversationResult.response must be IntentResponse with non-empty speech dict (VOICE-02).

    Pipeline reads .response.speech to forward text to the TTS engine.
    Both the type (IntentResponse) and non-empty speech dict are required.
    """
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.ha_ai_agent.intent_router.IntentRouter.async_route",
        new=AsyncMock(return_value="Cuisine eteinte."),
    ):
        component = hass.data.get("entity_components", {}).get("conversation")
        assert component is not None, "conversation entity_components not found in hass.data"
        entity = next(
            (e for e in component.entities if DOMAIN in getattr(e, "entity_id", "")),
            None,
        )
        assert entity is not None, "HaAiConversationAgent entity not found after setup"

        user_input = ConversationInput(
            text="eteins la cuisine",
            context=Context(),
            conversation_id=None,
            device_id=None,
            language="fr",
            agent_id=None,
            satellite_id=None,
        )
        chat_log = MagicMock(spec=ChatLog)
        chat_log.async_add_assistant_content_without_tools = MagicMock()

        result = await entity._async_handle_message(user_input, chat_log)

        assert isinstance(result.response, conversation_intent.IntentResponse), (
            f"Expected IntentResponse, got {type(result.response)}. "
            "Pipeline requires this exact type."
        )
        assert "plain" in result.response.speech, (
            f"'plain' key missing from speech dict: {result.response.speech!r}. "
            "TTS stage expects speech['plain']['speech']."
        )
        assert len(result.response.speech["plain"]["speech"]) > 0, (
            "Speech text is empty. TTS has nothing to speak."
        )
