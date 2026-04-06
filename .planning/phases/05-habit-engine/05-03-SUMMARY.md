---
phase: 05-habit-engine
plan: 03
subsystem: database
tags: [aiosqlite, sqlite, wal, habit-engine, pattern-detection, state-changed]

# Dependency graph
requires:
  - phase: 03-claude-llm-integration
    provides: __init__.py lifecycle pattern, hass.data[DOMAIN][entry_id] registration
  - phase: 02-conversation-bridge
    provides: CONF_ALLOWED_DOMAINS filtering, entity domain conventions
provides:
  - AgentStorage: aiosqlite WAL SQLite with meta/events/patterns tables, TTL purge, FIFO cap
  - HabitEngine: state_changed listener filtering D-01 (user_id) and D-02 (domain)
  - PatternDetector: SQL GROUP BY frequency analysis, 14-day window, 3-occurrence threshold
  - All three wired into async_setup_entry with proper teardown via entry.async_on_unload
affects:
  - 06-habit-feedback-loop: PatternDetector.async_detect() returns patterns for Claude context injection

# Tech tracking
tech-stack:
  added: [aiosqlite 0.22.1 (already in manifest.json), json stdlib, datetime stdlib]
  patterns:
    - WAL mode + NORMAL synchronous for crash-safe SQLite in async HA component
    - entry.async_on_unload for both storage.async_close and habit_engine.async_stop
    - SQL GROUP BY HAVING for threshold-based time-series pattern detection
    - Service inference from old_state → new_state transition (state_changed pitfall)
    - hass.states.async_all(domain) for person.* and weather.* context reads

key-files:
  created:
    - custom_components/ha_ai_agent/storage.py
    - custom_components/ha_ai_agent/habit_engine.py
    - custom_components/ha_ai_agent/pattern_detector.py
    - tests/test_storage.py
    - tests/test_habit_engine.py
    - tests/test_pattern_detector.py
    - .planning/phases/05-habit-engine/05-03-PLAN.md
  modified:
    - custom_components/ha_ai_agent/__init__.py
    - custom_components/ha_ai_agent/const.py

key-decisions:
  - "AgentStorage stores _db_path at init time using hass.config.config_dir + DB_FILENAME for testability (tmp_path injection)"
  - "Service inferred from old_state→new_state (turn_on/turn_off/state_change) — state_changed event doesn't carry service per HA design"
  - "PatternDetector uses pure SQL GROUP BY on hour (not minute) as ±30min window — minute not stored per D-07 (conservatively covers window)"
  - "persons_home returns None (not empty list) when no person.* entities exist, per D-05"
  - "patterns table uses UNIQUE(entity_id, service, day_of_week, hour) with ON CONFLICT DO UPDATE for idempotent upsert"

patterns-established:
  - "AgentStorage pattern: open/close lifecycle with async_open() and async_close() bound to entry.async_on_unload"
  - "TDD pattern: RED (import fails) → GREEN (implement) → commit per task"
  - "Fixture isolation: _FakeHass with config.config_dir pointing to tmp_path for SQLite tests"

requirements-completed: [HABIT-01, HABIT-02, HABIT-03, SEC-02]

# Metrics
duration: 8min
completed: 2026-04-05
---

# Phase 5 Plan 03: Habit Engine Summary

**aiosqlite WAL SQLite with HabitEngine state_changed filtering and SQL GROUP BY pattern detection (3 occurrences / 14 days)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-05T14:39:50Z
- **Completed:** 2026-04-05T14:48:03Z
- **Tasks:** 4
- **Files modified:** 9 (7 created, 2 modified)

## Accomplishments

- AgentStorage with WAL mode, meta/events/patterns tables, 90-day TTL purge, 10,000-event FIFO cap
- HabitEngine subscribing to state_changed, filtering automation events (user_id=None) and non-allowed domains
- PatternDetector running SQL GROUP BY on last 14 days, detecting patterns with COUNT >= 3
- Full wiring in __init__.py with entry.async_on_unload teardown for both storage and habit engine
- 28 new tests (9 storage + 12 habit_engine + 7 pattern_detector) — all 73 project tests green

## Task Commits

Each task was committed atomically:

1. **Task 1: AgentStorage** - `3f1370d` (feat)
2. **Task 2: HabitEngine** - `404bf0e` (feat)
3. **Task 3: PatternDetector** - `57d6149` (feat)
4. **Task 4: Wire __init__.py** - `a2f39ef` (feat)

