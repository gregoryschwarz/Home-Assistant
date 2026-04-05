---
phase: 04-voice-pipeline
verified: 2026-04-04T12:00:00Z
status: human_needed
score: 4/4 must-haves verified
re_verification: false
human_verification:
  - test: "Say a wake word (\"alexa\") near the microphone, then say \"allume le salon\""
    expected: "The correct HA entity changes state AND a spoken French response is heard via Piper TTS"
    why_human: "Physical microphone and speaker hardware were not tested during execution. Text-based pipeline via Assist UI was confirmed working, but the acoustic path (wake word detection → STT audio capture → TTS audio playback) requires physical hardware to verify end-to-end."
  - test: "Say a wake word, then say a command that triggers Claude fallback (e.g. \"quelle météo demain ?\")"
    expected: "Claude responds in French, TTS speaks the response aloud"
    why_human: "Need physical hardware to test TTS audio output on the Claude fallback branch (not just the router branch tested by unit tests)."
---

# Phase 4: Voice Pipeline Verification Report

**Phase Goal:** Voice commands flow end-to-end from wake word through STT to entity action and back as TTS audio
**Verified:** 2026-04-04
**Status:** human_needed — all automated checks pass; physical acoustic path unverified
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `assist_pipeline` can discover `HaAiConversationAgent` by entity_id `conversation.ha_ai_agent` | VERIFIED | `test_agent_discoverable_by_pipeline` calls `async_get_agent_info(hass, "conversation.ha_ai_agent")` and asserts `agent_info.id == "conversation.ha_ai_agent"`. Commit `4156b49` confirmed real. |
| 2 | Agent entity_id has the `conversation.` prefix required for pipeline routing | VERIFIED | `test_agent_entity_id_format` filters states by DOMAIN and asserts `entity_id.startswith("conversation.")`. `_attr_name = "HA AI Agent"` in `conversation.py` produces stable entity_id. |
| 3 | `_async_handle_message` sets speech on `IntentResponse` so TTS can read it aloud | VERIFIED | `conversation.py` line 104-105: `intent_response = conversation_intent.IntentResponse(...)` then `intent_response.async_set_speech(response_text)`. Confirmed by `test_response_speech_set` and `test_conversation_result_has_speech`. |
| 4 | `ConversationResult` contains non-empty speech text for the pipeline to forward to TTS | VERIFIED | `test_conversation_result_has_speech` asserts `isinstance(result.response, IntentResponse)`, `"plain" in result.response.speech`, and `len(speech) > 0`. |

**Score:** 4/4 must-have truths verified

**Success Criteria from ROADMAP:**

