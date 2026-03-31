---
phase: 02-conversation-bridge
plan: 02
subsystem: api
tags: [homeassistant, intent-router, regex, nlp, tdd]

requires:
  - phase: 02-conversation-bridge/02-01
    provides: IntentRouter stub wired to conversation.py, EntityContextBuilder stub, hass.data storage pattern

provides:
  - IntentRouter with compiled TURN_ON/TURN_OFF/SET_TEMP/MEDIA regex patterns (FR+EN)
  - async_route normalizes U+2019 curly apostrophe before matching
  - _dispatch resolves entity via EntityContextBuilder.resolve_entity, calls hass.services.async_call
  - ServiceNotFound and HomeAssistantError caught, return French error strings (no propagation)
  - Unrecognized commands return "Je n'ai pas compris la commande."
  - EntityContextBuilder stub updated with resolve_entity(user_entity_text) -> str | None
  - test_intent_router.py with 7 GREEN unit tests covering all intent types and error paths

affects:
  - 02-03 (EntityContextBuilder implementation — replace resolve_entity stub with real fuzzy matching)
  - 03-claude-fallback (IntentRouter feeds unmatched commands to LLM path)

tech-stack:
  added: []
  patterns:
    - "Compile regex at module level with re.IGNORECASE | re.UNICODE for zero-overhead routing"
    - "Normalize U+2019 curly apostrophe to ASCII apostrophe before regex matching (text.replace)"
    - "Lazy import EntityContextBuilder inside _dispatch to avoid circular import with entity_context.py"
    - "Patch homeassistant.core.ServiceRegistry.async_call at class level for unit tests (instance attribute is read-only)"
    - "Handle both accented (règle) and unaccented (regle) French input in regex character classes"

key-files:
  created:
    - tests/test_intent_router.py
  modified:
    - custom_components/ha_ai_agent/intent_router.py
    - custom_components/ha_ai_agent/entity_context.py

key-decisions:
  - "SET_TEMP_RE uses r[e\\u00e8]gle to match both accented and unaccented French input — must-have truth requires 'regle la temperature a 21' to work"
  - "Patch target for ServiceRegistry.async_call must be at class level (homeassistant.core.ServiceRegistry.async_call) — instance attribute is read-only in Python 3.14"
  - "EntityContextBuilder stub augmented with resolve_entity stub method so tests can patch it before plan 02-03 implements it"

patterns-established:
  - "IntentRouter._dispatch: lazy import pattern for entity_context to avoid circular dependency"
  - "Test pattern: patch EntityContextBuilder.resolve_entity on the class in entity_context module, not on the intent_router module"

requirements-completed: [NLU-02, NLU-05]

duration: ~15min
completed: 2026-03-31
---

# Phase 02 Plan 02: IntentRouter Full Implementation Summary

**FR+EN compiled regex routing for TURN_ON/TURN_OFF/SET_TEMP/MEDIA with hass.services.async_call dispatch, ServiceNotFound/HomeAssistantError handling, and U+2019 apostrophe normalization**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-31T14:12:26Z
- **Completed:** 2026-03-31T14:27:00Z
- **Tasks:** 2
- **Files modified:** 3 (intent_router.py, entity_context.py, test_intent_router.py)

## Accomplishments
- Replaced IntentRouter stub with full implementation: 4 compiled regex patterns, async_route, _dispatch
- All 7 test_intent_router.py tests green covering TURN_ON FR/EN, TURN_OFF EN, SET_TEMP, fallback, ServiceNotFound, HomeAssistantError, curly apostrophe
- EntityContextBuilder stub augmented with resolve_entity(user_entity_text) -> str | None so tests can patch it
- Full test suite: 23 passed, 2 skipped (placeholders for 02-02 in test_conversation_bridge.py)

## Task Commits

1. **Task 1: Wave 0 test scaffold (RED)** - `50c86d8` (test)
2. **Task 2: IntentRouter implementation (GREEN)** - `da3dbf8` (feat)

## Files Created/Modified
- `custom_components/ha_ai_agent/intent_router.py` — full implementation replacing stub
- `custom_components/ha_ai_agent/entity_context.py` — added resolve_entity stub method
- `tests/test_intent_router.py` — 7 unit tests for all intent types, error paths, apostrophe edge case

## Decisions Made
- SET_TEMP_RE updated to handle both `règle` (accented) and `regle` (unaccented) — the plan's interface section used the accented form but the must-have truth requires the unaccented form to work.
- Patch target for `hass.services.async_call` must be `homeassistant.core.ServiceRegistry.async_call` (class-level) since `ServiceRegistry` attributes are read-only in HA 2026.x with Python 3.14.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SET_TEMP_RE accent mismatch**
- **Found during:** Task 2 (GREEN phase — test_set_temperature failing)
- **Issue:** Plan's interface section provided `règle` (accented) in the regex, but must-have truth says "regle la temperature a 21" (unaccented) must trigger climate.set_temperature. `re.IGNORECASE` does not handle accent normalization.
- **Fix:** Changed `r\u00e8gle` to `r[e\u00e8]gle` to match both forms in a single character class.
- **Files modified:** `custom_components/ha_ai_agent/intent_router.py`
- **Verification:** `python -c "SET_TEMP_RE.match('regle la temperature a 21')"` returns match; all 7 tests green.
- **Committed in:** `da3dbf8`

**2. [Rule 3 - Blocking] EntityContextBuilder missing resolve_entity method**
- **Found during:** Task 1 (test scaffold — patch target did not exist)
- **Issue:** Tests patch `EntityContextBuilder.resolve_entity` but the stub from plan 02-01 had no such method.
- **Fix:** Added `resolve_entity(self, user_entity_text: str) -> str | None` returning `None` to the stub.
- **Files modified:** `custom_components/ha_ai_agent/entity_context.py`
- **Verification:** Patch target resolves; all 7 tests collected with no ImportError/AttributeError.
- **Committed in:** `50c86d8`

**3. [Rule 3 - Blocking] ServiceRegistry.async_call read-only in Python 3.14**
- **Found during:** Task 1 (initial test run)
- **Issue:** `patch.object(hass.services, "async_call", ...)` raises `AttributeError: 'ServiceRegistry' object attribute 'async_call' is read-only` in Python 3.14.
- **Fix:** Changed patch target to class level `homeassistant.core.ServiceRegistry.async_call`.
- **Files modified:** `tests/test_intent_router.py`
- **Verification:** Patch succeeds; mock registers calls correctly.
- **Committed in:** `50c86d8` / `da3dbf8`

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking)
**Impact on plan:** All fixes necessary for correctness and test execution. No scope creep.

## Issues Encountered
- Python 3.14 enforces read-only instance attributes on some HA core objects — requires class-level patching for ServiceRegistry.
- When patching `ServiceRegistry.async_call` at class level with `new=AsyncMock(...)`, Python passes `self` automatically so assertions should NOT include the instance as first arg.

## Known Stubs
- `EntityContextBuilder.resolve_entity` in `entity_context.py` returns `None` for all inputs — plan 02-03 will implement real fuzzy entity matching. Tests mock this method to return a specific entity_id.

## Next Phase Readiness
- Plan 02-03 can start: `EntityContextBuilder.resolve_entity` stub is in place with correct signature
- IntentRouter fully tested and production-ready pending real entity resolution
- The 2 skipped tests in `test_conversation_bridge.py` (test_confirmation_message_after_turn_on, test_entity_not_found_returns_error) can now be activated in 02-03

---
*Phase: 02-conversation-bridge*
*Completed: 2026-03-31*
