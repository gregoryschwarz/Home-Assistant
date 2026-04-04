---
phase: 4
slug: voice-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `tests/conftest.py` |
| **Quick run command** | `python -m pytest tests/ -q --tb=short` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -q --tb=short`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | VOICE-01 | unit | `python -m pytest tests/test_pipeline.py -q` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | VOICE-01 | unit | `python -m pytest tests/test_pipeline.py -q` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | VOICE-02 | unit | `python -m pytest tests/test_pipeline.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline.py` — stubs for VOICE-01, VOICE-02 (agent discoverability, speech output)
- [ ] `tests/conftest.py` — shared fixtures (if not already present)

*Note: Pipeline infrastructure (Wyoming add-ons, HA UI config) is manual-only; automated tests cover agent discoverability and speech output registration.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wake word triggers pipeline | VOICE-01 | Requires physical microphone and running HA instance | Speak wake word + command; verify entity changes state |
| TTS plays response audio | VOICE-02 | Requires audio output device and running HA instance | Issue voice command; verify spoken confirmation is heard |
| Wyoming add-ons running | VOICE-01 | Infrastructure check, not testable in unit tests | Verify Whisper + Piper add-ons show as Running in HA |
| Pipeline selects correct agent | VOICE-01 | HA UI configuration, not unit-testable | Verify `conversation.ha_ai_agent` selected in pipeline config |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
