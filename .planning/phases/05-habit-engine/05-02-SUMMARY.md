---
phase: 05-habit-engine
plan: 02
subsystem: database
tags: [habit-engine, state-changed, event-listener, filtering, context, aiosqlite, sqlite, homeassistant]

# Dependency graph
requires:
  - phase: 05-01-habit-engine
    provides: AgentStorage with async_record_event, async_purge_old_events, tmp_storage fixture

provides:
  - HabitEngine class (async_start, async_stop, _handle_state_changed)
  - D-01 filtering: automation events (user_id=None) ignored
  - D-02 filtering: only allowed domains tracked
  - D-05: persons_home context from person.* entities
  - D-06: weather_condition context from weather.* entities
  - service inference: turn_on/off, media_play/pause, set_temperature, fallback state_change
  - daily TTL purge via async_track_time_interval with clean teardown
  - 18 tests covering all filtering, inference, context, lifecycle, and SEC-02 behaviours

affects: [05-03-pattern-detector, 06-habit-feedback-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - HabitEngine async_start/async_stop: subscribe/unsubscribe pattern with _unsub_state and _cancel_purge cancel callbacks
    - async_track_time_interval for daily purge: HA lifecycle-safe periodic task (cancel_callback stored for teardown)
    - Service inference heuristic: old_state.state -> new_state.state transition rules, temperature attribute delta for climate
    - hass.states.async_all(domain) for person.* and weather.* context gathering
    - TYPE_CHECKING import guard for AgentStorage: avoids circular import, keeps type hints

key-files:
  created:
    - custom_components/ha_ai_agent/habit_engine.py
    - tests/test_habit_engine.py
  modified: []

key-decisions:
  - "HabitEngine._get_persons_home returns None (not empty list) when no person.* entities exist — consistent with D-05 contract and async_record_event signature"
  - "old_state=None events ignored: entity creation is not a user transition — avoids false positives on first HA load"
  - "service='state_change' as universal fallback: covers all unrecognized transitions without data loss"
  - "TYPE_CHECKING guard for AgentStorage import: avoids circular import between habit_engine and storage at runtime"

patterns-established:
  - "Pattern: HA event listener lifecycle — _unsub_state + _cancel_purge as instance attributes, both called and None-set in async_stop"
  - "Pattern: Context gathering with None-guard — async_all returns empty list when domain has no entities, convert to None for DB contract"

requirements-completed: [HABIT-01, HABIT-02, SEC-02]

# Metrics
duration: 3min
completed: 2026-04-05
---

# Phase 5 Plan 02: HabitEngine Summary

**state_changed event listener with D-01/D-02 filtering, service inference, presence/weather context gathering, and daily TTL purge via async_track_time_interval**

## Performance

- **Duration:** ~3 minutes
- **Started:** 2026-04-05T14:31:48Z
- **Completed:** 2026-04-05T14:34:56Z
- **Tasks:** 1 completed (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Implemented HabitEngine with D-01 filtering (user_id=None automations ignored) and D-02 filtering (non-allowed domains ignored)
- Service inference covering light/switch (turn_on/off), media_player (media_play/pause), climate (set_temperature/turn_on/off), fallback state_change
- D-05 presence context: persons_home list from person.* entities (friendly_name lowercased), None when no person entities
- D-06 weather context: weather_condition from first weather.* entity state, None when no weather entities
- Daily TTL purge via async_track_time_interval with clean async_stop teardown
- 18/18 test_habit_engine.py tests pass; 72/72 full suite, no regressions

## Task Commits

Each task was committed atomically with TDD approach:

1. **Task 1 RED: Failing tests** - `382d069` (test)
2. **Task 1 GREEN: HabitEngine implementation** - `a9d6257` (feat)

## Files Created/Modified

- `custom_components/ha_ai_agent/habit_engine.py` - HabitEngine class with event filtering, service inference, context gathering, purge lifecycle
- `tests/test_habit_engine.py` - 18 tests covering all filtering rules, inference cases, context gathering, lifecycle, and SEC-02

## Decisions Made

- `_get_persons_home` returns `None` when no `person.*` entities exist (not empty list `[]`) — matches the `list[str] | None` contract in `async_record_event` and D-05 spec. Returning `[]` would falsely imply persons were checked and none found.
- Events with `old_state=None` are ignored (entity creation) — only established transitions from a known state should generate habits.
- `TYPE_CHECKING` guard for `AgentStorage` import — keeps the runtime import chain clean, avoids potential circular import between modules.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — HabitEngine is fully wired. Service inference and context gathering are implemented. No placeholder values or TODO stubs.

## Issues Encountered

None — all 18 tests passed on first run. hass fixture from pytest-homeassistant-custom-component provides hass.states.async_set and hass.bus.async_listen as expected.

## Next Phase Readiness

- HabitEngine ready for Plan 05-03 (PatternDetector): events are being written to AgentStorage, TTL purge is running
- The `_infer_service` method uses heuristics covering all 4 allowed domains — PatternDetector can rely on the service field values documented here
- Full test suite (72 tests) remains green — no regressions in prior phases

## Self-Check: PASSED

- habit_engine.py: FOUND
- test_habit_engine.py: FOUND
- 05-02-SUMMARY.md: FOUND
- Commit 382d069 (RED): FOUND
- Commit a9d6257 (GREEN): FOUND
- tests/test_habit_engine.py: 18 passed
- Full suite: 72 passed

---
*Phase: 05-habit-engine*
*Completed: 2026-04-05*