## Files Created/Modified

- `custom_components/ha_ai_agent/storage.py` — AgentStorage: aiosqlite WAL, schema versioning, TTL purge, FIFO cap, event recording
- `custom_components/ha_ai_agent/habit_engine.py` — HabitEngine: state_changed listener, D-01/D-02 filters, service inference, context capture
- `custom_components/ha_ai_agent/pattern_detector.py` — PatternDetector: SQL GROUP BY frequency analysis, upsert to patterns table
- `custom_components/ha_ai_agent/__init__.py` — Wires storage + habit_engine + pattern_detector into lifecycle
- `custom_components/ha_ai_agent/const.py` — Added DB_FILENAME, HABIT_TTL_DAYS, HABIT_CAP, HABIT_SCHEMA_VERSION
- `tests/test_storage.py` — 9 tests: schema, WAL, record_event, purge, cap, close, SEC-02
- `tests/test_habit_engine.py` — 12 tests: start/stop, D-01/D-02 filters, service inference, persons_home, weather
- `tests/test_pattern_detector.py` — 7 tests: threshold, grouping, 14-day window, upsert, empty result
- `.planning/phases/05-habit-engine/05-03-PLAN.md` — Plan file created (missing, created as deviation)

## Decisions Made

- Service is inferred from old_state→new_state transition since state_changed events don't carry the service called (HA design per research pitfall 1)
- Pattern detection uses pure SQL GROUP BY on `hour` column without minutes — conservatively implements the ±30min window from D-03 since `minute` is not stored per D-07
- `persons_home` returns `None` (not `[]`) when no `person.*` entities exist at all, to allow downstream Phase 6 to distinguish "no entities" from "no one home"

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan file 05-03-PLAN.md did not exist**
- **Found during:** Execution start
- **Issue:** Plan 05-03-PLAN.md was not created by the planner — the phase only had CONTEXT.md and RESEARCH.md
- **Fix:** Created 05-03-PLAN.md with all 4 tasks based on ROADMAP.md description and CONTEXT.md/RESEARCH.md
- **Files modified:** .planning/phases/05-habit-engine/05-03-PLAN.md
- **Committed in:** 3f1370d (part of Task 1 commit)

**2. [Rule 3 - Blocking] AgentStorage and HabitEngine (05-01, 05-02 work) didn't exist**
- **Found during:** Task 1
- **Issue:** PatternDetector (plan 05-03) depends on AgentStorage and HabitEngine which hadn't been implemented (plans 05-01 and 05-02 were never executed)
- **Fix:** Implemented AgentStorage (Task 1) and HabitEngine (Task 2) as prerequisites — these are the 05-01 and 05-02 deliverables embedded in this execution
- **Files modified:** storage.py, habit_engine.py, test_storage.py, test_habit_engine.py
- **Committed in:** 3f1370d, 404bf0e

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking)
**Impact on plan:** Both fixes were essential prerequisites. Effectively delivered all three Phase 5 sub-plans (05-01, 05-02, 05-03) in one execution. No scope creep — all work was in the ROADMAP for Phase 5.

## Issues Encountered

None — aiosqlite already declared in manifest.json, all patterns directly from RESEARCH.md.

## User Setup Required

None — AgentStorage uses hass.config.config_dir for SQLite path, no external configuration required.

## Next Phase Readiness

- PatternDetector.async_detect() returns `List[dict]` with keys: entity_id, domain, service, day_of_week, hour, occurrences, last_seen
- Access via `hass.data[DOMAIN][entry_id]["pattern_detector"]` from Phase 6
- Access via `hass.data[DOMAIN][entry_id]["storage"]` for direct DB queries if needed
- All 73 tests green — codebase stable for Phase 6 work

## Self-Check: PASSED

Files verified:
- FOUND: custom_components/ha_ai_agent/storage.py
- FOUND: custom_components/ha_ai_agent/habit_engine.py
- FOUND: custom_components/ha_ai_agent/pattern_detector.py
- FOUND: tests/test_storage.py
- FOUND: tests/test_habit_engine.py
- FOUND: tests/test_pattern_detector.py

Commits verified:
- FOUND: 3f1370d (AgentStorage)
- FOUND: 404bf0e (HabitEngine)
- FOUND: 57d6149 (PatternDetector)
- FOUND: a2f39ef (wire __init__.py)

All 73 project tests pass.

---
*Phase: 05-habit-engine*
*Completed: 2026-04-05*
