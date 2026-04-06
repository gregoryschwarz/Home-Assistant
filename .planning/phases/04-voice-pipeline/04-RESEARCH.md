# Phase 4: Voice Pipeline - Research

**Researched:** 2026-04-04
**Domain:** Home Assistant assist_pipeline, Wyoming protocol (Whisper STT + Piper TTS), pipeline configuration UI
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VOICE-01 | Les commandes vocales via le pipeline `assist_pipeline` de HA sont traitées par le composant | The ConversationEntity already registered in HA (`conversation.ha_ai_agent`) is used as `conversation_engine` in the pipeline. No new code required. |
| VOICE-02 | La réponse textuelle de l'agent est transmise au moteur TTS de HA pour lecture audio | The text returned by `_async_handle_message` → `IntentResponse.async_set_speech(text)` is already in the correct format. The pipeline routes it to the configured TTS engine automatically. |
</phase_requirements>

---

## Summary

Phase 4 is a **configuration-only phase** — zero new Python code is required in the custom component. The `HaAiConversationAgent` entity registered in Phases 1-2 is already a fully compatible pipeline backend. The work is: (1) install Wyoming STT add-on (Whisper / faster-whisper), (2) install Wyoming TTS add-on (Piper), (3) configure a new Assist pipeline in HA UI that wires these components together and selects `conversation.ha_ai_agent` as the conversation engine.

**The key mechanism:** `assist_pipeline` resolves its conversation agent by calling `conversation.async_get_agent(hass, conversation_engine)`. When `conversation_engine` contains a dot (e.g., `"conversation.ha_ai_agent"`), HA looks up the entity directly via `hass.data[DATA_COMPONENT].get_entity(agent_id)`. The entity's `_async_handle_message` is already wired to `IntentRouter` and `ClaudeClient`. Nothing in the component needs to change.

**Primary recommendation:** Configure the pipeline entirely through the HA UI. Validate with a smoke test by calling `assist_pipeline/run` over WebSocket, then write a unit test that asserts `async_get_agent_info` finds our entity.

---

## Standard Stack

### Core (already installed, no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `homeassistant` | 2026.3.4 (installed) | `assist_pipeline`, `conversation`, `stt`, `tts` built-in integrations | Platform — no installation needed |
| Wyoming Whisper add-on | latest from HA add-on store | Local STT (speech-to-text) | The standard local STT stack since HA 2023.9; no cloud dependency |
| Wyoming Piper add-on | latest from HA add-on store | Local TTS (text-to-speech) | The standard local TTS stack since HA 2023.9; fast neural synthesis |
| `pytest-homeassistant-custom-component` | 0.13.320 (installed) | Test harness for pipeline assertions | Already in use |

### No New Python Requirements

The `manifest.json` already declares `"after_dependencies": ["assist_pipeline"]`. No new entries are needed in `requirements`, `dependencies`, or `after_dependencies`.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Wyoming Whisper (local) | Google Cloud STT or Nabu Casa cloud | Cloud requires internet, costs money, privacy concern — local preferred |
| Wyoming Piper (local) | Google Cloud TTS or Nabu Casa cloud | Same reasons; Piper is fast and produces good quality output |
| Whisper (STT) | Speech-to-Phrase | Speech-to-Phrase is faster but recognizes only pre-defined phrases; Whisper handles free-form French |

---

## Architecture Patterns

### How the Pipeline Routes Voice to Our Agent

```
[User speaks near microphone]
       │
       ▼
[Wake word engine (openWakeWord or Rhasspy)]
       │ wake word detected
       ▼
[Whisper STT add-on — Wyoming protocol]
       │ transcribed text (e.g., "allume le salon")
       ▼
[assist_pipeline core — PipelineRun.recognize_intent()]
       │ calls conversation.async_get_agent(hass, "conversation.ha_ai_agent")
       ▼
[HaAiConversationAgent._async_handle_message()]
       │ routes via IntentRouter → local regex OR ClaudeClient
       ▼
[ConversationResult with IntentResponse.speech = "Salon allumé."]
       │ response text returned to pipeline
       ▼
[Piper TTS add-on — Wyoming protocol]
       │ synthesized audio
       ▼
[Audio output device / satellite speaker]
```

### Key Code Path in HA Source (verified in HA 2026.3.4)

```python
# homeassistant/components/conversation/agent_manager.py
def async_get_agent(hass, agent_id):
    # If agent_id contains a dot → it's a ConversationEntity
    if "." in agent_id:
        return hass.data[DATA_COMPONENT].get_entity(agent_id)
    # Otherwise look up in agent manager (legacy pattern)
    ...

# homeassistant/components/assist_pipeline/pipeline.py
agent_info = conversation.async_get_agent_info(
    self.hass,
    self.pipeline.conversation_engine or conversation.HOME_ASSISTANT_AGENT,
)
```

