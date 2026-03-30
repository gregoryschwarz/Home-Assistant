---
phase: 1
slug: ha-scaffold
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-homeassistant-custom-component |
| **Config file** | `tests/conftest.py` — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | HA-01 | unit | `pytest tests/test_init.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | HA-01 | unit | `pytest tests/test_manifest.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | HA-02 | unit | `pytest tests/test_config_flow.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | HA-02 | unit | `pytest tests/test_config_flow.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 2 | HA-03, HA-04 | unit | `pytest tests/test_conversation.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 2 | HA-03, HA-04 | unit | `pytest tests/test_conversation.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — fixtures HA mock (hass, config_entry)
- [ ] `tests/test_init.py` — stubs pour HA-01, HA-03
- [ ] `tests/test_manifest.py` — stubs pour HA-01
- [ ] `tests/test_config_flow.py` — stubs pour HA-02
- [ ] `tests/test_conversation.py` — stubs pour HA-04
- [ ] `pytest-homeassistant-custom-component` — si non installé

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Composant visible dans HA Integrations panel | HA-01 | Nécessite une instance HA réelle | Copier custom_components/ dans HA, redémarrer, vérifier dans Paramètres > Intégrations |
| Agent sélectionnable dans Voice Assistants | HA-04 | UI HA réelle requise | Aller dans Paramètres > Voice Assistants, vérifier que ha_ai_agent apparaît |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
