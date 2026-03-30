# Feature Research

**Domain:** Home Assistant autonomous AI agent (custom component, Claude API, voice+text, habit learning)
**Researched:** 2026-03-30
**Confidence:** MEDIUM — based on training knowledge (cutoff August 2025). WebSearch/WebFetch unavailable. HA ecosystem knowledge is deep but some specifics of late-2024/2025 releases may be incomplete.

---

## Ecosystem Context

### Existing HA AI Solutions (Competitors)

| Solution | Approach | Strengths | Gaps |
|----------|----------|-----------|------|
| **HA Assist (built-in)** | Intent-based NLU, local sentence matching via `hassil` | Zero-cloud, fast, integrated with `assist_pipeline` (STT/TTS) | No LLM, rigid sentence patterns, no memory, no learning |
| **extended_openai_conversation** | Custom component, OpenAI API tool-calling, exposes HA services as tools | Flexible NLU via LLM, tool-calling for real entity control, system prompt customizable | No habit learning, no local fallback, no proactive suggestions, OpenAI-specific |
| **llama_conversation** | Custom component, local LLM (Ollama/llama.cpp) via `conversation` entity | Full local execution, privacy | Slower, resource-heavy, no learning, limited tool-calling |
| **OpenAI conversation (official)** | Official HA integration, OpenAI GPT via `conversation` entity | Maintained, easy setup | No tool-calling in v1, no learning, no entity control by default |
| **HA + Claude (community)** | Ad-hoc scripts / AppDaemon | Claude API access | No HA integration, no voice, manual wiring |

**Key gap this project fills:** None of the above combine (1) Claude LLM, (2) HA-native voice pipeline, (3) habit learning/memory, and (4) a hybrid local-rules + LLM routing layer.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Natural language entity control | Core promise — "turn on the lights" must work | MEDIUM | Must map utterance → HA service call via LLM tool-calling or intent extraction; needs entity list in context |
| Config flow UI (HA standard) | Every HA integration uses config_entries setup; missing it = not a real integration | LOW | `config_flow.py` + `strings.json`; Claude API key entry, model selection |
| Claude API key management | Users expect secure credential storage, not plaintext YAML | LOW | HA `config_entries` stores secrets in `.storage/`; never in `configuration.yaml` |
| Conversation entity registration | Required to appear in HA's "voice assistants" settings and Assist pipeline | MEDIUM | Must implement `ConversationEntity` (or `AbstractConversationAgent` in older HA) and register via `async_setup_entry` |
| Basic intent parsing fallback | If Claude API is unreachable, something must respond — not a silent failure | MEDIUM | Fallback to Assist/hassil or a canned error message; users hate dead silences |
| HA entities in LLM context | Agent must know what devices exist to control them | MEDIUM | Inject `hass.states.async_all()` (filtered) into system prompt or tool schema |
| Service call execution | LLM decisions must translate into actual HA service calls | MEDIUM | `hass.services.async_call()` with domain/service/data from LLM response |
| Persistent configuration | Settings survive HA restarts | LOW | Standard via `config_entries` + `options_flow` |
| Logging / error visibility | Users need to debug "why didn't it do X" | LOW | `_LOGGER = logging.getLogger(__name__)` with meaningful messages; HA log viewer shows them |
| Multi-turn conversation context | Users naturally ask follow-up questions ("and also dim them to 50%") | MEDIUM | Maintain a per-session or per-user message history list; pass to Claude API as `messages` |

### Differentiators (Competitive Advantage)

