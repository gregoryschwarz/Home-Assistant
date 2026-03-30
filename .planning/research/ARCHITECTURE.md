# Architecture Research

**Domain:** Home Assistant custom component — autonomous AI agent (LLM + voice + habit learning)
**Researched:** 2026-03-30
**Confidence:** MEDIUM (training data through Aug 2025; web verification denied — flag critical interfaces for validation)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USER INPUT LAYER                               │
│  ┌───────────────────┐          ┌───────────────────────────────┐    │
│  │  Voice (mic)       │          │  Text (UI card / dashboard)   │    │
│  │  Satellite device  │          │  REST / WebSocket             │    │
│  └────────┬──────────┘          └──────────────┬────────────────┘    │
└───────────┼──────────────────────────────────────┼────────────────────┘
            │                                      │
            ▼                                      ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     HOME ASSISTANT CORE                               │
│                                                                       │
│  ┌─────────────────────────┐    ┌────────────────────────────────┐   │
│  │   assist_pipeline        │    │   conversation integration     │   │
│  │  (STT → NLU → TTS)       │    │   (routes text to agent)       │   │
│  │  homeassistant/components│    │   /api/conversation/process    │   │
│  └──────────┬──────────────┘    └──────────────┬─────────────────┘   │
│             │                                   │                     │
│             └──────────────────┬────────────────┘                     │
│                                ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │             HA Event Bus  /  State Machine  /  Service Registry  │  │
│  └──────────────────────────────┬──────────────────────────────────┘  │
└─────────────────────────────────┼──────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   CUSTOM COMPONENT: ha_ai_agent                       │
│                                                                       │
│  ┌───────────────────┐   ┌──────────────────┐   ┌─────────────────┐  │
│  │  ConversationAgent │   │  IntentRouter     │   │  HabitEngine    │  │
│  │  (AbstractAgent)   │──▶│  (local rules +  │──▶│  (observer +   │  │
│  │  handles process() │   │   LLM fallback)   │   │   pattern store)│  │
│  └───────────────────┘   └─────────┬────────┘   └────────┬────────┘  │
│                                    │                      │           │
│                     ┌──────────────┴──────┐    ┌──────────┴────────┐  │
│                     │  ClaudeClient        │    │  LocalStorage     │  │
│                     │  (Anthropic SDK)     │    │  (SQLite / JSON)  │  │
│                     │  async, streaming    │    │  /config/storage/ │  │
│                     └──────────────────────┘    └───────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                             │
│                                                                       │
│   ┌─────────────────────────────┐    ┌──────────────────────────┐    │
│   │  Anthropic API               │    │  HA Entity Platform       │    │
│   │  claude-sonnet-4-6           │    │  (lights, covers,        │    │
│   │  Messages API                │    │   climate, media, locks)  │    │
│   └─────────────────────────────┘    └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `assist_pipeline` (HA core) | Orchestrates voice: STT → wake word → NLU → TTS. Calls registered conversation agent | Built-in HA pipeline, configured in UI. Selects agent by config entry id |
| `conversation` (HA core) | Exposes `/api/conversation/process` REST endpoint and `conversation.process` service. Routes text to the active conversation agent | Built-in integration. Custom agent registers here via `conversation.async_set_agent()` |
| `ConversationAgent` (custom) | Entry point for all user input (text+voice). Implements `AbstractConversationAgent.async_process()`. Returns `ConversationResult` | Subclass of `homeassistant.components.conversation.AbstractConversationAgent` |
| `IntentRouter` (custom) | Decides: handle locally with rules, or escalate to Claude. Builds context for LLM (entity states, history) | Pure Python class. Runs deterministic regex/keyword matching first, then delegates to `ClaudeClient` |
| `ClaudeClient` (custom) | Wraps Anthropic Python SDK. Manages API key, system prompt, conversation history window, async calls | Thin async wrapper; handles retries, error translation, token budget |
| `HabitEngine` (custom) | Subscribes to HA event bus (`state_changed`). Detects recurring patterns (time + entity + user). Generates suggestions or automatic triggers | Event listener + time-series analysis over local storage |
| `LocalStorage` (custom) | Persists: conversation history window, habit patterns, user preferences, entity aliases | SQLite via `aiosqlite` (async-safe) or HA's built-in `Store` (JSON). Lives in `hass.config.path("custom_components/ha_ai_agent/")` |
| `config_entries` (HA core) | Stores API key, model name, thresholds. Manages component lifecycle (setup/unload) | Standard HA `ConfigEntry`; options flow for runtime changes |

