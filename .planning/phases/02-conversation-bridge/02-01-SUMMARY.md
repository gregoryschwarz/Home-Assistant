---
phase: 02-conversation-bridge
plan: 01
subsystem: api
tags: [homeassistant, intent-router, conversation-entity, tdd]

requires:
  - phase: 01-ha-scaffold
    provides: HaAiConversationAgent echo stub + async_setup_entry base pattern

provides:
  - _async_handle_message wired to IntentRouter.async_route (echo stub removed)
  - IntentRouter + EntityContextBuilder instantiated and stored in hass.data at setup
  - Stub intent_router.py and entity_context.py so imports resolve without error
  - CONF_ALLOWED_DOMAINS / DEFAULT_ALLOWED_DOMAINS constants in const.py
  - test_conversation_bridge.py with 2 GREEN routing tests + 2 skipped placeholders

affects:
  - 02-02 (entity control — fills IntentRouter stub)
  - 02-03 (entity context — fills EntityContextBuilder stub)
  - 03-claude-fallback (conversation.py routing path)

tech-stack:
  added: []
  patterns:
    - "Patch where the name is used (custom_components.ha_ai_agent.IntentRouter), not where it is defined"
    - "hass.data[DOMAIN][entry_id]['router'] / ['entity_context'] for cross-platform object sharing"

key-files:
  created:
    - custom_components/ha_ai_agent/intent_router.py
    - custom_components/ha_ai_agent/entity_context.py
    - tests/test_conversation_bridge.py
  modified:
    - custom_components/ha_ai_agent/__init__.py
    - custom_components/ha_ai_agent/conversation.py
    - custom_components/ha_ai_agent/const.py

key-decisions:
  - "Patch target must be the imported name in __init__.py (custom_components.ha_ai_agent.IntentRouter), not intent_router.IntentRouter — otherwise the mock never replaces the already-bound reference"
  - "Stubs created for intent_router.py and entity_context.py so async_setup_entry imports succeed before plans 02-02/02-03 fill them"

patterns-established:
  - "Router stored in hass.data[DOMAIN][entry_id]['router'] — conversation.py retrieves via self.hass.data[DOMAIN][self._entry.entry_id]"

requirements-completed: [NLU-01, NLU-04]

duration: ~20min (cross-session)
completed: 2026-03-31
---

# Plan 02-01: Conversation Bridge Wiring Summary

**`_async_handle_message` wired to `IntentRouter.async_route`, echo stub removed, stubs for 02-02/02-03 in place — 16 tests green**

## Performance

- **Duration:** ~20 min (split across two sessions)
- **Completed:** 2026-03-31
- **Tasks:** 2
- **Files modified:** 5 + 2 created

## Accomplishments
- Replaced Phase 1 echo stub with real `IntentRouter` dispatch in `conversation.py`
- `async_setup_entry` now stores `router` and `entity_context` in `hass.data`
- Stub modules (`intent_router.py`, `entity_context.py`) allow imports to resolve without error
- `CONF_ALLOWED_DOMAINS` / `DEFAULT_ALLOWED_DOMAINS` added to `const.py`
- `test_conversation_bridge.py` : 2 GREEN tests (routing + hass.data storage), 2 skipped placeholders for 02-02

## Task Commits

1. **Task 1: Wave 0 test scaffold** - `6dc8b7f` (test)
2. **Task 2: Wire __init__.py + conversation.py** — unstaged changes (fix patch path inclus)

## Files Created/Modified
- `custom_components/ha_ai_agent/conversation.py` — echo stub remplacé par `router.async_route`
- `custom_components/ha_ai_agent/__init__.py` — IntentRouter + EntityContextBuilder instanciés au setup
- `custom_components/ha_ai_agent/const.py` — CONF_ALLOWED_DOMAINS + DEFAULT_ALLOWED_DOMAINS
- `custom_components/ha_ai_agent/intent_router.py` — stub (retourne `[stub] {text}`)
- `custom_components/ha_ai_agent/entity_context.py` — stub
- `tests/test_conversation_bridge.py` — fix patch target + 4 tests (2 green, 2 skipped)

## Decisions Made
- **Patch target corrigé :** `custom_components.ha_ai_agent.IntentRouter` (référence importée dans `__init__.py`) plutôt que `custom_components.ha_ai_agent.intent_router.IntentRouter`. Le test généré dans Task 1 patchait la mauvaise cible — Python lie la référence à l'import, pas au module source.

## Deviations from Plan
### Auto-fixed Issues
**1. Patch target incorrect dans test_conversation_bridge.py**
- **Found during:** Reprise de session — tests RED malgré le code correct
- **Issue:** `sys.modules.setdefault` sans effet (module déjà chargé) + patch sur la définition au lieu de l'utilisation
- **Fix:** Simplifié le test pour patcher `custom_components.ha_ai_agent.IntentRouter`
- **Files modified:** `tests/test_conversation_bridge.py`
- **Verification:** `pytest tests/ — 16 passed, 2 skipped`

---
**Total deviations:** 1 auto-fixed (patch path)
**Impact on plan:** Fix nécessaire pour la correction du test. Pas de scope creep.

## Issues Encountered
- `sys.modules.setdefault` dans le test n'avait aucun effet car `intent_router.py` existe déjà et est chargé au démarrage — le mock module injecté était ignoré.

## Next Phase Readiness
- Plan 02-02 peut démarrer : `IntentRouter.async_route` est appelé correctement depuis `conversation.py`
- Les tests 3-4 (`test_confirmation_message_after_turn_on`, `test_entity_not_found_returns_error`) attendent 02-02
- Bloceur vérifié : `IntentRouter` import path OK — `from custom_components.ha_ai_agent.intent_router import IntentRouter`

---
*Phase: 02-conversation-bridge*
*Completed: 2026-03-31*