Features that set this product apart. Not expected by default, but create strong loyalty when present.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Habit learning & pattern detection | Agent notices "you turn off lights every night at 23:00" and suggests/automates it — no manual automation config | HIGH | Requires event listener on HA state changes + time-bucketed storage (SQLite recommended over JSON at scale); pattern matching algorithm (frequency + recency scoring) |
| Hybrid routing: local rules vs LLM | Fast/cheap for frequent commands, intelligent for complex ones — reduces API cost and latency | HIGH | Rule cache keyed on intent fingerprint; LRU eviction; confidence threshold to decide LLM escalation |
| Proactive suggestions | Agent surfaces "I noticed you usually do X at this time — want me to?" — moves from reactive to anticipatory | HIGH | Requires habit store + scheduler + notification mechanism (HA persistent_notification or mobile push) |
| Contextual memory across sessions | "Remember I prefer warm light in the evening" persists beyond a single conversation | MEDIUM | Per-user preference store (SQLite table); injected into system prompt as user context block |
| Privacy-first design (local data) | Explicit commitment: only NL queries leave the device, all learning stays local | LOW | Architecture decision already made; surface it prominently in docs/UI as a trust signal |
| Named automations via voice | "Set up a rule: turn on the fan when temperature exceeds 25°C" — create HA automations from speech | HIGH | LLM generates automation YAML/dict; `hass.services.async_call("automation", "create", ...)` or write to automations.yaml |
| Explainable actions | "I turned on the heating because you usually do this on Monday mornings" | MEDIUM | LLM generates rationale string alongside action; store and surface in frontend card or notification |
| Multi-user awareness | Different habits/preferences per household member | MEDIUM | HA `context.user_id` is available on conversation turns; key habit store by user_id |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem desirable but introduce serious complexity or risk in v1.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Fully autonomous decisions (no prompt) | "The agent just handles everything automatically" | Unpredictable behavior without learning phase; can trigger unwanted actions; trust/safety issue | Implement as v2 after habit store has sufficient data and user has validated suggestions |
| Multi-LLM support (GPT-4, Ollama, Gemini) | Flexibility, avoid vendor lock-in | Requires abstraction layer that multiplies test surface; different tool-calling APIs; premature generalization | Fix on Claude for v1; design thin `LLMBackend` interface so it's addable later without rewrite |
| Cloud sync of habits/preferences | Share settings across HA instances | Major privacy/security surface; GDPR complexity; not in core value | Keep local; document export/import as a future feature |
| Complex multi-agent orchestration | "Sub-agents for different rooms or devices" | Over-engineering for the problem size; HA state is already centralized | Single agent with full entity access is sufficient; rooms are just entity filters |
| Real-time streaming TTS responses | "More natural feel with word-by-word speech" | HA's `tts` and `assist_pipeline` don't natively support streaming audio chunks well in 2024.x; complex buffering | Use full-response TTS; acceptable latency for home control use case |
| Web UI / custom dashboard panel | Full custom Lovelace panel for the agent | Scope explosion; HA's conversation UI (`ha-voice-command-dialog`) already exists | Use HA built-in conversation UI; optionally add a Lovelace card for habit review only |
| Training a custom model | Fine-tune a model on user data | Enormous complexity, data requirements, cost — and Claude API already covers the NLU need | Use Claude + habit store injection into system prompt instead |
| Scheduled polling of all entity states | Continuously scanning every state change for learning | Performance and battery impact; HA has ~1000s of state changes/day | Use targeted event subscriptions on specific entity domains (light, climate, switch) |

---

## Feature Dependencies

```
[Conversation Entity (HA integration)]
    └──requires──> [Config Flow (API key, model)]
                       └──requires──> [Claude API client]

[Entity Control]
    └──requires──> [Conversation Entity]
    └──requires──> [Entity list injection into LLM context]
    └──requires──> [Service call executor]

[Multi-turn context]
    └──requires──> [Conversation Entity]
    └──requires──> [Session/message history store]

[Habit Learning]
    └──requires──> [HA event listener (state_changed)]
    └──requires──> [Local storage (SQLite)]
    └──enhances──> [Contextual memory]

[Proactive Suggestions]
    └──requires──> [Habit Learning] (needs pattern data)
    └──requires──> [HA scheduler / async_track_time_interval]
    └──requires──> [Notification mechanism]

[Hybrid Routing (local rules + LLM)]
    └──requires──> [Entity Control] (rules must produce same output)
    └──requires──> [Intent fingerprinting]
    └──enhances──> [Habit Learning] (frequent patterns become local rules)

[Explainable Actions]
    └──requires──> [Entity Control]
    └──enhances──> [Proactive Suggestions] (rationale for suggestions)

[Multi-user awareness]
    └──requires──> [Habit Learning]
    └──requires──> [HA user_id from context]
```

### Dependency Notes

- **Entity Control requires Entity list injection:** The LLM cannot reliably control entities it doesn't know exist. The entity list (filtered to relevant domains) must be in the system prompt or available as a tool. This is the single biggest integration complexity.
- **Proactive Suggestions requires Habit Learning:** You cannot suggest patterns you haven't detected. This is a hard ordering dependency — habit store must be populated before suggestions make sense (minimum ~2 weeks of data).
- **Hybrid Routing requires Entity Control:** The local rule cache is just a fast path that produces the same service calls as the LLM path. It only makes sense once the LLM path is working correctly.
- **Multi-user awareness requires Habit Learning:** HA conversation context provides `user_id`; the habit store must be keyed by it from the start or migration is painful.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept and produce real value.

