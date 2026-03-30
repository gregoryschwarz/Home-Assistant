# Project Research Summary

**Project:** HA Autonomous AI Agent (custom component)
**Domain:** Home Assistant custom component — LLM agent with voice, text, and habit learning
**Researched:** 2026-03-30
**Confidence:** MEDIUM

## Executive Summary

This project is a Home Assistant custom component that plugs Claude (via the Anthropic API) into HA's native voice and conversation pipeline, adds a habit-learning engine backed by local SQLite storage, and routes commands through a hybrid local-rules/LLM layer. It is the only existing solution that combines all four capabilities: Claude LLM, HA-native voice pipeline, habit learning/memory, and hybrid local-rule routing. The correct implementation pattern is a subclass of `AbstractConversationAgent` registered via `conversation.async_set_agent()` at config entry setup time — this is the single officially-supported path for plugging a custom LLM into HA's Assist voice pipeline and conversation UI.

The recommended build sequence follows a strict dependency order: HA scaffolding first (lifecycle, config flow), then a working conversation bridge with local rules only, then Claude added as a fallback to that working bridge, then voice (which is nearly free once the agent is registered), then habit storage and pattern detection, and finally the feedback loop that surfaces habit suggestions. This order is dictated by architecture: the habit engine is meaningless without a working conversation loop, and Claude integration should never be the first thing wired up because it creates an untestable dependency on an external API during the critical scaffold phase.

The top risks are: (1) blocking HA's asyncio event loop with the synchronous Anthropic SDK client — this freezes the entire HA instance and must be prevented from day one by using `AsyncAnthropic`; (2) sending raw `hass.states.async_all()` to Claude on every request — this causes token cost explosion and latency that makes the product feel broken; and (3) prompt injection via voice input triggering unintended entity control — mitigated by a structured output schema and a service call whitelist that must be in place before any real device control is wired up.

---

## Key Findings

### Recommended Stack

The stack is Python 3.12 (HA's bundled runtime — do not package a separate interpreter), the `anthropic` SDK pinned to `>=0.27,<1` for stable `tool_use` and async client support, and `aiosqlite>=0.20` for habit storage. All three are async-native, which is mandatory because HA runs on a single-threaded asyncio event loop. Development tooling is `ruff` (linting/formatting, matches HA core's own tooling) and `pytest-homeassistant-custom-component>=0.13` with `pytest-asyncio>=0.23` for testing. `voluptuous` handles config schema validation natively within HA's config entry system.

**Core technologies:**
- Python 3.12: HA's bundled runtime — do not package separately
- `anthropic>=0.27,<1`: Official Anthropic async SDK; `tool_use` stable in this range; never use the sync `Anthropic()` client inside HA
- `aiosqlite>=0.20`: Async SQLite for habit/pattern storage; crash-safe with WAL mode; already a transitive HA dep
- `voluptuous>=0.14`: Config schema validation — HA-native; do not use Pydantic
- `homeassistant.components.conversation.AbstractConversationAgent`: The only supported public API for custom LLM conversation agents

