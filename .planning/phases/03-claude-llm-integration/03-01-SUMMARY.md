---
phase: 03-claude-llm-integration
plan: 01
subsystem: api
tags: [anthropic, claude, async, tool_use, llm, homeassistant]

# Dependency graph
requires:
  - phase: 02-conversation-bridge
    provides: EntityContextBuilder with entity registry access, IntentRouter for local NLU

provides:
  - ClaudeClient async wrapper with async_complete, _handle_response, _execute_service, async_close
  - const.py extended with SYSTEM_PROMPT, MAX_HISTORY_TURNS, EXECUTE_HA_SERVICE_TOOL
  - __init__.py lifecycle integration: ClaudeClient instantiated at setup, closed at unload
  - 7 unit tests in test_claude_client.py covering all core behaviors

affects: [03-claude-llm-integration/03-02, conversation.py fallback branch, entity_context list_entities_for_llm]

# Tech tracking
tech-stack:
  added: [anthropic>=0.27,<1 (AsyncAnthropic SDK)]
  patterns:
    - AsyncAnthropic with timeout=10.0 and max_retries=0 for manual retry control
    - deque(maxlen=MAX_HISTORY_TURNS) for sliding window conversation history
    - Pitfall 1 avoidance — store only text strings in history (not raw content blocks)
    - French error string returns for all error cases (no re-raise)

key-files:
  created:
    - custom_components/ha_ai_agent/claude_client.py
    - tests/test_claude_client.py
  modified:
    - custom_components/ha_ai_agent/const.py
    - custom_components/ha_ai_agent/__init__.py

key-decisions:
  - "AsyncAnthropic initialized with timeout=10.0 (D-07) and max_retries=0 (D-04) for exact retry control"
  - "History stores text-only strings to avoid tool_use block / tool_result mismatch (Pitfall 1)"
  - "D-11 domain validation in ClaudeClient._handle_response — rejects non-allowed domains before hass.services.async_call"
  - "anthropic SDK installed as dev dependency (not in manifest.json requirements yet — needed for test environment)"

patterns-established:
  - "Pattern: import module at top of test file to allow patch() to resolve dotted path"
  - "Pattern: ClaudeClient.async_close() called in async_unload_entry before hass.data pop"

requirements-completed: [NLU-03, SEC-01]

# Metrics
duration: 3min
completed: 2026-04-01
---

# Phase 03 Plan 01: ClaudeClient LLM Wrapper Summary

**AsyncAnthropic wrapper with tool_use dispatch, 10-turn sliding window history, domain validation, and French error handling wired into HA component lifecycle**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-01T10:56:49Z
- **Completed:** 2026-04-01T11:00:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `claude_client.py` with ClaudeClient class: async_complete (retry loop, system prompt, entity list), _handle_response (tool_use + end_turn branches), _execute_service (hass.services.async_call), async_close
- Extended `const.py` with SYSTEM_PROMPT (French persona, allowed_domains placeholder), MAX_HISTORY_TURNS=10, EXECUTE_HA_SERVICE_TOOL JSON schema
- Wired ClaudeClient into `__init__.py`: instantiated in async_setup_entry with entry.data[CONF_API_KEY], closed in async_unload_entry
- 7 unit tests pass: tool_use dispatch, free text return, auth error (D-19), connection error (D-18), domain validation rejection (D-11), history cap, async_close

## Task Commits

1. **Task 1: Add constants and create ClaudeClient** - `2ad3739` (feat)
2. **Task 2: Wire ClaudeClient into component lifecycle** - `28179c6` (feat)

## Files Created/Modified

- `custom_components/ha_ai_agent/claude_client.py` — ClaudeClient async wrapper around AsyncAnthropic
- `custom_components/ha_ai_agent/const.py` — Added SYSTEM_PROMPT, MAX_HISTORY_TURNS, EXECUTE_HA_SERVICE_TOOL
- `custom_components/ha_ai_agent/__init__.py` — ClaudeClient instantiation at setup, async_close at unload
- `tests/test_claude_client.py` — 7 unit tests covering all core behaviors

## Decisions Made

- Used `max_retries=0` on AsyncAnthropic and manual retry loop with `asyncio.sleep(1)` per D-04 — SDK retries don't cover APITimeoutError with custom 10s timeout
- History stores only text strings (not raw content blocks) to avoid the tool_use / tool_result turn mismatch (Pitfall 1 from RESEARCH.md)
- `anthropic` package installed via pip (`anthropic>=0.27,<1`) since not pre-installed in dev environment; already declared in manifest.json for HA runtime

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Install anthropic SDK in test environment**
- **Found during:** Task 1 (RED phase test run)
- **Issue:** `anthropic` package not installed in dev environment, causing ModuleNotFoundError on test collection
- **Fix:** Ran `py -m pip install "anthropic>=0.27,<1"` — package already declared in manifest.json for HA runtime
- **Files modified:** None (environment install only)
- **Verification:** Tests collect and run successfully
- **Committed in:** N/A (environment setup, not a code change)

**2. [Rule 3 - Blocking] Add top-level module import in test file to allow patch() resolution**
- **Found during:** Task 1 (GREEN phase, first test run)
- **Issue:** `patch("custom_components.ha_ai_agent.claude_client.AsyncAnthropic")` raised AttributeError because `claude_client` submodule was not yet imported into the parent package namespace
- **Fix:** Added `import custom_components.ha_ai_agent.claude_client` at the top of the test file so `patch()` can resolve the dotted path
- **Files modified:** `tests/test_claude_client.py`
- **Verification:** All 7 tests pass
- **Committed in:** `2ad3739` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes were blocking environment/import issues, not behavioral changes. No scope creep.

## Issues Encountered

- `patch()` cannot resolve `custom_components.ha_ai_agent.claude_client.AsyncAnthropic` without the module being imported first — fixed by adding explicit module import at test file top level. This is a standard Python patching pattern for submodules.

## Known Stubs

None — ClaudeClient is fully wired. SYSTEM_PROMPT uses `{allowed_domains}` placeholder that is formatted at call time with the live allowed_domains list.

## User Setup Required

None — API key is already stored in entry.data[CONF_API_KEY] from Phase 1 config flow. No new environment variables required.

## Next Phase Readiness

- ClaudeClient is ready for Plan 03-02: conversation.py needs the None-sentinel branch from IntentRouter and the `claude_client.async_complete()` call
- `entity_context.list_entities_for_llm()` is already implemented (Plan 03-03 parallel agent)
- `intent_router.py` line 96 sentinel change (return None) is deferred to Plan 03-02

---
*Phase: 03-claude-llm-integration*
*Completed: 2026-04-01*
