# Roadmap: HA Autonomous Agent

## Overview

Six phases that follow a strict dependency chain: HA scaffold first (lifecycle and config flow), then a working conversation bridge driven by local rules and entity control, then Claude added as a fallback to that proven bridge, then voice integration (nearly free once the agent is registered), then habit data collection with crash-safe SQLite storage, and finally the feedback loop that surfaces habit context into Claude and surfaces suggestions to the user. Every phase delivers a coherent, independently verifiable capability. Nothing is built on an untested foundation.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: HA Scaffold** - Custom component loads in HA with secure API key config and clean lifecycle (completed 2026-03-31)
- [x] **Phase 2: Conversation Bridge** - Text commands control HA entities via local rules, no LLM required (completed 2026-03-31)
- [x] **Phase 3: Claude LLM Integration** - Complex commands handled by Claude with entity filtering and security controls (completed 2026-04-01)
- [ ] **Phase 4: Voice Pipeline** - Wake word to TTS response end-to-end through the registered conversation agent
- [ ] **Phase 5: Habit Engine** - State changes observed, events stored in crash-safe SQLite, patterns detected
- [x] **Phase 6: Habit Feedback Loop** - Habit context enriches Claude responses and surfaces proactive suggestions (completed 2026-04-05)

## Phase Details

### Phase 1: HA Scaffold
**Goal**: Custom component is installed, loadable, and configurable via HA UI with no feature code yet
**Depends on**: Nothing (first phase)
**Requirements**: HA-01, HA-02, HA-03, HA-04
**Success Criteria** (what must be TRUE):
  1. Component appears in HA Integrations panel after copying to `custom_components/ha_ai_agent/`
  2. User can enter and save a Claude API key through the HA config flow UI
  3. Component can be reloaded from the HA UI without restarting Home Assistant
  4. Component appears as a selectable conversation agent in HA Settings > Voice Assistants
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — manifest.json, const.py, and __init__.py with async_setup_entry / async_unload_entry skeleton
- [x] 01-02-PLAN.md — config_flow.py with API key input, validation, and secure storage via ConfigEntry.data
- [x] 01-03-PLAN.md — Conversation agent registration and deregistration tied to config entry lifecycle

### Phase 2: Conversation Bridge
**Goal**: Users can issue text commands that control HA entities using local regex rules, with no LLM dependency
**Depends on**: Phase 1
**Requirements**: NLU-01, NLU-02, NLU-04, NLU-05, SEC-03
**Success Criteria** (what must be TRUE):
  1. User can type "allume la lumiere du salon" in the HA conversation panel and the entity turns on
  2. Common commands (turn on, turn off, set temperature) resolve via local regex without any Claude API call
  3. The agent replies with a natural language confirmation after each successful action
  4. The agent returns a clear error message when the requested entity is not found or the service is unavailable
  5. A configurable whitelist limits which HA domains (light, switch, climate, media_player) can be controlled
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Wire _async_handle_message to IntentRouter: const additions, setup wiring, echo stub removal
- [x] 02-02-PLAN.md — IntentRouter with FR+EN regex patterns, hass.services.async_call dispatch, error handling
- [x] 02-03-PLAN.md — EntityContextBuilder 3-pass entity resolution, domain whitelist, OptionsFlowHandler

### Phase 3: Claude LLM Integration
**Goal**: Ambiguous and complex commands are resolved by Claude, with privacy and security controls active from day one
**Depends on**: Phase 2
**Requirements**: NLU-03, SEC-01, SEC-02
**Success Criteria** (what must be TRUE):
  1. A command like "mets l'ambiance pour regarder un film" triggers appropriate scene or device actions via Claude
  2. Only the filtered list of relevant entities (not all HA states) is sent to the Claude API
  3. Claude API failures fall back gracefully to local rules with a clear user-facing message
  4. Raw habit data and full entity state dumps never leave the local network to Anthropic
**Plans**: TBD

Plans:
- [x] 03-01: ClaudeClient async wrapper with AsyncAnthropic, system prompt, conversation history window, and retry logic
- [x] 03-02: IntentRouter LLM fallback branch with tool_use schema for HA service calls and structured output validation
- [x] 03-03: EntityContextBuilder filtering (domain/area/count cap at 50) and privacy disclosure in config flow

### Phase 4: Voice Pipeline
**Goal**: Voice commands flow end-to-end from wake word through STT to entity action and back as TTS audio
**Depends on**: Phase 3
**Requirements**: VOICE-01, VOICE-02
**Success Criteria** (what must be TRUE):
  1. Saying a wake word followed by a voice command controls the correct HA entity
  2. The agent's text response is read aloud via HA's TTS engine after each voice command
**Plans**: TBD

Plans:
- [ ] 04-01: assist_pipeline configuration to select the registered conversation agent as backend, plus STT (Wyoming/Whisper) and TTS (Piper) setup and validation
**UI hint**: yes

### Phase 5: Habit Engine
**Goal**: The component observes and persists home state change events in a crash-safe local database ready for pattern analysis
**Depends on**: Phase 3
**Requirements**: HABIT-01, HABIT-02, HABIT-03, SEC-02
**Success Criteria** (what must be TRUE):
  1. Every user-initiated state change (light on, thermostat adjusted, etc.) is recorded in the local SQLite database
  2. Each event record includes entity ID, action, timestamp, day of week, and available context (presence, weather)
  3. After sufficient data accumulates, the pattern detector identifies recurring routines (e.g., kitchen lights on at 7 AM on weekdays)
  4. Habit data never leaves the device — no sync, no cloud, no external write
**Plans**: TBD

Plans:
- [x] 05-01: AgentStorage with aiosqlite, WAL mode, schema versioning (meta table), TTL purge, and 10,000-event cap
- [x] 05-02: HabitEngine subscribing to state_changed events with user-initiated filtering and event record writing
- [ ] 05-03: Pattern detection algorithm (time-series frequency analysis over events table) and patterns table storage

### Phase 6: Habit Feedback Loop
**Goal**: Detected habits enrich Claude's context and surface as actionable suggestions in HA notifications
**Depends on**: Phase 5
**Requirements**: HABIT-04
**Success Criteria** (what must be TRUE):
  1. Claude's responses reflect known user routines (e.g., "I see you usually turn on the kitchen lights at 7 AM — done")
  2. Detected habit patterns appear as persistent notifications in HA suggesting automations or routines
**Plans**: TBD

Plans:
- [x] 06-01: Habit context injection into ClaudeClient system prompt (relevant habits keyed by time/entity)
- [ ] 06-02: Proactive suggestion delivery via HA persistent_notification service when new patterns are detected

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. HA Scaffold | 3/3 | Complete   | 2026-03-31 |
| 2. Conversation Bridge | 3/3 | Complete   | 2026-03-31 |
| 3. Claude LLM Integration | 3/3 | Complete   | 2026-04-01 |
| 4. Voice Pipeline | 0/1 | Not started | - |
| 5. Habit Engine | 2/3 | In Progress|  |
| 6. Habit Feedback Loop | 1/1 | Complete   | 2026-04-05 |
