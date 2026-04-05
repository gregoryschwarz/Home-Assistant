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

Phase 6 additions:
  - _filter_relevant_habits: contextual habit filtering (D-01 Phase 6 CONTEXT)
    entity_id mentioned in text OR hour within ±2h of current hour
"""
from __future__ import annotations

import datetime

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
from .intent_router import IntentRouter


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
    """HA AI Agent conversation entity — Phase 2: routes via IntentRouter.

    Phase 3 will add Claude API fallback for unrecognized intents.
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

    @staticmethod
    def _filter_relevant_habits(
        habits: list[dict],
        text: str,
        current_hour: int,
    ) -> list[dict]:
        """Return habits relevant to the current request (D-01 Phase 6).

        A habit is relevant if:
          1. Its entity_id appears anywhere in the command text (case-insensitive), OR
          2. Its hour is within ±2h of current_hour (modulo 24).

        Args:
            habits: All stored pattern dicts from async_get_patterns().
            text: The raw user command text.
            current_hour: Current hour (0-23).

        Returns:
            Filtered subset of habits (may be empty).
        """
        text_lower = text.lower()
        relevant = []
        for h in habits:
            entity_id = str(h.get("entity_id", ""))
            habit_hour = int(h.get("hour", -1))
            # Rule 1: entity_id mentioned in text
            if entity_id and entity_id.lower() in text_lower:
                relevant.append(h)
                continue
            # Rule 2: hour within ±2h window (modulo 24)
            if habit_hour >= 0:
                delta = min((habit_hour - current_hour) % 24, (current_hour - habit_hour) % 24)
                if delta <= 2:
                    relevant.append(h)
        return relevant

    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult:
        """Route message via IntentRouter (Phase 2). Claude fallback added in Phase 3."""
        router: IntentRouter = self.hass.data[DOMAIN][self._entry.entry_id]["router"]
        response_text = await router.async_route(
            text=user_input.text,
            language=user_input.language,
        )

        if response_text is None:
            # D-02: LLM fallback — IntentRouter found no regex match
            entry_data = self.hass.data[DOMAIN][self._entry.entry_id]
            claude_client = entry_data["claude_client"]
            entity_context = entry_data["entity_context"]
            entities = entity_context.list_entities_for_llm(user_input.text)

            # Phase 6: retrieve and filter relevant habits (D-01)
            relevant_habits: list[dict] = []
            pattern_detector = entry_data.get("pattern_detector")
            if pattern_detector is not None:
                try:
                    all_habits = await pattern_detector.async_get_patterns()
                    current_hour = datetime.datetime.now().hour
                    relevant_habits = self._filter_relevant_habits(
                        all_habits, user_input.text, current_hour
                    )
                except Exception:  # noqa: BLE001 — never let habit fetch crash the agent
                    relevant_habits = []

            response_text = await claude_client.async_complete(
                user_input.text, entities, habits=relevant_habits or None
            )
            # D-03: if Claude also returns None, final fallback
            if response_text is None:
                response_text = "Je n'ai pas compris la commande."

        # Add assistant response to chat log (required by ConversationEntity API in HA 2024.6+)
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id=self.entity_id, content=response_text)
        )

        # Build ConversationResult with IntentResponse
        intent_response = conversation_intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_text)

        return ConversationResult(
            response=intent_response,
            conversation_id=user_input.conversation_id,
        )