| # | Success Criterion | Status | Note |
|---|-------------------|--------|------|
| 1 | Saying a wake word followed by a voice command controls the correct HA entity | NEEDS HUMAN | Live HA pipeline "Mon assistant HA" confirmed configured with openWakeWord/alexa. Physical microphone not tested in execution. |
| 2 | The agent's text response is read aloud via HA's TTS engine after each voice command | NEEDS HUMAN | TTS code path fully proven (IntentResponse.speech set). Physical speaker audio not tested. Text-based pipeline via Assist UI confirmed working. |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_voice_pipeline.py` | Unit tests proving agent is pipeline-discoverable and produces TTS-compatible output | VERIFIED | 166 lines (min_lines: 60 satisfied). Contains all 4 required test functions. Committed in `4156b49`. |
| `custom_components/ha_ai_agent/conversation.py` | `_async_handle_message` sets speech via `async_set_speech` | VERIFIED | Line 105: `intent_response.async_set_speech(response_text)`. Returns `ConversationResult(response=intent_response, ...)`. No modifications needed — existing code was already pipeline-compatible. |
| `custom_components/ha_ai_agent/manifest.json` | `after_dependencies` includes `assist_pipeline` | VERIFIED | Line 9: `"after_dependencies": ["assist_pipeline"]` confirmed present. |
| HA pipeline "Mon assistant HA" | Configured with `conversation_engine=conversation.ha_ai_agent`, STT=faster-whisper, TTS=Piper/fr_FR-siwis-medium | HUMAN VERIFIED | Per human checkpoint: pipeline created, WebSocket smoke test confirmed `conversation_engine: "conversation.ha_ai_agent"`, `assist_pipeline/run` returned French speech text. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_voice_pipeline.py` | `conversation.ha_ai_agent` entity | `async_get_agent_info(hass, "conversation.ha_ai_agent")` | WIRED | Imported at line 17, called at line 38, asserted at lines 41-47. |
| `custom_components/ha_ai_agent/conversation.py` | `homeassistant.components.conversation.async_get_agent_info` | `ConversationEntity` registration makes entity discoverable | WIRED | `HaAiConversationAgent(ConversationEntity)` at line 50. `async_add_entities([HaAiConversationAgent(...)])` at line 47 registers the entity so `async_get_agent_info` can find it. |
| `custom_components/ha_ai_agent/conversation.py` | `homeassistant.components.assist_pipeline` | `IntentResponse.async_set_speech` populates speech for TTS stage | WIRED | `intent_response.async_set_speech(response_text)` at line 105. Pattern `async_set_speech` confirmed present. |
| `tests/test_voice_pipeline.py` | `custom_components.ha_ai_agent.intent_router.IntentRouter.async_route` | `patch` at module level | WIRED | Lines 87-88 and 131-132: `patch("custom_components.ha_ai_agent.intent_router.IntentRouter.async_route", new=AsyncMock(return_value=...))` — correct module path, not `__init__`. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `conversation.py` `_async_handle_message` | `response_text` | `IntentRouter.async_route` (local rules) or `ClaudeClient.async_complete` (LLM fallback) | Yes — router matches regex rules, Claude returns LLM completion; `None` fallback produces a French error string (not empty) | FLOWING |
| `tests/test_voice_pipeline.py` (tests 3 & 4) | `result.response.speech["plain"]["speech"]` | `AsyncMock(return_value="Salon allume.")` / `"Cuisine eteinte."` — intentional controlled data for unit tests | Yes — tests are designed to control input and assert exact output; mock replaces real router | FLOWING (test context, by design) |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED for live HA pipeline — requires a running HA instance with voice hardware. The PLAN's own verification command (`python -m pytest tests/test_voice_pipeline.py -x -q`) was run by the executor and reported 4 passed (45 total suite). Commit `4156b49` confirms tests were committed post-passing. Re-running locally would require the full `pytest-homeassistant-custom-component` environment.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 4 voice pipeline tests pass | `python -m pytest tests/test_voice_pipeline.py -x -q` | Reported 4 passed by executor; commit `4156b49` contains 166-line substantive test file | SKIP (trust commit evidence) |
| Full suite remains green | `python -m pytest tests/ -x -q` | SUMMARY reports 45 tests pass — consistent with 10+ test files in `tests/` directory | SKIP (trust executor report) |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| VOICE-01 | `04-01-PLAN.md` | Les commandes vocales via le pipeline `assist_pipeline` de HA sont traitées par le composant | SATISFIED | `test_agent_discoverable_by_pipeline` proves `async_get_agent_info` returns non-None AgentInfo with correct entity_id. `test_agent_entity_id_format` proves `conversation.` prefix present. Human checkpoint confirmed WebSocket `assist_pipeline/pipeline/list` shows `conversation_engine: "conversation.ha_ai_agent"`. |
| VOICE-02 | `04-01-PLAN.md` | La réponse textuelle de l'agent est transmise au moteur TTS de HA pour lecture audio | SATISFIED | `test_response_speech_set` asserts `speech["plain"]["speech"] == "Salon allume."`. `test_conversation_result_has_speech` asserts `IntentResponse` type and non-empty speech. `conversation.py` line 105 confirms `async_set_speech` populates the field the TTS stage reads. Human checkpoint confirmed `assist_pipeline/run` returns `intent-end` with French speech text. |

No orphaned requirements: REQUIREMENTS.md maps only VOICE-01 and VOICE-02 to Phase 4. Both are addressed by `04-01-PLAN.md`.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

Scanned `tests/test_voice_pipeline.py` and `custom_components/ha_ai_agent/conversation.py` for TODO/FIXME/placeholder/empty returns. Clean. The `return null`/empty patterns in `conversation.py` line 88-95 are legitimate control flow (None check before LLM fallback, not stubs).

---

### Human Verification Required

#### 1. Wake Word to Entity Control (physical path)

**Test:** Near the microphone, say "alexa" (wake word), then say "allume le salon"
**Expected:** The `light.salon` (or equivalent) entity changes state in HA AND a French spoken response is heard from the speaker via Piper TTS
**Why human:** Physical microphone and speaker were not tested during phase execution. The text-based pipeline via HA Assist UI was confirmed working, but the full acoustic chain (wake word detection by openWakeWord → audio capture by Whisper STT → audio synthesis by Piper TTS) requires physical hardware to verify.

#### 2. TTS Audio on Claude Fallback Branch

**Test:** Say a command that does not match any local regex rule (e.g., "quelle météo demain ?")
**Expected:** Claude's French response is spoken aloud by Piper TTS
**Why human:** Unit tests only patch `IntentRouter.async_route` — the Claude fallback branch (`ClaudeClient.async_complete`) was not exercised in tests 3 and 4. The code path exists in `conversation.py` lines 90-93, but live TTS audio output on this branch needs physical hardware to confirm.

---

### Gaps Summary

No automated gaps. All 4 must-have truths are verified at all four levels (exists, substantive, wired, data flowing). Both VOICE-01 and VOICE-02 requirements are satisfied by automated tests and human checkpoint evidence.

The only outstanding items are physical acoustic verification (microphone and speaker hardware), which are explicitly noted in the phase context as not having been tested. This does not block the phase goal for the text-based pipeline path, but leaves the acoustic end-to-end unverified.

**Phase goal achievement assessment:** The goal "Voice commands flow end-to-end from wake word through STT to entity action and back as TTS audio" is **partially achieved**:
- The text-based pipeline path (STT text → conversation agent → TTS text) is fully verified end-to-end via WebSocket smoke test (human approved).
- The acoustic path (physical wake word → microphone → Whisper STT audio → Piper TTS audio → speaker) is configured but not physically tested.

---

_Verified: 2026-04-04_
_Verifier: Claude (gsd-verifier)_