---

## Recommended Project Structure

```
custom_components/ha_ai_agent/
├── __init__.py              # async_setup_entry(), async_unload_entry(), component setup
├── manifest.json            # domain, version, dependencies, codeowners, iot_class
├── config_flow.py           # UI-driven setup: API key input, model selection, test connection
├── const.py                 # DOMAIN, default values, config keys, event names
├── conversation_agent.py    # HaAiConversationAgent(AbstractConversationAgent)
├── intent_router.py         # IntentRouter: local rules → LLM decision tree
├── claude_client.py         # ClaudeClient: async Anthropic SDK wrapper
├── habit_engine.py          # HabitEngine: event listener, pattern detector
├── storage.py               # AgentStorage: aiosqlite or hass.helpers.storage.Store
├── entity_context.py        # Builds HA entity state snapshots for LLM context
├── strings.json             # UI strings (config flow labels, descriptions)
├── translations/
│   └── en.json              # English translations for UI
└── services.yaml            # Custom service declarations (if exposing HA services)
```

### Structure Rationale

- `__init__.py` is the HA entry point — must define `async_setup_entry` and `async_unload_entry`. Keep it thin; delegate to other modules.
- `conversation_agent.py` is the single integration boundary with HA's conversation system — one class, one responsibility.
- `intent_router.py` contains the hybrid logic; separating it from the agent makes it independently testable.
- `claude_client.py` isolates all Anthropic SDK calls — easier to mock in tests and swap model versions.
- `habit_engine.py` runs as a long-lived async listener; must be set up and torn down with the config entry lifecycle.
- `storage.py` abstracts persistence — allows switching between JSON `Store` (simple) and SQLite (scalable) without touching business logic.

---

## Architectural Patterns

### Pattern 1: AbstractConversationAgent Registration

**What:** HA's `conversation` integration exposes a registration API. Custom agents implement `AbstractConversationAgent` and register themselves at setup time. The `assist_pipeline` and UI conversation panel then route text to the active registered agent.

**When to use:** This is the only supported pattern for plugging a custom LLM into HA's conversation and voice pipeline. Mandatory for this project.

**Trade-offs:** Ties you to HA's `ConversationResult` / `ConversationInput` data model. HA may change internal interfaces across versions — pin HA version in `manifest.json` `homeassistant` field.

**Example:**
```python
# conversation_agent.py
from homeassistant.components.conversation import AbstractConversationAgent, ConversationInput, ConversationResult

class HaAiConversationAgent(AbstractConversationAgent):
    """Custom conversation agent backed by Claude."""

    @property
    def supported_languages(self) -> list[str]:
        return ["fr", "en"]  # declare supported locales

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Called by HA for every utterance."""
        response_text = await self._intent_router.route(user_input.text, user_input.context)
        # Return HA-compatible result
        ...

# __init__.py — register at setup
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    agent = HaAiConversationAgent(hass, entry)
    conversation.async_set_agent(hass, entry, agent)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    conversation.async_unset_agent(hass, entry)
    return True
```

**Confidence:** MEDIUM — `AbstractConversationAgent` API existed in HA 2023.x and was stable through 2024.x. Verify exact import path and `async_set_agent` signature against HA 2024.x+ source before building.

---

### Pattern 2: Hybrid Local-Rules / LLM Routing

**What:** Route user intents through a fast deterministic layer first. Only invoke Claude when local rules cannot match with sufficient confidence. This controls API cost and latency.

**When to use:** Always — avoids sending "turn on the lights" to an LLM API when a regex suffices.

**Trade-offs:** Local rule set needs maintenance as vocabulary grows. Risk of rules blocking valid LLM calls if thresholds are too high. Tune via user feedback loop.

**Example:**
```python
# intent_router.py
class IntentRouter:
    LOCAL_PATTERNS = [
        (r"(allume|turn on)\s+(?P<entity>.+)", "turn_on"),
        (r"(éteins|turn off)\s+(?P<entity>.+)", "turn_off"),
    ]

    async def route(self, text: str, context: Context) -> str:
        # 1. Try local rules
        for pattern, service in self.LOCAL_PATTERNS:
            if m := re.search(pattern, text, re.IGNORECASE):
                entity = self._resolve_entity(m.group("entity"))
                if entity:
                    await self._call_ha_service(service, entity)
                    return f"Done — {service} {entity}"

        # 2. Fall back to Claude
        return await self._claude_client.ask(
            text,
            entity_context=self._entity_context.snapshot()
        )
```

