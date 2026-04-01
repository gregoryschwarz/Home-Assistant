"""Unit tests for ClaudeClient — NLU-03 (LLM fallback), SEC-01, D-11, D-18, D-19."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

# Force import of the module so that patch() can resolve its attributes.
import custom_components.ha_ai_agent.claude_client  # noqa: F401

# Patch target: AsyncAnthropic constructor inside claude_client module
_CLAUDE_PATCH = "custom_components.ha_ai_agent.claude_client.AsyncAnthropic"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(hass: HomeAssistant):
    """Construct a ClaudeClient with test defaults."""
    from custom_components.ha_ai_agent.claude_client import ClaudeClient

    return ClaudeClient(
        hass=hass,
        api_key="test-key",
        allowed_domains=["light", "switch", "climate", "media_player"],
    )


def _make_tool_response(domain="light", service="turn_on", entity_id="light.salon"):
    """Build a mock tool_use response."""
    mock_response = MagicMock()
    mock_response.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {
        "domain": domain,
        "service": service,
        "entity_id": entity_id,
    }
    mock_response.content = [tool_block]
    return mock_response


def _make_text_response(text="Bonjour, comment puis-je vous aider ?"):
    """Build a mock end_turn text response."""
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    mock_response.content = [text_block]
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_async_complete_tool_use(hass: HomeAssistant) -> None:
    """tool_use response: hass.services.async_call called, French confirmation returned."""
    from unittest.mock import patch as _patch
    from homeassistant.core import ServiceRegistry

    mock_response = _make_tool_response(
        domain="light", service="turn_on", entity_id="light.salon"
    )

    with patch(_CLAUDE_PATCH) as MockAsyncAnthropic:
        instance = MockAsyncAnthropic.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        client = make_client(hass)

        with patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new=AsyncMock(return_value=None),
        ) as mock_svc:
            result = await client.async_complete(
                "allume la lumiere du salon",
                [{"entity_id": "light.salon", "friendly_name": "Lumiere salon", "state": "off"}],
            )

    assert isinstance(result, str) and len(result) > 0
    assert "light.salon" in result or "action" in result.lower() or "accord" in result.lower()
    mock_svc.assert_awaited_once()


async def test_async_complete_free_text(hass: HomeAssistant) -> None:
    """end_turn response: text block returned directly (D-12)."""
    mock_response = _make_text_response("Il fait beau aujourd'hui.")

    with patch(_CLAUDE_PATCH) as MockAsyncAnthropic:
        instance = MockAsyncAnthropic.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        client = make_client(hass)
        result = await client.async_complete("quel temps fait-il ?", [])

    assert result == "Il fait beau aujourd'hui."


async def test_async_complete_auth_error(hass: HomeAssistant) -> None:
    """AuthenticationError (401) returns D-19 string and logs WARNING, no exception raised."""
    from anthropic import AuthenticationError

    with patch(_CLAUDE_PATCH) as MockAsyncAnthropic:
        instance = MockAsyncAnthropic.return_value
        instance.messages.create = AsyncMock(
            side_effect=AuthenticationError(
                "Unauthorized",
                response=MagicMock(status_code=401, headers={}),
                body=None,
            )
        )

        client = make_client(hass)
        result = await client.async_complete("allume la lumiere", [])

    assert "invalide" in result.lower() or "cle api" in result.lower() or "configuration" in result.lower()
    assert isinstance(result, str)


async def test_async_complete_connection_error(hass: HomeAssistant) -> None:
    """APIConnectionError after retry returns D-18 string, no exception raised."""
    from anthropic import APIConnectionError

    with patch(_CLAUDE_PATCH) as MockAsyncAnthropic:
        instance = MockAsyncAnthropic.return_value
        # Both attempts raise connection error
        instance.messages.create = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )

        with patch("asyncio.sleep", new=AsyncMock()):
            client = make_client(hass)
            result = await client.async_complete("allume la lumiere", [])

    assert "indisponible" in result.lower() or "reessayer" in result.lower()
    assert isinstance(result, str)


async def test_domain_validation_rejects(hass: HomeAssistant) -> None:
    """tool_use with domain NOT in allowed_domains: hass.services NOT called, rejection returned (D-11)."""
    mock_response = _make_tool_response(
        domain="camera", service="snapshot", entity_id="camera.front_door"
    )

    with patch(_CLAUDE_PATCH) as MockAsyncAnthropic:
        instance = MockAsyncAnthropic.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        client = make_client(hass)

        with patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new=AsyncMock(return_value=None),
        ) as mock_svc:
            result = await client.async_complete(
                "prends une photo",
                [{"entity_id": "camera.front_door", "friendly_name": "Camera entree", "state": "idle"}],
            )

    assert isinstance(result, str) and len(result) > 0
    assert "autoris" in result.lower() or "refus" in result.lower()
    mock_svc.assert_not_awaited()


async def test_history_cap(hass: HomeAssistant) -> None:
    """History deque grows and caps at MAX_HISTORY_TURNS=10 (D-08)."""
    from custom_components.ha_ai_agent.const import MAX_HISTORY_TURNS

    mock_response = _make_text_response("OK")

    with patch(_CLAUDE_PATCH) as MockAsyncAnthropic:
        instance = MockAsyncAnthropic.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        client = make_client(hass)

        # 6 calls = 6 user + 6 assistant entries = 12 total, but capped at MAX_HISTORY_TURNS=10
        for i in range(6):
            await client.async_complete(f"commande {i}", [])

    assert len(client._history) == MAX_HISTORY_TURNS


async def test_async_close(hass: HomeAssistant) -> None:
    """async_close is callable without error (D-09)."""
    with patch(_CLAUDE_PATCH) as MockAsyncAnthropic:
        instance = MockAsyncAnthropic.return_value
        instance.close = AsyncMock(return_value=None)

        client = make_client(hass)
        await client.async_close()

    instance.close.assert_awaited_once()
