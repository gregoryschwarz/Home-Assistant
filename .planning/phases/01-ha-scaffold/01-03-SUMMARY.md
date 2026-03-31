---
phase: 01-ha-scaffold
plan: 03
subsystem: infra
tags: [homeassistant, custom-component, conversation-entity, pytest, python, voice-assistant]

# Dependency graph
requires:
  - phase: 01-01
    provides: "conversation.py stub + PLATFORMS=['conversation'] + async_forward_entry_setups/async_unload_platforms lifecycle"
provides:
  - "HaAiConversationAgent(ConversationEntity) with echo stub — selectable agent in HA Voice Assistants (HA-04)"
  - "Verified HA 2026.3.4 import paths for ConversationEntity, AssistantContent, ChatLog, ConversationResult"
  - "tests/test_conversation.py: 4 tests covering entity registration, unique_id, supported_languages, reload safety"
affects:
  - 02 (IntentRouter replaces _async_handle_message body)
  - 03 (Claude API client called from _async_handle_message)
  - all future conversation phases

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ConversationEntity subclass registered via async_add_entities in platform async_setup_entry"
    - "_async_handle_message(user_input: ConversationInput, chat_log: ChatLog) -> ConversationResult"
    - "AssistantContent added to chat_log before returning ConversationResult"
    - "IntentResponse(language) + async_set_speech() for response assembly"
    - "_attr_unique_id = entry.entry_id — entity deregisters with config entry"

key-files:
  created:
    - tests/test_conversation.py
  modified:
    - custom_components/ha_ai_agent/conversation.py

key-decisions:
  - "AssistantContent imports from top-level homeassistant.components.conversation (not .models or .chat_log)"
  - "_async_handle_message takes (user_input, chat_log) — ChatLog parameter required for response assembly"
  - "ConversationResult constructor: (response: IntentResponse, conversation_id: str | None)"
  - "entity_registry access in tests uses homeassistant.helpers.entity_registry.async_get(hass)"

patterns-established:
  - "Test pattern: entity_registry access via er.async_get(hass) from homeassistant.helpers.entity_registry"
  - "Conversation pattern: always call chat_log.async_add_assistant_content_without_tools before returning ConversationResult"

requirements-completed: [HA-04, HA-03]

# Metrics
duration: 15min
completed: 2026-03-30
---

# Phase 1 Plan 03: Conversation Entity Summary

**HaAiConversationAgent(ConversationEntity) echo scaffold registered via PLATFORMS=['conversation'], verified on HA 2026.3.4 — 14 Phase 1 tests pass**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-30T00:00:00Z
- **Completed:** 2026-03-30
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Verified exact HA 2026.3.4 import paths: AssistantContent, ChatLog, ConversationResult all importable from top-level `homeassistant.components.conversation`; `_async_handle_message(user_input, chat_log)` signature confirmed from base class
- `conversation.py` stub replaced with full `HaAiConversationAgent(ConversationEntity)` — entity registers via platform lifecycle, appears selectable in Voice Assistants (HA-04); unloads cleanly on entry reload (HA-03)
- All 14 Phase 1 tests pass: 4 conversation + 4 init + 4 config_flow + 2 manifest

## Task Commits

1. **Task 1: Inspect HA source + create test_conversation.py** - `43a06e1` (feat)
2. **Task 2: Implement HaAiConversationAgent in conversation.py** - `4c2f46d` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/test_conversation.py` — 4 tests: entity registration, unique_id, supported_languages, reload safety; import inspection comments documenting verified HA 2026.3.4 paths
- `custom_components/ha_ai_agent/conversation.py` — replaces no-op stub with HaAiConversationAgent(ConversationEntity): async_setup_entry, supported_languages=['fr','en'], _async_handle_message echo stub

## Decisions Made

- AssistantContent is re-exported from the top-level `homeassistant.components.conversation` module — no sub-module import needed (`.models` and `.chat_log` also work but top-level is cleaner)
- `_async_handle_message` must receive `ChatLog` as second parameter (not optional) — required for `async_add_assistant_content_without_tools` call which HA requires before returning ConversationResult
- Entity registry access in tests: use `from homeassistant.helpers import entity_registry as er; er.async_get(hass)` — the `hass.helpers.entity_registry.async_get(hass)` variant from the plan template also works on HA 2026.x

## Deviations from Plan

None - plan executed exactly as written. Verified import paths matched the plan's template paths. No import path adjustments were needed.

## Issues Encountered

None. All HA imports verified successfully. The full test suite was passing on first run after implementing conversation.py.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 (IntentRouter): replace `_async_handle_message` body in `conversation.py` with intent routing. The method signature and ConversationResult construction pattern are established.
- Phase 3 (Claude API): add Claude client call as fallback in `_async_handle_message`. The entry_id-keyed data store in `hass.data[DOMAIN][entry.entry_id]` is available for storing the client.
- All Phase 1 requirements complete: HA-01 (loads), HA-02 (config flow), HA-03 (reload), HA-04 (conversation agent)
- Verified import paths documented in test_conversation.py header — Phase 2/3 can use these directly without re-inspection

## Known Stubs

- `custom_components/ha_ai_agent/conversation.py` — `_async_handle_message` returns echo text stub (`[HA AI Agent scaffold] Received: {user_input.text}`). Intentional Phase 1 placeholder. Phase 2 (IntentRouter) replaces this body with actual intent routing. The echo text does flow to HA Voice Assistants UI — it is a valid ConversationResult, not a null/empty response.

---
*Phase: 01-ha-scaffold*
*Completed: 2026-03-30*
