---
phase: 05-habit-engine
plan: 01
subsystem: database
tags: [aiosqlite, sqlite, wal, habit-engine, storage, ttl, fifo]

# Dependency graph
requires:
  - phase: 03-claude-llm-integration
    provides: const.py with MAX_HISTORY_TURNS and project conventions for hass.data storage
provides:
  - AgentStorage class (async_open, async_close, _ensure_schema, async_record_event, async_purge_old_events, async_enforce_cap)
  - SQLite WAL-mode database at {config_dir}/ha_ai_agent_habits.db
  - Schema versioning via meta table (schema_version=1)
  - D-07 events table with idx_events_entity_ts index
  - tmp_storage pytest fixture for Phase 5 tests
affects: [05-02-habit-engine, 05-03-pattern-detector, 06-habit-feedback-loop]

# Tech tracking
tech-stack:
  added: [aiosqlite (already declared in manifest.json 0.22.1)]
  patterns:
    - AgentStorage uses __new__ + _db_path injection to allow testability without hass
    - WAL + synchronous=NORMAL activated in async_open for every connection
    - _ensure_schema called on every async_open (idempotent CREATE IF NOT EXISTS)
    - async_enforce_cap called inside async_record_event to maintain FIFO cap atomically

key-files:
  created:
    - custom_components/ha_ai_agent/storage.py
    - tests/test_storage.py
  modified:
    - custom_components/ha_ai_agent/const.py
    - tests/conftest.py

key-decisions:
  - "AgentStorage.__new__ + _db_path injection: allows tests to bypass hass dependency without mock"
  - "async_enforce_cap called inside async_record_event: FIFO cap enforced atomically after every insert"
  - "WAL mode activated in async_open (not _ensure_schema): confirms WAL on every reconnection per SQLite docs"
  - "persons_home serialized as json.dumps([]) not None when empty list: consistent JSON column contract"

patterns-established:
  - "Pattern: Storage testability — AgentStorage.__new__ + inject _db_path avoids hass mock for unit tests"
  - "Pattern: Idempotent schema — CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE prevents duplicate schema init"

requirements-completed: [HABIT-01, HABIT-02, SEC-02]

# Metrics
duration: 3min
completed: 2026-04-05
---

# Phase 5 Plan 01: Habit Engine Storage Summary

**WAL-mode SQLite storage layer for habit events with D-07 schema, TTL purge (90d), and FIFO cap (10,000 events) via aiosqlite.**

## Performance

- **Duration:** ~3 minutes
- **Started:** 2026-04-05T14:24:29Z
- **Completed:** 2026-04-05T14:27:03Z
- **Tasks:** 1 completed (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments

- Implemented AgentStorage class with crash-safe WAL SQLite using aiosqlite
- D-07 events table schema: entity_id, domain, service, timestamp, day_of_week, hour, persons_home, weather_condition with idx_events_entity_ts index
- Schema versioning via meta table (schema_version=1), TTL purge (90 days), FIFO cap (10,000 events)
- 9/9 test_storage.py tests pass; full suite green (50 tests, no regressions)
- Added tmp_storage fixture to conftest.py for Phase 5 test infrastructure

## Task Commits

Each task was committed atomically with TDD approach:

1. **Task 1 RED: Failing tests** - `e91f2af` (test)
2. **Task 1 GREEN: AgentStorage implementation** - `a19750e` (feat)

## Files Created/Modified

- `custom_components/ha_ai_agent/storage.py` - AgentStorage class (WAL SQLite, schema, record, purge, cap)
- `custom_components/ha_ai_agent/const.py` - Added DB_FILENAME, HABIT_TTL_DAYS=90, HABIT_EVENT_CAP=10_000
- `tests/test_storage.py` - 9 tests covering WAL mode, schema, D-07 fields, TTL purge, FIFO cap, idempotent close, SEC-02
- `tests/conftest.py` - Added tmp_storage fixture and AgentStorage import

## Decisions Made

- AgentStorage.__new__ + _db_path injection pattern: avoids hass mock for pure storage unit tests — consistent with research recommendation
- async_enforce_cap called inside async_record_event: cap enforced atomically after each insert rather than as a separate scheduled task
- WAL PRAGMA confirmed on every async_open: SQLite stores WAL in .db file but PRAGMA must be re-issued on reconnect

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — AgentStorage is fully wired. No placeholder values or empty data flows.

## Issues Encountered

None — aiosqlite 0.22.1 already installed, all tests passed on first run.

## Next Phase Readiness

- AgentStorage fully operational — HabitEngine (05-02) can import and use AgentStorage directly
- tmp_storage fixture available in conftest.py for 05-02 and 05-03 tests
- Constants DB_FILENAME, HABIT_TTL_DAYS, HABIT_EVENT_CAP exported from const.py

## Self-Check: PASSED

- storage.py: FOUND
- test_storage.py: FOUND
- 05-01-SUMMARY.md: FOUND
- Commit e91f2af (RED): FOUND
- Commit a19750e (GREEN): FOUND
- tests/test_storage.py: 9 passed

---
*Phase: 05-habit-engine*
*Completed: 2026-04-05*
