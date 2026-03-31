---
phase: 01-ha-scaffold
plan: 01
subsystem: infra
tags: [homeassistant, custom-component, pytest, pytest-homeassistant-custom-component, asyncio, python]

# Dependency graph
requires: []
provides:
  - "HA custom component skeleton: manifest.json, const.py, __init__.py, conversation.py stub, config_flow.py, strings.json, translations/en.json"
  - "Test infrastructure: pyproject.toml, tests/__init__.py, conftest.py, test_init.py, test_manifest.py"
  - "Windows pytest compatibility: fcntl/resource stubs, SelectorEventLoop policy, pytest-socket ProactorEventLoop patch"
affects:
  - 01-02
  - 01-03
  - all Phase 1 plans (shared test infrastructure)

# Tech tracking
tech-stack:
  added:
    - pytest-homeassistant-custom-component==0.13.320
    - pytest-asyncio==1.3.0
    - ruff==0.15.8
    - homeassistant==2026.3.4
    - aiohttp, aiodns, hassil, home-assistant-intents (HA transitive deps)
  patterns:
    - "HA custom component: manifest.json declares config_flow, dependencies, iot_class"
    - "Symmetric async_setup_entry/async_unload_entry with async_forward_entry_setups/async_unload_platforms"
    - "hass.data[DOMAIN][entry.entry_id] for per-entry storage"
    - "enable_custom_integrations + async_setup_component(homeassistant) for HA test lifecycle"
    - "hass_config_dir override pointing to project root so HA discovers custom_components/"

key-files:
  created:
    - custom_components/ha_ai_agent/manifest.json
    - custom_components/ha_ai_agent/const.py
    - custom_components/ha_ai_agent/__init__.py
    - custom_components/ha_ai_agent/conversation.py
    - custom_components/ha_ai_agent/config_flow.py
    - custom_components/ha_ai_agent/strings.json
    - custom_components/ha_ai_agent/translations/en.json
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_init.py
    - tests/test_manifest.py
    - pyproject.toml
    - conftest.py
  modified: []

key-decisions:
  - "config_flow.py added (Rule 2): HA requires config_flow.py when manifest has config_flow=true; without it async_setup_entry fails with 'platform not found'"
  - "conversation.py stub (plan-specified): PLATFORMS=[conversation] requires a conversation.py platform module; stub allows lifecycle tests to pass; Plan 01-03 replaces it"
  - "Windows compatibility (Rule 3): Python 3.14 on Windows lacks fcntl/resource; stub modules created at site-packages level; pytest-socket ProactorEventLoop incompatibility patched in root conftest.py"
  - "hass_config_dir override: pytest-homeassistant-custom-component sets DATA_CUSTOM_COMPONENTS={} by default, blocking discovery; override points config_dir to project root"
  - "enable_custom_integrations + async_setup_component(homeassistant): needed to allow HA to discover custom_components/ and set up exposed_entities before conversation loads"

patterns-established:
  - "Test pattern: mock_config_entry fixture uses enable_custom_integrations + async_setup_component(homeassistant) before entry setup"
  - "Test pattern: hass_config_dir fixture points to PROJECT_ROOT so HA finds custom_components/"
  - "Windows pattern: root conftest.py patches pytest-socket disable_socket to allow AF_INET on Windows"

requirements-completed: [HA-01, HA-03]

# Metrics
duration: 26min
completed: 2026-03-31
---

# Phase 1 Plan 01: HA Scaffold Summary

**HA custom component skeleton with manifest, async_setup_entry/async_unload_entry lifecycle, conversation platform stub, and pytest infrastructure — 6 tests green on Python 3.14/Windows**

## Performance

- **Duration:** 26 min
- **Started:** 2026-03-31T01:54:54Z
- **Completed:** 2026-03-31T02:20:50Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments

- Component directory `custom_components/ha_ai_agent/` created with all required files (manifest.json, const.py, __init__.py, conversation.py stub, config_flow.py, strings.json, translations/en.json)
- `async_setup_entry` stores entry in `hass.data[DOMAIN][entry.entry_id]` and forwards `conversation` platform; `async_unload_entry` symmetrically unloads and clears data
- Shared test infrastructure (pyproject.toml with asyncio_mode=auto, conftest.py fixtures, test_init.py + test_manifest.py) established for all Phase 1 plans — 6 tests pass

## Task Commits

1. **Task 1: Test infrastructure and project config (Wave 0)** - `8f0c35b` (feat)
2. **Task 2: Component skeleton (manifest, const, __init__, conversation stub, strings, translations)** - `d08baf6` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `custom_components/ha_ai_agent/manifest.json` — domain=ha_ai_agent, version=0.1.0, config_flow=true, dependencies=[conversation], iot_class=cloud_polling
- `custom_components/ha_ai_agent/const.py` — DOMAIN, CONF_API_KEY, DEFAULT_MODEL constants
- `custom_components/ha_ai_agent/__init__.py` — async_setup_entry, async_unload_entry, PLATFORMS=["conversation"]
- `custom_components/ha_ai_agent/conversation.py` — no-op stub platform (replaced by Plan 01-03)
- `custom_components/ha_ai_agent/config_flow.py` — minimal HAAgentConfigFlow (Rule 2 deviation)
- `custom_components/ha_ai_agent/strings.json` + `translations/en.json` — config flow UI strings
- `tests/__init__.py` — empty package marker
- `tests/conftest.py` — hass_config_dir, mock_config_entry fixtures; Windows asyncio compat
- `tests/test_init.py` — 4 lifecycle tests (setup LOADED, stores data, unload NOT_LOADED, clears data)
- `tests/test_manifest.py` — 2 manifest field tests (required fields, no deprecated iot_class)
- `pyproject.toml` — pytest asyncio_mode=auto, testpaths=tests, ruff py312
- `conftest.py` — root-level Windows pytest-socket/ProactorEventLoop compat patch