**Explicitly avoid:** LangChain/LlamaIndex (async model incompatibility, version churn), SQLAlchemy (unnecessary weight for simple key-value/time-series storage), `multiprocessing` or `threading.Thread` (incompatible with HA's asyncio model), HA add-on pattern (loses direct entity access).

### Expected Features

The MVP requires seven P1 items that must all ship together or the product feels incomplete. The most technically demanding P1 item is entity list injection into the LLM context — without it, Claude cannot control devices. Basic habit event listening must also start in v1 even if suggestions are not yet surfaced, because the pattern store needs real data before suggestions make sense (minimum ~2 weeks).

**Must have (table stakes):**
- Config flow with API key entry and model selection — gates all other functionality
- Conversation entity registration — makes the component selectable in HA voice assistants settings
- Claude API integration with multi-turn message history — core NLU
- Entity list injection into system prompt (filtered by configured domains) — without this, entity control is blind
- LLM tool-calling for HA service calls — the actual control loop
- API failure fallback — production baseline; silent failures are unacceptable
- Habit event listener + SQLite storage — data collection must start in v1

**Should have (competitive differentiators):**
- Hybrid routing (local rule cache) — reduces API cost and latency for frequent commands
- Habit pattern detection + proactive suggestions — core differentiator vs all competitors
- Contextual user preference memory — persists preferences across sessions
- Multi-user awareness (user_id keying) — supports household members with different habits
- Explainable actions — surfaces rationale for agent-initiated actions

**Defer (v2+):**
- Fully autonomous decisions without prompt trigger — requires validated habit store and user trust baseline
- Named automation creation via voice — HA automation schema complexity is significant
- Multi-LLM backend abstraction — add only if Claude API becomes a hard blocker

### Architecture Approach

The component has five internal classes with clearly separated responsibilities, registered with HA via the standard `config_entries` lifecycle. `ConversationAgent` is the single HA integration boundary; `IntentRouter` contains the hybrid routing logic (deterministic first, Claude fallback) and is independently testable; `ClaudeClient` is a thin async wrapper that isolates all Anthropic SDK calls for easy mocking; `HabitEngine` subscribes to HA's event bus and writes patterns to storage; `AgentStorage` provides a single async access point to SQLite, preventing concurrent write conflicts. All resources are created in `async_setup_entry` and destroyed in `async_unload_entry`.

**Major components:**
1. `HaAiConversationAgent` (subclass of `AbstractConversationAgent`) — single HA integration boundary; implements `async_process(ConversationInput) -> ConversationResult`
2. `IntentRouter` — hybrid local-rules/LLM routing; deterministic regex matching first, Claude escalation on no-match
3. `ClaudeClient` — async Anthropic SDK wrapper; manages API key, system prompt, conversation history window, retries
4. `HabitEngine` — subscribes to `state_changed` events; detects recurring patterns; generates suggestions or auto-triggers
5. `AgentStorage` — async SQLite access via `aiosqlite`; single write path; schema versioning from day one
6. `EntityContextBuilder` — builds scoped entity state snapshots for LLM context; filters by domain/area; capped at 50 entities max

### Critical Pitfalls

1. **Blocking HA's event loop with the sync Anthropic client** — use `AsyncAnthropic` and `await` everywhere from day one; never retrofit; a 2-second Claude call freezes the entire HA instance
2. **Sending full entity state dump to Claude on every request** — implement `EntityContextBuilder` with domain/area filtering before wiring Claude to real entity states; cap at 50 entities; cache snapshots with a short TTL
3. **Prompt injection via voice input** — separate system instructions from user input using proper message roles; implement a service call whitelist; validate Claude's structured JSON output before executing any `hass.services.async_call`
4. **Resource leaks on integration reload** — implement `async_unload_entry` that cancels tasks, removes event listeners, closes DB connections; test with UI "Reload" not just HA restart
5. **Habit storage corruption on crash** — use SQLite with WAL mode (`PRAGMA journal_mode=WAL`); version the schema from day one; implement TTL purging; cap store at 10,000 events

---

## Implications for Roadmap

Based on the combined research, the architecture research's six-phase build order is well-reasoned and directly follows dependency chains. The phase groupings below refine it with pitfall prevention integrated.

### Phase 1: HA Component Scaffold

**Rationale:** HA lifecycle must work correctly before any feature code is written. Async patterns, config entry lifecycle, and migration skeleton cannot be retrofitted — they establish the foundation everything else runs on. HACS manifest must also be correct from the first commit.
**Delivers:** Component loads in HA, API key is stored securely via config flow, config entry setup/unload cycle works cleanly, manifest.json is HACS-compliant.
**Addresses:** Config flow (P1 table stakes), persistent configuration (P1), Claude API key management (P1)
**Avoids:** Event loop blocking (establish async patterns before feature code), resource leaks on reload (implement full unload skeleton), config entry migration failures (implement `async_migrate_entry` stub), HACS manifest gaps

### Phase 2: Conversation Bridge (Local Rules, No LLM)

**Rationale:** Validate the HA conversation integration without any external API dependency. A working local-rules conversation agent is independently valuable and provides a fast-path fallback. Proves entity control mechanics before adding LLM complexity.
**Delivers:** `HaAiConversationAgent` registered and selectable in HA voice assistants; `IntentRouter` with regex-based local rules; entity state snapshot for context; service call execution; HA conversation panel works for common commands.
**Uses:** `homeassistant.components.conversation.AbstractConversationAgent`, `hass.services.async_call()`, `EntityContextBuilder`
**Implements:** ConversationAgent, IntentRouter (local path), EntityContextBuilder

### Phase 3: Claude LLM Integration

**Rationale:** LLM is an enhancement to an already-working conversation bridge. Claude is added as the fallback branch of the existing `IntentRouter`, meaning all HA integration complexity is already solved. Privacy and security controls (entity filtering, prompt injection prevention, action whitelist) must ship in this phase — not deferred.
**Delivers:** Complex/ambiguous commands resolved by Claude; multi-turn conversation history; entity-filtered context sent to Claude; structured output schema with service call whitelist; API failure fallback activates local rules; privacy disclosure in config flow.
**Uses:** `anthropic.AsyncAnthropic`, `tool_use` for structured HA service calls, `ClaudeClient` wrapper
**Avoids:** Full entity state dump (entity filter in place), prompt injection (action whitelist + structured schema), privacy/entity leakage

### Phase 4: Voice Pipeline

**Rationale:** Nearly free once Phase 2-3 are working. No new component code is required — this phase is HA configuration: select the registered conversation agent as the assist_pipeline backend, configure STT (Wyoming/Whisper) and TTS (Piper). Voice input flows through the existing `ConversationAgent.async_process()`.
**Delivers:** Wake word → voice command → entity action → TTS response end-to-end.
**Uses:** HA `assist_pipeline`, Wyoming protocol, Whisper STT, Piper TTS
**Avoids:** Implementing custom STT/TTS (HA pipeline handles this); avoid calling `assist_pipeline` internals directly

### Phase 5: Habit Engine

**Rationale:** Requires the conversation loop from Phase 2-3 to be meaningful. Habit data collection must start here so patterns can accumulate before suggestions are possible. Storage safety (WAL mode, schema versioning, TTL) must be built into the initial design.
**Delivers:** `HabitEngine` subscribing to `state_changed` events; `AgentStorage` with crash-safe SQLite (WAL mode); event records with timestamp/entity/user context; schema versioning and TTL purge on startup; pattern detection algorithm.
**Uses:** `aiosqlite>=0.20`, SQLite WAL mode, `hass.bus.async_listen(EVENT_STATE_CHANGED, ...)`
**Avoids:** Habit storage corruption, unbounded growth, using Claude for batch habit analysis (use local frequency/time-series algorithms instead)

### Phase 6: Habit Feedback Loop

**Rationale:** Depends on Phase 5 having accumulated real data (~2 weeks minimum). Closes the loop: habits flow from storage into Claude's context and surface as proactive suggestions via HA notifications. Multi-user awareness is naturally added here by keying the habit store on `context.user_id`.
**Delivers:** Habit context injected into Claude system prompt; proactive suggestions via HA persistent notifications; explainable actions (rationale string alongside executed action); multi-user habit store keying; contextual user preference memory.
**Uses:** `hass.helpers.entity_registry`, HA notification service, `AsyncAnthropic` with habit-enriched system prompt
**Implements:** Full habit feedback loop (HabitEngine → LocalStorage → ClaudeClient context enrichment → ConversationAgent)

### Phase Ordering Rationale

- Phase 1 before everything: HA lifecycle correctness cannot be retrofitted; wrong async or lifecycle patterns corrupt all downstream code
- Phase 2 before Phase 3: validates entity control without API dependency; cheap iteration loop; establishes the router that Phase 3 extends
- Phase 3 after Phase 2: Claude is strictly an enhancement to a working system, never its foundation
- Phase 4 after Phase 2-3: requires no new code; voice just routes through the existing agent
- Phase 5 after Phase 3: habit patterns are only meaningful once user is regularly using the conversation loop
- Phase 6 after Phase 5: habit suggestions require populated pattern data; multi-user keying is much cheaper to add at Phase 5 than to migrate later

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3:** `AbstractConversationAgent` exact import path and `conversation.async_set_agent()` signature may have changed in HA 2024.x+; `tool_use` schema for HA service calls needs validation against current Anthropic SDK; verify `ConversationEntity` vs `AbstractConversationAgent` — HA 2024.x may have renamed this
- **Phase 4:** `assist_pipeline` agent selection API — exactly how a config entry's conversation agent is selected as the pipeline backend needs validation against current HA source
- **Phase 5:** Confirm `aiosqlite` WAL mode pragma syntax works correctly in the async context; verify HA's `hass.helpers.storage.Store` atomic write guarantees on Raspberry Pi ext4 filesystem

Phases with standard patterns (skip research-phase):
- **Phase 1:** Config flow, manifest.json, config entry lifecycle are extremely well-documented stable HA patterns; HIGH confidence
- **Phase 2:** Local regex routing and `hass.services.async_call()` are core HA patterns with no uncertainty
- **Phase 6:** Notification via HA persistent_notification service is a standard pattern; no research needed

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core technologies (Python 3.12, anthropic SDK, aiosqlite) are HIGH confidence. Wyoming/Piper for voice is MEDIUM — became standard in 2024 but web verification unavailable. Anthropic SDK version range should be verified at pypi.org before pinning. |
| Features | MEDIUM | Table stakes features and dependency chain are HIGH confidence. Competitor feature gap analysis is MEDIUM — late-2025 updates to extended_openai_conversation or similar may have closed some gaps. Habit learning complexity estimates are MEDIUM. |
| Architecture | MEDIUM | HA config entry lifecycle patterns and `hass.services.async_call()` are HIGH confidence (stable since 2021.x). `AbstractConversationAgent` API is MEDIUM — stable through 2024.x per training data but exact import path and method signatures must be verified against HA 2024.x+ source before Phase 2 begins. |
| Pitfalls | MEDIUM-HIGH | Async/blocking pitfalls and config entry lifecycle pitfalls are HIGH confidence — these are recurrent documented issues. Prompt injection risk assessment is MEDIUM — Claude's resistance is behavioral, not guaranteed. HACS validation requirements are MEDIUM — may have evolved. |

**Overall confidence:** MEDIUM

The research provides a reliable foundation for roadmap planning. The main gap is HA API surface verification — two specific interfaces (`AbstractConversationAgent` and `conversation.async_set_agent`) need to be checked against current HA source before Phase 2 implementation begins. Everything else (async patterns, config entry lifecycle, Claude SDK usage, storage patterns) is well-established with HIGH confidence.

### Gaps to Address

- **`AbstractConversationAgent` vs `ConversationEntity`:** HA may have transitioned to `ConversationEntity` as the primary subclassing target in 2024.x. Verify the correct class name and import path at `homeassistant/components/conversation/` source before Phase 2. Handle during Phase 2 kickoff research.
- **`conversation.async_set_agent()` signature:** May use `entry` object or `agent_id` string depending on HA version. Verify exact call signature before writing `__init__.py`. Handle during Phase 1 final integration check.
- **`assist_pipeline` agent selection:** Exactly how the pipeline backend is configured to use a custom conversation agent (config entry ID? UI selection?) needs validation. Handle as Phase 4 pre-work.
- **Anthropic `tool_use` schema for HA services:** The exact JSON schema for exposing `hass.services.async_call` as Claude tools needs to be designed. This is Phase 3 planning work, not a research gap per se, but no sample schema was validated against a live HA instance.
- **HACS validation requirements:** Current HACS docs should be checked at `hacs.xyz/docs/publish/integration` before Phase 1 manifest.json is finalized; training knowledge may be slightly stale.

---

## Sources

### Primary (HIGH confidence)
- Home Assistant Developer Documentation — custom components, config entries, conversation integration (training data, stable patterns since 2023.x)
- Anthropic Python SDK — `anthropic.AsyncAnthropic`, `client.messages.create()`, `tool_use` (SDK stable, well-documented)
- HA integration quality scale requirements — blocking I/O, config entry lifecycle (stable across HA versions)
- `homeassistant.helpers.storage.Store` — atomic write, versioning (core HA API since 2021.x)

### Secondary (MEDIUM confidence)
- `extended_openai_conversation` custom component patterns (GitHub, training knowledge through mid-2025) — competitor feature baseline
- HA community forum patterns for LLM integrations — blocking call warnings, config entry migration failures, HACS validation issues
- Wyoming + Piper as standard local STT/TTS stack — became standard in 2024, per training knowledge
- `homeassistant/components/conversation/` source — `AbstractConversationAgent` interface stable through 2024.x

### Tertiary (LOW confidence — needs validation)
- Exact `conversation.async_set_agent()` / `async_unset_agent()` call signatures in HA 2024.x+
- HACS validation requirements current state (hacs.xyz)
- HA `config_entry.options` vs `config_entry.data` encryption behavior for sensitive values

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
