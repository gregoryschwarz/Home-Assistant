"""Tests for Phase 6 habit context injection (HABIT-04).

Coverage:
  - ClaudeClient.async_complete: habits block injected in message to Claude
  - ClaudeClient.async_complete: no injection when habits=[] or habits=None
  - HaAiConversationAgent._filter_relevant_habits: entity_id match
  - HaAiConversationAgent._filter_relevant_habits: hour ±2h window
  - HaAiConversationAgent._filter_relevant_habits: combined filtering
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLAUDE_PATCH = "custom_components.ha_ai_agent.claude_client.AsyncAnthropic"


def make_client(hass: HomeAssistant):
    """Construct a ClaudeClient with test defaults."""
    from custom_components.ha_ai_agent.claude_client import ClaudeClient

    return ClaudeClient(
        hass=hass,
        api_key="test-key",
        allowed_domains=["light", "switch", "climate", "media_player"],
    )


def _make_text_response(text="Réponse test."):
    """Build a mock end_turn text response."""
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    mock_response.content = [text_block]
    return mock_response


_SAMPLE_HABIT = {
    "entity_id": "light.cuisine",
    "domain": "light",
    "service": "turn_on",
    "day_of_week": 1,  # lundi (SQLite %w: 1=Monday)
    "hour": 7,
    "occurrences": 5,
    "last_seen": "2026-04-04 07:02:00",
}

_SAMPLE_HABIT_WEEKEND = {
    "entity_id": "climate.salon",
    "domain": "climate",
    "service": "set_temperature",
    "day_of_week": 6,  # samedi
    "hour": 19,
    "occurrences": 4,
    "last_seen": "2026-04-04 19:15:00",
}


# ---------------------------------------------------------------------------
# ClaudeClient habits injection tests
# ---------------------------------------------------------------------------


async def test_habits_injected_in_user_content(hass: HomeAssistant) -> None:
    """Habits block appears in the message body sent to Claude API when habits provided."""
    mock_response = _make_text_response("D'accord, je tiens compte de tes habitudes.")
    captured_messages = []

    async def mock_create(**kwargs):
        captured_messages.append(kwargs.get("messages", []))
        return mock_response

    with patch(_CLAUDE_PATCH) as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create = mock_create

        client = make_client(hass)
        result = await client.async_complete(
            "allume la lumiere",
            [{"entity_id": "light.cuisine", "friendly_name": "Cuisine", "state": "off"}],
            habits=[_SAMPLE_HABIT],
        )

    assert result == "D'accord, je tiens compte de tes habitudes."
    assert captured_messages, "No messages captured — create was not called"
    user_message = captured_messages[0][0]
    assert user_message["role"] == "user"
    content = user_message["content"]
    assert "Habitudes connues" in content
    assert "light.cuisine" in content
    assert "lundi" in content
    assert "7h" in content
    assert "5 fois" in content


async def test_empty_habits_no_injection(hass: HomeAssistant) -> None:
    """No habits block injected when habits=[] or habits=None."""
    mock_response = _make_text_response("Réponse sans habitudes.")
    captured_messages: list = []

    async def mock_create(**kwargs):
        captured_messages.append(kwargs.get("messages", []))
        return mock_response

    with patch(_CLAUDE_PATCH) as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create = mock_create

        client = make_client(hass)

        # habits=[]
        await client.async_complete("quel temps fait-il ?", [], habits=[])
        assert "Habitudes connues" not in captured_messages[-1][0]["content"]

        # habits=None
        await client.async_complete("quel temps fait-il ?", [], habits=None)
        assert "Habitudes connues" not in captured_messages[-1][0]["content"]

        # habits omitted (default)
        await client.async_complete("quel temps fait-il ?", [])
        assert "Habitudes connues" not in captured_messages[-1][0]["content"]


async def test_habits_day_name_mapping(hass: HomeAssistant) -> None:
    """Day of week is correctly mapped to French day name."""
    mock_response = _make_text_response("OK")
    captured_messages: list = []

    async def mock_create(**kwargs):
        captured_messages.append(kwargs.get("messages", []))
        return mock_response

    with patch(_CLAUDE_PATCH) as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create = mock_create

        client = make_client(hass)

        # day_of_week=6 → samedi
        await client.async_complete(
            "teste", [], habits=[_SAMPLE_HABIT_WEEKEND]
        )

    content = captured_messages[-1][0]["content"]
    assert "samedi" in content
    assert "19h" in content


# ---------------------------------------------------------------------------
# _filter_relevant_habits tests
# ---------------------------------------------------------------------------


def test_habit_filter_by_entity_id() -> None:
    """entity_id mentioned in command text → habit included."""
    from custom_components.ha_ai_agent.conversation import HaAiConversationAgent

    habits = [_SAMPLE_HABIT, _SAMPLE_HABIT_WEEKEND]
    # "light.cuisine" appears in text, "climate.salon" does not, hour is 15 (not in ±2h of 7 or 19)
    result = HaAiConversationAgent._filter_relevant_habits(habits, "allume light.cuisine", 15)
    assert len(result) == 1
    assert result[0]["entity_id"] == "light.cuisine"


def test_habit_filter_by_time_window() -> None:
    """Hour within ±2h of current_hour → habit included; outside → excluded."""
    from custom_components.ha_ai_agent.conversation import HaAiConversationAgent

    habits = [_SAMPLE_HABIT, _SAMPLE_HABIT_WEEKEND]
    # current_hour=8 → ±2h = [6,10] → covers hour=7 (light.cuisine), not 19
    result = HaAiConversationAgent._filter_relevant_habits(habits, "commande générique", 8)
    assert len(result) == 1
    assert result[0]["entity_id"] == "light.cuisine"

    # current_hour=20 → ±2h = [18,22] → covers hour=19 (climate.salon), not 7
    result = HaAiConversationAgent._filter_relevant_habits(habits, "commande générique", 20)
    assert len(result) == 1
    assert result[0]["entity_id"] == "climate.salon"


def test_habit_filter_combined() -> None:
    """Multiple habits: entity match + time match → union without duplicates."""
    from custom_components.ha_ai_agent.conversation import HaAiConversationAgent

    habits = [_SAMPLE_HABIT, _SAMPLE_HABIT_WEEKEND]
    # entity mention: light.cuisine → included
    # time window at current_hour=21: [19,23] → climate.salon at hour=19 → included
    result = HaAiConversationAgent._filter_relevant_habits(
        habits, "allume light.cuisine s'il fait froid", 21
    )
    entity_ids = [h["entity_id"] for h in result]
    assert "light.cuisine" in entity_ids
    assert "climate.salon" in entity_ids


def test_habit_filter_empty_habits() -> None:
    """Empty habits list returns empty list (D-02)."""
    from custom_components.ha_ai_agent.conversation import HaAiConversationAgent

    result = HaAiConversationAgent._filter_relevant_habits([], "allume la lumiere", 7)
    assert result == []


def test_habit_filter_midnight_wrap() -> None:
    """Time window wraps correctly around midnight (e.g., current_hour=1, habit at hour=23)."""
    from custom_components.ha_ai_agent.conversation import HaAiConversationAgent

    late_habit = {
        "entity_id": "light.entree",
        "domain": "light",
        "service": "turn_off",
        "day_of_week": 0,
        "hour": 23,
        "occurrences": 3,
    }
    # current_hour=1 → delta from 23: min((23-1)%24, (1-23)%24) = min(22, 2) = 2 → included
    result = HaAiConversationAgent._filter_relevant_habits([late_habit], "teste", 1)
    assert len(result) == 1
    assert result[0]["entity_id"] == "light.entree"

    # current_hour=4 → delta from 23: min((23-4)%24, (4-23)%24) = min(19, 5) = 5 → excluded
    result = HaAiConversationAgent._filter_relevant_habits([late_habit], "teste", 4)
    assert len(result) == 0