## Decisions Made

- `config_flow.py` added per Rule 2: HA raises "Platform ha_ai_agent.config_flow not found" without it, preventing config entry setup
- `hass_config_dir` fixture overrides default to project root so HA loader finds `custom_components/ha_ai_agent`
- `enable_custom_integrations` fixture used to clear the empty `DATA_CUSTOM_COMPONENTS` dict pre-populated by the test harness
- `async_setup_component(hass, "homeassistant", {})` called before entry setup to populate `exposed_entities` required by the conversation component

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added config_flow.py**
- **Found during:** Task 2 (component skeleton creation)
- **Issue:** HA logs "Error importing platform config_flow from integration ha_ai_agent" and refuses to load entry without config_flow.py, even in tests
- **Fix:** Created minimal `HAAgentConfigFlow` with `async_step_user` — single-field form for API key, `already_configured` abort guard
- **Files modified:** `custom_components/ha_ai_agent/config_flow.py`
- **Verification:** `python -m pytest tests/test_init.py -v` — 4/4 pass
- **Committed in:** d08baf6 (Task 2 commit)

**2. [Rule 3 - Blocking] Windows environment: fcntl, resource, ProactorEventLoop**
- **Found during:** Task 1 verification (first pytest run)
- **Issue:** `homeassistant.runner` imports `fcntl` (Unix-only); asyncio ProactorEventLoop on Python 3.14/Windows conflicts with pytest-socket; aiohttp requires aiodns
- **Fix:**
  - Created stub `fcntl.py` and `resource.py` at site-packages level
  - Root `conftest.py` patches `pytest_socket.disable_socket` to allow AF_INET sockets on Windows (needed by SelectorEventLoop internal socketpair)
  - `tests/conftest.py` sets `asyncio.WindowsSelectorEventLoopPolicy` (and DeprecationWarning noted for Python 3.16 removal)
  - Installed 20+ missing transitive HA dependencies iteratively
- **Files modified:** `conftest.py`, `tests/conftest.py`, site-packages stubs
- **Verification:** All 6 tests pass on Windows Python 3.14
- **Committed in:** d08baf6 (Task 2 commit)

**3. [Rule 3 - Blocking] Test harness blocks custom component discovery**
- **Found during:** Task 2 test run (test_init.py first run)
- **Issue:** `async_test_home_assistant` pre-sets `hass.data[DATA_CUSTOM_COMPONENTS] = {}` — empty dict prevents HA from discovering custom_components/; config_dir defaults to package's testing_config/ not project root
- **Fix:** Added `hass_config_dir` fixture returning `PROJECT_ROOT`; added `enable_custom_integrations` fixture to `mock_config_entry` (clears empty dict, triggers rediscovery); added `async_setup_component(hass, "homeassistant", {})` to satisfy conversation's exposed_entities dependency
- **Files modified:** `tests/conftest.py`
- **Verification:** 4/4 init tests pass — "Setting up ha_ai_agent" appears in logs
- **Committed in:** d08baf6 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 missing critical, 2 blocking)
**Impact on plan:** All auto-fixes necessary for the component to load and tests to pass on Windows Python 3.14. No scope creep — config_flow.py is explicitly referenced in plan context for Plan 01-02.

## Issues Encountered

- Python 3.14 on Windows has ~25 missing transitive HA dependencies not installable via `pip install homeassistant` (lru-dict build failure). Resolved by iterative dependency installation with `--no-deps` and `--pre` flags.
- pytest-homeassistant-custom-component 0.13.320 blocks custom component discovery by design (security); requires explicit `enable_custom_integrations` fixture use.
- HA 2026.3 conversation integration requires `homeassistant` core component (exposed_entities) to be set up first in test context — not documented in test helper.

## Known Stubs

- `custom_components/ha_ai_agent/conversation.py` — no-op `async_setup_entry` stub; intentional placeholder for Plan 01-03 which will implement the ConversationEntity. The stub exists solely to satisfy `PLATFORMS=["conversation"]` platform forwarding during lifecycle tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 01-02 (config flow UI): `config_flow.py` skeleton exists, `strings.json` and `translations/en.json` ready — Plan 01-02 extends the step validation
- Plan 01-03 (conversation agent): `conversation.py` stub exists at the correct module name — Plan 01-03 replaces it with `ConversationEntity`
- Shared fixtures (`mock_config_entry`, `hass_config_dir`) available for Plans 01-02 and 01-03
- Blocker for Plan 01-03: verify exact `AbstractConversationAgent` import path in HA 2026.x (STATE.md concern still valid)

---
*Phase: 01-ha-scaffold*
*Completed: 2026-03-31*