---

### Pattern 3: Config Entry Lifecycle Management

**What:** All component resources (listeners, HTTP sessions, DB connections) must be created in `async_setup_entry` and destroyed in `async_unload_entry`. This ensures HA can reload the component without restart.

**When to use:** Mandatory for all long-lived resources (HabitEngine event listeners, aiosqlite connections, aiohttp sessions for Anthropic SDK).

**Trade-offs:** Adds boilerplate but is required for HA integration quality standards (needed if ever submitting to HACS or core).

**Example:**
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    storage = AgentStorage(hass)
    await storage.async_load()

    habit_engine = HabitEngine(hass, storage)
    # Register event listener — returns a callable to remove it
    unsubscribe = hass.bus.async_listen(EVENT_STATE_CHANGED, habit_engine.handle_state_change)

    hass.data[DOMAIN][entry.entry_id] = {
        "storage": storage,
        "habit_engine": habit_engine,
        "unsubscribe": unsubscribe,
    }
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data[DOMAIN].pop(entry.entry_id)
    data["unsubscribe"]()          # remove event listener
    await data["storage"].async_close()
    return True
```

---

### Pattern 4: Entity Context Snapshot for LLM

**What:** Before calling Claude, build a structured snapshot of relevant HA entity states. Include only entities relevant to the domain of the user's request (reduce token usage). Inject as system context.

**When to use:** Every LLM call. Essential for grounding Claude in current home state.

**Trade-offs:** Large homes (100+ entities) can produce bloated context. Filter by area, domain, or recently-changed entities. Cache snapshot with a short TTL (5s) to avoid redundant state reads.

**Example:**
```python
# entity_context.py
class EntityContextBuilder:
    def snapshot(self, domains: list[str] | None = None) -> str:
        states = self.hass.states.async_all(domains)
        lines = [f"{s.entity_id}: {s.state} ({s.attributes})" for s in states[:50]]
        return "\n".join(lines)
```

---

## Data Flow

### Primary Flow: Voice Command → HA Action

```
[User speaks]
    │
    ▼
[Wyoming satellite / local mic]
    │  raw audio stream
    ▼
[assist_pipeline (HA core)]
    │  STT → transcribed text
    ▼
[conversation.async_process()]
    │  ConversationInput(text, language, context)
    ▼
[HaAiConversationAgent.async_process()]
    │  text + metadata
    ▼
[IntentRouter.route()]
    │
    ├──[Local rule match?]──YES──▶ [hass.services.async_call()]
    │                                     │
    │                              [HA Service Registry]
    │                                     │
    │                              [Entity state changed]
    │                                     │
    └──[No match]──▶ [ClaudeClient.ask()]  │
                          │                │
                    [Anthropic API]        │
                          │                │
                    [LLM response]         │
                          │                │
                    [Parse tool_use/text]──┘
                          │
                    [hass.services.async_call() if action]
                          │
    ◀─────────────────────┘
    [ConversationResult(response_text)]
    │
    ▼
[assist_pipeline]
    │  TTS synthesis
    ▼
[Audio output to user]
```

### Habit Learning Flow

```
[Any entity state_changed event]
    │
    ▼
[HabitEngine.handle_state_change()]
    │  filters: was it user-initiated? what time?
    ▼
[LocalStorage — append event record]
    │  entity_id, new_state, timestamp, context
    ▼
[Pattern analysis (async, scheduled)]
    │  detect: same entity, same state, same time window, N+ occurrences
    ▼
[Pattern stored as "habit"]
    │
    ├──[Suggestion mode] ──▶ [notify user via HA notification]
    │
    └──[Auto-execute mode]──▶ [hass.services.async_call() at trigger time]
```

### LLM Context Assembly Flow

```
[User utterance received]
    │
    ├──▶ [EntityContextBuilder.snapshot()]
    │        → current states of relevant entities
    │
    ├──▶ [LocalStorage.get_conversation_history()]
    │        → last N turns (sliding window, e.g. 10 messages)
    │
    ├──▶ [LocalStorage.get_relevant_habits()]
    │        → habits matching current time / entities
    │
    └──▶ [Claude Messages API]
             system: "You control a home assistant. Current state: {entity_context}
                      Known habits: {habits}. Reply with actions or clarifications."
             messages: [{role, content}, ...history..., {role: user, content: utterance}]
