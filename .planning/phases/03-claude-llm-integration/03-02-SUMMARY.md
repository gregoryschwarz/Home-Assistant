---
phase: 03-claude-llm-integration
plan: 02
subsystem: nlu
tags: [intent-router, conversation, claude-client, llm-fallback, entity-context]

# Dependency graph
requires:
  - phase: 03-01
    provides: ClaudeClient.async_complete and hass.data[DOMAIN][entry_id]['claude_client']
  - phase: 02-conversation-bridge
    provides: IntentRouter.async_route and conversation.py _async_handle_message

provides:
  - IntentRouter.async_route returns str | None (None = LLM fallback sentinel)
  - conversation.py None-check branch delegating unrecognized commands to ClaudeClient
  - Final fallback string 'Je n ai pas compris la commande.' when Claude also returns None

affects: [03-03, 04-voice-pipeline, any code reading async_route return value]

# Tech tracking
tech-stack:
  added: []
  patterns: [sentinel-None LLM handoff, graceful double-fallback chain]

key-files:
  created: []
  modified:
    - custom_components/ha_ai_agent/intent_router.py
    - custom_components/ha_ai_agent/conversation.py
    - tests/test_intent_router.py

key-decisions:
  - "async_route returns None (not a hardcoded string) as sentinel so conversation.py controls fallback wording"
  - "Final fallback 'Je n ai pas compris la commande.' lives in conversation.py, not IntentRouter, keeping router stateless"
  - "Test input changed from 'joue de la guitare' to 'mets l ambiance pour un film' — 'joue' matches MEDIA_RE pattern"

patterns-established:
  - "None-sentinel pattern: router returns None, caller decides fallback — clean separation of concerns"
  - "Double-fallback chain: regex -> LLM -> hardcoded string ensures response_text is always non-None before chat_log"

requirements-completed: [NLU-03]

# Metrics
duration: 2min
completed: 2026-04-01
---

# Phase 03 Plan 02: LLM Fallback Wiring Summary

**IntentRouter now returns None as LLM sentinel; conversation.py delegates unrecognized commands to ClaudeClient with entity context and final hardcoded fallback**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-01T11:04:07Z
- **Completed:** 2026-04-01T11:05:47Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `async_route` return type widened to `str | None` — None signals no regex match (D-01)
- `conversation.py` None-check branch calls `claude_client.async_complete(text, entities)` with filtered entity list (D-02)
- Double-fallback chain ensures `response_text` is always a non-None string before the `chat_log` call (D-03)
- Full test suite passes: 41 tests, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Change IntentRouter sentinel and update test** - `ddc3ab5` (feat)
2. **Task 2: Wire LLM fallback in conversation.py** - `b1b03fd` (feat)

**Plan metadata:** pending docs commit (docs: complete plan)

## Files Created/Modified

- `custom_components/ha_ai_agent/intent_router.py` - Return type `str | None`, line 97 returns `None` instead of hardcoded string
- `custom_components/ha_ai_agent/conversation.py` - 10-line None-check block after `async_route` call wiring ClaudeClient and entity context
- `tests/test_intent_router.py` - `test_unrecognized_command_returns_fallback` now asserts `result is None`

## Decisions Made

- `async_route` returns `None` (sentinel) rather than a hardcoded fallback string — keeps the router stateless and lets `conversation.py` own the user-facing error message wording
- Test input changed from `"joue de la guitare"` to `"mets l'ambiance pour un film"` — `"joue"` is matched by `MEDIA_RE` (joue[rz]?), so the original test input was not actually unrecognized

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test input "joue de la guitare" matched MEDIA_RE pattern**
- **Found during:** Task 1 (test verification)
- **Issue:** "joue de la guitare" matched `joue[rz]?` in MEDIA_RE, returned "Entite introuvable : de la guitare." instead of None
- **Fix:** Changed test input to "mets l'ambiance pour un film" which truly matches no compiled regex
- **Files modified:** tests/test_intent_router.py
- **Verification:** pytest tests/test_intent_router.py -x -q — 7/7 pass
- **Committed in:** ddc3ab5 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test input assumption)
**Impact on plan:** Fix required for correctness. No scope creep.

## Issues Encountered

- The plan's example unrecognized input "joue de la guitare" was actually caught by the MEDIA_RE pattern (joue[rz]? matches "joue"). Substituted with "mets l'ambiance pour un film" which passes through all four regex patterns without matching.

## Known Stubs

None — conversation.py accesses `entity_context.list_entities_for_llm` at runtime. This method was implemented in plan 03-03 (wave 2, parallel execution). If 03-03 was not yet executed when this code runs, the AttributeError will surface at runtime. No stub in the code itself.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- LLM fallback path fully wired: regex miss -> Claude -> hardcoded fallback
- Plan 03-03 (EntityContextBuilder.list_entities_for_llm) must be complete before the full path can be tested end-to-end in a live HA instance
- Phase 4 (voice pipeline) can proceed — conversation.py fallback is language-agnostic

---
*Phase: 03-claude-llm-integration*
*Completed: 2026-04-01*

## Self-Check: PASSED

- FOUND: custom_components/ha_ai_agent/intent_router.py
- FOUND: custom_components/ha_ai_agent/conversation.py
- FOUND: tests/test_intent_router.py
- FOUND: .planning/phases/03-claude-llm-integration/03-02-SUMMARY.md
- FOUND commit: ddc3ab5 (Task 1)
- FOUND commit: b1b03fd (Task 2)