**Implication:** Set `conversation_engine = "conversation.ha_ai_agent"` in the pipeline. HA will call `get_entity("conversation.ha_ai_agent")` and find our `HaAiConversationAgent`.

### Our Entity's ID

The entity_id is auto-assigned by HA from: platform (`conversation`) + `_attr_name` ("HA AI Agent").
Result: `conversation.ha_ai_agent`.

Verified by `test_conversation_entity_unique_id` in `tests/test_conversation.py`:
```python
agent_states = [s for s in states if DOMAIN in s.entity_id]
# → DOMAIN = "ha_ai_agent" → entity_id = "conversation.ha_ai_agent"
```

### Pipeline Dataclass (verified from HA 2026.3.4 source)

```python
@dataclass(frozen=True)
class Pipeline:
    conversation_engine: str        # ← "conversation.ha_ai_agent"
    conversation_language: str      # ← "fr"
    language: str                   # ← "fr"
    name: str                       # ← "Mon assistant HA"
    stt_engine: str | None          # ← "stt.faster_whisper" (from Wyoming add-on)
    stt_language: str | None        # ← "fr"
    tts_engine: str | None          # ← "tts.piper" (from Wyoming add-on)
    tts_language: str | None        # ← "fr"
    tts_voice: str | None           # ← "fr_FR-siwis-medium" or similar
    wake_word_entity: str | None    # ← "wake_word.openWakeWord" or None
    wake_word_id: str | None        # ← "ok_nabu" or None
    prefer_local_intents: bool = False
    id: str = field(default_factory=ulid_util.ulid_now)
```

### Configuration UI Flow (Settings > Voice Assistants)

1. Settings → Voice Assistants → Add Assistant
2. Name: "Mon assistant HA" (or any name)
3. Conversation agent: select "HA AI Agent" (our `HaAiConversationAgent` entity)
4. Language: French
5. Speech-to-text: select "faster-whisper" (from Wyoming Whisper add-on)
6. Text-to-speech: select "Piper" + choose a French voice
7. Wake word: select openWakeWord or skip (optional)
8. Save

**No YAML or code changes required** — the UI writes to HA's pipeline storage.

### Anti-Patterns to Avoid

- **Implementing STT/TTS in the component:** The pipeline handles STT and TTS; our component receives already-transcribed text and returns plain text. Never process audio in `_async_handle_message`.
- **Using `conversation.async_set_agent()` (legacy pattern):** The `ConversationEntity` pattern used in our code is the correct modern approach. Do not add `conversation.async_set_agent()` calls.
- **Assuming entity_id is stable:** Entity IDs can change if `_attr_name` changes. Our entity_id `conversation.ha_ai_agent` is stable because `_attr_name = "HA AI Agent"` is a constant.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Speech to text | Custom Whisper Python integration | Wyoming Whisper add-on | Already handles audio chunking, VAD, streaming; battle-tested |
| Text to speech | Custom Piper subprocess wrapper | Wyoming Piper add-on | Already handles voice model loading, audio streaming, language selection |
| Wake word detection | Custom keyword spotting | openWakeWord (built into HA or as add-on) | Optimized for low-power continuous listening; our code never sees audio |
| Pipeline configuration | Programmatic pipeline creation | HA Settings UI | Pipelines are user configuration, not component state; writing to pipeline storage from component code would be anti-pattern |

**Key insight:** For Phase 4, "don't hand-roll" applies to the phase itself — the component already does everything it needs to. The work is infrastructure setup, not code.

---

## Common Pitfalls

### Pitfall 1: Wrong conversation_engine Value in Pipeline
**What goes wrong:** Setting `conversation_engine = "ha_ai_agent"` (domain only) instead of `"conversation.ha_ai_agent"` (full entity_id).
**Why it happens:** The HA UI shows a dropdown label "HA AI Agent" without showing the underlying entity_id.
**How to avoid:** Verify via the WebSocket API: `assist_pipeline/pipeline/list` returns the stored value. Or check the entity registry.
**Warning signs:** `IntentRecognitionError: intent-not-supported` with message "engine ha_ai_agent is not found".

