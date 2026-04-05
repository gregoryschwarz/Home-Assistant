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
affects: [04-voice-pipeline]

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
duration: 8min
completed: 2026-04-05
---

# Phase 4 Plan 01: Voice Pipeline Compatibility Summary

**4 unit tests prove HaAiConversationAgent is discoverable by assist_pipeline (VOICE-01) and produces TTS-compatible IntentResponse speech output (VOICE-02) — zero new component code needed**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-05T08:27:40Z
- **Completed:** 2026-04-05T08:35:00Z
- **Tasks:** 1/2 complete (Task 2 is a human-verify checkpoint)
- **Files modified:** 2

## Accomplishments

- Created `tests/test_voice_pipeline.py` with 4 tests covering both VOICE-01 and VOICE-02 requirements
- Confirmed existing HaAiConversationAgent requires zero modification for voice pipeline compatibility
- All 45 tests pass (including 4 new); no regressions
- Added `.gitignore` to exclude `__pycache__` and build artifacts (missing from project)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create voice pipeline unit tests** - `4156b49` (feat)

**Plan metadata:** (pending — awaiting Task 2 checkpoint completion)

_Note: Task 2 is a `checkpoint:human-verify` requiring HA UI pipeline configuration and end-to-end voice verification._

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

**Task 2 requires manual HA configuration.** The checkpoint below details the steps:

1. Install Wyoming Whisper add-on (STT) — Settings > Add-ons > Add-on Store > "Whisper"
2. Install Wyoming Piper add-on (TTS) — Settings > Add-ons > Add-on Store > "Piper"
3. (Optional) Install openWakeWord add-on
4. Create Assist pipeline named "Mon assistant HA" with:
   - Conversation agent: HA AI Agent (entity `conversation.ha_ai_agent`)
   - STT: faster-whisper, language fr
   - TTS: Piper, voice `fr_FR-siwis-medium`
   - Wake word: openWakeWord/alexa (optional, non-commercial)
5. Verify via WebSocket: `assist_pipeline/pipeline/list` shows `conversation_engine: "conversation.ha_ai_agent"`
6. Smoke test: `assist_pipeline/run` with `start_stage: "intent"` returns `intent-end` with speech text

## Next Phase Readiness

- VOICE-01 and VOICE-02 proven by automated tests — no blockers on the code side
- Task 2 (pipeline configuration) awaits human verification in HA UI
- Once Task 2 is verified, Phase 4 Plan 01 is complete and Phase 4 is done

## Self-Check: PASSED

- FOUND: `tests/test_voice_pipeline.py`
- FOUND: `.gitignore`
- FOUND: `.planning/phases/04-voice-pipeline/04-01-SUMMARY.md`
- FOUND: commit `4156b49`

---
*Phase: 04-voice-pipeline*
*Completed: 2026-04-05 (Task 1 complete; Task 2 pending human verification)*
