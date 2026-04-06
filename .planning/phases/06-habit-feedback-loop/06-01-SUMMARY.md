---
phase: 06-habit-feedback-loop
plan: "01"
subsystem: llm-integration
tags: [anthropic, habits, context-injection, pattern-detection, sqlite]

# Dependency graph
requires:
  - phase: 05-habit-engine
    provides: PatternDetector.async_get_patterns(), patterns table schema (entity_id, domain, service, day_of_week, hour, occurrences)
  - phase: 03-claude-llm-integration
    provides: ClaudeClient.async_complete(text, entities) — extended in this plan
provides:
  - ClaudeClient.async_complete(text, entities, habits=None) — optional habits injection
  - HaAiConversationAgent._filter_relevant_habits() — contextual habit filtering (entity match + ±2h window)
  - "Habitudes connues" block injected in Claude message when relevant habits exist
affects:
  - 06-02-proactive-notifications — pattern_detector already wired in conversation.py

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "habits=None default param: opt-in habit injection, fully backward-compatible"
    - "Contextual filtering: entity_id substring match OR hour delta ≤ 2 (modulo 24)"
    - "Guard pattern: entry_data.get('pattern_detector') + try/except — habit fetch never crashes agent"

key-files:
  created:
    - tests/test_habit_injection.py
    - .planning/phases/06-habit-feedback-loop/06-01-PLAN.md
  modified:
    - custom_components/ha_ai_agent/claude_client.py
    - custom_components/ha_ai_agent/conversation.py

key-decisions:
  - "SQLite strftime('%w') stores 0=Sunday: _DOW_NAMES[0]='dimanche' matches Phase 5 storage convention"
  - "habits=[] and habits=None both suppress injection (D-02): single `if habits:` guard handles both"
  - "Habit fetch wrapped in try/except BLE001: pattern_detector errors must never propagate to user"
  - "relevant_habits or None passed to async_complete: empty list treated as no-injection (D-02)"

patterns-established:
  - "Phase 6 filtering: _filter_relevant_habits is a pure static method — testable without HA fixtures"
  - "Habits block format: 'Habitudes connues (contexte personnel) :' prefix, one line per habit"

requirements-completed: [HABIT-04]

# Metrics
duration: 4min
completed: 2026-04-05
---

# Phase 6 Plan 01: Habit Context Injection Summary

**ClaudeClient extended with optional habits param that injects "Habitudes connues" block; conversation.py wires PatternDetector filtering (entity_id mention OR ±2h time window) before every Claude fallback call.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-05T19:00:21Z
- **Completed:** 2026-04-05T19:04:36Z
- **Tasks:** 3
- **Files modified:** 3 (+ 1 test file created)

## Accomplishments

- `async_complete(text, entities, habits=None)` — backward-compatible extension with French-named habits block injected after entity list
- `_filter_relevant_habits(habits, text, current_hour)` pure static method with dual matching: entity_id substring OR ±2h modulo-24 time window
- 8 new tests (all passing), full regression suite at 87/87

## Task Commits

1. **Task 1: Extend ClaudeClient.async_complete with habits parameter** - `62a8f68` (feat)
2. **Task 2: Add habit filtering helper in conversation.py** - `ec6b89f` (feat)
3. **Task 3: Tests for habit injection** - `9874b23` (test)

## Files Created/Modified

- `custom_components/ha_ai_agent/claude_client.py` — `_DOW_NAMES` class attr, extended `async_complete` signature, habits block construction
- `custom_components/ha_ai_agent/conversation.py` — `import datetime`, `_filter_relevant_habits` static method, pattern_detector retrieval + filtering in `_async_handle_message`
- `tests/test_habit_injection.py` — 8 tests covering injection, non-injection, entity filter, time filter, combined, midnight wrap

## Decisions Made

- **SQLite day_of_week convention:** Phase 5 uses SQLite `strftime('%w', ...)` which yields 0=Sunday. `_DOW_NAMES` is indexed accordingly (dimanche=0, lundi=1, ..., samedi=6).
- **`habits=[]` treated same as `None`:** The guard `if habits:` handles both falsy cases identically, matching D-02 (no injection when empty).
- **Exception guard for habit fetch:** `try/except Exception` with `relevant_habits = []` fallback ensures pattern_detector errors (e.g., DB locked) never surface to the user.
- **`relevant_habits or None` to async_complete:** Converts empty list to None for cleaner downstream check.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 06-02 (proactive notifications) can now access `pattern_detector` from `entry_data` — already wired in `__init__.py` and accessible from conversation.py
- `async_detect_patterns()` (upsert + return) is the entry point for notification triggering; `async_get_patterns()` is already used here for context injection

---
*Phase: 06-habit-feedback-loop*
*Completed: 2026-04-05*