- [ ] Config flow (API key entry, model selector, entity domain filter) — gating everything else
- [ ] Conversation entity registered with HA — enables voice pipeline + Assist UI
- [ ] Claude API integration with multi-turn message history — core NLU
- [ ] Entity list injection into system prompt (filtered by configured domains) — without this, entity control is blind
- [ ] LLM tool-calling for HA service calls — the actual control loop
- [ ] Basic habit event listener + SQLite storage — even if suggestions aren't surfaced yet, data collection must start in v1 or there's nothing to show in v2
- [ ] Error handling + fallback on API failure — production-quality baseline

### Add After Validation (v1.x)

Features to add once core entity control is proven stable.

- [ ] Hybrid routing (local rule cache) — add when API cost or latency becomes a concern in real usage
- [ ] Habit pattern detection + proactive suggestions — add when habit store has ~2 weeks of real data
- [ ] Contextual user preference memory — add alongside habit suggestions
- [ ] Multi-user support (user_id keying) — add when second household member adopts it
- [ ] Explainable actions — add when users ask "why did it do that"

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Fully autonomous decisions (no prompt trigger) — defer until habit learning is validated and user trust is established
- [ ] Named automation creation via voice — significant complexity, HA automation schema is complex
- [ ] Multi-LLM backend abstraction — add only if Claude API becomes a blocker (cost, availability, capability)
- [ ] Export/import habit data — operational concern, not core value

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Config flow (API key, setup) | HIGH | LOW | P1 |
| Conversation entity (HA integration) | HIGH | MEDIUM | P1 |
| Multi-turn Claude conversation | HIGH | MEDIUM | P1 |
| Entity list injection | HIGH | MEDIUM | P1 |
| Service call execution (entity control) | HIGH | MEDIUM | P1 |
| API failure fallback | HIGH | LOW | P1 |
| Habit event listener + SQLite store | MEDIUM | MEDIUM | P1 (data collection start) |
| Hybrid local-rules routing | MEDIUM | HIGH | P2 |
| Habit pattern detection | HIGH | HIGH | P2 |
| Proactive suggestions | HIGH | HIGH | P2 |
| Contextual memory (preferences) | MEDIUM | MEDIUM | P2 |
| Multi-user awareness | MEDIUM | MEDIUM | P2 |
| Explainable actions | MEDIUM | MEDIUM | P2 |
| Autonomous decisions (no prompt) | HIGH (desired) | HIGH | P3 |
| Named automation creation via voice | MEDIUM | HIGH | P3 |
| Multi-LLM abstraction | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v1 launch
- P2: Should have — add in v1.x after core validation
- P3: Nice to have — v2+

---

## Competitor Feature Analysis

| Feature | HA Assist (built-in) | extended_openai_conversation | llama_conversation | This Project |
|---------|----------------------|-----------------------------|--------------------|--------------|
| Natural language control | Partial (rigid patterns) | YES (tool-calling) | YES (prompt-based) | YES (Claude tool-calling) |
| Voice pipeline integration | YES (native) | YES (via conversation entity) | YES (via conversation entity) | YES (via conversation entity) |
| Multi-turn context | NO | YES (message history) | YES | YES |
| Habit learning | NO | NO | NO | YES (core differentiator) |
| Proactive suggestions | NO | NO | NO | YES (v1.x) |
| Local data / privacy | YES | NO (OpenAI cloud) | YES (local LLM) | YES (habits local, only NL to Claude) |
| Hybrid local/LLM routing | NO | NO | NO | YES (v1.x) |
| Multi-user awareness | Partial (HA users) | NO | NO | YES (v1.x) |
| Config flow (HA standard) | YES (built-in) | YES | YES | YES |
| Offline operation | YES | NO | YES | Partial (fallback only) |
| Cost | Free | OpenAI API cost | Free | Claude API cost |

---

## Sources

- Home Assistant Assist documentation and `assist_pipeline` integration (training knowledge, HA 2024.x)
- `extended_openai_conversation` custom component (GitHub, training knowledge through mid-2025)
- `llama_conversation` custom component (GitHub, training knowledge)
- Home Assistant `conversation` integration API (`ConversationEntity`, `async_process`) — training knowledge, MEDIUM confidence
- HA community forums patterns for LLM integrations — training knowledge, MEDIUM confidence
- Project context: `.planning/PROJECT.md`

**Confidence notes:**
- Table stakes features: HIGH confidence — HA integration architecture is stable and well-documented
- Competitor feature gaps: MEDIUM confidence — verified against known component codebases, but late-2025 updates may have changed features
- Habit learning complexity estimates: MEDIUM confidence — based on general ML pattern-detection knowledge + SQLite in Python
- HA `ConversationEntity` API details: MEDIUM confidence — API was stable through HA 2024.6; minor changes possible in later releases

---

*Feature research for: Home Assistant autonomous AI agent (custom component)*
*Researched: 2026-03-30*