```

### Key Data Flows

1. **Config persistence:** API key + options stored in HA `ConfigEntry.data` / `ConfigEntry.options` — never in custom files. Read via `entry.data["api_key"]`.
2. **Habit data persistence:** Written to `hass.config.path()` via `aiosqlite` or `hass.helpers.storage.Store`. Must use async I/O — never blocking file operations in the event loop.
3. **Service calls:** `await hass.services.async_call(domain, service, service_data, blocking=False)` — non-blocking; HA handles execution asynchronously.
4. **State reads:** `hass.states.get(entity_id)` is synchronous and safe in the event loop (in-memory state machine). No async needed for reads.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Anthropic API | `anthropic.AsyncAnthropic` client, `await client.messages.create(...)`. Key from `ConfigEntry.data` | Use `tool_use` / function calling for structured action extraction. Handle `RateLimitError`, `APIError` with exponential backoff. Budget: set `max_tokens` to control cost |
| HA STT providers | Registered via `assist_pipeline` — component does NOT need to implement STT. Pipeline handles Whisper, Google, etc. | Component receives already-transcribed text. No STT code needed in custom component |
| HA TTS providers | Same — `assist_pipeline` calls TTS after receiving text response from conversation agent | Return plain text from `async_process()`. Pipeline handles synthesis |
| HA entity platform | `hass.services.async_call()` for actions. `hass.states.async_all()` / `hass.states.get()` for state reads | Never import entity modules directly — use the service/state API for decoupling |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `ConversationAgent` ↔ `IntentRouter` | Direct async method call (same process) | `IntentRouter` is a dependency-injected collaborator, not a separate service |
| `IntentRouter` ↔ `ClaudeClient` | Direct async method call | `ClaudeClient` is awaited; handles its own retry logic |
| `IntentRouter` ↔ HA core | `hass.services.async_call()`, `hass.states.get()` | Only interaction point with HA core from router layer |
| `HabitEngine` ↔ HA event bus | `hass.bus.async_listen(EVENT_STATE_CHANGED, handler)` | Returns unsubscribe callable — must be stored and called at unload |
| `HabitEngine` ↔ `LocalStorage` | Direct async method call | Storage is injected; engine never touches I/O directly |
| All components ↔ `LocalStorage` | Async read/write via `AgentStorage` interface | Single access point to disk — prevents concurrent write conflicts |

---

## Suggested Build Order

Dependencies determine order. Later phases depend on earlier ones being stable.

```
Phase 1: Foundation (HA wiring, no AI)
    manifest.json + __init__.py + config_flow.py + const.py
    → Component loads, API key stored, config entry works
    → Validate: component appears in HA integrations panel

Phase 2: Conversation bridge (text → HA actions, no LLM)
    conversation_agent.py + intent_router.py (local rules only) + entity_context.py
    → Text commands work via HA conversation panel
    → Validate: "turn on lights" works without Claude

Phase 3: LLM integration (Claude added to router)
    claude_client.py + extend intent_router.py (LLM fallback)
    → Complex/ambiguous commands resolved by Claude
    → Validate: "make it cozy" triggers appropriate scene

Phase 4: Voice pipeline
    No new code — configure assist_pipeline to use Phase 2-3 agent
    → Voice input flows through existing ConversationAgent
    → Validate: wake word → voice command → entity action → TTS response

Phase 5: Habit engine
    storage.py + habit_engine.py (listener + pattern detection)
    → Patterns detected and stored
    → Validate: repeated actions create habit records

Phase 6: Habit feedback loop
    Extend ConversationAgent + IntentRouter to consume habits from storage
    + notification service for suggestions
    → Claude context includes known habits
    → Validate: habit suggestions appear at right time
