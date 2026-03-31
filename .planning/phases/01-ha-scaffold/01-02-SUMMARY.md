---
phase: 01-ha-scaffold
plan: 02
subsystem: infra
tags: [homeassistant, config-flow, pytest, tdd, python]

# Dependency graph
requires:
  - "01-01 (const.py with DOMAIN, CONF_API_KEY; test infrastructure; conftest fixtures)"
provides:
  - "config_flow.py: HaAiAgentConfigFlow with async_step_user, duplicate prevention, API key stored in entry.data"
  - "tests/test_config_flow.py: 4 tests verifying form display, entry creation, duplicate abort, data-not-options"
  - "hass_with_homeassistant fixture in conftest.py for config flow test lifecycle"
affects:
  - 01-03
  - all plans using config entry (API key access via entry.data[CONF_API_KEY])

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Config flow TDD: write failing tests first, implement flow, verify all 4 pass"
    - "hass_with_homeassistant fixture: enable_custom_integrations + async_setup_component(homeassistant) before flow init"
    - "Duplicate prevention: async_set_unique_id(DOMAIN) + _abort_if_unique_id_configured() — both calls required"
    - "API key stored in entry.data (not entry.options) — credentials vs runtime settings convention"

key-files:
  created:
    - tests/test_config_flow.py
  modified:
    - custom_components/ha_ai_agent/config_flow.py
    - tests/conftest.py

key-decisions:
  - "HaAiAgentConfigFlow class name: matches plan spec (prior plan used HAAgentConfigFlow)"
  - "FlowResult import from homeassistant.data_entry_flow: explicit return type annotation"
  - "hass_with_homeassistant fixture (Rule 3): config flow init triggers conversation dependency resolution which requires homeassistant core component with exposed_entities"
  - "No API key validation in Phase 1: Phase 3 will add Anthropic SDK call with invalid_auth error handling"

# Metrics
duration: 12min
completed: 2026-03-30
---

# Phase 1 Plan 02: Config Flow Summary

**Config flow capturing Claude API key via HA Integrations UI — TDD, 4 tests green, duplicate prevention via unique_id=DOMAIN**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-30
- **Completed:** 2026-03-30
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `config_flow.py` updated with `HaAiAgentConfigFlow` class — clean TDD spec matching plan requirements: `FlowResult` return type, explicit `{CONF_API_KEY: ...}` in `async_create_entry`, `VERSION = 1`
- `tests/test_config_flow.py` created with 4 tests: form display, success path, duplicate abort, data-not-options storage — all 4 pass
- `hass_with_homeassistant` fixture added to `tests/conftest.py` — reusable for any plan that needs config flow init without full entry setup

## Task Commits

1. **Task 1: Write config flow tests (RED)** - `bdc939a` (test)
2. **Task 2: Implement HaAiAgentConfigFlow with tests (GREEN)** - `c2546e7` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `custom_components/ha_ai_agent/config_flow.py` — `HaAiAgentConfigFlow` with `async_step_user`, `STEP_USER_DATA_SCHEMA`, duplicate prevention, API key stored in `entry.data`
- `tests/test_config_flow.py` — 4 async tests using `hass_with_homeassistant` fixture
- `tests/conftest.py` — added `hass_with_homeassistant` fixture (enable_custom_integrations + async_setup_component homeassistant)

## Decisions Made

- `hass_with_homeassistant` fixture: config flow `async_init` triggers HA to load the integration's dependencies (including `conversation`), which requires `homeassistant` core component with `exposed_entities` — same root cause as Plan 01-01 lifecycle tests
- No API key validation: Phase 1 stores the key as-is; Phase 3 (Claude LLM integration) will add `anthropic.Anthropic().models.list()` call to validate before creating entry, setting `errors["base"] = "invalid_auth"` on failure
- `async_set_unique_id(DOMAIN)` + `_abort_if_unique_id_configured()`: both calls required — `set_unique_id` registers the ID, `_abort_if_unique_id_configured` checks for conflicts

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] hass_with_homeassistant fixture required for config flow tests**
- **Found during:** Task 2 verification (first pytest run after GREEN implementation)
- **Issue:** `hass.config_entries.flow.async_init(DOMAIN, ...)` triggers HA to process dependencies of `ha_ai_agent`, including `conversation`. The `conversation` component's `async_hass_started` callback accesses `hass.data[DATA_EXPOSED_ENTITIES]` (KeyError) unless `homeassistant` core is set up first
- **Fix:** Added `hass_with_homeassistant` fixture to `tests/conftest.py` that calls `async_setup_component(hass, "homeassistant", {})` after `enable_custom_integrations`; updated all 4 test functions to use this fixture
- **Files modified:** `tests/conftest.py`, `tests/test_config_flow.py`
- **Commit:** c2546e7 (Task 2 commit)

## Test Results

```
tests/test_config_flow.py ....                                           [100%]
4 passed, 1 warning in 0.30s
```

Full regression (Plans 01-01 + 01-02):
```
tests/test_config_flow.py ....                                           [ 40%]
tests/test_init.py ....                                                  [ 80%]
tests/test_manifest.py ..                                                [100%]
10 passed, 1 warning in 0.48s
```

Note: `tests/test_conversation.py` has 1 pre-existing failure (`test_conversation_entity_registered`) from Plan 01-03 partial execution — out of scope for Plan 01-02.

## Phase 3 Handoff

`config_flow.py` TODO comment at line 33-35 marks the Phase 3 extension point:
```python
# Phase 3 will add: try minimal Anthropic API call, catch AuthenticationError,
# set errors["base"] = "invalid_auth" and re-show form on failure
```

## Known Stubs

- `async_step_user`: accepts any non-empty string as API key (no Anthropic validation). Intentional Phase 1 stub — Plan 01-03 (Claude LLM integration) will add real validation.

## Self-Check

Files created:
- [x] `tests/test_config_flow.py` — created
- [x] `custom_components/ha_ai_agent/config_flow.py` — updated

Commits:
- [x] bdc939a — test(01-02) RED phase
- [x] c2546e7 — feat(01-02) GREEN phase

## Self-Check: PASSED
