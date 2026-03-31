"""Unit tests for IntentRouter — NLU-02 (local rules) and NLU-05 (clear errors).

Wave 0 scaffold: 7 tests RED until plan 02-02 implements IntentRouter.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

from custom_components.ha_ai_agent.intent_router import IntentRouter

# Patch targets
# EntityContextBuilder.resolve_entity is patched on the class where it is defined
# so that any instance constructed inside _dispatch picks up the mock.
_EC_PATCH = "custom_components.ha_ai_agent.entity_context.EntityContextBuilder.resolve_entity"

# ServiceRegistry.async_call is a method on the class — patch at class level.
_SVC_PATCH = "homeassistant.core.ServiceRegistry.async_call"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_router(hass: HomeAssistant) -> IntentRouter:
    """Construct an IntentRouter with the standard allowed domains."""
    return IntentRouter(
        hass,
        allowed_domains=["light", "switch", "climate", "media_player"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_turn_on_french(hass: HomeAssistant) -> None:
    """'allume la lumiere du salon' must call light.turn_on for light.salon."""
    hass.states.async_set("light.salon", "off", {"friendly_name": "Lumiere salon"})

    router = make_router(hass)

    with patch(_EC_PATCH, return_value="light.salon"), patch(
        _SVC_PATCH, new=AsyncMock(return_value=None)
    ) as mock_call:
        result = await router.async_route("allume la lumiere du salon", "fr")

    mock_call.assert_awaited_once_with(
        domain="light",
        service="turn_on",
        service_data={"entity_id": "light.salon"},
        blocking=True,
    )
    assert "salon" in result.lower(), (
        f"Expected 'salon' in response, got: {result!r}"
    )


async def test_turn_off_english(hass: HomeAssistant) -> None:
    """'turn off the kitchen light' must call light.turn_off."""
    hass.states.async_set("light.kitchen", "on", {"friendly_name": "Kitchen Light"})

    router = make_router(hass)

    with patch(_EC_PATCH, return_value="light.kitchen"), patch(
        _SVC_PATCH, new=AsyncMock(return_value=None)
    ) as mock_call:
        result = await router.async_route("turn off the kitchen light", "en")

    mock_call.assert_awaited_once_with(
        domain="light",
        service="turn_off",
        service_data={"entity_id": "light.kitchen"},
        blocking=True,
    )
    assert isinstance(result, str) and len(result) > 0


async def test_set_temperature(hass: HomeAssistant) -> None:
    """'regle la temperature a 21' must call climate.set_temperature with temperature=21.0."""
    hass.states.async_set(
        "climate.thermostat", "heat", {"friendly_name": "Thermostat"}
    )

    router = make_router(hass)

    with patch(_EC_PATCH, return_value="climate.thermostat"), patch(
        _SVC_PATCH, new=AsyncMock(return_value=None)
    ) as mock_call:
        result = await router.async_route("regle la temperature a 21", "fr")

    call_args = mock_call.call_args
    assert call_args is not None, "async_call was never called"
    # First positional arg is 'self' (the ServiceRegistry instance) when patched at class level
    args = call_args.args
    kwargs = call_args.kwargs

    # Extract domain/service/service_data from kwargs
    assert kwargs.get("domain") == "climate" or (len(args) > 1 and args[1] == "climate"), (
        f"Expected domain='climate', got args={args!r} kwargs={kwargs!r}"
    )
    assert kwargs.get("service") == "set_temperature" or (len(args) > 2 and args[2] == "set_temperature"), (
        f"Expected service='set_temperature', got kwargs={kwargs!r}"
    )
    service_data = kwargs.get("service_data") or (args[3] if len(args) > 3 else {})
    assert service_data.get("temperature") == 21.0, (
        f"Expected temperature=21.0 in service_data, got {service_data!r}"
    )
    assert isinstance(result, str) and len(result) > 0


async def test_unrecognized_command_returns_fallback(hass: HomeAssistant) -> None:
    """Command matching no pattern must return a non-empty string (no exception)."""
    router = make_router(hass)
    result = await router.async_route("joue de la guitare", "fr")

    assert isinstance(result, str), (
        f"Expected str fallback, got {type(result)}"
    )
    assert len(result) > 0, "Fallback response must be non-empty"


async def test_service_not_found_returns_error(hass: HomeAssistant) -> None:
    """ServiceNotFound must be caught and returned as a French error string."""
    hass.states.async_set("light.salon", "off", {"friendly_name": "Lumiere salon"})

    router = make_router(hass)

    with patch(_EC_PATCH, return_value="light.salon"), patch(
        _SVC_PATCH, new=AsyncMock(side_effect=ServiceNotFound("light", "turn_on"))
    ):
        result = await router.async_route("allume la lumiere du salon", "fr")

    assert isinstance(result, str), (
        f"Expected str error message, got {type(result)}"
    )
    assert len(result) > 0, "Error response must be non-empty"


async def test_homeassistant_error_returns_error(hass: HomeAssistant) -> None:
    """HomeAssistantError must be caught and returned as a French error string."""
    hass.states.async_set("light.salon", "off", {"friendly_name": "Lumiere salon"})

    router = make_router(hass)

    with patch(_EC_PATCH, return_value="light.salon"), patch(
        _SVC_PATCH,
        new=AsyncMock(side_effect=HomeAssistantError("Unreachable")),
    ):
        result = await router.async_route("allume la lumiere du salon", "fr")

    assert isinstance(result, str), (
        f"Expected str error message, got {type(result)}"
    )
    assert len(result) > 0, "Error response must be non-empty"


async def test_curly_apostrophe(hass: HomeAssistant) -> None:
    """U+2019 curly apostrophe in 'l\u2019eclairage' must match the same as ASCII apostrophe."""
    hass.states.async_set("light.salon", "off", {"friendly_name": "Lumiere salon"})

    router = make_router(hass)

    with patch(_EC_PATCH, return_value="light.salon") as mock_resolve, patch(
        _SVC_PATCH, new=AsyncMock(return_value=None)
    ):
        # ASCII apostrophe version
        await router.async_route("allume l'eclairage du salon", "fr")
        ascii_call_count = mock_resolve.call_count

        # Reset mock
        mock_resolve.reset_mock()

        # Curly apostrophe U+2019
        await router.async_route("allume l\u2019eclairage du salon", "fr")
        curly_call_count = mock_resolve.call_count

    assert ascii_call_count == 1, (
        "ASCII apostrophe version did not match TURN_ON pattern"
    )
    assert curly_call_count == 1, (
        "Curly apostrophe (U+2019) version did not match TURN_ON pattern — normalization missing"
    )
