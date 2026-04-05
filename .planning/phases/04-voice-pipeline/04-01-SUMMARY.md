---
phase: 04-voice-pipeline
plan: 01
subsystem: testing
tags: [home-assistant, assist_pipeline, voice, tts, stt, conversation, pytest]

# Dependency graph
requires:
  - phase: 03-claude-llm-integration
    provides: HaAiConversationAgent with IntentRouter + Claude fallback wired in conversation.py
  - phase: 02-conversation-bridge
    provides: ConversationEntity registration, entity_id conversation.ha_ai_agent
provides:
  - Unit tests proving agent is pipeline-discoverable (VOICE-01)
  - Unit tests proving TTS-compatible speech output via IntentResponse (VOICE-02)
  - .gitignore excluding __pycache__ and build artifacts
affects: [05-habitlearning, any phase touching voice or conversation pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "async_get_agent_info(hass, entity_id) to verify pipeline discoverability"
    - "patch IntentRouter.async_route at module level for conversation handler tests"
    - "MagicMock(spec=ChatLog) for chat_log arg to _async_handle_message"

key-files:
  created:
    - tests/test_voice_pipeline.py
    - .gitignore
  modified: []

key-decisions:
  - "No new Python code in component: Phase 4 validates existing implementation via tests only"
  - "IntentRouter.async_route patched at custom_components.ha_ai_agent.intent_router level (not __init__) for accurate module-level mocking"

patterns-established:
  - "Voice pipeline tests: patch router to return text, verify speech['plain']['speech'] field"
  - "async_get_agent_info used directly to simulate pipeline agent discovery"

requirements-completed: [VOICE-01, VOICE-02]

# Metrics
duration: ~35min
completed: 2026-04-04
---

# Phase 4 Plan 01: Voice Pipeline Compatibility Summary

**4 unit tests prove HaAiConversationAgent is discoverable by assist_pipeline (VOICE-01) and produces TTS-compatible IntentResponse speech output (VOICE-02) — zero new component code needed; live HA pipeline "Mon assistant HA" configured and verified end-to-end in French**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-05T08:27:40Z
- **Completed:** 2026-04-04T00:00:00Z
- **Tasks:** 2/2 complete
- **Files modified:** 2

## Accomplishments

- Created `tests/test_voice_pipeline.py` with 4 tests covering both VOICE-01 and VOICE-02 requirements
- Confirmed existing HaAiConversationAgent requires zero modification for voice pipeline compatibility
- All 45 tests pass (including 4 new); no regressions
- Added `.gitignore` to exclude `__pycache__` and build artifacts (missing from project)
- HA voice pipeline "Mon assistant HA" configured in live instance with STT=faster-whisper (fr), TTS=Piper (fr_FR-siwis-medium), conversation agent=HA AI Agent (conversation.ha_ai_agent)
- WebSocket smoke test confirmed pipeline routes to conversation.ha_ai_agent and returns French speech responses — VOICE-01 and VOICE-02 verified end-to-end

## Task Commits

Each task was committed atomically:

1. **Task 1: Create voice pipeline unit tests** - `4156b49` (feat)
2. **Task 2: Configure and verify HA voice pipeline end-to-end** - Human verification (approved — no code commit)

**Plan metadata:** `b34be9f` (docs: complete voice pipeline plan)

## Files Created/Modified

- `tests/test_voice_pipeline.py` - 4 tests: pipeline discoverability (VOICE-01 x2) and TTS speech output (VOICE-02 x2)
- `.gitignore` - excludes `__pycache__/`, `*.pyc`, `.pytest_cache/`, etc.

## Decisions Made

- No new component code: the existing `conversation.py` already calls `intent_response.async_set_speech(response_text)` and returns `ConversationResult(response=intent_response)`, which satisfies pipeline TTS requirements
- `IntentRouter.async_route` patched at `custom_components.ha_ai_agent.intent_router.IntentRouter.async_route` level (not `__init__`) — follows standard Python mock pattern and avoids module injection complexity from `test_conversation_bridge.py`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added .gitignore**
- **Found during:** Task 1 (staging files)
- **Issue:** `__pycache__/` and `*.pyc` files were untracked; no `.gitignore` in project
- **Fix:** Created `.gitignore` with standard Python exclusions
- **Files modified:** `.gitignore`
- **Verification:** `git status` shows no `__pycache__` untracked entries after commit
- **Committed in:** `4156b49` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Added `.gitignore` for repo hygiene. No scope creep.

## Issues Encountered

- Python executable required explicit path (`/c/Users/Gsch6/AppData/Local/Python/pythoncore-3.14-64/python.exe`) — `python` and `python3` commands not on PATH in Git Bash shell. Tests ran correctly once the full path was used.

## User Setup Required

**Task 2 (completed — human verified):** HA voice pipeline configured manually:

1. Wyoming Whisper add-on installed (STT, port 10300) — confirmed via Wyoming Protocol integration
2. Wyoming Piper add-on installed (TTS, port 10200) — confirmed via Wyoming Protocol integration
3. openWakeWord add-on installed (optional, wake word "alexa" — non-commercial use only)
4. Assist pipeline "Mon assistant HA" created with:
   - Conversation agent: HA AI Agent (entity `conversation.ha_ai_agent`)
   - STT: faster-whisper, language fr
   - TTS: Piper, voice `fr_FR-siwis-medium`
   - Wake word: openWakeWord/alexa
5. WebSocket verified: `assist_pipeline/pipeline/list` shows `conversation_engine: "conversation.ha_ai_agent"`
6. Smoke test passed: `assist_pipeline/run` returns `intent-end` with French speech text

## Next Phase Readiness

- VOICE-01 and VOICE-02 fully satisfied — proven by both automated tests and live HA end-to-end verification
- Voice pipeline "Mon assistant HA" operational: French voice commands processed by HaAiConversationAgent with TTS responses
- Phase 04 complete — Phase 05 (habit learning) can proceed without any voice pipeline blockers

## Self-Check: PASSED

- FOUND: `tests/test_voice_pipeline.py`
- FOUND: `.gitignore`
- FOUND: `.planning/phases/04-voice-pipeline/04-01-SUMMARY.md`
- FOUND: commit `4156b49`
- FOUND: commit `b34be9f`

---
*Phase: 04-voice-pipeline*
*Completed: 2026-04-04*