```

**Rationale for this order:**
- Phase 1 before anything: HA lifecycle must work or nothing runs
- Phase 2 before Phase 3: validates HA integration without API dependency; cheap to iterate
- Phase 3 after Phase 2: LLM is an enhancement to an already-working router
- Phase 4 is nearly free once Phases 2-3 work — no custom code needed for voice
- Phase 5-6 after Phase 3: habits need a working conversation loop to be meaningful

---

## Scaling Considerations

This is a single-household system. Scaling here means: handling more entities, more commands, more habits — not horizontal scaling.

| Concern | At 10 entities / light use | At 100+ entities / heavy use |
|---------|---------------------------|------------------------------|
| Entity context size | Full snapshot fits in one LLM message | Filter to relevant domain/area before sending; cache snapshot |
| Habit storage | JSON `Store` sufficient | Switch to SQLite (`aiosqlite`) for indexed queries by time/entity |
| API cost | Low (~few calls/day) | Implement local rule cache to absorb frequent repeated commands |
| Event bus load | `state_changed` listener is negligible | Add debounce / filter to `HabitEngine` (ignore rapid flapping states) |
| LLM latency | 1-3s acceptable for voice | Add loading indicator; consider streaming `Messages` API for faster first-token |

### Scaling Priorities

1. **First bottleneck:** LLM context size — filter entity snapshots early, use domain/area filters.
2. **Second bottleneck:** API call volume — expand local rules incrementally as usage patterns emerge from habit data.

---

## Anti-Patterns

### Anti-Pattern 1: Blocking I/O in the Event Loop

**What people do:** Use `open()`, `json.load()`, synchronous SQLite, `requests.get()` inside `async def` functions.

**Why it's wrong:** HA runs on a single-threaded asyncio event loop. Any blocking call freezes the entire HA instance — all automations, integrations, UI stop responding.

**Do this instead:** Use `aiofiles` or `aiosqlite` for file/DB I/O. Use `httpx.AsyncClient` or `aiohttp` for HTTP. Use `hass.async_add_executor_job(sync_fn)` only when a synchronous library cannot be avoided.

---

### Anti-Pattern 2: Storing Secrets Outside ConfigEntry

**What people do:** Write API keys to a custom JSON file, hardcode in `const.py`, or store in `hass.data`.

**Why it's wrong:** HA's `ConfigEntry` data is encrypted at rest (in recent HA versions), supports secret redaction in logs, and integrates with the UI credential management system.

**Do this instead:** Store API key in `entry.data` via the config flow. Read it as `entry.data[CONF_API_KEY]`. Never log it.

---

### Anti-Pattern 3: Using `hass.loop.run_until_complete()` or `asyncio.run()`

**What people do:** Try to call async functions from a synchronous context inside a custom component.

**Why it's wrong:** HA already owns the event loop. Nesting loops causes deadlocks.

**Do this instead:** All component code must be async from top to bottom. Use `hass.async_create_task()` to fire-and-forget coroutines. Use `async_call_later` for delayed execution.

---

### Anti-Pattern 4: Registering the Conversation Agent Outside the Config Entry

**What people do:** Call `conversation.async_set_agent()` in a global `async_setup()` function instead of `async_setup_entry()`.

**Why it's wrong:** If the config entry is reloaded or disabled, the agent stays registered and may operate with stale configuration (wrong API key, etc.).

**Do this instead:** Always register in `async_setup_entry` and unregister in `async_unload_entry`. Mirror every registration with a cleanup.

---

### Anti-Pattern 5: Sending Full Home State to LLM on Every Request

**What people do:** Dump all 200 entity states into the system prompt for every message.

**Why it's wrong:** Inflates token usage (cost), increases latency, and dilutes LLM attention on relevant context.

**Do this instead:** Build a scoped `EntityContextBuilder` that selects entities by: (a) domain mentioned in utterance, (b) area/room mentioned, (c) recently-changed entities, (d) entities in known habits. Default to top 30-50 entities maximum.

---

## Sources

- Home Assistant Developer Documentation — custom components, config entries, conversation integration (training data, HIGH confidence for patterns stable since 2023.x)
- `homeassistant/components/conversation/` source (AbstractConversationAgent interface) — MEDIUM confidence; verify exact method signatures against HA 2024.x source
- `homeassistant/components/assist_pipeline/` — pipeline orchestration, STT/TTS selection — MEDIUM confidence
- Anthropic Python SDK — `anthropic.AsyncAnthropic`, `client.messages.create()` — HIGH confidence (SDK stable, async client well-documented)
- HA integration quality scale requirements (blocking I/O, config entry lifecycle) — HIGH confidence, stable across versions
- `hass.helpers.storage.Store` for JSON persistence — HIGH confidence, standard pattern since HA 2021.x

**Note:** WebSearch and WebFetch were unavailable during this research session. All findings derive from training data (cutoff Aug 2025). Recommend validating the following before building:
1. Exact import path for `AbstractConversationAgent` in HA 2024.x+ (`homeassistant.components.conversation` vs sub-module)
2. Exact signature of `conversation.async_set_agent()` / `async_unset_agent()` — may use `entry` object or `agent_id` string depending on HA version
3. `assist_pipeline` agent selection API — how a config entry's conversation agent is selected as the pipeline backend

---
*Architecture research for: HA autonomous AI agent (custom component)*
*Researched: 2026-03-30*