### Pitfall 2: STT Add-on Not Discovered by Wyoming Integration
**What goes wrong:** Whisper or Piper add-ons run but don't appear as options in the pipeline UI.
**Why it happens:** Wyoming integration discovers services via Zeroconf/mDNS. On some networks mDNS is blocked.
**How to avoid:** Go to Settings > Devices & Services > Add Integration > Wyoming Protocol and manually enter `localhost` + the port (Whisper: 10300, Piper: 10200).
**Warning signs:** STT or TTS dropdown shows "No engines available".

### Pitfall 3: Wrong French Voice Model for Piper
**What goes wrong:** Piper is configured but TTS audio is in English or has very poor French quality.
**Why it happens:** Piper defaults may select a non-French voice if language isn't explicitly set.
**How to avoid:** In the pipeline UI, after selecting Piper for TTS, explicitly set language to French and choose a voice like `fr_FR-siwis-medium` or `fr_FR-upmc-medium`.
**Warning signs:** TTS audio sounds wrong or `tts_language` is `"en"` in pipeline config.

### Pitfall 4: supported_languages Mismatch
**What goes wrong:** Pipeline is configured for French, but our entity's `supported_languages = ["fr", "en"]` is correct — however HA may filter agents based on language match.
**Why it happens:** `assisted_pipeline` checks language compatibility before selecting an agent.
**How to avoid:** Our entity already returns `["fr", "en"]`. This is correct. Do not change it to `["*"]` unless testing reveals issues — specific language lists are preferred.
**Warning signs:** Agent doesn't appear in the pipeline dropdown (filtered out by language).

### Pitfall 5: Home Assistant OS vs Container vs Core
**What goes wrong:** Wyoming add-ons require HA OS or HA Supervised. They are not available on HA Container or Core without manual installation.
**Why it happens:** HA add-on store only exists in OS/Supervised installations.
**How to avoid:** For HA Container or Core: manually run Wyoming Whisper and Piper as Docker containers, then add Wyoming integration manually pointing to their host/port. For HA OS: standard add-on store installation.
**Warning signs:** Add-on store not accessible, or "Add-on is not compatible" error.

---

## Code Examples

### Verify Our Entity is Visible as a Pipeline Backend (Unit Test Pattern)

```python
# Source: verified from HA 2026.3.4 conversation/agent_manager.py
async def test_agent_discoverable_by_pipeline(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Pipeline must be able to find our agent by entity_id."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    from homeassistant.components.conversation import async_get_agent_info
    agent_info = async_get_agent_info(hass, "conversation.ha_ai_agent")
    assert agent_info is not None
    assert agent_info.id == "conversation.ha_ai_agent"
```

### WebSocket Smoke Test (manual validation)

```json
// Send to HA WebSocket at ws://HA_HOST:8123/api/websocket
// First: authenticate, then:
{
    "type": "assist_pipeline/run",
    "start_stage": "intent",
    "end_stage": "intent",
    "input": {
        "text": "allume le salon"
    },
    "pipeline": "<pipeline_id_from_list>"
}
// Verify: event type "intent-end" contains speech response from our agent
```

### Pipeline List (verify conversation_engine)

