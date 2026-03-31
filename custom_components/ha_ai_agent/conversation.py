"""Conversation platform for HA Autonomous AI Agent (HA-04).

Uses ConversationEntity (HA 2024.6+ API).
Do NOT use AbstractConversationAgent — deprecated, breaks on HA 2025.x.

Verified import paths (HA 2026.3.4):
  - ConversationEntity, ConversationInput, ConversationResult: homeassistant.components.conversation
  - AssistantContent: homeassistant.components.conversation (top-level, re-exported)
  - ChatLog: homeassistant.components.conversation (top-level, re-exported)
  - intent: homeassistant.components.conversation.intent

_async_handle_message signature (confirmed from ConversationEntity base class source):
    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult
"""
from __future__ import annotations

from homeassistant.components.conversation import (
    AssistantContent,
    ChatLog,
    ConversationEntity,
    ConversationInput,
    ConversationResult,
    intent as conversation_intent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entity from config entry.

    HA calls this because PLATFORMS = ['conversation'] in __init__.py.
    This function name and signature are the HA platform contract.
    """
    async_add_entities([HaAiConversationAgent(hass, config_entry)])


class HaAiConversationAgent(ConversationEntity):
    """HA AI Agent conversation entity — Phase 1 scaffold (echo stub only).

    Phase 2 will replace _async_handle_message with IntentRouter + local rules.
    Phase 3 will add Claude API fallback.
    """

    _attr_has_entity_name = True
    _attr_name = "HA AI Agent"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the conversation agent."""
        self.hass = hass
        self._entry = entry
        # Tie unique_id to config entry so entity is removed on entry deletion
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages.

        Required abstract property of ConversationEntity (Pitfall 5 from research).
        Without this, HA may filter the agent from Voice Assistants for the user's language.
        Use MATCH_ALL = '*' to support all languages, or list specific codes.
        """
        return ["fr", "en"]

    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult:
        """Process a conversation message. Phase 1: echo stub only.

        Phase 2 replaces this body with:
            intent = await intent_router.async_route(user_input.text, hass)
            return await intent.async_execute(hass, user_input, chat_log)
        """
        response_text = f"[HA AI Agent scaffold] Received: {user_input.text}"

        # Add assistant response to chat log (required by ConversationEntity API in HA 2024.6+)
        # Verified: AssistantContent is importable from homeassistant.components.conversation
        # and accepts (agent_id: str, content: str | None)
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id=self.entity_id, content=response_text)
        )

        # Build ConversationResult with IntentResponse
        # IntentResponse(language: str) — confirmed constructor signature
        intent_response = conversation_intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_text)

        return ConversationResult(
            response=intent_response,
            conversation_id=user_input.conversation_id,
        )
