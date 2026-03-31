---
phase: 2
slug: conversation-bridge
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-homeassistant-custom-component |
| **Config file** | `tests/conftest.py` — exists from Phase 1 |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 02-01 | 1 | NLU-01, NLU-04 | unit | `pytest tests/test_conversation_bridge.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-02 | 02-01 | 1 | NLU-01, NLU-04 | integration | `pytest tests/test_conversation_bridge.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02-02 | 1 | NLU-02 | unit | `pytest tests/test_intent_router.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02-02 | 1 | NLU-02, NLU-05 | unit | `pytest tests/test_intent_router.py -x -q` | ❌ W0 | ⬜ pending |
| 2-03-01 | 02-03 | 1 | NLU-01, SEC-03 | unit | `pytest tests/test_entity_resolver.py -x -q` | ❌ W0 | ⬜ pending |
| 2-03-02 | 02-03 | 1 | SEC-03 | unit | `pytest tests/test_entity_resolver.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_conversation_bridge.py` — stubs pour NLU-01, NLU-04, NLU-05
- [ ] `tests/test_intent_router.py` — stubs pour NLU-02, NLU-05
- [ ] `tests/test_entity_resolver.py` — stubs pour NLU-01, SEC-03
- [ ] Vérifier import `mock_service` dans pytest-homeassistant-custom-component 0.13.320
- [ ] Fallback : `AsyncMock` sur `hass.services.async_call` si `mock_service` indisponible

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| "allume la lumière du salon" via HA Voice UI contrôle l'entité | NLU-01 | STT + HA conversation panel réel requis | Utiliser le chat dans HA, taper/dire la commande, vérifier l'état de l'entité |
| Whitelist visible/configurable dans HA Options | SEC-03 | OptionsFlow UI HA réelle | Aller dans Intégrations > HA AI Agent > Configurer, vérifier les domaines |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
