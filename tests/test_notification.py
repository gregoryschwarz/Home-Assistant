"""Tests for HabitNotifier — persistent_notification dispatch with anti-spam (D-06 to D-09).

Plan 06-02 TDD RED phase.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHabitNotifier:
    """Tests for HabitNotifier in notification.py."""

    def _make_hass(self, entity_state=None):
        """Build a minimal mock hass with services.async_call as AsyncMock."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = AsyncMock()
        hass.states = MagicMock()
        if entity_state is not None:
            hass.states.get = MagicMock(return_value=entity_state)
        else:
            hass.states.get = MagicMock(return_value=None)
        return hass

    def _make_pattern(
        self,
        entity_id="light.cuisine",
        day_of_week=0,
        hour=7,
        occurrences=5,
    ) -> dict:
        return {
            "entity_id": entity_id,
            "domain": "light",
            "service": "turn_on",
            "day_of_week": day_of_week,
            "hour": hour,
            "occurrences": occurrences,
            "last_seen": "2026-04-05T07:00:00",
        }

    # ------------------------------------------------------------------
    # Test 1: new pattern notifies
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_new_pattern_calls_persistent_notification(self):
        """async_notify_new_patterns([pattern]) must call hass.services.async_call."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass()
        notifier = HabitNotifier(hass)
        pattern = self._make_pattern()
        await notifier.async_notify_new_patterns([pattern])
        hass.services.async_call.assert_awaited_once()
        args = hass.services.async_call.call_args
        assert args[0][0] == "persistent_notification"
        assert args[0][1] == "create"

    # ------------------------------------------------------------------
    # Test 2: notification_id format (D-07)
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_notification_id_format(self):
        """notification_id must follow ha_ai_agent_habit_{entity_id}_{day_of_week}_{hour}."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass()
        notifier = HabitNotifier(hass)
        pattern = self._make_pattern(entity_id="light.cuisine", day_of_week=1, hour=8)
        await notifier.async_notify_new_patterns([pattern])
        call_kwargs = hass.services.async_call.call_args[0][2]
        assert call_kwargs["notification_id"] == "ha_ai_agent_habit_light.cuisine_1_8"

    # ------------------------------------------------------------------
    # Test 3: message format (D-08)
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_message_format(self):
        """Message must match D-08 template with friendly_name, day, hour, occurrences."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        # Mock state with friendly_name
        state = MagicMock()
        state.attributes = {"friendly_name": "Lumiere cuisine"}
        hass = self._make_hass(entity_state=state)
        notifier = HabitNotifier(hass)
        pattern = self._make_pattern(
            entity_id="light.cuisine", day_of_week=0, hour=7, occurrences=5
        )
        await notifier.async_notify_new_patterns([pattern])
        call_kwargs = hass.services.async_call.call_args[0][2]
        msg = call_kwargs["message"]
        assert "Lumiere cuisine" in msg
        assert "lundi" in msg
        assert "7h" in msg
        assert "5" in msg
        assert "14 jours" in msg
        assert "automatisation" in msg

    # ------------------------------------------------------------------
    # Test 4: anti-spam blocks second call within 24h
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_antispam_blocks_duplicate_within_24h(self):
        """Same pattern called twice within 24h — second call must NOT create notification."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass()
        notifier = HabitNotifier(hass)
        pattern = self._make_pattern()

        await notifier.async_notify_new_patterns([pattern])
        await notifier.async_notify_new_patterns([pattern])

        # Only one notification should have been sent
        assert hass.services.async_call.await_count == 1

    # ------------------------------------------------------------------
    # Test 5: anti-spam expires after 24h
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_antispam_expires_after_24h(self):
        """After 24h+, the same pattern must trigger a new notification."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass()
        notifier = HabitNotifier(hass)
        pattern = self._make_pattern()

        # First call
        with patch("custom_components.ha_ai_agent.notification.time") as mock_time:
            mock_time.monotonic.return_value = 1000.0
            await notifier.async_notify_new_patterns([pattern])

        # Second call after 25h (> 86400s)
        with patch("custom_components.ha_ai_agent.notification.time") as mock_time:
            mock_time.monotonic.return_value = 1000.0 + 86400 + 1
            await notifier.async_notify_new_patterns([pattern])

        # Both calls should have sent notifications
        assert hass.services.async_call.await_count == 2

    # ------------------------------------------------------------------
    # Test 6: multiple patterns, all notified
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_multiple_patterns_all_notified(self):
        """Two different patterns in one call — both must get notifications."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass()
        notifier = HabitNotifier(hass)
        p1 = self._make_pattern(entity_id="light.cuisine", day_of_week=0, hour=7)
        p2 = self._make_pattern(entity_id="switch.bureau", day_of_week=2, hour=9)

        await notifier.async_notify_new_patterns([p1, p2])

        assert hass.services.async_call.await_count == 2

    # ------------------------------------------------------------------
    # Test 7: mixed new and seen — only new triggers notification
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_mixed_new_and_seen_only_new_notified(self):
        """One new pattern + one seen <24h ago — only the new one must notify."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass()
        notifier = HabitNotifier(hass)
        p_seen = self._make_pattern(entity_id="light.cuisine", day_of_week=0, hour=7)
        p_new = self._make_pattern(entity_id="switch.bureau", day_of_week=2, hour=9)

        # Send p_seen first (marks it as notified recently)
        await notifier.async_notify_new_patterns([p_seen])
        hass.services.async_call.reset_mock()

        # Now send both — only p_new should produce a notification
        await notifier.async_notify_new_patterns([p_seen, p_new])
        assert hass.services.async_call.await_count == 1
        call_kwargs = hass.services.async_call.call_args[0][2]
        assert "switch.bureau" in call_kwargs["notification_id"]

    # ------------------------------------------------------------------
    # Test 8: empty list — no notification
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_empty_list_no_notification(self):
        """async_notify_new_patterns([]) must not call hass.services.async_call."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass()
        notifier = HabitNotifier(hass)
        await notifier.async_notify_new_patterns([])
        hass.services.async_call.assert_not_awaited()

    # ------------------------------------------------------------------
    # Test 9: friendly_name resolution + fallback to entity_id
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_friendly_name_resolution(self):
        """entity_id resolved to friendly_name; falls back to entity_id if not found."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        # Entity found with friendly_name
        state = MagicMock()
        state.attributes = {"friendly_name": "Lumiere salon"}
        hass = self._make_hass(entity_state=state)
        notifier = HabitNotifier(hass)
        await notifier.async_notify_new_patterns([self._make_pattern(entity_id="light.salon")])
        call_kwargs = hass.services.async_call.call_args[0][2]
        assert "Lumiere salon" in call_kwargs["message"]
        assert "light.salon" not in call_kwargs["message"]

    @pytest.mark.asyncio
    async def test_friendly_name_fallback_to_entity_id(self):
        """If entity not found in hass.states, falls back to entity_id in message."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass(entity_state=None)  # state not found
        notifier = HabitNotifier(hass)
        await notifier.async_notify_new_patterns([self._make_pattern(entity_id="light.unknown")])
        call_kwargs = hass.services.async_call.call_args[0][2]
        assert "light.unknown" in call_kwargs["message"]

    # ------------------------------------------------------------------
    # Test 10: day_of_week to French mapping
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_day_of_week_lundi(self):
        """day_of_week=0 must map to 'lundi' in notification message."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass()
        notifier = HabitNotifier(hass)
        await notifier.async_notify_new_patterns([self._make_pattern(day_of_week=0)])
        call_kwargs = hass.services.async_call.call_args[0][2]
        assert "lundi" in call_kwargs["message"]

    @pytest.mark.asyncio
    async def test_day_of_week_dimanche(self):
        """day_of_week=6 must map to 'dimanche' in notification message."""
        from custom_components.ha_ai_agent.notification import HabitNotifier

        hass = self._make_hass()
        notifier = HabitNotifier(hass)
        await notifier.async_notify_new_patterns([self._make_pattern(day_of_week=6)])
        call_kwargs = hass.services.async_call.call_args[0][2]
        assert "dimanche" in call_kwargs["message"]