```json
// WebSocket
{"type": "assist_pipeline/pipeline/list"}
// Expected response contains pipeline where:
// "conversation_engine": "conversation.ha_ai_agent"
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| HA 2026.3.4 | Everything | ✓ | 2026.3.4 | — |
| assist_pipeline (built-in) | VOICE-01 | ✓ | bundled with HA | — |
| Wyoming Whisper add-on | VOICE-01 (STT) | ✗ (not checked) | — | Docker container on same host |
| Wyoming Piper add-on | VOICE-02 (TTS) | ✗ (not checked) | — | Docker container on same host |
| openWakeWord add-on | Wake word (optional) | ✗ (not checked) | — | Skip wake word — trigger pipeline manually |
| Docker | Wyoming via Docker | ✗ (not found on dev machine) | — | Not needed if HA OS/Supervised |

**Notes:**
- Add-on availability depends on HA installation type (OS/Supervised required for add-on store). This cannot be determined from the dev machine.
- Docker is not available on the dev machine, but this is irrelevant if the user runs HA OS on a dedicated device (Raspberry Pi, etc.).
- Wake word is **optional for VOICE-01/VOICE-02** — the pipeline can be triggered programmatically or via the HA app's microphone button without a dedicated wake word engine.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-homeassistant-custom-component 0.13.320 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_voice_pipeline.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VOICE-01 | `async_get_agent_info(hass, "conversation.ha_ai_agent")` returns non-None AgentInfo | unit | `pytest tests/test_voice_pipeline.py::test_agent_discoverable_by_pipeline -x` | ❌ Wave 0 |
| VOICE-01 | Agent entity_id starts with `"conversation."` (pipeline routing prerequisite) | unit | `pytest tests/test_voice_pipeline.py::test_agent_entity_id_format -x` | ❌ Wave 0 |
| VOICE-02 | `_async_handle_message` response text is set via `intent_response.async_set_speech()` | unit | `pytest tests/test_voice_pipeline.py::test_response_speech_set -x` | ❌ Wave 0 |
| VOICE-02 | TTS pipeline integration: `ConversationResult.response.speech` is populated | unit | `pytest tests/test_voice_pipeline.py::test_conversation_result_has_speech -x` | ❌ Wave 0 |

**Note:** VOICE-01 pipeline configuration (STT/TTS add-on setup, pipeline UI selection) cannot be automated in unit tests. These require Human UAT with a real HA instance running.

### Sampling Rate

- **Per task commit:** `pytest tests/test_voice_pipeline.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_voice_pipeline.py` — covers VOICE-01 and VOICE-02 unit-testable assertions
- [ ] `tests/conftest.py` — already exists, no changes needed

*(Existing test infrastructure (conftest.py, fixtures) fully covers the new test file's needs.)*

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `AbstractConversationAgent.async_process()` | `ConversationEntity._async_handle_message()` | HA 2024.6 | Our code already uses the new API (confirmed in Phase 1) |
| `conversation.async_set_agent()` registration | `ConversationEntity` auto-registers as platform entity | HA 2024.6 | Our code already uses the new pattern |
| Manual pipeline YAML config | Pipeline configuration fully in UI | HA 2023.5 | No YAML needed |
| Cloud STT/TTS only | Local Wyoming Whisper + Piper | HA 2023.9 | Full local voice pipeline possible |

---

## Open Questions

1. **HA installation type (OS vs Container vs Core)**
   - What we know: Add-ons require HA OS or Supervised
   - What's unclear: What installation type the user runs
   - Recommendation: Plan 04-01 should document both paths (add-on store vs Docker manual); UAT validation should confirm which applies

2. **Wake word requirement**
   - What we know: Wake word is optional — pipeline can start from STT stage directly
   - What's unclear: Whether the user wants hands-free activation or push-to-talk
   - Recommendation: Default plan should treat wake word as optional; document how to add it if desired

3. **French Piper voice quality**
   - What we know: Piper offers multiple French voices (`fr_FR-siwis-medium`, `fr_FR-upmc-medium`, etc.)
   - What's unclear: Which voice the user will find most natural
   - Recommendation: Suggest `fr_FR-siwis-medium` as default (commonly cited as highest quality French voice); leave final choice to UAT

---

## Sources

### Primary (HIGH confidence)
- HA 2026.3.4 source: `homeassistant/components/assist_pipeline/pipeline.py` — Pipeline dataclass, `conversation_engine` field, agent lookup at runtime (verified from installed package at `C:\Users\Gsch6\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\homeassistant\components\assist_pipeline\pipeline.py`)
- HA 2026.3.4 source: `homeassistant/components/conversation/agent_manager.py` — `async_get_agent` function, entity_id dot-notation lookup (verified from installed package)
- HA 2026.3.4 source: `homeassistant/components/conversation/entity.py` — `ConversationEntity` base class, `_async_handle_message` signature (verified from installed package)
- `tests/test_conversation.py` (project) — confirms entity_id pattern `"conversation.ha_ai_agent"` is used in existing tests
- `custom_components/ha_ai_agent/conversation.py` (project) — confirms `HaAiConversationAgent` returns `IntentResponse` with speech set via `async_set_speech()`

### Secondary (MEDIUM confidence)
- https://developers.home-assistant.io/docs/voice/pipelines/ — pipeline WebSocket API, `assist_pipeline/run` parameters
- https://developers.home-assistant.io/docs/core/entity/conversation/ — `ConversationEntity` required methods, `_async_handle_message` documentation
- https://www.home-assistant.io/voice_control/voice_remote_local_assistant/ — Wyoming Whisper + Piper UI setup walkthrough

### Tertiary (LOW confidence)
- https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/assist_pipeline/pipeline.py — `dev` branch (not same as 2026.3.4 but consistent with installed source)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from installed HA 2026.3.4 source code
- Architecture: HIGH — verified `conversation_engine` lookup path from source; entity_id confirmed by existing tests
- Pitfalls: MEDIUM — STT/TTS pitfalls based on WebSearch + community knowledge; not verified against live add-on behavior
- Pipeline configuration UI: MEDIUM — WebSearch + official docs; cannot verify exact UI labels without live HA instance

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (30 days — HA core pipeline API is stable between minor releases)
