---
phase: 02-conversation-bridge
plan: 03
subsystem: api
tags: [homeassistant, entity-resolution, nlp, regex, tdd, config-flow, options-flow]

requires:
  - phase: 02-conversation-bridge/02-01
    provides: EntityContextBuilder stub with resolve_entity method, conversation.py wired to IntentRouter
  - phase: 02-conversation-bridge/02-02
    provides: IntentRouter with compiled regex patterns, _dispatch calling EntityContextBuilder.resolve_entity

provides:
  - EntityContextBuilder with 3-pass entity resolution cascade (slug/registry-name/alias) and domain whitelist
  - _normalize helper: NFKD accent stripping, French article removal, U+2019 curly apostrophe handling
  - HaAiAgentOptionsFlow for SEC-03 domain whitelist UI configuration
  - async_get_options_flow classmethod registered on HaAiAgentConfigFlow
  - tests/test_entity_resolver.py with 5 GREEN unit tests covering all resolution passes
  - test_conversation_bridge.py end-to-end tests now active (0 skipped)

affects:
  - 03-claude-fallback (IntentRouter now resolves real entities, LLM fallback gets accurate context)

tech-stack:
  added: []
  patterns:
    - "3-pass entity resolution: Pass 1 slug (hass.states.get), Pass 2 registry name match (er.async_get), Pass 3 alias match"
    - "_normalize: text.replace(U+2019) -> NFKD decompose -> strip combining chars -> FRENCH_ARTICLES.sub -> lowercase underscore slug"
    - "er.async_get(hass) synchronous call safe on event loop for registry iteration"
    - "entry.aliases guard: (entry.aliases or []) handles None and frozenset"
    - "OptionsFlow pattern: HaAiAgentOptionsFlow(OptionsFlow) with async_step_init reading self.config_entry.options"

key-files:
  created:
    - tests/test_entity_resolver.py
  modified:
    - custom_components/ha_ai_agent/entity_context.py
    - custom_components/ha_ai_agent/config_flow.py
    - tests/test_conversation_bridge.py

key-decisions:
  - "3-pass cascade order: slug first (O(1)), registry name second, alias third — optimized for common case"
  - "Substring matching in both directions (normalized in norm_candidate OR norm_candidate in normalized) for partial name coverage"
  - "ConversationInput requires device_id and satellite_id in HA 2026.x — test_conversation_bridge tests fixed with explicit None values"

patterns-established:
  - "Entity resolution: normalize user text to slug, compare against domain-filtered registry entries"
  - "Test pattern for OptionsFlow: verify class existence and async_get_options_flow registration"

requirements-completed: [NLU-01, SEC-03]

duration: ~10min
completed: 2026-03-31
---

# Phase 02 Plan 03: EntityContextBuilder 3-Pass Resolution and OptionsFlow Summary

**EntityContextBuilder with slug/registry-name/alias 3-pass cascade replacing stub, domain whitelist enforced, HaAiAgentOptionsFlow wired — 30 tests pass, 0 skipped**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-31T14:26:52Z
- **Completed:** 2026-03-31T14:37:00Z
- **Tasks:** 2
- **Files modified:** 4 (entity_context.py, config_flow.py, test_entity_resolver.py, test_conversation_bridge.py)

## Accomplishments
- Replaced EntityContextBuilder stub with full 3-pass cascade: Pass 1 slug (hass.states.get), Pass 2 registry original_name/name match, Pass 3 alias match
- _normalize helper strips NFKD accents, French articles, handles U+2019 curly apostrophe
- HaAiAgentOptionsFlow added to config_flow.py with CONF_ALLOWED_DOMAINS vol.Schema; async_get_options_flow registered on HaAiAgentConfigFlow
- All 30 tests GREEN, 0 skipped (including 2 previously-skipped end-to-end tests in test_conversation_bridge.py)

## Task Commits

1. **Task 1: Wave 0 RED scaffold** - `500b8b9` (test)
2. **Task 2: EntityContextBuilder + OptionsFlowHandler GREEN** - `c913d35` (feat)

## Files Created/Modified
- `custom_components/ha_ai_agent/entity_context.py` — full 3-pass implementation replacing stub
- `custom_components/ha_ai_agent/config_flow.py` — HaAiAgentOptionsFlow + async_get_options_flow classmethod
- `tests/test_entity_resolver.py` — 5 unit tests: slug, registry name, domain whitelist, curly apostrophe, alias
- `tests/test_conversation_bridge.py` — activated 2 previously-skipped end-to-end tests

## Decisions Made
- Substring match in both directions (`normalized in norm_candidate OR norm_candidate in normalized`) covers both abbreviated input ("cuisine" matching "Lumiere Cuisine") and full user phrases containing the entity name.
- ConversationInput in HA 2026.x requires `device_id` and `satellite_id` args — needed for the two reactivated bridge tests (Rule 1 auto-fix).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ConversationInput missing required device_id and satellite_id arguments**
- **Found during:** Task 2 (GREEN phase — test_confirmation_message_after_turn_on failing with TypeError)
- **Issue:** Plan's test code template did not include `device_id=None, satellite_id=None` — HA 2026.x ConversationInput.__init__ requires both parameters
- **Fix:** Added `device_id=None, satellite_id=None` to both ConversationInput instantiations in test_conversation_bridge.py
- **Files modified:** `tests/test_conversation_bridge.py`
- **Verification:** Both end-to-end tests pass after fix; full suite 30/30 green
- **Committed in:** `c913d35`

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix necessary for correct test execution. No scope creep.

## Issues Encountered
- 02-02 commits existed in `worktree-agent-acc08120` branch but not in `master`. Merge required before plan could proceed. STATE.md merge conflict resolved by keeping 02-02 version.

## Known Stubs
None — EntityContextBuilder.resolve_entity is fully implemented. All previously-stubbed functionality is now production-ready.

## Next Phase Readiness
- Phase 2 complete: NLU-01, NLU-02, NLU-04, NLU-05, SEC-03 all implemented and tested
- Phase 3 (claude-fallback) can start: IntentRouter passes unmatched commands, entity context is real
- No known blockers for Phase 3

---
*Phase: 02-conversation-bridge*
*Completed: 2026-03-31*

## Self-Check: PASSED

- FOUND: entity_context.py
- FOUND: config_flow.py
- FOUND: test_entity_resolver.py
- FOUND: 02-03-SUMMARY.md
- FOUND commit 500b8b9 (test RED scaffold)
- FOUND commit c913d35 (feat GREEN implementation)
