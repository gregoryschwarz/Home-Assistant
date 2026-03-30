# Stack Research

**Domain:** Home Assistant custom component — autonomous AI agent (LLM + voice + habit learning)
**Researched:** 2026-03-30
**Confidence:** MEDIUM (based on training knowledge through Aug 2025; web tools unavailable for live verification)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Runtime (HA enforces its own interpreter) | HA 2024.1+ ships Python 3.12; 3.11 is the minimum for async `TaskGroup`, match-statements, and `tomllib`. Do not package a separate interpreter. |
| Home Assistant Core | 2024.11+ | Host platform, entity/state machine, event bus | Target the latest stable release family. 2024.11 introduced Assist pipeline v2 with multi-step conversation turns. 2025.x continues on the same architecture. |
| `anthropic` (Anthropic SDK) | `>=0.27,<1` | Claude API client — completions, tool_use | Official Anthropic Python SDK. `0.27+` introduced `tool_use` as stable and async streaming via `AsyncAnthropic`. Pin a range, not `latest`, to avoid silent breaking changes when Anthropic releases v1. |
| `aiosqlite` | `>=0.20` | Async SQLite access for habit/pattern storage | HA's event loop is asyncio; blocking I/O on the main loop causes watchdog kills. `aiosqlite` wraps `sqlite3` with `asyncio` correctly. Already used by HA core itself (recorder integration), so it is available as a transitive dep — declare it explicitly anyway. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `voluptuous` | `>=0.14` | Config schema validation in `config_flow` and `configuration.yaml` | Always — HA uses voluptuous natively; it validates user inputs in the config entry flow. Do not use Pydantic here (HA does not ship it, and adding it inflates install size). |
| `homeassistant` (dev dep) | matches target HA version | Type stubs, `homeassistant.core`, `homeassistant.helpers` for development | Needed only in your dev environment and tests. Import from `homeassistant.components.assist_pipeline`, `homeassistant.components.conversation`, `homeassistant.helpers.entity_platform`. |
| `pytest-homeassistant-custom-component` | `>=0.13` | HA test harness for custom components | Provides `hass` fixture, mocking of `config_entries`, async test utilities. Without it, testing HA integrations is extremely painful. |
| `pytest-asyncio` | `>=0.23` | Async test runner | Required alongside the HA test harness. Pin `asyncio_mode = "auto"` in `pytest.ini`. |
| `sqlalchemy` | NOT recommended | ORM over SQLite | Avoid — heavy, async support requires `greenlet`, and `aiosqlite` alone is sufficient for the simple key-value / time-series patterns needed here. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `ruff` | Linting + formatting (replaces flake8 + black + isort) | HA core itself migrated to ruff in 2024. Single tool, fast, covers everything. Configure via `pyproject.toml`. |
| `mypy` | Static type checking | HA APIs are fully typed. Running mypy against your component catches misuse of `hass.states`, `hass.services`, async context mismatches early. |
| `pre-commit` | Git hooks for ruff + mypy | Prevents committing code that would fail HA's CI quality checks. |
| VS Code + HA dev container | Local HA instance for manual testing | The official `devcontainer.json` in `homeassistant/core` provides a ready-to-use dev environment. Use it rather than installing HA system-wide. |

---

## Installation

```bash
# In your component's requirements (manifest.json "requirements" field):
# anthropic>=0.27,<1
# aiosqlite>=0.20

# Dev environment (not shipped in the component):
pip install \
  anthropic>=0.27 \
  aiosqlite>=0.20 \
  voluptuous>=0.14 \
  pytest-homeassistant-custom-component>=0.13 \
  pytest-asyncio>=0.23 \
  ruff \
  mypy
```

**Important:** The `requirements` field in `manifest.json` is how HA installs runtime deps. Do NOT use a `requirements.txt` for runtime — only `manifest.json` matters.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `aiosqlite` (raw SQL) | `SQLAlchemy` async | Only if the data model grows to 10+ tables with complex joins — not expected for habit patterns in v1. |
| `aiosqlite` | JSON file on disk | For prototyping only. JSON has no atomic writes, no concurrent-safe reads, no querying. Graduate to SQLite before any production use. |
| `anthropic` SDK (async) | Direct `httpx` calls to the Anthropic REST API | Never — the SDK handles retry logic, token counting, streaming, and `tool_use` protocol details. Rolling your own is not worth it. |
| HA `conversation` integration entity | Standalone HTTP server inside HA | The `conversation` entity approach is the native HA pattern. A standalone server would bypass the Assist pipeline entirely and break voice integration. |
| `voluptuous` | `pydantic` | Only if you are building a standalone Python app, not a HA component. HA's internals are voluptuous-native; mixing Pydantic creates double-validation confusion. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `openai` SDK | Project is locked to Claude/Anthropic. Adding OpenAI creates dead code and a second large dependency. | `anthropic` SDK only |
| LangChain / LlamaIndex | Massive dependency trees, version churn, abstractions that leak badly when HA's async model clashes with LangChain's sync-first design. In 2024-2025, LangChain's HA integrations broke repeatedly on minor version bumps. | Direct `anthropic` SDK calls. At this scale, the abstraction costs more than it saves. |
| `multiprocessing` for blocking I/O | HA's process model is single-process async. Spawning subprocesses for DB or API calls adds IPC complexity and breaks HA's restart/reload lifecycle. | `asyncio` + `aiosqlite` + `anthropic` AsyncAnthropic client |
| `threading.Thread` for the main agent loop | Same as above — HA's `hass.async_create_task()` is the correct primitive. | `hass.async_create_task()` / `asyncio.create_task()` |
| HA Add-on (Docker container) | PROJECT.md explicitly rules this out. An add-on would require a separate REST/WebSocket bridge to HA, losing direct entity access. | Custom component in `custom_components/ha_ai_agent/` |
| Storing raw conversation text in the habit DB | Privacy risk — if the DB is ever exported, full user conversations are exposed. | Store only extracted intent/pattern metadata, not raw text. |

