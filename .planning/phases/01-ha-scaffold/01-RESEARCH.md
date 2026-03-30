# Phase 1: HA Scaffold - Research

**Researched:** 2026-03-30
**Domain:** Home Assistant custom component scaffolding — manifest, config flow, conversation entity registration
**Confidence:** MEDIUM-HIGH

---

## Summary

Phase 1 establishes the complete HA integration skeleton: the component must load correctly from `custom_components/ha_ai_agent/`, expose a config flow for API key capture, support UI reload without HA restart, and register itself as a selectable conversation agent in Voice Assistants. No AI feature code is written in this phase — only the wiring.

The critical discovery from live web research (2026-03-30) is that the conversation agent API changed significantly from what earlier research documented. The `AbstractConversationAgent` pattern (with `async_set_agent` + `async_process`) is **deprecated**. The current (HA 2024.6+) pattern is `ConversationEntity` with `_async_handle_message(user_input, chat_log)`, registered via the standard HA platform mechanism (`PLATFORMS = ["conversation"]` + `async_forward_entry_setups`). The planner must use the new pattern to avoid breaking on any HA 2025.x release.

Config flow and manifest patterns are stable and well-documented. The `async_unload_entry` contract is the key enabler for HA-03 (reload without restart) and must be implemented correctly from day one — including cleanup of forwarded platforms via `async_unload_platforms`.

**Primary recommendation:** Implement `ConversationEntity` (not `AbstractConversationAgent`) with `_async_handle_message`, use `PLATFORMS = ["conversation"]` + `async_forward_entry_setups` in `__init__.py`, and implement both `async_setup_entry` and `async_unload_entry` with symmetric resource management from the first commit.

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md contains only one directive: "Projet vide — en cours d'initialisation via `/gsd:new-project`." No additional project-specific constraints beyond the requirements and PROJECT.md constraints below.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HA-01 | Component installs via `custom_components/ha_ai_agent/` and appears in HA integrations panel | manifest.json with correct required fields + `config_flow: true` + `async_setup_entry` returning `True` |
| HA-02 | User can configure Claude API key via HA config flow UI | `ConfigFlow.async_step_user` with `vol.Schema`, key stored in `entry.data[CONF_API_KEY]`, test call during validation |
| HA-03 | Component can be reloaded without restarting Home Assistant | `async_unload_entry` that calls `async_unload_platforms` and clears `hass.data[DOMAIN]` |
| HA-04 | Component registers as a selectable conversation agent in Voice Assistants | `ConversationEntity` subclass in `conversation_agent.py`, `PLATFORMS = ["conversation"]`, `async_forward_entry_setups` |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 (HA-managed) | Runtime | HA 2024.x+ ships with Python 3.12; do not install a separate interpreter |
| Home Assistant Core | 2024.11+ | Host platform | Target the latest stable release family; conversation entity API stable since 2024.6 |
| `voluptuous` | `>=0.14` (HA built-in) | Config flow schema validation | HA ships voluptuous natively; standard for all config entry forms |

**Phase 1 has no pip-installable runtime dependencies.** The `anthropic` and `aiosqlite` dependencies belong in `manifest.json["requirements"]` but are not needed until Phase 2/5. Phase 1's skeleton should declare them to avoid later manifest bumps, but they need not be imported.

### Supporting (dev / test)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-homeassistant-custom-component` | `>=0.13` (tracks HA version) | Provides `hass` fixture, `enable_custom_integrations`, config flow test helpers | All tests in this phase |
| `pytest-asyncio` | `>=0.23` | Async test runner | Required alongside HA test harness; set `asyncio_mode = "auto"` in `pytest.ini` |
| `ruff` | latest | Linting + formatting | HA core migrated to ruff; configure via `pyproject.toml` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ConversationEntity` + `PLATFORMS` | `AbstractConversationAgent` + `async_set_agent` | **Do not use** — `AbstractConversationAgent` is deprecated in HA 2024.6+; breaks on HA 2025.x |
| `entry.data[CONF_API_KEY]` for secrets | `entry.options` | Options dictionary is less secure (not cleared on entry removal in all contexts); use `data` for credentials |
| `async_unload_platforms` | Manual platform cleanup | `async_unload_platforms` is the correct symmetric call for `async_forward_entry_setups`; manual teardown misses edge cases |

**Installation (dev environment only):**
```bash
pip install \
  pytest-homeassistant-custom-component>=0.13 \
  pytest-asyncio>=0.23 \
  ruff
