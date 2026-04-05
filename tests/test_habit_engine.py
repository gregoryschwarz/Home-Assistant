"""Tests for HabitEngine — state_changed event filtering and context gathering.

Covers HABIT-01, HABIT-02, SEC-02 (plan 05-02).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.ha_ai_agent.habit_engine import HabitEngine
from custom_components.ha_ai_agent.const import DEFAULT_ALLOWED_DOMAINS


# ---------------------------------------------------------------------------
# Helper: build a synthetic state_changed Event
# ---------------------------------------------------------------------------

def make_state_changed_event(
    entity_id: str,
    old_state_val: str,
    new_state_val: str,
    user_id: str | None = "user123",
    old_attrs: dict | None = None,
    new_attrs: dict | None = None,
) -> MagicMock:
    """Return a MagicMock mimicking a HA state_changed Event."""
    old_attrs = old_attrs or {}
    new_attrs = new_attrs or {}

    old_state = MagicMock()
    old_state.state = old_state_val
    old_state.attributes = old_attrs

    new_state = MagicMock()
    new_state.state = new_state_val
    new_state.entity_id = entity_id
    new_state.attributes = new_attrs
    new_state.context = MagicMock()
    new_state.context.user_id = user_id

    event = MagicMock()
    event.data = {
        "old_state": old_state,
        "new_state": new_state,
    }
    return event


# ---------------------------------------------------------------------------
# Fixture: HabitEngine with mocked AgentStorage
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_storage() -> AsyncMock:
    storage = AsyncMock()
    storage.async_record_event = AsyncMock()
    storage.async_purge_old_events = AsyncMock()
    return storage


@pytest.fixture
def engine(hass: HomeAssistant, mock_storage: AsyncMock) -> HabitEngine:
    """Create a HabitEngine with default allowed domains."""
    return HabitEngine(hass, mock_storage, list(DEFAULT_ALLOWED_DOMAINS))


# ---------------------------------------------------------------------------
# Tests: filtering — D-01, D-02
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_human_event_on_allowed_domain_records(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """Human-initiated state change on allowed domain calls async_record_event."""
    event = make_state_changed_event("light.salon", "off", "on", user_id="user-abc")
    await engine._handle_state_changed(event)
    mock_storage.async_record_event.assert_called_once()


@pytest.mark.asyncio
async def test_automation_event_not_recorded(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """Automation event (user_id is None) is NOT recorded (D-01)."""
    event = make_state_changed_event("light.salon", "off", "on", user_id=None)
    await engine._handle_state_changed(event)
    mock_storage.async_record_event.assert_not_called()


@pytest.mark.asyncio
async def test_non_allowed_domain_not_recorded(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """State change on a non-allowed domain (sensor) is NOT recorded (D-02)."""
    event = make_state_changed_event("sensor.temperature", "20", "21", user_id="user-abc")
    await engine._handle_state_changed(event)
    mock_storage.async_record_event.assert_not_called()


@pytest.mark.asyncio
async def test_new_state_none_ignored(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """Event with new_state=None (entity removed) is ignored."""
    event = MagicMock()
    event.data = {"old_state": MagicMock(), "new_state": None}
    await engine._handle_state_changed(event)
    mock_storage.async_record_event.assert_not_called()


@pytest.mark.asyncio
async def test_old_state_none_ignored(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """Event with old_state=None (entity creation, not a transition) is ignored."""
    event = MagicMock()
    new_state = MagicMock()
    new_state.state = "on"
    new_state.entity_id = "light.salon"
    new_state.context = MagicMock()
    new_state.context.user_id = "user-abc"
    event.data = {"old_state": None, "new_state": new_state}
    await engine._handle_state_changed(event)
    mock_storage.async_record_event.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: service inference
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_service_inferred_turn_on(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """service='turn_on' inferred when old=off new=on."""
    event = make_state_changed_event("light.salon", "off", "on")
    await engine._handle_state_changed(event)
    _, kwargs = mock_storage.async_record_event.call_args
    args = mock_storage.async_record_event.call_args[0]
    assert args[2] == "turn_on"


@pytest.mark.asyncio
async def test_service_inferred_turn_off(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """service='turn_off' inferred when old=on new=off."""
    event = make_state_changed_event("light.salon", "on", "off")
    await engine._handle_state_changed(event)
    args = mock_storage.async_record_event.call_args[0]
    assert args[2] == "turn_off"


@pytest.mark.asyncio
async def test_service_inferred_climate_set_temperature(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """service='set_temperature' inferred for climate when temperature attribute changes."""
    event = make_state_changed_event(
        "climate.salon",
        "heat",
        "heat",
        old_attrs={"temperature": 19.0},
        new_attrs={"temperature": 21.0},
    )
    await engine._handle_state_changed(event)
    args = mock_storage.async_record_event.call_args[0]
    assert args[2] == "set_temperature"


@pytest.mark.asyncio
async def test_service_fallback_state_change(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """Unrecognized transition falls back to 'state_change'."""
    event = make_state_changed_event("switch.garage", "unavailable", "unknown")
    await engine._handle_state_changed(event)
    args = mock_storage.async_record_event.call_args[0]
    assert args[2] == "state_change"


# ---------------------------------------------------------------------------
# Tests: context gathering — D-05, D-06
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persons_home_populated(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """persons_home populated from person.* entities with state='home' (D-05)."""
    hass.states.async_set("person.greg", "home", {"friendly_name": "Greg"})
    hass.states.async_set("person.pam", "away", {"friendly_name": "Pam"})
    event = make_state_changed_event("light.salon", "off", "on")
    await engine._handle_state_changed(event)
    args = mock_storage.async_record_event.call_args[0]
    persons_home = args[3]
    assert "greg" in persons_home
    assert "pam" not in persons_home


@pytest.mark.asyncio
async def test_persons_home_none_when_no_persons(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """persons_home is None when no person.* entities exist."""
    # Ensure no person entities
    event = make_state_changed_event("light.salon", "off", "on")
    await engine._handle_state_changed(event)
    args = mock_storage.async_record_event.call_args[0]
    persons_home = args[3]
    assert persons_home is None


@pytest.mark.asyncio
async def test_weather_condition_populated(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """weather_condition populated from first weather.* entity state (D-06)."""
    hass.states.async_set("weather.home", "sunny", {})
    event = make_state_changed_event("light.salon", "off", "on")
    await engine._handle_state_changed(event)
    args = mock_storage.async_record_event.call_args[0]
    weather_condition = args[4]
    assert weather_condition == "sunny"


@pytest.mark.asyncio
async def test_weather_condition_none_when_no_weather(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """weather_condition is None when no weather.* entities exist."""
    event = make_state_changed_event("light.salon", "off", "on")
    await engine._handle_state_changed(event)
    args = mock_storage.async_record_event.call_args[0]
    weather_condition = args[4]
    assert weather_condition is None


# ---------------------------------------------------------------------------
# Tests: lifecycle — async_start / async_stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_start_subscribes_to_state_changed(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """async_start subscribes to state_changed event bus and sets _unsub_state."""
    assert engine._unsub_state is None
    await engine.async_start()
    assert engine._unsub_state is not None
    # Cleanup
    await engine.async_stop()


@pytest.mark.asyncio
async def test_async_start_runs_initial_purge(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """async_start calls async_purge_old_events on startup."""
    await engine.async_start()
    mock_storage.async_purge_old_events.assert_called_once()
    await engine.async_stop()


@pytest.mark.asyncio
async def test_async_stop_unsubscribes(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """async_stop calls unsubscribe callback and sets _unsub_state to None."""
    await engine.async_start()
    assert engine._unsub_state is not None
    await engine.async_stop()
    assert engine._unsub_state is None


@pytest.mark.asyncio
async def test_async_stop_cancels_purge_timer(
    hass: HomeAssistant, engine: HabitEngine, mock_storage: AsyncMock
):
    """async_stop cancels the daily purge timer and sets _cancel_purge to None."""
    await engine.async_start()
    assert engine._cancel_purge is not None
    await engine.async_stop()
    assert engine._cancel_purge is None


# ---------------------------------------------------------------------------
# Tests: SEC-02 — no network imports
# ---------------------------------------------------------------------------

def test_no_network_imports_in_habit_engine():
    """habit_engine.py must not import httpx, requests, aiohttp, or urllib (SEC-02)."""
    import ast
    import pathlib

    source_path = (
        pathlib.Path(__file__).parent.parent
        / "custom_components"
        / "ha_ai_agent"
        / "habit_engine.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"httpx", "requests", "aiohttp", "urllib"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden, (
                        f"Forbidden import: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                assert module not in forbidden, f"Forbidden import: {node.module}"
