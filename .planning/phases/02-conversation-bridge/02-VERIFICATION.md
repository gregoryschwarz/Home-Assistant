---
phase: 02-conversation-bridge
verified: 2026-03-31T16:00:00Z
status: passed
score: 15/15 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 14/15
  gaps_closed:
    - "REQUIREMENTS.md NLU-04 checkbox updated to [x] and traceability row updated to Complete"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Install the component in a real HA instance, send 'allume la lumiere du salon' via a Voice Assistant panel"
    expected: "The light entity turns on and the assistant reads back a French confirmation such as 'D\u2019accord, j\u2019ai allume lumiere du salon.'"
    why_human: "End-to-end voice pipeline (assist_pipeline TTS readback) cannot be exercised in unit tests"
  - test: "Open HA UI > Settings > Devices & Services > HA AI Agent > Configure (Options flow)"
    expected: "A form appears allowing the user to edit the domain whitelist (light, switch, climate, media_player by default)"
    why_human: "OptionsFlow UI rendering cannot be verified programmatically"
---

# Phase 02: Conversation Bridge — Verification Report

**Phase Goal:** Text commands control HA entities via local rules, no LLM required
**Verified:** 2026-03-31T16:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (NLU-04 documentation fix)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `_async_handle_message` routes to `IntentRouter`, not echo | VERIFIED | `conversation.py:82-86` — `router.async_route()` called, no echo string present |
| 2 | `IntentRouter` response text appears in `ConversationResult` speech | VERIFIED | `conversation.py:94-100` — `intent_response.async_set_speech(response_text)` |
| 3 | `IntentRouter` instantiated in `async_setup_entry`, stored in `hass.data` | VERIFIED | `__init__.py:18-24` — `router = IntentRouter(...)`, stored at `hass.data[DOMAIN][entry.entry_id]["router"]` |
| 4 | Echo stub removed from `conversation.py` | VERIFIED | grep confirms no `scaffold.*Received` string; file has 101 lines of real routing code |
| 5 | French/English TURN_ON/TURN_OFF triggers correct `hass.services.async_call` | VERIFIED | `intent_router.py:78-84`, 4 compiled regex patterns; `test_turn_on_french` + `test_turn_off_english` green |
| 6 | SET_TEMP triggers `climate.set_temperature` with `temperature` float | VERIFIED | `intent_router.py:86-91`; `test_set_temperature` green, including unaccented `regle` variant |
| 7 | Unrecognized command returns French fallback string | VERIFIED | `intent_router.py:96` returns `"Je n'ai pas compris la commande."` |
| 8 | `ServiceNotFound` returns French error string, no exception propagation | VERIFIED | `intent_router.py:135-139`; `test_service_not_found_returns_error` green |
| 9 | `HomeAssistantError` returns French error string, no exception propagation | VERIFIED | `intent_router.py:141-143`; `test_homeassistant_error_returns_error` green |
| 10 | U+2019 curly apostrophe normalized before matching | VERIFIED | `intent_router.py:76` — `text.replace("\u2019", "'")`; `test_curly_apostrophe` green |
| 11 | `resolve_entity("lumiere du salon")` returns `light.salon` via slug normalization | VERIFIED | `entity_context.py:44-48` Pass 1; `test_slug_resolution` green |
| 12 | Registry name substring match returns correct `entity_id` (Pass 2) | VERIFIED | `entity_context.py:51-68`; `test_registry_name_match` green |
| 13 | Domain whitelist blocks out-of-whitelist entities | VERIFIED | `entity_context.py:53` — domain filter; `test_domain_whitelist_blocks` green |
| 14 | `HaAiAgentOptionsFlow` exists and `async_get_options_flow` registered | VERIFIED | `config_flow.py:49-53` (classmethod) + `config_flow.py:56-76` (class definition) |
| 15 | REQUIREMENTS.md marks NLU-04 as complete | VERIFIED | Line 20: `[x] **NLU-04**`; line 81: `NLU-04 \| Phase 2 \| Complete` |