```

**Runtime requirements go in `manifest.json["requirements"]`, not pip.**

---

## Architecture Patterns

### Recommended Project Structure (Phase 1 scope)

```
custom_components/ha_ai_agent/
├── __init__.py              # async_setup_entry, async_unload_entry, PLATFORMS
├── manifest.json            # domain, version, dependencies, iot_class, config_flow: true
├── config_flow.py           # ConfigFlow with async_step_user — API key input + validation stub
├── const.py                 # DOMAIN, CONF_API_KEY, default constants
├── conversation_agent.py    # HaAiConversationAgent(ConversationEntity) — scaffold only, no AI logic
├── strings.json             # Config flow UI strings
└── translations/
    └── en.json              # English translations
```

Files NOT created in Phase 1 (deferred to later phases):
- `intent_router.py`, `claude_client.py`, `habit_engine.py`, `storage.py`, `entity_context.py`

### Pattern 1: manifest.json — Required Fields

**What:** The manifest is the HA component loader entry point. Missing fields silently prevent loading or cause HACS validation failure.

**When to use:** Always — first file created.

```json
{
  "domain": "ha_ai_agent",
  "name": "HA Autonomous AI Agent",
  "version": "0.1.0",
  "documentation": "",
  "issue_tracker": "",
  "requirements": ["anthropic>=0.27,<1", "aiosqlite>=0.20"],
  "dependencies": ["conversation"],
  "after_dependencies": ["assist_pipeline"],
  "codeowners": [],
  "config_flow": true,
  "iot_class": "cloud_polling",
  "integration_type": "service",
  "quality_scale": "custom"
}
```

Key decisions:
- `"config_flow": true` — required for HA-01 (appears in integrations panel with UI setup)
- `"dependencies": ["conversation"]` — HA will load the `conversation` integration before ours; required for `ConversationEntity` to work
- `"iot_class": "cloud_polling"` — accurate: calls Anthropic API (cloud)
- `"integration_type": "service"` — recommended for 2024.x+ integrations without physical devices
- `"version"` — required for custom components since HA 2021.3; required for HACS

**Confidence:** HIGH — manifest fields verified through official HA developer docs search.

---

### Pattern 2: __init__.py — Setup/Unload Lifecycle

**What:** The entry point for a config-flow integration. Must implement `async_setup_entry` (called when config entry is created/loaded) and `async_unload_entry` (called when user clicks Reload or Remove in HA UI).

**When to use:** Mandatory for HA-03 (reload without restart).

```python
# __init__.py
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[str] = ["conversation"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA AI Agent from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
```

**Confidence:** HIGH — `async_forward_entry_setups` + `async_unload_platforms` is the current standard pattern confirmed via HA community and HA core source references.

---

### Pattern 3: config_flow.py — API Key Config Flow

**What:** HA UI calls `async_step_user` when the user initiates setup. The method shows a form, collects the API key, validates it (Phase 1 can use a stub; Phase 2 adds real API validation), then creates the config entry.

**When to use:** Required for HA-02.

```python
# config_flow.py
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_API_KEY

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
})


class HaAiAgentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA AI Agent."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Phase 1: store key as-is (Phase 2 will add real API validation)
            # TODO Phase 2: validate key with a minimal Anthropic API call
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="HA AI Agent",
                data={CONF_API_KEY: user_input[CONF_API_KEY]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
```

**Important:** Store the API key in `entry.data`, NOT `entry.options`. The `data` dict is for credentials; `options` is for user-adjustable runtime settings.

**Confidence:** HIGH — standard pattern confirmed by official HA config_entries docs search.

---

### Pattern 4: ConversationEntity — Conversation Agent Registration (HA 2024.6+)

**What:** The current pattern for registering a custom conversation agent. `ConversationEntity` is a proper HA entity that is forwarded to the `conversation` platform. HA's `assist_pipeline` and Voice Assistants UI will list all registered `ConversationEntity` instances as selectable agents.

**CRITICAL:** `AbstractConversationAgent` with `conversation.async_set_agent()` is **deprecated**. Do not use it.

**When to use:** Required for HA-04. Use `_async_handle_message` as the primary handler (backwards compatible with `async_process`).

```python
# conversation_agent.py
from __future__ import annotations

from homeassistant.components.conversation import ConversationEntity, ConversationInput, ConversationResult
from homeassistant.components.conversation.models import ConversationResult as CR
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up conversation entity from config entry."""
    agent = HaAiConversationAgent(hass, config_entry)
    async_add_entities([agent])


class HaAiConversationAgent(ConversationEntity):
    """HA AI Agent conversation entity (scaffold — no AI logic yet)."""

    _attr_has_entity_name = True
    _attr_name = "HA AI Agent"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str]:
        return ["fr", "en"]

    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log,
    ) -> ConversationResult:
        """Process a conversation message. Phase 1: echo stub only."""
        # Phase 2 will replace this with IntentRouter + ClaudeClient
        response_text = f"[HA AI Agent scaffold] Received: {user_input.text}"

        # Add response to chat log (required by new ConversationEntity API)
        from homeassistant.components.conversation import AssistantContent
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id=self.entity_id, content=response_text)
        )

        from homeassistant.components.conversation.models import ConversationResult
        from homeassistant.components.conversation import intent as conversation_intent
        intent_response = conversation_intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_text)
        return ConversationResult(response=intent_response, conversation_id=user_input.conversation_id)
```

**Note on import paths:** The exact import path for `AssistantContent`, `ChatLog`, and `ConversationResult` may require verification against the live HA source. The pattern above follows the structure observed in community implementations as of early 2026. The planner should include a verification task in Wave 0.

**Confidence:** MEDIUM — `ConversationEntity` + `_async_handle_message` confirmed via web search. Exact import paths for `AssistantContent` and `ChatLog` need live HA source verification before implementation.

---

### Pattern 5: const.py — Domain and Config Constants

```python
# const.py
DOMAIN = "ha_ai_agent"
CONF_API_KEY = "api_key"
DEFAULT_MODEL = "claude-sonnet-4-6"
```

---

### Pattern 6: strings.json + translations/en.json

```json
// strings.json
{
  "config": {
    "step": {
      "user": {
        "title": "Configure HA AI Agent",
        "description": "Enter your Anthropic API key. Your commands will be processed by Claude.",
        "data": {
          "api_key": "Anthropic API Key"
        }
      }
    },
    "error": {
      "cannot_connect": "Failed to connect to Claude API",
      "invalid_auth": "Invalid API key"
    },
    "abort": {
      "already_configured": "HA AI Agent is already configured"
    }
  }
}
```

`translations/en.json` should be a copy of `strings.json` (HA requires both for the UI to work).

---

### Anti-Patterns to Avoid

- **Using `AbstractConversationAgent`:** Deprecated since HA 2024.6. Causes `ImportError` or silent failure on 2025.x releases. Use `ConversationEntity` only.
- **Calling `conversation.async_set_agent()` manually:** Replaced by the platform mechanism (`async_forward_entry_setups`). Registering outside the platform lifecycle breaks reload (HA-03).
- **Storing API key in `entry.options`:** Use `entry.data` for credentials. Options are for user-tunable settings exposed in HA's options flow.
- **Omitting `async_unload_entry`:** Without it, HA cannot reload the component (HA-03 fails). Implement from the first commit.
- **Setting `unique_id` to a static string without `_abort_if_unique_id_configured`:** Allows duplicate entries, causing two conversation agents to appear.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config form rendering and submission | Custom HTML / JS form | `ConfigFlow.async_show_form` + `vol.Schema` | HA renders the form automatically from schema; custom UI would bypass HA's credential handling |
| Atomic JSON writes | `open().write(json.dumps(...))` | `homeassistant.helpers.storage.Store` | HA's Store handles atomic writes, crash safety, versioning |
| Platform lifecycle management | Manual entity registry calls | `async_forward_entry_setups` + `async_unload_platforms` | HA handles entity registration, state tracking, and teardown |
| Config entry uniqueness | Custom duplicate detection | `async_set_unique_id` + `_abort_if_unique_id_configured` | HA provides this; re-implementing creates race conditions |
| API key validation in test | Mock Anthropic server | `pytest-homeassistant-custom-component` flow mocking | The test harness provides async flow simulation without real API calls |

**Key insight:** Phase 1 is almost entirely HA framework glue. Every problem at this level has a built-in HA solution.

---

## Runtime State Inventory

Phase 1 creates no runtime state that persists beyond the config entry. The only stored artifact is:

| Category | Items | Action Required |
|----------|-------|-----------------|
| Stored data | `ConfigEntry.data` in HA's `.storage/core.config_entries` (plain JSON) | Code edit only — created by config flow |
| Live service config | None | None |
| OS-registered state | None | None |
| Secrets/env vars | None (API key in config entry, not env) | None |
| Build artifacts | None (no compiled Python, no pip installs at phase 1) | None |

**Note on API key security:** HA stores config entries in `.storage/core.config_entries` as **plain JSON** (not encrypted) on most platforms. This is documented HA behavior — warn the user in the config flow description that backups of `.storage/` contain the key. This is the standard approach for all HA cloud integrations.

---

## Common Pitfalls

### Pitfall 1: Using Deprecated AbstractConversationAgent
**What goes wrong:** Code that subclasses `AbstractConversationAgent` and calls `conversation.async_set_agent()` works on HA 2023.x but raises `ImportError` or is silently ignored on HA 2025.x, causing HA-04 to fail.
**Why it happens:** Most tutorials and Stack Overflow answers pre-date the 2024.6 API change. Prior research documents also referenced the old API.
**How to avoid:** Always use `ConversationEntity` subclass + `PLATFORMS = ["conversation"]`. Verify the correct imports against the live HA source before first commit.
**Warning signs:** The agent does not appear in Settings > Voice Assistants after setup.

### Pitfall 2: Missing `async_unload_platforms` in `async_unload_entry`
**What goes wrong:** The component cannot be reloaded from the HA UI (HA-03 fails). After clicking Reload, conversation entity lingers in entity registry but stops responding. Second reload creates a duplicate.
**Why it happens:** Developers implement `async_unload_entry` that only clears `hass.data` but forgets to call `async_unload_platforms`, leaving the forwarded `conversation` platform entities registered.
**How to avoid:** Always mirror `async_forward_entry_setups(entry, PLATFORMS)` with `async_unload_platforms(entry, PLATFORMS)` in the unload function.
**Warning signs:** After Reload, two "HA AI Agent" entries appear in Voice Assistants.

### Pitfall 3: Missing `version` in manifest.json
**What goes wrong:** HA logs a warning and may refuse to load the integration: "No 'version' key in the manifest file for custom integration 'ha_ai_agent'." HACS also rejects the component without a valid semver/calver version string.
**Why it happens:** Developers copy minimal manifest examples that pre-date HA 2021.3.
**How to avoid:** Always include `"version": "0.1.0"` in manifest.json from day one.
**Warning signs:** HA logs `WARNING ... No 'version' key in manifest`.

### Pitfall 4: Duplicate Config Entry (no unique_id guard)
**What goes wrong:** User clicks "Add Integration" twice, creating two config entries. Both register a `ConversationEntity`, and two "HA AI Agent" agents appear in Voice Assistants — confusing the user.
**Why it happens:** Config flow without `async_set_unique_id` + `_abort_if_unique_id_configured` allows unlimited re-adds.
**How to avoid:** Add both calls in `async_step_user` before creating the entry (see Pattern 3 above).
**Warning signs:** Multiple entries in HA integrations panel for the same component.

### Pitfall 5: Conversation Agent Missing `supported_languages`
**What goes wrong:** HA may not display the agent in Voice Assistants, or filters it out for the user's language, even if the conversation agent is correctly registered.
**Why it happens:** `supported_languages` is an abstract property of `ConversationEntity` that must be overridden. Without it, the entity is incomplete.
**How to avoid:** Always implement `supported_languages` returning `["fr", "en"]` (or `MATCH_ALL` from `homeassistant.components.conversation`).
**Warning signs:** Agent registered but not visible in Settings > Voice Assistants language-filtered view.

---

## Code Examples

Verified patterns from official/community sources:

### async_forward_entry_setups + async_unload_platforms
```python
# Source: HA core openai_conversation/__init__.py (dev branch)
PLATFORMS: list[str] = ["conversation"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

### Config Flow with unique_id guard
```python
# Source: HA Developer Docs config_entries_config_flow_handler
async def async_step_user(self, user_input=None):
    if user_input is not None:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="HA AI Agent", data=user_input)
    return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
```

### ConversationEntity platform setup function
```python
# Source: HA Developer Docs core/entity/conversation
async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities([HaAiConversationAgent(hass, config_entry)])
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `AbstractConversationAgent` + `async_set_agent` | `ConversationEntity` + `PLATFORMS = ["conversation"]` | HA 2024.6 | All new custom components must use the new approach |
| `async_process(ConversationInput)` as sole handler | `_async_handle_message(user_input, chat_log)` | HA 2024.6+ | New method includes ChatLog for multi-turn; `async_process` still works as fallback |
| `async_setup_platforms` | `async_forward_entry_setups` (awaited) | HA 2023.3 | Non-awaited setup causes deprecation warnings and fails in HA 2023.3+ |

**Deprecated/outdated:**
- `AbstractConversationAgent`: deprecated, do not use for new components
- `conversation.async_set_agent()` / `async_unset_agent()`: replaced by platform mechanism
- `async_setup_platforms` (non-awaited): replaced by `await async_forward_entry_setups`

---

## Open Questions

1. **Exact import path for `AssistantContent` and `ChatLog` in HA 2025.x**
   - What we know: `ConversationEntity` + `_async_handle_message(user_input, chat_log)` is confirmed
   - What's unclear: Whether `AssistantContent` is imported from `homeassistant.components.conversation` directly or a sub-module (e.g., `.models`, `.chat_log`)
   - Recommendation: Wave 0 task — grep `homeassistant/components/conversation/` in the installed HA package to confirm exact import paths before writing `conversation_agent.py`

2. **`ConversationResult` construction in 2025.x**
   - What we know: `ConversationResult` wraps an `IntentResponse`
   - What's unclear: Whether the constructor signature changed with the `ChatLog` refactor (the chat log pattern may handle response assembly differently)
   - Recommendation: Look at `homeassistant/components/openai_conversation/entity.py` in the live HA install as a reference implementation

3. **`integration_type` field in manifest.json**
   - What we know: `integration_type` is recommended for 2024.x+ with config flow; default is "hub" if omitted
   - What's unclear: Whether "service" or "hub" is more appropriate for a conversation-agent-only component
   - Recommendation: Use `"service"` — the component provides AI service functionality without controlling physical devices

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11+ | HA runtime requirement | ✓ | 3.14.3 (dev machine) | — |
| Home Assistant Core | HA-01, HA-02, HA-03, HA-04 | Unknown (not verified on dev machine) | — | Use HA dev container |
| `pytest-homeassistant-custom-component` | Phase 1 tests | Unknown | — | Install via pip |
| HA dev container (Docker) | Local HA instance for manual testing | Unknown | — | Install HA OS in VM |

**Missing dependencies with no fallback:**
- A running Home Assistant instance is required to manually verify HA-01 through HA-04. If HA is not installed locally, the official HA dev container (`homeassistant/core` devcontainer.json) is the recommended approach.

**Missing dependencies with fallback:**
- `pytest-homeassistant-custom-component`: install via `pip install pytest-homeassistant-custom-component` — straightforward.

**Note:** Python 3.14.3 is detected on the dev machine. HA 2024.x/2025.x ships with Python 3.12. The component code must be compatible with Python 3.12 (the HA runtime) even if the dev machine runs 3.14. Do not use any 3.13+ syntax (no new 3.13/3.14 features). Test harness runs in the HA Python environment, not the dev machine's.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-homeassistant-custom-component |
| Config file | `tests/pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — Wave 0 gap |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HA-01 | Config entry loads successfully; `async_setup_entry` returns `True` | unit | `pytest tests/test_init.py -x` | Wave 0 gap |
| HA-02 | Config flow `async_step_user` creates entry with API key in `data` | unit | `pytest tests/test_config_flow.py -x` | Wave 0 gap |
| HA-03 | `async_unload_entry` returns `True`; `hass.data[DOMAIN]` cleared after unload | unit | `pytest tests/test_init.py::test_unload_entry -x` | Wave 0 gap |
| HA-04 | `ConversationEntity` is added via platform; entity appears in entity registry | unit | `pytest tests/test_conversation_agent.py -x` | Wave 0 gap |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py` — empty, marks tests as package
- [ ] `tests/conftest.py` — `enable_custom_integrations` fixture, shared `hass` setup
- [ ] `tests/test_init.py` — covers HA-01, HA-03
- [ ] `tests/test_config_flow.py` — covers HA-02
- [ ] `tests/test_conversation_agent.py` — covers HA-04
- [ ] `pyproject.toml` or `tests/pytest.ini` — `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- [ ] Framework install: `pip install pytest-homeassistant-custom-component pytest-asyncio ruff`

---

## Sources

### Primary (HIGH confidence)
- [Conversation entity — HA Developer Docs](https://developers.home-assistant.io/docs/core/entity/conversation/) — ConversationEntity API, `_async_handle_message`, deprecation of `AbstractConversationAgent`
- [Config flow handler — HA Developer Docs](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/) — `async_step_user`, schema, credential storage in `entry.data`
- [Integration manifest — HA Developer Docs](https://developers.home-assistant.io/docs/creating_integration_manifest/) — required fields, `version`, `config_flow`, `integration_type`
- [Config entry unloading — HA Developer Docs](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-entry-unloading/) — `async_unload_entry`, `async_unload_platforms`

### Secondary (MEDIUM confidence)
- [HA core openai_conversation __init__.py (dev)](https://github.com/home-assistant/core/blob/dev/homeassistant/components/openai_conversation/__init__.py) — `PLATFORMS = ["conversation"]`, `async_forward_entry_setups` pattern (reference implementation)
- [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) — `hass` fixture, `enable_custom_integrations`, flow testing API
- [Extended OpenAI Conversation custom component](https://github.com/jekalmin/extended_openai_conversation) — real-world `ConversationEntity` implementation pattern

### Tertiary (LOW confidence — flag for validation)
- Web search summaries about `AssistantContent` import paths — unverified, requires live HA source inspection
- `integration_type: "service"` recommendation — based on HA docs description, not tested against a running instance

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Python version, voluptuous, manifest fields are stable documented facts
- Architecture: MEDIUM-HIGH — ConversationEntity + PLATFORMS confirmed via HA dev docs search; exact import paths need live verification
- Pitfalls: HIGH — reload lifecycle, unique_id, manifest version are well-documented stable HA requirements
- API change (AbstractConversationAgent → ConversationEntity): HIGH — confirmed via HA dev docs and community sources

**Research date:** 2026-03-30
**Valid until:** 2026-06-30 (HA releases monthly; check for breaking changes in conversation entity API after each HA monthly release)