---

## Stack Patterns by Variant

**For the conversation entity (text interface):**
- Implement `homeassistant.components.conversation.AbstractConversationAgent`
- Register via `async_setup_entry` calling `conversation.async_set_agent(hass, entry, agent)`
- This makes the component appear as a selectable "Conversation agent" in HA Settings > Voice Assistants
- The Assist pipeline calls `async_process(ConversationInput)` → return `ConversationResult`
- Confidence: HIGH (stable API since HA 2023.5, unchanged through 2025.x)

**For voice pipeline integration (STT + TTS):**
- Do NOT implement your own STT/TTS — plug into HA's existing `assist_pipeline`
- The pipeline chains: Wake word → STT → Conversation agent → TTS
- Your component is the "Conversation agent" step only
- STT: recommend `faster-whisper` via the `wyoming` protocol (Wyoming integration, local, fast)
- TTS: recommend `piper` via `wyoming` (local, no cloud) or cloud TTS built into HA
- Confidence: MEDIUM (Wyoming + Piper became the standard local stack in 2024)

**For habit/pattern storage:**
- Use SQLite via `aiosqlite`, file path: `hass.config.path("ha_ai_agent.db")`
- Schema: `events` table (timestamp, entity_id, action, context), `patterns` table (pattern_id, rule, confidence, last_triggered)
- Run migrations in `async_setup_entry` using a version integer stored in a `meta` table
- Confidence: HIGH (pattern established by HA recorder integration)

**For Claude API calls:**
- Use `AsyncAnthropic` (not the sync `Anthropic` client) — HA is async-native
- Wrap calls in `hass.async_add_executor_job()` only if you must use sync code; prefer the async client
- Use `tool_use` / function calling to give Claude access to HA service calls as tools — more reliable than parsing free-text responses
- Model: `claude-sonnet-4-6` as specified in PROJECT.md (confirm it is available in your API tier)
- Confidence: HIGH for async client pattern; MEDIUM for `tool_use` as the right architecture (best practice confirmed in 2024-2025 HA community integrations)

**For config flow (UI-based setup):**
- Implement `homeassistant.config_entries.ConfigFlow` with `async_step_user`
- Validate the Anthropic API key during setup by making a minimal API call
- Store the key via `config_entry.data` (encrypted by HA's credential store on supported platforms)
- Use `OptionsFlow` for runtime settings (model choice, verbosity, habit learning toggle)
- Confidence: HIGH (standard HA pattern, well-documented)

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `anthropic>=0.27,<1` | Python 3.11, 3.12 | `0.27` added stable `tool_use`. Avoid `<0.20` (old `completion` API, not `messages`). |
| `aiosqlite>=0.20` | Python 3.11, 3.12 | `0.20` added proper `asynccontextmanager` support. Works with Python's built-in `sqlite3`. |
| `pytest-homeassistant-custom-component>=0.13` | HA 2024.1+ | Must match your target HA version. Check the package changelog — it releases in lockstep with HA. |
| HA `conversation.AbstractConversationAgent` | HA 2023.5+ | API stable. The `ConversationInput`/`ConversationResult` dataclasses were stabilized in 2023.5 and are unchanged through 2025.x (to knowledge cutoff). |
| `wyoming` protocol for STT/TTS | HA 2023.9+ | Introduced in 2023.9. Stable integration path. Requires running a separate Wyoming satellite (Piper, Whisper) — usually as an HA add-on or separate process. |

---

## Key Architecture Decision: manifest.json

The `manifest.json` is the entry point for HA's component loader. Critical fields for this project:

```json
{
  "domain": "ha_ai_agent",
  "name": "HA Autonomous AI Agent",
  "version": "0.1.0",
  "documentation": "",
  "requirements": ["anthropic>=0.27,<1", "aiosqlite>=0.20"],
  "dependencies": ["conversation", "assist_pipeline"],
  "after_dependencies": ["wyoming"],
  "codeowners": [],
  "config_flow": true,
  "iot_class": "cloud_polling",
  "quality_scale": "custom"
}
```

- `dependencies`: HA will load `conversation` and `assist_pipeline` before this component
- `iot_class`: `cloud_polling` because it calls the Anthropic API (cloud). Habit learning is local but the LLM calls are not.
- `quality_scale`: `custom` — custom components cannot claim `internal` or `platinum`

---

## Sources

- Training knowledge (Python, HA architecture, Anthropic SDK) — cutoff August 2025
- Confidence levels: HIGH = stable HA patterns confirmed across multiple release cycles; MEDIUM = patterns observed in 2024-2025 community integrations but not verified against live docs; LOW = architectural judgment calls
- **Note:** WebSearch and WebFetch were unavailable during this research session. Verify `anthropic` package version at https://pypi.org/project/anthropic/ before pinning. Verify HA conversation API at https://developers.home-assistant.io/docs/core/conversation/custom_agent before implementation.

---
*Stack research for: HA autonomous AI agent custom component*
*Researched: 2026-03-30*