**Score:** 15/15 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/ha_ai_agent/conversation.py` | `_async_handle_message` wired to `IntentRouter` | VERIFIED | 101 lines; `router.async_route` at line 83; no echo stub |
| `custom_components/ha_ai_agent/__init__.py` | `IntentRouter` + `EntityContextBuilder` instantiated at setup | VERIFIED | 35 lines; both instantiated lines 18-19, stored in `hass.data` |
| `custom_components/ha_ai_agent/intent_router.py` | `IntentRouter` with 4 compiled regex patterns, `async_route`, `_dispatch` | VERIFIED | 152 lines; 4 `re.compile` calls confirmed; `services.async_call` with `blocking=True` |
| `custom_components/ha_ai_agent/entity_context.py` | `EntityContextBuilder` with 3-pass cascade and domain whitelist | VERIFIED | 76 lines; `resolve_entity` defined; `er.async_get` used; `hass.states.get` for Pass 1 |
| `custom_components/ha_ai_agent/config_flow.py` | `HaAiAgentOptionsFlow` + `async_get_options_flow` | VERIFIED | `async_get_options_flow` at line 51; `HaAiAgentOptionsFlow` class at line 56 |
| `custom_components/ha_ai_agent/const.py` | `CONF_ALLOWED_DOMAINS`, `DEFAULT_ALLOWED_DOMAINS` exports | VERIFIED | Lines 6-7 confirm both constants |
| `tests/test_conversation_bridge.py` | 4 tests covering routing + hass.data + end-to-end | VERIFIED | 193 lines; 4 tests collected, 0 skipped, all green |
| `tests/test_intent_router.py` | 7 tests covering all intent types, error paths, apostrophe | VERIFIED | 189 lines; 7 tests, all green |
| `tests/test_entity_resolver.py` | 5 tests covering 3-pass cascade, whitelist, unicode | VERIFIED | 100 lines; 5 tests, all green |
| `.planning/REQUIREMENTS.md` | NLU-04 marked complete (checkbox + traceability) | VERIFIED | `[x] **NLU-04**` at line 20; `NLU-04 \| Phase 2 \| Complete` at line 81 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `conversation.py` | `intent_router.py` | `hass.data[DOMAIN][entry_id]["router"].async_route()` | WIRED | `conversation.py:82-86` — retrieves router from `hass.data`, calls `async_route` |
| `__init__.py` | `intent_router.py` | `IntentRouter(hass, allowed_domains=allowed_domains)` | WIRED | `__init__.py:9` (import) + `__init__.py:18` (instantiation) |
| `intent_router.py` | `homeassistant.services` | `await hass.services.async_call(..., blocking=True)` | WIRED | `intent_router.py:129-134` — `blocking=True` confirmed |
| `intent_router.py` | `entity_context.py` | `EntityContextBuilder.resolve_entity(entity_text)` | WIRED | `intent_router.py:106` (lazy import) + `intent_router.py:119` (call) |
| `entity_context.py` | `homeassistant.helpers.entity_registry` | `er.async_get(hass).entities.values()` | WIRED | `entity_context.py:51` |
| `entity_context.py` | `homeassistant.core.StateMachine` | `hass.states.get(candidate)` | WIRED | `entity_context.py:47` |
| `config_flow.py` | `const.py` | `CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS` | WIRED | `config_flow.py:10` (import) + `config_flow.py:71-72` (used in schema) |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `conversation.py` | `response_text` | `router.async_route(text, language)` | Yes — `IntentRouter` dispatches to real `hass.services.async_call` | FLOWING |
| `intent_router.py` | `entity_id` | `EntityContextBuilder.resolve_entity(entity_text)` | Yes — 3-pass cascade against live `hass.states` and entity registry | FLOWING |
| `entity_context.py` | candidate entity_id | `hass.states.get(candidate)` / `er.async_get(hass).entities` | Yes — reads live HA state machine and entity registry | FLOWING |

---

## Behavioral Spot-Checks

Step 7b: Full pytest suite executed as a behavioral proxy.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite — 30 tests | `python -m pytest tests/ -v` | 30 passed, 0 failed, 0 skipped, 1 warning | PASS |
| Echo stub absent from conversation.py | `grep "scaffold.*Received" conversation.py` | No match | PASS |
| `router.async_route` wired in conversation.py | `grep "router\.async_route" conversation.py` | 1 match (line 83) | PASS |
| `IntentRouter` import + instantiation in `__init__.py` | `grep "IntentRouter" __init__.py` | 2 matches (line 9 + line 18) | PASS |
| 4 compiled regex patterns in `intent_router.py` | `grep -c "re.compile" intent_router.py` | 4 | PASS |
| `blocking=True` present in `services.async_call` | `grep "blocking=True" intent_router.py` | 1 match (line 134) | PASS |
| `resolve_entity` defined in `entity_context.py` | `grep "resolve_entity" entity_context.py` | 1 method definition | PASS |
| `async_get_options_flow` registered | `grep "async_get_options_flow" config_flow.py` | 1 match (line 51) | PASS |
| NLU-04 checkbox in REQUIREMENTS.md | `grep "NLU-04" REQUIREMENTS.md` | `[x] **NLU-04**` at line 20; `Complete` at line 81 | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| NLU-01 | 02-01, 02-03 | Text command controls HA entity end-to-end | SATISFIED | `test_confirmation_message_after_turn_on` green; full path: text -> `async_route` -> `_dispatch` -> `resolve_entity` -> `hass.services.async_call` |
| NLU-02 | 02-02 | Simple commands processed locally, no LLM | SATISFIED | `intent_router.py` uses only compiled regex + HA services API; no network call; `test_turn_on_french` etc. green |
| NLU-04 | 02-01 | Natural language confirmation after each action | SATISFIED | `intent_router.py:151` returns `"D'accord, j'ai {action_label} {entity_text}."` — French confirmation verified in `test_confirmation_message_after_turn_on`; REQUIREMENTS.md `[x]` and `Complete` confirmed |
| NLU-05 | 02-02 | Clear error messages for entity-not-found, service unavailable | SATISFIED | `intent_router.py:121` (entity not found), `intent_router.py:135-143` (ServiceNotFound + HomeAssistantError); `test_entity_not_found_returns_error`, `test_service_not_found_returns_error`, `test_homeassistant_error_returns_error` green |
| SEC-03 | 02-03 | Configurable domain whitelist | SATISFIED | `entity_context.py:53` domain filter enforced; `HaAiAgentOptionsFlow` in `config_flow.py`; `test_domain_whitelist_blocks` green |

**Orphaned requirements check:** REQUIREMENTS.md traceability table maps NLU-01, NLU-02, NLU-04, NLU-05, SEC-03 to Phase 2 — all five are claimed in the plans. No orphaned requirements.

All five requirements are now fully satisfied: code implemented, tested, and documentation consistent.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No TODOs, FIXMEs, placeholder returns, echo stubs, or hardcoded empty data found in any Phase 2 modified file.

---

## Human Verification Required

### 1. End-to-end voice command in real HA instance

**Test:** Install the integration in a real Home Assistant instance. Open the Voice Assistants panel (or use an Assist widget). Send: "allume la lumiere du salon" with a light entity named "lumiere salon" in the `light` domain.
**Expected:** The light entity turns on; the assistant returns a French confirmation: "D'accord, j'ai allume lumiere du salon." (or similar)
**Why human:** The full `assist_pipeline` TTS readback path and actual HA service execution against real hardware cannot be exercised in unit tests.

### 2. OptionsFlow UI in real HA instance

**Test:** Go to Settings > Devices & Services > HA AI Agent > Configure.
**Expected:** A form appears with a domain whitelist field pre-filled with `["light", "switch", "climate", "media_player"]`. Editing and saving the field changes the active whitelist without restarting HA.
**Why human:** OptionsFlow form rendering and persistence cannot be verified programmatically outside HA's config_entries UI machinery.

---

## Gaps Summary

No gaps. The single documentation gap from the initial verification has been resolved:

- NLU-04 checkbox updated from `[ ]` to `[x]` in `.planning/REQUIREMENTS.md`
- NLU-04 traceability row updated from `Pending` to `Complete`

All 15 must-haves are now verified. All 30 tests pass (0 failures, 0 skips). All key links are wired. No stubs or anti-patterns detected. Phase goal achieved: text commands control HA entities via local rules, with no LLM required.

---

_Verified: 2026-03-31T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
